#!/usr/bin/env python3
"""Upsert a released Git-backed plugin into the Codex marketplace."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_repo import (
    PLUGIN_NAME_RE,
    ROOT,
    non_empty_string,
    valid_git_ref,
    valid_https_url,
    valid_relative_plugin_path,
)


DEFAULT_MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add or update a released git-subdir plugin in marketplace.json."
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--category", default="Productivity")
    parser.add_argument("--marketplace", type=Path, default=DEFAULT_MARKETPLACE)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if PLUGIN_NAME_RE.fullmatch(args.name) is None:
        raise ValueError("--name must use lowercase kebab-case")
    if not valid_https_url(args.url):
        raise ValueError("--url must be a safe HTTPS URL")
    if not valid_relative_plugin_path(args.path):
        raise ValueError("--path must be a safe './'-relative path")
    if not valid_git_ref(args.ref):
        raise ValueError("--ref must be a valid Git ref")
    if not non_empty_string(args.category):
        raise ValueError("--category must be a non-empty string")


def released_entry(args: argparse.Namespace) -> dict[str, object]:
    return {
        "name": args.name,
        "source": {
            "source": "git-subdir",
            "url": args.url,
            "path": args.path,
            "ref": args.ref,
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": args.category,
    }


def upsert_marketplace(marketplace: dict[str, object], args: argparse.Namespace) -> bool:
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise ValueError("marketplace.json must contain a plugins array")

    entry = released_entry(args)
    existing_index = next(
        (
            index
            for index, plugin in enumerate(plugins)
            if isinstance(plugin, dict) and plugin.get("name") == args.name
        ),
        None,
    )
    if existing_index is None:
        plugins.append(entry)
    elif plugins[existing_index] == entry:
        return False
    else:
        plugins[existing_index] = entry

    return True


def update_marketplace(args: argparse.Namespace) -> bool:
    marketplace_path = args.marketplace.resolve()
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    if not isinstance(marketplace, dict):
        raise ValueError("marketplace.json must contain a JSON object")

    changed = upsert_marketplace(marketplace, args)
    if not changed:
        return False

    marketplace_path.write_text(
        json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        changed = update_marketplace(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"marketplace update failed: {error}") from error

    state = "updated" if changed else "already current"
    print(f"{args.name}@{args.ref}: marketplace {state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
