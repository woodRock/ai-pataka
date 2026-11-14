#!/usr/bin/env python3
"""Scaffold a new talk folder from the example.

Usage: python3 scripts/new_talk.py 2026-12-02-surname
Creates talks/<slug>/talk.yaml (a copy of talks/_example/talk.yaml) to edit.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if len(sys.argv) != 2:
    sys.exit(__doc__)
slug = sys.argv[1].strip().lower().replace(" ", "-")
dest = ROOT / "talks" / slug
if dest.exists():
    sys.exit(f"error: {dest.relative_to(ROOT)} already exists")
dest.mkdir(parents=True)
shutil.copy(ROOT / "talks/_example/talk.yaml", dest / "talk.yaml")
print(f"created {dest.relative_to(ROOT)}/talk.yaml — fill it in, then run:\n"
      f"  python3 scripts/render.py talks/{slug}")
