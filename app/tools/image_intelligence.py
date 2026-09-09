"""Image intelligence, validation, deduplication, semantic ranking, and placement tool."""

import hashlib
import io
import logging
import math
import re
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.schemas.generation_state import AssetMetadata, ImagePlacementMode

logger = logging.getLogger(__name__)


class ImageIntelligence:
    """Deterministic image processing, quality gating, and layout geometry."""

    @staticmethod
    def compute_dhash(image_bytes: bytes, hash_size: int = 8) -> str:
        """Computes difference hash (dHash) for perceptual similarity comparison."""
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
                pixels = list(gray.getdata())
                diff = []
                for row in range(hash_size):
                    for col in range(hash_size):
                        pixel_left = pixels[row * (hash_size + 1) + col]
                        pixel_right = pixels[row * (hash_size + 1) + col + 1]
                        diff.append(pixel_left > pixel_right)
                decimal_val = 0
                hex_str = []
                for index, value in enumerate(diff):
                    if value:
                        decimal_val += 2 ** (index % 4)
                    if (index % 4) == 3:
                        hex_str.append(hex(decimal_val)[2:])
                        decimal_val = 0
                return "".join(hex_str)
        except Exception:
            return hashlib.md5(image_bytes).hexdigest()[:16]

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        if len(hash1) != len(hash2):
            return 999
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    @classmethod
    def validate_image_quality(cls, image_bytes: bytes) -> tuple[bool, float, str]:
        """Validates resolution, blur, variance, aspect ratio, and QR rejection.
        
        Returns (is_valid, score, reason).
        """
        try:
            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return False, 0.0, "Corrupted or unreadable image bytes"

            height, width = img.shape[:2]
            if width < 50 or height < 50 or (width * height) < 4000:
                return False, 0.1, "Resolution too small"

            aspect = width / max(1, height)
            if aspect < 0.18 or aspect > 5.5:
                return False, 0.2, "Extreme or invalid aspect ratio"

            # Check standard deviation of grayscale (reject blank white/black boxes)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            std_dev = float(gray.std())
            if std_dev < 3.0:
                return False, 0.1, "Uniform or blank image"

            # Check Laplacian variance for blur
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            blur_score = min(1.0, laplacian_var / 150.0)

            # Check QR code on square monochrome images
            if 0.85 <= aspect <= 1.15:
                diff = np.abs(img[:, :, 0].astype(int) - img[:, :, 1].astype(int)) + np.abs(img[:, :, 1].astype(int) - img[:, :, 2].astype(int))
                if diff.mean() < 12:
                    detected, _ = cv2.QRCodeDetector().detect(img)
                    if bool(detected):
                        return False, 0.0, "QR Code asset rejected"

            quality_score = round(0.5 + 0.3 * blur_score + 0.2 * min(1.0, (width * height) / 200000.0), 3)
            return True, quality_score, "High-quality visual asset"
        except Exception as e:
            logger.warning("Image validation error: %s", e)
            return True, 0.8, "Validation fallback"

    @classmethod
    def deduplicate_assets(
        cls,
        assets: list[tuple[str, bytes, AssetMetadata]],
        threshold: int = 4,
    ) -> list[tuple[str, bytes, AssetMetadata]]:
        """Deduplicates images based on sha256 and perceptual dHash."""
        seen_sha = set()
        seen_hashes: list[tuple[str, AssetMetadata]] = []
        unique_assets = []

        for key, payload, meta in assets:
            if meta.sha256 in seen_sha:
                continue
            seen_sha.add(meta.sha256)

            dhash = cls.compute_dhash(payload)
            meta.perceptual_hash = dhash

            # Check perceptual distance
            is_dup = False
            for existing_hash, existing_meta in seen_hashes:
                dist = cls.hamming_distance(dhash, existing_hash)
                if dist <= threshold:
                    is_dup = True
                    break

            if not is_dup:
                seen_hashes.append((dhash, meta))
                unique_assets.append((key, payload, meta))

        return unique_assets

    @classmethod
    def score_relevance(cls, slide_text: str, meta: AssetMetadata) -> float:
        """Scores relevance between slide content and asset metadata without requiring remote models."""
        slide_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", slide_text.lower()))
        if not slide_tokens:
            return 0.0

        meta_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", f"{meta.caption} {meta.nearby_text} {meta.source_file}".lower()))
        if not meta_tokens:
            return 0.1

        overlap = slide_tokens.intersection(meta_tokens)
        keyword_score = len(overlap) / max(1, min(len(slide_tokens), 15))

        # Explicit figure reference bonus (e.g. 'Fig 3.5' or 'Figure 2')
        fig_bonus = 0.0
        fig_match = re.search(r"\b(?:fig(?:ure)?\.?\s*(\d+(?:\.\d+)?))\b", slide_text, re.IGNORECASE)
        if fig_match and fig_match.group(1) in meta.caption:
            fig_bonus = 0.5

        return round(min(1.0, keyword_score * 0.5 + fig_bonus + 0.2), 3)

    @classmethod
    def compute_placement_box(
        cls,
        available_x: float,
        available_y: float,
        available_w: float,
        available_h: float,
        img_w: int,
        img_h: int,
        mode: ImagePlacementMode = ImagePlacementMode.SIDE_VISUAL,
    ) -> tuple[float, float, float, float]:
        """Calculates fitted (x, y, w, h) in inches respecting aspect ratio."""
        if img_w <= 0 or img_h <= 0:
            return available_x, available_y, available_w, available_h

        img_aspect = img_w / float(img_h)
        avail_aspect = available_w / max(0.01, available_h)

        if mode in (ImagePlacementMode.CONTAIN, ImagePlacementMode.SIDE_VISUAL, ImagePlacementMode.FRAME_INSET):
            if img_aspect > avail_aspect:
                # Width constrained
                w = available_w
                h = available_w / img_aspect
                x = available_x
                y = available_y + (available_h - h) / 2.0
            else:
                # Height constrained
                h = available_h
                w = available_h * img_aspect
                y = available_y
                x = available_x + (available_w - w) / 2.0
            return x, y, w, h
        elif mode == ImagePlacementMode.COVER or mode == ImagePlacementMode.HERO_VISUAL:
            # Full coverage inside bounds
            return available_x, available_y, available_w, available_h
        else:
            return available_x, available_y, available_w, available_h
