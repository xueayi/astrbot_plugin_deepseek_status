"""Tests for official status response handling."""

import unittest

from status import PAGE_ID, format_changes, format_current, snapshot


class StatusTests(unittest.TestCase):
    def test_new_update_and_resolution_have_distinct_fingerprints(self):
        active = {
            "page": {"page_id": PAGE_ID, "components": []},
            "active_changes": [],
        }
        event = {
            "change_id": 1,
            "title": "API 性能下降",
            "status": "investigating",
            "start_at_seconds": 1,
            "updates": [{"update_id": "u1", "description": "排查中"}],
        }
        first, _ = snapshot(active, {"items": [event]})
        self.assertEqual(first, {"1": "investigating:u1"})

        event["status"] = "resolved"
        event["updates"].append({"update_id": "u2", "description": "已恢复"})
        second, events = snapshot(active, {"items": [event]})
        self.assertEqual(second, {"1": "resolved:u2"})
        self.assertIn("已解决", format_changes(events))
        self.assertIn("已恢复", format_changes(events))

    def test_current_status_uses_active_component_state(self):
        active = {
            "page": {
                "page_id": PAGE_ID,
                "components": [{"component_id": "api", "name": "API 服务"}],
            },
            "active_changes": [
                {
                    "change_id": 2,
                    "title": "性能下降",
                    "status": "investigating",
                    "affected_components": [
                        {"component_id": "api", "status": "degraded"}
                    ],
                }
            ],
        }
        text = format_current(active)
        self.assertIn("API 服务：性能下降", text)
        self.assertIn("1 个进行中事件", text)

    def test_rejects_unexpected_page(self):
        with self.assertRaises(ValueError):
            snapshot({"page": {"page_id": 0}, "active_changes": []}, {"items": []})


if __name__ == "__main__":
    unittest.main()
