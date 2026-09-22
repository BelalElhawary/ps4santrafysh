#!/usr/bin/env python3
"""Verify and update file hashes in cache.appcache.

Recomputes the SHA-256 hash of every file listed in the manifest's cache
section and rewrites any line whose recorded hash no longer matches.
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

ENTRY_RE = re.compile(r"^(\S+)\s+#([0-9a-fA-F]{64})$")
SECTION_HEADERS = {"NETWORK:", "FALLBACK:", "CACHE MANIFEST"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        default="cache.appcache",
        help="Path to the cache manifest (default: cache.appcache)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only report mismatches/missing files, don't write changes",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_file():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    base_dir = manifest_path.parent
    raw = manifest_path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    lines = raw.decode("utf-8").splitlines()

    in_cache_section = True
    changed = 0
    missing = []
    unchanged = 0
    new_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped in SECTION_HEADERS or stripped.startswith("#"):
            new_lines.append(line)
            if stripped in ("NETWORK:", "FALLBACK:"):
                in_cache_section = False
            continue

        match = ENTRY_RE.match(stripped) if in_cache_section else None
        if not match:
            new_lines.append(line)
            continue

        entry_name, recorded_hash = match.groups()
        file_name = entry_name.split("?", 1)[0]
        file_path = base_dir / file_name

        if not file_path.is_file():
            print(f"MISSING  {entry_name}")
            missing.append(entry_name)
            new_lines.append(line)
            continue

        actual_hash = sha256_of(file_path)
        if actual_hash.lower() == recorded_hash.lower():
            unchanged += 1
            new_lines.append(line)
            continue

        changed += 1
        print(f"UPDATE   {entry_name}\n  old: {recorded_hash}\n  new: {actual_hash}")
        new_lines.append(f"{entry_name} #{actual_hash}")

    print(
        f"\n{unchanged} unchanged, {changed} updated, {len(missing)} missing"
        f" (of {unchanged + changed + len(missing)} entries)"
    )

    if changed and not args.check:
        content = newline.join(new_lines) + newline
        manifest_path.write_bytes(content.encode("utf-8"))
        print(f"Wrote updated hashes to {manifest_path}")
    elif changed and args.check:
        print("Run without --check to write the updated hashes.")

    return 1 if (changed and args.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
