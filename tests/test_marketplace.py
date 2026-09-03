from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_marketplace  # noqa: E402
import validate_repo  # noqa: E402


class MarketplaceUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.marketplace = {
            "name": "s-plugins",
            "interface": {"displayName": "S Plugins"},
            "plugins": [],
        }

    def release_args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "name": "design-rag",
            "version": "0.3.0",
            "ref": "v0.3.0",
            "url": "https://github.com/tadazly/design-rag.git",
            "path": "./plugins/design-rag",
            "description": "DRAG 本地游戏策划案与配置表检索、分析和索引管理工具",
            "display_name": "DRAG 游戏策划知识库",
            "short_description": "检索本地策划案、配表和历史版本",
            "long_description": "使用本地只读索引检索和分析游戏策划资料。",
            "developer_name": "tadazly",
            "website_url": "https://github.com/tadazly/design-rag",
            "marketplace": validate_repo.MARKETPLACE_PATH,
            "readme": validate_repo.README_PATH,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def register_plugin(self) -> None:
        args = self.release_args()
        update_marketplace.validate_args(args)
        self.assertTrue(update_marketplace.upsert_release(self.marketplace, args))

    def minimal_update_args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "version": "0.3.1",
            "ref": "v0.3.1",
            "url": None,
            "path": None,
            "description": None,
            "display_name": None,
            "short_description": None,
            "long_description": None,
            "developer_name": None,
            "website_url": None,
        }
        values.update(overrides)
        return self.release_args(**values)

    def test_first_release_requires_complete_source_and_display_metadata(self) -> None:
        args = self.release_args(display_name=None, website_url=None)
        update_marketplace.validate_args(args)
        with self.assertRaisesRegex(ValueError, "first release requires"):
            update_marketplace.upsert_release(self.marketplace, args)

    def test_first_release_adds_complete_marketplace_entry(self) -> None:
        self.register_plugin()
        plugin = self.marketplace["plugins"][0]
        self.assertEqual("0.3.0", plugin["version"])
        self.assertEqual("v0.3.0", plugin["source"]["ref"])
        self.assertEqual("AVAILABLE", plugin["policy"]["installation"])
        self.assertEqual("ON_INSTALL", plugin["policy"]["authentication"])
        self.assertEqual("Productivity", plugin["category"])
        self.assertEqual("DRAG 游戏策划知识库", plugin["interface"]["displayName"])

    def test_existing_release_only_requires_identity_and_version(self) -> None:
        self.register_plugin()
        args = self.minimal_update_args()
        update_marketplace.validate_args(args)
        self.assertTrue(update_marketplace.upsert_release(self.marketplace, args))
        plugin = self.marketplace["plugins"][0]
        self.assertEqual("0.3.1", plugin["version"])
        self.assertEqual("v0.3.1", plugin["source"]["ref"])
        self.assertEqual("DRAG 游戏策划知识库", plugin["interface"]["displayName"])
        self.assertFalse(update_marketplace.upsert_release(self.marketplace, args))

    def test_optional_metadata_updates_marketplace_and_readme_source(self) -> None:
        self.register_plugin()
        args = self.minimal_update_args(
            description="Updated package description",
            display_name="DRAG Knowledge Base",
            short_description="Updated summary",
            website_url="https://github.com/tadazly/design-rag/releases",
        )
        update_marketplace.validate_args(args)
        update_marketplace.upsert_release(self.marketplace, args)
        plugin = self.marketplace["plugins"][0]
        self.assertEqual("Updated package description", plugin["description"])
        self.assertEqual("DRAG Knowledge Base", plugin["interface"]["displayName"])
        self.assertEqual("Updated summary", plugin["interface"]["shortDescription"])
        self.assertEqual(
            "https://github.com/tadazly/design-rag/releases",
            plugin["interface"]["websiteURL"],
        )

    def test_existing_release_cannot_retarget_source(self) -> None:
        self.register_plugin()
        args = self.minimal_update_args(url="https://github.com/example/other.git")
        update_marketplace.validate_args(args)
        with self.assertRaisesRegex(ValueError, "cannot change.*URL"):
            update_marketplace.upsert_release(self.marketplace, args)

    def test_rendered_catalog_uses_marketplace_metadata_without_markers(self) -> None:
        self.register_plugin()
        rendered = validate_repo.render_plugin_catalog(self.marketplace)
        self.assertIn(
            "[DRAG 游戏策划知识库](<https://github.com/tadazly/design-rag>)",
            rendered,
        )
        self.assertNotIn("| ID |", rendered)
        self.assertNotIn("| 版本 |", rendered)
        self.assertNotIn("BEGIN GENERATED", rendered)

    def test_catalog_section_is_replaced_by_heading(self) -> None:
        self.register_plugin()
        readme = "# Title\n\n## 插件目录\n\nold\n\n## 发布插件\n\nnext\n"
        updated = validate_repo.replace_plugin_catalog(
            readme, validate_repo.render_plugin_catalog(self.marketplace)
        )
        self.assertNotIn("old", updated)
        self.assertIn("## 发布插件\n\nnext", updated)
        self.assertNotIn("<!--", updated)

    def test_invalid_release_payload_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "--path"):
            update_marketplace.validate_args(self.release_args(path="../../outside"))
        with self.assertRaisesRegex(ValueError, "--ref"):
            update_marketplace.validate_args(self.release_args(ref="bad ref"))
        with self.assertRaisesRegex(ValueError, "--version"):
            update_marketplace.validate_args(self.release_args(version="v0.3.0"))
        with self.assertRaisesRegex(ValueError, "--website-url"):
            update_marketplace.validate_args(
                self.release_args(website_url="https://example.com/<unsafe>")
            )

    def test_catalog_text_escapes_markdown_and_html(self) -> None:
        self.register_plugin()
        self.marketplace["plugins"][0]["interface"]["shortDescription"] = (
            "A <tag> & [label] | `code`"
        )
        rendered = validate_repo.render_plugin_catalog(self.marketplace)
        self.assertIn(
            "A &lt;tag&gt; &amp; \\[label\\] \\| \\`code\\`",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
