"""CLI script to execute the DataCleaner policy for Cloudflare R2 and document storage.

Usage:
    python scripts/run_data_cleaner.py --retention-days 3
    python scripts/run_data_cleaner.py --retention-days 3 --dry-run
"""

import argparse
import json
import logging
import os
import sys

# Ensure backend root on sys.path
backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.db.engine import SessionLocal
from app.services.data_cleaner import DataCleanerService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("data_cleaner_cli")


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean up unused user document images and data from Cloudflare R2 / storage.")
    parser.add_argument("--retention-days", type=int, default=3, help="Retention period in days (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate cleanup without deleting any data")
    parser.add_argument("--apply-r2-lifecycle", action="store_true", help="Apply native Cloudflare R2 bucket lifecycle rules")
    args = parser.parse_args()

    print("=" * 70)
    print("DECKPILOT AI: DATA CLEANER & STORAGE OPTIMIZATION POLICY")
    print(f"Retention Window: {args.retention_days} days (72 hours)")
    print(f"Dry Run Mode:     {args.dry_run}")
    print("=" * 70)

    if args.apply_r2_lifecycle:
        print("\nApplying native Cloudflare R2 bucket lifecycle configuration...")
        res = DataCleanerService.apply_r2_bucket_lifecycle_configuration()
        print("R2 Lifecycle Result:", json.dumps(res, indent=2))

    with SessionLocal() as db:
        report = DataCleanerService.run_cleanup_policy(
            db=db,
            retention_days=args.retention_days,
            dry_run=args.dry_run,
        )

    print("\nCLEANUP REPORT:")
    print(json.dumps(report, indent=2))

    if report.get("errors"):
        print("\n[WARNING] Cleanup completed with errors.")
        return 1

    print("\n[SUCCESS] DataCleaner policy executed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
