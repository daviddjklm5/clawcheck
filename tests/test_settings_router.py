from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from automation.api.routers.settings import (
    CollectScheduleUpdateRequest,
    get_runtime_settings,
    put_runtime_collect_schedule,
)


class SettingsRouterTest(unittest.TestCase):
    def test_get_runtime_settings_returns_summary(self) -> None:
        payload = {"stats": [], "runtime": [], "collectSchedule": {}}

        with patch("automation.api.routers.settings.get_runtime_configuration_summary", return_value=payload):
            result = get_runtime_settings()

        self.assertEqual(result, payload)

    def test_put_runtime_collect_schedule_updates_and_returns_summary(self) -> None:
        payload = {"stats": [], "runtime": [], "collectSchedule": {"enabled": True, "intervalMinutes": 15, "autoAudit": True}}
        request = CollectScheduleUpdateRequest(enabled=True, intervalMinutes=15, autoAudit=True)

        with (
            patch("automation.api.routers.settings.update_collect_schedule") as mocked_update,
            patch("automation.api.routers.settings.get_runtime_configuration_summary", return_value=payload),
        ):
            result = put_runtime_collect_schedule(request)

        self.assertEqual(result, payload)
        mocked_update.assert_called_once_with(enabled=True, interval_minutes=15, auto_audit=True)

    def test_put_runtime_collect_schedule_raises_400_for_invalid_interval(self) -> None:
        request = CollectScheduleUpdateRequest(enabled=True, intervalMinutes=0, autoAudit=True)

        with patch(
            "automation.api.routers.settings.update_collect_schedule",
            side_effect=ValueError("启用定时采集时，采集频率必须为大于 0 的分钟数。"),
        ):
            with self.assertRaises(HTTPException) as context:
                put_runtime_collect_schedule(request)

        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
