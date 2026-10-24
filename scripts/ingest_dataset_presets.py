"""Ingest all 100 palettes, typography, and format fingerprints from deck_training_dataset into DeckPilotAI."""

import csv
import json
import re
from pathlib import Path


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    dataset_dir = root_dir.parent / "deck_training_dataset"

    palettes_file = dataset_dir / "dataset" / "palettes.json"
    index_file = dataset_dir / "dataset" / "index.csv"

    if not palettes_file.exists() or not index_file.exists():
        raise FileNotFoundError(f"Dataset files not found in {dataset_dir}")

    with open(palettes_file, "r", encoding="utf-8") as f:
        palettes = json.load(f)

    pal_by_name = {p["name"]: p for p in palettes}

    with open(index_file, "r", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))

    presets = []
    for row in csv_rows:
        pname = row["palette"]
        pdata = pal_by_name.get(pname)
        if not pdata:
            continue
        c = pdata["colors"]
        cnt = pdata.get("contrast", {})
        mode = pdata.get("mode", "light")
        is_dark = mode == "dark"

        preset_id = f"preset_{row['id']}_{slug(pname)}"
        preset = {
            "id": preset_id,
            "name": f"{pname} ({row['purpose']} Benchmark)",
            "deck_id": row["id"],
            "family": "B" if is_dark else "A",
            "source": "training_dataset",
            "purpose": row["purpose"],
            "subject": row["subject"],
            "mode": mode,
            "scheme": pdata.get("scheme", "analogous"),
            "base_hue": pdata.get("base_hue", 0.0),
            "colors": {
                "ink": f"#{c['text']}",
                "primary": f"#{c['primary']}",
                "secondary": f"#{c['secondary']}",
                "accent": f"#{c['accent']}",
                "tint_a": f"#{c['surface']}",
                "tint_b": f"#{c['surface2']}",
                "alert": "#F43F5E" if is_dark else "#DC2626",
                "background": f"#{c['bg']}",
                "paper": f"#{c['bg']}",
                "card_fill": f"#{c['surface']}",
                "card_fill_alt": f"#{c['surface2']}",
                "neutral": f"#{c['surface']}",
                "text_primary": f"#{c['text']}",
                "text_secondary": f"#{c['muted']}",
                "line": f"#{c['line']}",
                "onPrimary": f"#{c['onPrimary']}",
                "onAccent": f"#{c['onAccent']}",
            },
            "contrast": cnt,
            "typography": {
                "title_font": row["heading_font"],
                "body_font": row["body_font"],
                "numeric_font": row["heading_font"],
            },
            "format": {
                "cover_style": int(row.get("cover_style", 1)),
                "title_style": row.get("title_style", "kicker"),
                "card_style": row.get("card_style", "solid"),
                "icon_style": row.get("icon_style", "circle"),
                "divider_style": int(row.get("divider_style", 1)),
                "footer_style": row.get("footer_style", "left"),
                "bg_style": row.get("bg_style", "plain"),
                "image_style": row.get("image_style", "frame"),
                "density": row.get("density", "airy"),
            },
            "grid": {
                "eyebrow_y": 0.45,
                "title_y": 0.85,
                "accent_tick_y": 1.72,
                "content_start_y": 1.95,
                "footer_y": 7.05,
            },
        }
        presets.append(preset)

    res_dir = root_dir / "app" / "resources"
    res_dir.mkdir(parents=True, exist_ok=True)
    out_file = res_dir / "training_dataset_presets.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2)

    storage_dir = root_dir / "local_storage" / "design_presets"
    storage_dir.mkdir(parents=True, exist_ok=True)
    for pr in presets:
        with open(storage_dir / f"{pr['id']}.json", "w", encoding="utf-8") as f:
            json.dump(pr, f, indent=2)

    print(f"Successfully generated {len(presets)} benchmark presets into {out_file} and {storage_dir}")


if __name__ == "__main__":
    main()
