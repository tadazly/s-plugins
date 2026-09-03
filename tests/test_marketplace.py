from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest import mock


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

    def release_args(self, **overrides: str) -> argparse.Namespace:
        values = {
            "name": "design-rag",
            "url": "https://github.com/tadazly/design-rag.git",
            "path": "./plugins/design-rag",
            "ref": "v0.3.0",
            "category": "Productivity",
            "marketplace": ROOT / ".agents" / "plugins" / "marketplace.json",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_release_is_added_and_repeated_notification_is_idempotent(self) -> None:
        args = self.release_args()
        update_marketplace.validate_args(args)

        self.assertTrue(update_marketplace.upsert_marketplace(self.marketplace, args))
        first_entry = dict(self.marketplace["plugins"][0])
        self.assertFalse(update_marketplace.upsert_marketplace(self.marketplace, args))
        self.assertEqual(first_entry, self.marketplace["plugins"][0])

        with mock.patch.object(validate_repo, "load_json", return_value=self.marketplace):
            self.assertEqual([], validate_repo.validate())

    def test_invalid_release_payload_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "--path"):
            update_marketplace.validate_args(self.release_args(path="../../outside"))
        with self.assertRaisesRegex(ValueError, "--ref"):
            update_marketplace.validate_args(self.release_args(ref="bad ref"))


if __name__ == "__main__":
    unittest.main()
