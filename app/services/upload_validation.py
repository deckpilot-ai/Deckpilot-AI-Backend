"""Validation and normalization for user-supplied reference files."""

import io
import re
import zipfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError


class UploadValidationError(ValueError):
    pass


MIME_TYPES: dict[str, set[str]] = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".csv": {"text/csv", "application/csv", "text/plain"},
    ".tsv": {"text/tab-separated-values", "text/plain"},
    ".json": {"application/json", "text/json", "text/plain"},
    ".yaml": {"application/yaml", "text/yaml", "text/plain", "application/x-yaml"},
    ".yml": {"application/yaml", "text/yaml", "text/plain", "application/x-yaml"},
    ".xml": {"application/xml", "text/xml", "text/plain"},
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xlsm": {"application/vnd.ms-excel.sheet.macroenabled.12"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".gif": {"image/gif"},
    ".bmp": {"image/bmp"},
    ".tiff": {"image/tiff"},
}

_OFFICE_PREFIXES = {".docx": "word/", ".xlsx": "xl/", ".xlsm": "xl/", ".pptx": "ppt/"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}
_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml"}


def normalize_filename(raw_filename: str | None) -> str:
    value = (raw_filename or "").replace("\\", "/").split("/")[-1].strip()
    value = re.sub(r"[^A-Za-z0-9._ -]", "_", value)[:160].strip(" .")
    if not value or value in {".", ".."}:
        raise UploadValidationError("A valid filename is required")
    return value


def validate_upload(data: bytes, filename: str, claimed_mime: str | None) -> str:
    """Validate content and return a canonical MIME type."""
    if not data:
        raise UploadValidationError("The uploaded file is empty")

    extension = Path(filename).suffix.lower()
    allowed_mimes = MIME_TYPES.get(extension)
    if not allowed_mimes:
        raise UploadValidationError(f"Unsupported file extension: {extension or '(none)'}")

    normalized_mime = (claimed_mime or "").split(";", 1)[0].strip().lower()
    if normalized_mime and normalized_mime != "application/octet-stream" and normalized_mime not in allowed_mimes:
        raise UploadValidationError("File content type does not match its extension")

    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise UploadValidationError("Invalid or corrupted PDF file")
    if extension in _OFFICE_PREFIXES:
        _validate_office_archive(data, _OFFICE_PREFIXES[extension])
    if extension in _IMAGE_EXTENSIONS:
        _validate_image(data, extension)
    if extension in _TEXT_EXTENSIONS:
        _validate_text(data)

    return min(allowed_mimes)


def _validate_office_archive(data: bytes, required_prefix: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or not any(name.startswith(required_prefix) for name in names):
                raise UploadValidationError("File does not contain the expected Office document structure")
            if len(entries) > 5_000:
                raise UploadValidationError("Office document contains too many archive entries")
            total_uncompressed = sum(entry.file_size for entry in entries)
            if total_uncompressed > 100 * 1024 * 1024:
                raise UploadValidationError("Expanded Office document is too large")
            compressed = max(1, sum(entry.compress_size for entry in entries))
            if total_uncompressed / compressed > 200:
                raise UploadValidationError("Suspicious Office document compression ratio")
    except (zipfile.BadZipFile, OSError) as exc:
        raise UploadValidationError("Invalid or corrupted Office document") from exc


def _validate_image(data: bytes, extension: str) -> None:
    expected = "jpeg" if extension in {".jpg", ".jpeg"} else extension.lstrip(".")
    try:
        with Image.open(io.BytesIO(data)) as image:
            actual = (image.format or "").lower()
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UploadValidationError("Invalid or corrupted image file") from exc
    if actual != expected:
        raise UploadValidationError("Image content does not match its extension")


def _validate_text(data: bytes) -> None:
    if b"\x00" in data[:8192]:
        raise UploadValidationError("Text upload contains binary data")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadValidationError("Text uploads must use UTF-8 encoding") from exc
