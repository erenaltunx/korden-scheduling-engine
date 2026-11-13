"""Create a consistent SQLite recovery backup: python backup.py --out ~/optera-backups/backup.sqlite3"""
from __future__ import annotations
import argparse
from pathlib import Path
from optera.storage import backup_database


def main():
    parser = argparse.ArgumentParser(description="Back up OPTERA experiment history")
    parser.add_argument("--out", required=True, type=Path, help="New backup filename; existing files are never overwritten")
    args = parser.parse_args()
    path = backup_database(args.out)
    print(f"Verified SQLite backup written to: {path}")

if __name__ == "__main__":
    main()
