from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
from pathlib import Path
import threading
from typing import TypeVar

from automation.chat.approval_models import ApprovalPlan, TERMINAL_APPROVAL_PLAN_STATUSES

T = TypeVar("T")


class ApprovalPlanStore:
    def __init__(self, root_dir: Path) -> None:
        self._root_dir = root_dir
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def save_plan(self, plan: ApprovalPlan) -> ApprovalPlan:
        with self._lock:
            self._write_plan(plan)
        return plan

    def get_plan(self, session_id: str, plan_id: str) -> ApprovalPlan | None:
        with self._lock:
            plan = self._read_plan(session_id, plan_id)
            if plan is None:
                return None
            if plan.status not in TERMINAL_APPROVAL_PLAN_STATUSES and plan.is_expired():
                plan.status = "expired"
                plan.updatedAt = _now_text()
                self._write_plan(plan)
            return plan

    def list_session_plans(self, session_id: str) -> list[ApprovalPlan]:
        with self._lock:
            plans: list[ApprovalPlan] = []
            for path in sorted(self._root_dir.glob(f"{session_id}_*.json")):
                try:
                    plan = ApprovalPlan.model_validate_json(path.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                if plan.status not in TERMINAL_APPROVAL_PLAN_STATUSES and plan.is_expired():
                    plan.status = "expired"
                    plan.updatedAt = _now_text()
                    self._write_plan(plan)
                plans.append(plan)
            plans.sort(key=lambda item: (item.createdAt, item.planId))
            return plans

    def update_plan(
        self,
        session_id: str,
        plan_id: str,
        updater: Callable[[ApprovalPlan], T],
    ) -> T | None:
        with self._lock:
            plan = self._read_plan(session_id, plan_id)
            if plan is None:
                return None
            if plan.status not in TERMINAL_APPROVAL_PLAN_STATUSES and plan.is_expired():
                plan.status = "expired"
                plan.updatedAt = _now_text()
                self._write_plan(plan)
            result = updater(plan)
            self._write_plan(plan)
            return result

    def _plan_path(self, session_id: str, plan_id: str) -> Path:
        return self._root_dir / f"{session_id}_{plan_id}.json"

    def _read_plan(self, session_id: str, plan_id: str) -> ApprovalPlan | None:
        path = self._plan_path(session_id, plan_id)
        if not path.exists():
            return None
        return ApprovalPlan.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_plan(self, plan: ApprovalPlan) -> None:
        path = self._plan_path(plan.sessionId, plan.planId)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        tmp_path.replace(path)


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
