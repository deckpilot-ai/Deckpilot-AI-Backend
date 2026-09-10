"""CLI tool to auto-configure any reference PowerPoint presentation into the DeckPilotAI design system.

Usage:
    python scripts/configure_ppt_design.py "path/to/my_deck.pptx" --name "My Custom Theme"
"""

import argparse
import json
import os
import sys

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.tools.design_auto_configurator import DesignAutoConfigurator
from app.services.design_preset_registry import DesignPresetRegistry


def main():
    parser = argparse.ArgumentParser(description="Auto-configure PPT design from a reference .pptx file")
    parser.add_argument("pptx_path", help="Path to the reference .pptx file")
    parser.add_argument("--name", "-n", help="Name for the extracted design preset", default=None)
    parser.add_argument("--family", "-f", choices=["A", "B"], default="A", help="Design family: A (Editorial) or B (Executive)")

    args = parser.parse_args()

    if not os.path.exists(args.pptx_path):
        print(f"Error: File '{args.pptx_path}' does not exist.")
        sys.exit(1)

    print(f"Analyzing and reverse-engineering design from: {args.pptx_path}...")
    preset = DesignAutoConfigurator.configure_from_pptx(
        pptx_source=args.pptx_path,
        name=args.name,
        family_hint=args.family,
    )

    print("\n" + "=" * 60)
    print("SUCCESSFULLY CONFIGURED PPT DESIGN PRESET")
    print("=" * 60)
    print(f"Preset ID:             {preset['id']}")
    print(f"Preset Name:           {preset['name']}")
    print(f"Design Family:         Family {preset['family']}")
    print(f"Slide Count Analyzed:  {preset['slide_count']}")
    print(f"Widescreen 16:9:       {preset['dimensions']['is_widescreen']} ({preset['dimensions']['width_in']}\" x {preset['dimensions']['height_in']}\")")
    print("\n[Color Tokens Extracted]")
    for token, hex_val in preset["colors"].items():
        print(f"  - {token:<15}: {hex_val}")
    print("\n[Typography Pairings]")
    for role, font in preset["typography"].items():
        print(f"  - {role:<15}: {font}")
    print("\n[Detected Layout Archetypes]")
    print(f"  {', '.join(preset['detected_archetypes'])}")
    print("=" * 60)
    print(f"Preset is active and saved to local_storage/design_presets/{preset['id']}.json")


if __name__ == "__main__":
    main()
