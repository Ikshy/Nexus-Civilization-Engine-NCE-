#!/usr/bin/env python3
"""
Build script: packages the entire NCE project into a zip file.
"""
import os
import zipfile
import sys

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SOURCE_DIR, "nexus_civilization_engine.zip")

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".next", "node_modules",
    ".mypy_cache", ".pytest_cache", "*.egg-info", "dist", "build",
}
EXCLUDE_EXTS = {".pyc", ".pyo", ".DS_Store", ".env"}
EXCLUDE_FILES = {"nexus_civilization_engine.zip"}


def should_exclude(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
        if any(part.endswith(e) for e in EXCLUDE_DIRS if "*" in e):
            return True
    _, ext = os.path.splitext(path)
    if ext in EXCLUDE_EXTS:
        return True
    if os.path.basename(path) in EXCLUDE_FILES:
        return True
    return False


def build_zip():
    print(f"Building zip from: {SOURCE_DIR}")
    print(f"Output: {OUTPUT_PATH}")

    file_count = 0
    total_size = 0

    with zipfile.ZipFile(OUTPUT_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(SOURCE_DIR):
            # Filter out excluded dirs in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            rel_root = os.path.relpath(root, os.path.dirname(SOURCE_DIR))

            for filename in files:
                filepath = os.path.join(root, filename)
                arcname = os.path.join(rel_root, filename)

                if should_exclude(arcname):
                    continue

                try:
                    zf.write(filepath, arcname)
                    size = os.path.getsize(filepath)
                    total_size += size
                    file_count += 1
                    if file_count % 20 == 0:
                        print(f"  Added {file_count} files...")
                except Exception as e:
                    print(f"  Warning: could not add {filepath}: {e}")

    zip_size = os.path.getsize(OUTPUT_PATH)
    print(f"\n✓ Build complete!")
    print(f"  Files included: {file_count}")
    print(f"  Source size:    {total_size / 1024:.1f} KB")
    print(f"  Zip size:       {zip_size / 1024:.1f} KB")
    print(f"  Compression:    {(1 - zip_size / max(total_size, 1)) * 100:.1f}%")
    print(f"  Output:         {OUTPUT_PATH}")


if __name__ == "__main__":
    build_zip()
