#!/usr/bin/env python3
"""Apply a trusted plugin release notification to every marketplace and README."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_repo import (
    MARKETPLACE_FILE,
    PLUGIN_NAME_RE,
    ROOT,
    SEMVER_RE,
    dump_json,
    non_empty_string,
    render_generated_files,
    valid_git_ref,
    valid_https_url,
    valid_relative_plugin_path,
    write_text_if_changed,
)


INTERFACE_FIELDS = {
    "displayName": "display_name",
    "shortDescription": "short_description",
    "longDescription": "long_description",
    "developerName": "developer_name",
    "websiteURL": "website_url",
}
FIRST_RELEASE_FIELDS = ("url", "path", "description", *INTERFACE_FIELDS.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add or update a released git-subdir plugin and its README catalog entry."
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--url")
    parser.add_argument("--path")
    parser.add_argument("--description")
    parser.add_argument("--display-name")
    parser.add_argument("--short-description")
    parser.add_argument("--long-description")
    parser.add_argument("--developer-name")
    parser.add_argument("--website-url")
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    for field in ("name", "version", "ref", *FIRST_RELEASE_FIELDS):
        value = getattr(args, field, None)
        if isinstance(value, str):
            setattr(args, field, value.strip() or None)
    return args


def validate_args(args: argparse.Namespace) -> None:
    normalize_args(args)
    if not non_empty_string(args.name) or PLUGIN_NAME_RE.fullmatch(args.name) is None:
        raise ValueError("--name must use lowercase kebab-case")
    if not non_empty_string(args.version) or SEMVER_RE.fullmatch(args.version) is None:
        raise ValueError("--version must use strict semver")
    if not valid_git_ref(args.ref):
        raise ValueError("--ref must be a valid Git ref")
    if args.url is not None and not valid_https_url(args.url):
        raise ValueError("--url must be a safe HTTPS URL")
    if args.path is not None and not valid_relative_plugin_path(args.path):
        raise ValueError("--path must be a safe './'-relative path")
    if args.description is not None:
        if not non_empty_string(args.description) or len(args.description) > 500:
            raise ValueError("--description must contain 1 to 500 characters")
    limits = {
        "display_name": 80,
        "short_description": 240,
        "long_description": 1000,
        "developer_name": 80,
    }
    for field, limit in limits.items():
        value = getattr(args, field)
        if value is not None and (not non_empty_string(value) or len(value) > limit):
            flag = "--" + field.replace("_", "-")
            raise ValueError(f"{flag} must contain 1 to {limit} characters")
    if args.website_url is not None and not valid_https_url(args.website_url):
        raise ValueError("--website-url must be a safe HTTPS URL")


def require_first_release_fields(args: argparse.Namespace) -> None:
    missing = [field for field in FIRST_RELEASE_FIELDS if getattr(args, field) is None]
    if missing:
        flags = ", ".join("--" + field.replace("_", "-") for field in missing)
        raise ValueError(f"first release requires: {flags}")


def find_named_entry(entries: list[object], name: str) -> dict | None:
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return None


def new_marketplace_entry(args: argparse.Namespace) -> dict[str, object]:
    return {
        "name": args.name,
        "version": args.version,
        "description": args.description,
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
        "category": "Productivity",
        "interface": {
            field: getattr(args, argument)
            for field, argument in INTERFACE_FIELDS.items()
        },
    }


def upsert_release(
    marketplace: dict[str, object],
    args: argparse.Namespace,
) -> bool:
    marketplace_plugins = marketplace.get("plugins")
    if not isinstance(marketplace_plugins, list):
        raise ValueError("marketplace.json must contain a plugins array")

    marketplace_entry = find_named_entry(marketplace_plugins, args.name)

    if marketplace_entry is None:
        require_first_release_fields(args)
        marketplace_plugins.append(new_marketplace_entry(args))
        return True

    source = marketplace_entry.get("source")
    if not isinstance(source, dict) or source.get("source") != "git-subdir":
        raise ValueError(f"plugin {args.name!r} is not a git-subdir release")
    if args.url is not None and args.url != source.get("url"):
        raise ValueError("release notification cannot change an existing plugin URL")
    if args.path is not None and args.path != source.get("path"):
        raise ValueError("release notification cannot change an existing plugin path")

    changed = source.get("ref") != args.ref or marketplace_entry.get("version") != args.version
    source["ref"] = args.ref
    marketplace_entry["version"] = args.version
    if args.description is not None and marketplace_entry.get("description") != args.description:
        marketplace_entry["description"] = args.description
        changed = True

    interface = marketplace_entry.get("interface")
    if not isinstance(interface, dict):
        if any(getattr(args, field) is None for field in INTERFACE_FIELDS.values()):
            raise ValueError("existing plugin without interface metadata requires all interface fields")
        interface = {}
        marketplace_entry["interface"] = interface
        changed = True
    for field, argument in INTERFACE_FIELDS.items():
        value = getattr(args, argument)
        if value is not None and interface.get(field) != value:
            interface[field] = value
            changed = True
    return changed


def load_object(path: Path, label: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def update_repository(args: argparse.Namespace) -> bool:
    root = args.root.resolve()
    marketplace_path = root / MARKETPLACE_FILE
    marketplace = load_object(marketplace_path, "marketplace.json")

    upsert_release(marketplace, args)
    outputs = {
        marketplace_path: dump_json(marketplace),
        **render_generated_files(root, marketplace),
    }
    written = [write_text_if_changed(path, content) for path, content in outputs.items()]
    return any(written)


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        changed = update_repository(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"plugin release update failed: {error}") from error

    state = "updated" if changed else "already current"
    print(f"{args.name}@{args.version} ({args.ref}): marketplaces and README {state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
