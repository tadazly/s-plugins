#!/usr/bin/env python3
"""Regenerate the README plugin catalog from repository metadata."""

from __future__ import annotations

import json

from validate_repo import (
    MARKETPLACE_PATH,
    README_PATH,
    render_plugin_catalog,
    replace_plugin_catalog,
)


def main() -> int:
    marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
    readme = README_PATH.read_text(encoding="utf-8")
    updated = replace_plugin_catalog(readme, render_plugin_catalog(marketplace))
    if updated == readme:
        print("README plugin catalog is already current.")
        return 0
    README_PATH.write_text(updated, encoding="utf-8")
    print("README plugin catalog updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
