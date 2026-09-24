from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plugin_compat  # noqa: E402
import validate_repo  # noqa: E402


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class PluginCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_root_mcp_json_breaks_workbuddy_but_not_claude(self) -> None:
        # egret-agent-inspector 5.0.1: Codex config at the root, launcher inline for Claude Code.
        write(self.root / ".codex-plugin/plugin.json", {"name": "p", "mcpServers": "./.mcp.json"})
        write(self.root / ".mcp.json", {"mcpServers": {"s": {"command": "node", "args": ["./scripts/start.js"], "cwd": "."}}})
        write(self.root / ".claude-plugin/plugin.json", {"name": "p", "mcpServers": {"s": {"command": "${CLAUDE_PLUGIN_ROOT}/bin/s"}}})
        errors, warnings = plugin_compat.check_plugin(self.root)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("[WorkBuddy] server 's' from .mcp.json: './scripts/start.js' is relative", errors[0])
        self.assertEqual(["[WorkBuddy] server 's' from .mcp.json: needs 'node' on PATH, which WorkBuddy does not provide"], warnings)

    def test_per_client_manifests_pass(self) -> None:
        write(self.root / ".codex-plugin/plugin.json", {"name": "p", "mcpServers": "./.codex-mcp.json"})
        write(self.root / ".codex-mcp.json", {"mcpServers": {"s": {"command": "./bin/s", "cwd": "."}}})
        write(self.root / ".claude-plugin/plugin.json", {"name": "p", "mcpServers": {"s": {"command": "${CLAUDE_PLUGIN_ROOT}/bin/s"}}})
        write(self.root / ".codebuddy-plugin/plugin.json", {"name": "p", "mcpServers": {"s": {"command": "${CODEBUDDY_PLUGIN_ROOT}/bin/s"}}})
        self.assertEqual(([], []), plugin_compat.check_plugin(self.root))
        clients = plugin_compat.effective_servers(self.root)
        self.assertEqual(".codebuddy-plugin/plugin.json", clients["WorkBuddy"]["s"][0])

    def test_mcp_directory_overrides_and_interpreters(self) -> None:
        write(self.root / ".claude-plugin/plugin.json", {"name": "p", "mcpServers": {"s": {"command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/s.py"]}}})
        write(self.root / "mcp/extra.json", {"mcpServers": {"s": {"command": "${CODEBUDDY_PLUGIN_ROOT}/bin/s"}, "t": {"command": "${CODEBUDDY_PLUGIN_ROOT}/bin/t", "args": ["../t.json"]}}})
        errors, _ = plugin_compat.check_plugin(self.root)
        self.assertTrue(any(e.startswith("[Claude Code] server 's'") and "interpreter 'python3'" in e for e in errors), errors)
        self.assertTrue(any(e.startswith("[WorkBuddy] server 't' from mcp/extra.json: '../t.json' is relative") for e in errors), errors)
        self.assertFalse(any(e.startswith("[WorkBuddy] server 's'") for e in errors), errors)


class LocalPluginTests(unittest.TestCase):
    def test_local_plugin_rejects_root_mcp_json_and_mismatched_workbuddy_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(validate_repo, "ROOT", Path(directory)):
            plugin = Path(directory) / "plugins" / "p"
            write(plugin / ".codex-plugin/plugin.json", {
                "name": "p", "version": "1.0.0", "description": "d", "author": {"name": "a"},
                "interface": {"displayName": "P", "shortDescription": "s", "longDescription": "l", "developerName": "a",
                              "category": "Productivity", "capabilities": ["Read"], "defaultPrompt": ["x"]},
                "mcpServers": "./.mcp.json",
            })
            write(plugin / ".mcp.json", {"mcpServers": {"s": {"command": "./bin/s", "cwd": "."}}})
            write(plugin / ".codebuddy-plugin/plugin.json", {"name": "p", "version": "0.9.0"})
            errors: list[str] = []
            validate_repo.validate_manifest("p", plugin / ".codex-plugin/plugin.json", errors)
            self.assertTrue(any(e.startswith("plugins/p/.mcp.json: Claude Code and WorkBuddy load") for e in errors), errors)
            self.assertTrue(any("plugins/p/.codebuddy-plugin/plugin.json: version must match" in e for e in errors), errors)
            self.assertTrue(any("[WorkBuddy] server 's' from .mcp.json: './bin/s' is relative" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
