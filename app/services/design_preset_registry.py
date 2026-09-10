"""Design Preset Registry for storing, retrieving, and activating custom and benchmark PPT designs."""

import json
import logging
import os
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

PRESETS_DIR = os.path.join("local_storage", "design_presets")

# Pre-seeded benchmark presets matching real consulting reference decks
BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "preset_federalism",
        "name": "Institutional Teal & Amber (Federalism Benchmark)",
        "family": "A",
        "source": "builtin",
        "colors": {
            "ink": "#0C3B39",
            "primary": "#0E7C7B",
            "secondary": "#16A085",
            "accent": "#0E7C7B",
            "tint_a": "#E9F3F1",
            "tint_b": "#F6EFE2",
            "alert": "#C63A28",
            "background": "#FFFFFF",
            "paper": "#FAFAF9",
            "card_fill": "#E9F3F1",
            "neutral": "#E9F3F1",
            "text_primary": "#0C3B39",
            "text_secondary": "#475569",
        },
        "typography": {
            "title_font": "Cambria",
            "body_font": "Calibri",
            "numeric_font": "Cambria",
        },
        "grid": {
            "eyebrow_y": 0.45,
            "title_y": 0.85,
            "accent_tick_y": 1.72,
            "content_start_y": 1.95,
            "footer_y": 7.05,
        },
        "detected_archetypes": ["A1", "A4", "A5", "A6", "A8", "A10", "A13", "A14", "A17"],
    },
    {
        "id": "preset_marathas",
        "name": "Historical Maroon & Ochre (Marathas Benchmark)",
        "family": "A",
        "source": "builtin",
        "colors": {
            "ink": "#7E2C22",
            "primary": "#E4791F",
            "secondary": "#6B221C",
            "accent": "#E4791F",
            "tint_a": "#F7EEE3",
            "tint_b": "#FBF6EF",
            "alert": "#C63A28",
            "background": "#FFFFFF",
            "paper": "#FAFAF9",
            "card_fill": "#F7EEE3",
            "neutral": "#F7EEE3",
            "text_primary": "#7E2C22",
            "text_secondary": "#574336",
        },
        "typography": {
            "title_font": "Cambria",
            "body_font": "Calibri",
            "numeric_font": "Cambria",
        },
        "grid": {
            "eyebrow_y": 0.45,
            "title_y": 0.85,
            "accent_tick_y": 1.72,
            "content_start_y": 1.95,
            "footer_y": 7.05,
        },
        "detected_archetypes": ["A2", "A6", "A8", "A10", "A11", "A13", "A17", "A18"],
    },
    {
        "id": "preset_economy",
        "name": "Financial Navy & Blue (Sectors of Economy Benchmark)",
        "family": "A",
        "source": "builtin",
        "colors": {
            "ink": "#1F3864",
            "primary": "#5B9BD5",
            "secondary": "#2F5597",
            "accent": "#5B9BD5",
            "tint_a": "#F2F2F2",
            "tint_b": "#FFFFFF",
            "alert": "#C00000",
            "background": "#FFFFFF",
            "paper": "#FAFAF9",
            "card_fill": "#F2F2F2",
            "neutral": "#F2F2F2",
            "text_primary": "#1F3864",
            "text_secondary": "#475569",
        },
        "typography": {
            "title_font": "Cambria",
            "body_font": "Calibri",
            "numeric_font": "Cambria",
        },
        "grid": {
            "eyebrow_y": 0.45,
            "title_y": 0.85,
            "accent_tick_y": 1.72,
            "content_start_y": 1.95,
            "footer_y": 7.05,
        },
        "detected_archetypes": ["A1", "A6", "A9", "A13", "A14", "A16", "A17"],
    },
    {
        "id": "preset_governance",
        "name": "Executive Briefing Slate & Gold (Ministry Benchmark)",
        "family": "B",
        "source": "builtin",
        "colors": {
            "ink": "#132A52",
            "primary": "#C68A2E",
            "secondary": "#2563EB",
            "accent": "#C68A2E",
            "tint_a": "#EEF2F8",
            "tint_b": "#F8FAFC",
            "alert": "#DC2626",
            "background": "#FFFFFF",
            "paper": "#FAFAF9",
            "card_fill": "#EEF2F8",
            "neutral": "#EEF2F8",
            "text_primary": "#132A52",
            "text_secondary": "#475569",
        },
        "typography": {
            "title_font": "Segoe UI",
            "body_font": "Calibri",
            "numeric_font": "Segoe UI",
        },
        "grid": {
            "eyebrow_y": 0.45,
            "title_y": 0.85,
            "accent_tick_y": 1.72,
            "content_start_y": 1.95,
            "footer_y": 7.05,
        },
        "detected_archetypes": ["A3", "A11", "A16", "A20", "A21", "A22", "A23"],
    },
]


class DesignPresetRegistry:
    """Manages persistent custom design presets extracted from PPT files."""

    _memory_cache: dict[str, dict[str, Any]] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_init(cls) -> None:
        if cls._initialized:
            return
        os.makedirs(PRESETS_DIR, exist_ok=True)
        # Load builtins
        for p in BUILTIN_PRESETS:
            cls._memory_cache[p["id"]] = p

        # Load persisted presets from disk
        if os.path.exists(PRESETS_DIR):
            for fname in os.listdir(PRESETS_DIR):
                if fname.endswith(".json"):
                    fpath = os.path.join(PRESETS_DIR, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if "id" in data:
                                cls._memory_cache[data["id"]] = data
                    except Exception as e:
                        logger.warning("Could not load preset file %s: %s", fname, e)
        cls._initialized = True

    @classmethod
    def register_preset(cls, preset_data: dict[str, Any]) -> dict[str, Any]:
        """Save a new preset to disk and memory."""
        cls._ensure_init()
        preset_id = preset_data.get("id")
        if not preset_id:
            raise ValueError("Preset must have an 'id'")

        cls._memory_cache[preset_id] = preset_data

        # Persist to disk
        os.makedirs(PRESETS_DIR, exist_ok=True)
        fpath = os.path.join(PRESETS_DIR, f"{preset_id}.json")
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(preset_data, f, indent=2)
            logger.info("Persisted design preset %s to %s", preset_id, fpath)
        except Exception as e:
            logger.warning("Failed to persist preset %s to disk: %s", preset_id, e)

        return preset_data

    @classmethod
    def get_preset(cls, preset_id: str) -> dict[str, Any] | None:
        cls._ensure_init()
        return cls._memory_cache.get(preset_id)

    @classmethod
    def list_presets(cls) -> list[dict[str, Any]]:
        cls._ensure_init()
        return list(cls._memory_cache.values())
