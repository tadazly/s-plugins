#!/usr/bin/env python3
"""Check how Codex, Claude Code and WorkBuddy would start a plugin's MCP servers.

The clients resolve plugin MCP servers differently:

- Codex reads `.codex-plugin/plugin.json` and starts servers in the plugin root.
- Claude Code reads `.claude-plugin/plugin.json`; its inline `mcpServers` win over
  the root `.mcp.json`, which it also loads.
- WorkBuddy 5.6.2 reads the first of `.codebuddy-plugin`, `.workbuddy-plugin` and
  `.claude-plugin`, then merges manifest `mcpServers`, root `.mcp.json` and
  `mcp/*.json` with later sources winning.

Claude Code and WorkBuddy start servers in the user's workspace and ignore `cwd`,
so plugin files must be referenced through `${CLAUDE_PLUGIN_ROOT}` or
`${CODEBUDDY_PLUGIN_ROOT}`. Usage: plugin_compat.py <plugin-dir>...
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

WORKBUDDY_MANIFEST_DIRS = (".codebuddy-plugin", ".workbuddy-plugin", ".claude-plugin")
# macOS has no `python`; on Windows `python3` is often only the Microsoft Store stub.
INTERPRETER_RE = re.compile(r"^(?:python[0-9.]*|py)(?:\.exe)?$", re.I)
RELATIVE_RE = re.compile(r"^\.{1,2}[\\/]")

Servers = dict[str, tuple[str, Any]]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def read_servers(root: Path, value: Any, source: str) -> Servers:
    """Servers from an inline mapping or from a plugin-relative JSON file."""
    if isinstance(value, str):
        source = value.removeprefix("./")
        data = load_json(root / source)
        value = data.get("mcpServers") if isinstance(data, dict) else None
    return {name: (source, config) for name, config in value.items()} if isinstance(value, dict) else {}


def effective_servers(root: Path) -> dict[str, Servers]:
    """The MCP servers each client would start, keyed by client name."""
    clients: dict[str, Servers] = {}
    root_file = read_servers(root, "./.mcp.json", ".mcp.json") if (root / ".mcp.json").is_file() else {}

    codex = load_json(root / ".codex-plugin" / "plugin.json")
    if isinstance(codex, dict):
        clients["Codex"] = read_servers(root, codex.get("mcpServers"), ".codex-plugin/plugin.json")

    claude = load_json(root / ".claude-plugin" / "plugin.json")
    if isinstance(claude, dict):
        clients["Claude Code"] = {
            **root_file,
            **read_servers(root, claude.get("mcpServers"), ".claude-plugin/plugin.json"),
        }

    for directory in WORKBUDDY_MANIFEST_DIRS:
        manifest = load_json(root / directory / "plugin.json")
        if isinstance(manifest, dict):
            servers = read_servers(root, manifest.get("mcpServers"), f"{directory}/plugin.json")
            servers.update(root_file)
            for path in sorted((root / "mcp").glob("*.json")):
                servers.update(read_servers(root, f"./mcp/{path.name}", f"mcp/{path.name}"))
            clients["WorkBuddy"] = servers
            break
    return clients


def check_plugin(root: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the MCP servers each client would start."""
    errors: list[str] = []
    warnings: list[str] = []
    for client, servers in effective_servers(root).items():
        for name, (source, config) in servers.items():
            if not isinstance(config, dict) or not isinstance(config.get("command"), str):
                continue
            command = config["command"]
            where = f"[{client}] server {name!r} from {source}"
            if INTERPRETER_RE.fullmatch(command):
                errors.append(
                    f"{where}: starts the interpreter {command!r} by name; macOS has no 'python' and "
                    "Windows often only has a Store stub for 'python3', so start a launcher instead"
                )
            elif client != "Codex" and command.lower() in ("node", "node.exe"):
                warnings.append(f"{where}: needs 'node' on PATH, which {client} does not provide")
            if client == "Codex":
                continue
            for value in [command, *(config.get("args") or [])]:
                if isinstance(value, str) and RELATIVE_RE.match(value):
                    errors.append(
                        f"{where}: {value!r} is relative, but {client} starts servers in the user's "
                        "workspace; use ${CLAUDE_PLUGIN_ROOT} or ${CODEBUDDY_PLUGIN_ROOT}"
                    )
    return errors, warnings


def main(argv: list[str]) -> int:
    failed = False
    for argument in argv:
        root = Path(argument)
        errors, warnings = check_plugin(root)
        label = "/".join(root.parts[-2:])
        for message in warnings:
            print(f"::warning::{label}: {message}")
        for message in errors:
            print(f"::error::{label}: {message}")
        failed = failed or bool(errors)
        if not errors and not warnings:
            print(f"{label}: OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
