import json
import sqlite3
import unittest

from cashforge_monitor import init, create, list_all, set_enabled, compare_runs
from cashforge_ai import AIUnavailable, chat


class ExtensionTests(unittest.TestCase):
    def test_monitor_persists_and_can_pause(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        init(db)
        monitor_id = create(db, "AI tools for shops", "opportunity discovery",
                            ["Hacker News", "Google News"], 24)
        self.assertEqual(len(list_all(db)), 1)
        set_enabled(db, monitor_id, False)
        self.assertEqual(list_all(db)[0]["enabled"], 0)
        db.close()

    def test_run_comparison_finds_new_and_persistent_themes(self):
        old = {"analysis": {"opportunities": [{"title": "Billing automation"}]},
               "metrics": {"signals": 5}}
        new = {"analysis": {"opportunities": [{"title": "Billing automation"},
                                                {"title": "Returns management"}]},
               "metrics": {"signals": 8}}
        result = compare_runs(old, new)
        self.assertEqual(len(result["new_themes"]), 1)
        self.assertEqual(len(result["persistent_themes"]), 1)
        self.assertEqual(result["signal_delta"], 3)

    def test_ai_requires_key_without_crashing_local_mode(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        old = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            # Isolate this test from the developer's real, locally saved provider key.
            with tempfile.TemporaryDirectory() as tmp:
                with patch("cashforge_ai.SETTINGS_FILE", Path(tmp) / "provider_settings.json"):
                    with self.assertRaises(AIUnavailable):
                        chat([{"role": "user", "content": "test"}])
        finally:
            if old is not None:
                os.environ["OPENROUTER_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
