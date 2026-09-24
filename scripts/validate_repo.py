#!/usr/bin/env python3
"""Validate the plugin marketplaces, derived files and local plugin packages.

The Codex marketplace is the single source of truth; the Claude Code and
WorkBuddy (CodeBuddy) marketplaces and the README plugin catalog are generated
from it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import plugin_compat


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_FILE = Path(".agents/plugins/marketplace.json")
MARKETPLACE_PATH = ROOT / MARKETPLACE_FILE
MARKETPLACE_OWNER = "tadazly"
README_PATH = ROOT / "README.md"
PLUGINS_PATH = ROOT / "plugins"
CATALOG_HEADING = "## 插件目录"
CATALOG_SECTION_RE = re.compile(r"(?ms)^## 插件目录[^\n]*\n.*?(?=^## |\Z)")
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
INSTALL_POLICIES = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
AUTH_POLICIES = {"ON_INSTALL", "ON_USE"}
GIT_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
GIT_SHA_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")


def load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing file: {path.relative_to(ROOT)}")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"cannot read {path.relative_to(ROOT)}: {error}")
    return None


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_https_url(value: Any) -> bool:
    if not non_empty_string(value):
        return False
    if any(character.isspace() or character in "<>\\" for character in value):
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def valid_relative_plugin_path(value: Any) -> bool:
    if not non_empty_string(value) or not value.startswith("./") or "\\" in value:
        return False
    parts = value[2:].split("/")
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def valid_git_ref(value: Any) -> bool:
    return (
        non_empty_string(value)
        and GIT_REF_RE.fullmatch(value) is not None
        and ".." not in value
        and "//" not in value
        and not value.endswith("/")
        and not value.endswith(".lock")
    )


def escape_markdown_text(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("`", "\\`")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def render_plugin_catalog(marketplace: dict[str, object]) -> str:
    rows = [
        CATALOG_HEADING,
        "",
        "| 插件 | 简介 |",
        "| --- | --- |",
    ]
    entries = marketplace.get("plugins", [])
    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            interface = entry.get("interface")
            if not isinstance(interface, dict):
                continue
            display_name = interface.get("displayName")
            short_description = interface.get("shortDescription")
            website_url = interface.get("websiteURL")
            if not all(
                isinstance(value, str)
                for value in (
                    name,
                    display_name,
                    short_description,
                    website_url,
                )
            ):
                continue
            label = escape_markdown_text(display_name)
            summary = escape_markdown_text(short_description)
            rows.append(f"| [{label}](<{website_url}>) | {summary} |")
    return "\n".join(rows)


def replace_plugin_catalog(readme: str, rendered_catalog: str) -> str:
    matches = list(CATALOG_SECTION_RE.finditer(readme))
    if len(matches) != 1:
        raise ValueError("README must contain exactly one plugin catalog section")
    match = matches[0]
    replacement = rendered_catalog.rstrip() + "\n\n"
    return readme[: match.start()] + replacement + readme[match.end() :]


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_text_if_changed(path: Path, content: str) -> bool:
    try:
        if path.read_text(encoding="utf-8") == content:
            return False
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def render_claude_source(source: object) -> str | dict[str, object] | None:
    if not isinstance(source, dict):
        return None
    if source.get("source") == "local":
        return source.get("path")
    if source.get("source") != "git-subdir":
        return None
    # Claude Code rejects a leading "./" in git-subdir paths.
    path = source.get("path")
    rendered: dict[str, object] = {
        "source": "git-subdir",
        "url": source.get("url"),
        "path": path.removeprefix("./") if isinstance(path, str) else path,
    }
    for selector in ("ref", "sha"):
        if selector in source:
            rendered[selector] = source[selector]
    return rendered


def render_claude_marketplace(marketplace: dict[str, object]) -> dict[str, object]:
    """Derive the Claude Code marketplace, keeping only fields its schema knows."""
    plugins: list[dict[str, object]] = []
    entries = marketplace.get("plugins", [])
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        policy = entry.get("policy")
        if isinstance(policy, dict) and policy.get("installation") == "NOT_AVAILABLE":
            continue
        source = render_claude_source(entry.get("source"))
        if source is None:
            continue
        interface = entry.get("interface")
        if not isinstance(interface, dict):
            interface = {}
        category = entry.get("category")
        if isinstance(category, str):
            category = "-".join(category.lower().split())
        plugins.append(
            {
                "name": entry.get("name"),
                "displayName": interface.get("displayName"),
                "version": entry.get("version"),
                "description": entry.get("description"),
                "author": {"name": interface.get("developerName")},
                "homepage": interface.get("websiteURL"),
                "category": category,
                "source": source,
            }
        )

    interface = marketplace.get("interface")
    display_name = interface.get("displayName") if isinstance(interface, dict) else None
    return {
        "name": marketplace.get("name"),
        "owner": {"name": MARKETPLACE_OWNER},
        "metadata": {"description": display_name},
        "plugins": plugins,
    }


def render_codebuddy_marketplace(marketplace: dict[str, object]) -> dict[str, object]:
    """Derive the WorkBuddy / CodeBuddy marketplace.

    CodeBuddy follows the Claude Code plugin format, so entries reuse the Claude
    mapping but keep only the fields CodeBuddy documents (description is required).
    """
    claude = render_claude_marketplace(marketplace)
    fields = ("name", "description", "version", "author", "homepage", "category", "source")
    return {
        "name": claude["name"],
        "owner": claude["owner"],
        "description": claude["metadata"]["description"],
        "plugins": [{field: plugin[field] for field in fields} for plugin in claude["plugins"]],
    }


# Marketplaces generated from the Codex marketplace, relative to the repository
# root. Supporting another platform only needs a renderer and an entry here.
GENERATED_MARKETPLACES = {
    Path(".claude-plugin/marketplace.json"): render_claude_marketplace,
    Path(".codebuddy-plugin/marketplace.json"): render_codebuddy_marketplace,
}


def generated_paths(root: Path) -> list[Path]:
    return [root / relative for relative in GENERATED_MARKETPLACES] + [root / README_PATH.name]


def render_generated_files(root: Path, marketplace: dict[str, object]) -> dict[Path, str]:
    """Render every file derived from the Codex marketplace under ``root``."""
    readme_path = root / README_PATH.name
    readme = readme_path.read_text(encoding="utf-8")
    outputs = {
        root / relative: dump_json(render(marketplace))
        for relative, render in GENERATED_MARKETPLACES.items()
    }
    outputs[readme_path] = replace_plugin_catalog(readme, render_plugin_catalog(marketplace))
    return outputs


def validate_plugin_display_metadata(
    entry: dict[str, object], label: str, errors: list[str]
) -> None:
    version = entry.get("version")
    if not non_empty_string(version) or SEMVER_RE.fullmatch(version) is None:
        errors.append(f"{label}: version must use strict semver")
    description = entry.get("description")
    if not non_empty_string(description) or len(description) > 500:
        errors.append(f"{label}: description must contain 1 to 500 characters")

    interface = entry.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"{label}: interface must be an object")
        return
    limits = {
        "displayName": 80,
        "shortDescription": 240,
        "longDescription": 1000,
        "developerName": 80,
    }
    for field, limit in limits.items():
        value = interface.get(field)
        if not non_empty_string(value) or len(value) > limit:
            errors.append(f"{label}: interface.{field} must contain 1 to {limit} characters")
    if not valid_https_url(interface.get("websiteURL")):
        errors.append(f"{label}: interface.websiteURL must be a safe HTTPS URL")


def validate_generated_files(marketplace: dict[str, object], errors: list[str]) -> None:
    try:
        outputs = render_generated_files(ROOT, marketplace)
    except (OSError, ValueError) as error:
        errors.append(f"cannot render generated files: {error}")
        return
    for path, expected in outputs.items():
        label = path.relative_to(ROOT).as_posix()
        try:
            current = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            errors.append(f"missing file: {label}; run scripts/sync_generated.py")
            continue
        except OSError as error:
            errors.append(f"cannot read {label}: {error}")
            continue
        if current != expected:
            errors.append(f"{label} is stale; run scripts/sync_generated.py")


def validate_client_manifests(
    plugin_name: str, codex_version: Any, plugin_root: Path, errors: list[str]
) -> None:
    """Claude Code and WorkBuddy manifests must match the Codex manifest."""
    for directory in (".claude-plugin", ".codebuddy-plugin"):
        manifest_path = plugin_root / directory / "plugin.json"
        if not manifest_path.exists():
            continue
        manifest = load_json(manifest_path, errors)
        label = manifest_path.relative_to(ROOT).as_posix()
        if not isinstance(manifest, dict):
            if manifest is not None:
                errors.append(f"{label} must contain a JSON object")
            continue
        if manifest.get("name") != plugin_name:
            errors.append(f"{label}: name must be {plugin_name!r}")
        if "version" in manifest and manifest["version"] != codex_version:
            errors.append(f"{label}: version must match .codex-plugin/plugin.json")
    compat_errors, _ = plugin_compat.check_plugin(plugin_root)
    errors.extend(f"{plugin_root.relative_to(ROOT).as_posix()}: {message}" for message in compat_errors)


def validate_manifest(plugin_name: str, manifest_path: Path, errors: list[str]) -> None:
    manifest = load_json(manifest_path, errors)
    if not isinstance(manifest, dict):
        if manifest is not None:
            errors.append(f"{manifest_path.relative_to(ROOT)} must contain a JSON object")
        return

    label = str(manifest_path.relative_to(ROOT))
    if manifest.get("name") != plugin_name:
        errors.append(f"{label}: name must be {plugin_name!r}")

    version = manifest.get("version")
    if not non_empty_string(version) or SEMVER_RE.fullmatch(version) is None:
        errors.append(f"{label}: version must use strict semver")

    if not non_empty_string(manifest.get("description")):
        errors.append(f"{label}: description must be a non-empty string")

    author = manifest.get("author")
    if not isinstance(author, dict) or not non_empty_string(author.get("name")):
        errors.append(f"{label}: author.name must be a non-empty string")

    interface = manifest.get("interface")
    required_interface_fields = (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
    )
    if not isinstance(interface, dict):
        errors.append(f"{label}: interface must be an object")
    else:
        for field in required_interface_fields:
            if not non_empty_string(interface.get(field)):
                errors.append(f"{label}: interface.{field} must be a non-empty string")
        capabilities = interface.get("capabilities")
        if not isinstance(capabilities, list) or not all(
            non_empty_string(value) for value in capabilities
        ):
            errors.append(f"{label}: interface.capabilities must be an array of strings")
        prompts = interface.get("defaultPrompt", interface.get("default_prompt"))
        if not isinstance(prompts, list) or not prompts or not all(
            non_empty_string(value) for value in prompts
        ):
            errors.append(f"{label}: interface.defaultPrompt must be a non-empty array of strings")

    component_paths = {
        "skills": "skills",
        "apps": ".app.json",
    }
    for field, expected in component_paths.items():
        if field in manifest and manifest[field] != f"./{expected}":
            errors.append(f"{label}: {field} must be './{expected}' when declared")
        if field in manifest and not (manifest_path.parents[1] / expected).exists():
            errors.append(f"{label}: declared {field} path does not exist")

    plugin_root = manifest_path.parents[1]
    mcp_servers = manifest.get("mcpServers")
    if isinstance(mcp_servers, str):
        if not valid_relative_plugin_path(mcp_servers) or not mcp_servers.endswith(".json"):
            errors.append(f"{label}: string mcpServers must be a './'-relative JSON file")
        elif not (plugin_root / mcp_servers).is_file():
            errors.append(f"{label}: declared mcpServers path does not exist")
    for path in (plugin_root / ".mcp.json", *sorted((plugin_root / "mcp").glob("*.json"))):
        if path.is_file():
            errors.append(
                f"{path.relative_to(ROOT).as_posix()}: Claude Code and WorkBuddy load this file automatically "
                "and WorkBuddy lets it override manifest servers; keep the Codex MCP config in a file such as "
                "'./.codex-mcp.json'"
            )

    validate_client_manifests(plugin_name, version, plugin_root, errors)


def validate() -> list[str]:
    errors: list[str] = []
    marketplace = load_json(MARKETPLACE_PATH, errors)
    if not isinstance(marketplace, dict):
        if marketplace is not None:
            errors.append("marketplace.json must contain a JSON object")
        return errors

    if not non_empty_string(marketplace.get("name")):
        errors.append("marketplace.json: name must be a non-empty string")
    interface = marketplace.get("interface")
    if not isinstance(interface, dict) or not non_empty_string(interface.get("displayName")):
        errors.append("marketplace.json: interface.displayName must be a non-empty string")

    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        errors.append("marketplace.json: plugins must be an array")
        return errors

    listed_names: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"marketplace.json plugins[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: entry must be an object")
            continue

        name = entry.get("name")
        if not non_empty_string(name) or PLUGIN_NAME_RE.fullmatch(name) is None:
            errors.append(f"{label}: name must use lowercase kebab-case")
            continue
        if name in listed_names:
            errors.append(f"{label}: duplicate plugin name {name!r}")
        listed_names.add(name)

        source = entry.get("source")
        source_type = source.get("source") if isinstance(source, dict) else None
        if source_type == "local":
            expected_path = f"./plugins/{name}"
            if source.get("path") != expected_path:
                errors.append(f"{label}: local source.path must be {expected_path!r}")
        elif source_type == "git-subdir":
            if not valid_https_url(source.get("url")):
                errors.append(f"{label}: git-subdir source.url must be a safe HTTPS URL")
            if not valid_relative_plugin_path(source.get("path")):
                errors.append(f"{label}: git-subdir source.path must be a safe './'-relative path")
            selectors = int("ref" in source) + int("sha" in source)
            if selectors != 1:
                errors.append(f"{label}: git-subdir source requires exactly one of ref or sha")
            elif "ref" in source and not valid_git_ref(source.get("ref")):
                errors.append(f"{label}: git-subdir source.ref is invalid")
            elif "sha" in source and (
                not non_empty_string(source.get("sha"))
                or GIT_SHA_RE.fullmatch(source["sha"]) is None
            ):
                errors.append(f"{label}: git-subdir source.sha must be a full Git object ID")
        else:
            errors.append(f"{label}: source.source must be 'local' or 'git-subdir'")

        policy = entry.get("policy")
        if not isinstance(policy, dict):
            errors.append(f"{label}: policy must be an object")
        else:
            if policy.get("installation") not in INSTALL_POLICIES:
                errors.append(f"{label}: invalid policy.installation")
            if policy.get("authentication") not in AUTH_POLICIES:
                errors.append(f"{label}: invalid policy.authentication")
        if not non_empty_string(entry.get("category")):
            errors.append(f"{label}: category must be a non-empty string")
        validate_plugin_display_metadata(entry, label, errors)

        if source_type == "local":
            plugin_root = PLUGINS_PATH / name
            if not plugin_root.is_dir():
                errors.append(f"{label}: plugin directory does not exist: plugins/{name}")
                continue
            validate_manifest(name, plugin_root / ".codex-plugin" / "plugin.json", errors)

    if not PLUGINS_PATH.is_dir():
        errors.append("missing directory: plugins")
        return errors

    actual_names = {
        path.name
        for path in PLUGINS_PATH.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    }
    for name in sorted(actual_names - listed_names):
        errors.append(f"plugins/{name}: plugin directory is missing from marketplace.json")

    validate_generated_files(marketplace, errors)

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Plugin repository validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Plugin repository validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
