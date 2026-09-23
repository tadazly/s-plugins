#!/usr/bin/env python3
"""Regenerate the Claude Code marketplace and README plugin catalog."""

from __future__ import annotations

import json

from validate_repo import (
    CLAUDE_MARKETPLACE_PATH,
    MARKETPLACE_PATH,
    README_PATH,
    ROOT,
    dump_json,
    render_claude_marketplace,
    render_plugin_catalog,
    replace_plugin_catalog,
    write_text_if_changed,
)


def main() -> int:
    marketplace = json.loads(MARKETPLACE_PATH.read_text(encoding="utf-8"))
    readme = README_PATH.read_text(encoding="utf-8")
    outputs = {
        CLAUDE_MARKETPLACE_PATH: dump_json(render_claude_marketplace(marketplace)),
        README_PATH: replace_plugin_catalog(readme, render_plugin_catalog(marketplace)),
    }
    for path, content in outputs.items():
        state = "updated" if write_text_if_changed(path, content) else "already current"
        print(f"{path.relative_to(ROOT).as_posix()}: {state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
