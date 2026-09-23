#!/usr/bin/env python3
"""Regenerate the Claude Code / WorkBuddy marketplaces and README plugin catalog."""

from __future__ import annotations

import argparse
import json

from validate_repo import (
    MARKETPLACE_PATH,
    ROOT,
    generated_paths,
    render_generated_files,
    write_text_if_changed,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list-outputs",
        action="store_true",
        help="print the generated file paths, one per line, and exit",
    )
    args = parser.parse_args()
    if args.list_outputs:
        for path in generated_paths(ROOT):
            print(path.relative_to(ROOT).as_posix())
        return 0

    marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
    for path, content in render_generated_files(ROOT, marketplace).items():
        state = "updated" if write_text_if_changed(path, content) else "already current"
        print(f"{path.relative_to(ROOT).as_posix()}: {state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
