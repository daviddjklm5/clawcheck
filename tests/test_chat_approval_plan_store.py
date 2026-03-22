from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from automation.chat.approval_models import ApprovalPlan, ApprovalPlanSnapshot
from automation.chat.approval_plan_store import ApprovalPlanStore


def _build_plan(
    *,
    session_id: str = "s1",
    plan_id: str = "approval-plan-1",
    status: str = "pending_confirmation",
    expires_at: str | None = None,
) -> ApprovalPlan:
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return ApprovalPlan(
        planId=plan_id,
        sessionId=session_id,
        documentNo="RA-20260310-00019845",
        action="approve",
        approvalOpinion="同意，按当前职责范围处理。",
        approvalOpinionSource="user_input",
        requestedDryRun=False,
        status=status,  # type: ignore[arg-type]
        snapshot=ApprovalPlanSnapshot(
            todoProcessStatus="待处理",
            documentStatus="审批中",
            riskSummary="加强审核",
            assessmentBatchNo="audit_20260322_103000",
        ),
        confirmCommand=f"确认审批计划 {plan_id}",
        dryRunCommand=f"验证审批计划 {plan_id}",
        cancelCommand=f"取消审批计划 {plan_id}",
        createdAt=now_text,
        updatedAt=now_text,
        expiresAt=expires_at or (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
    )


def test_plan_store_persists_and_reads_back_plan(tmp_path: Path) -> None:
    store = ApprovalPlanStore(tmp_path / "approval-plans")
    plan = _build_plan()

    store.save_plan(plan)
    loaded = store.get_plan("s1", "approval-plan-1")

    assert loaded is not None
    assert loaded.planId == plan.planId
    assert loaded.documentNo == plan.documentNo


def test_plan_store_updates_plan_status_atomically(tmp_path: Path) -> None:
    store = ApprovalPlanStore(tmp_path / "approval-plans")
    store.save_plan(_build_plan())

    updated = store.update_plan(
        "s1",
        "approval-plan-1",
        lambda plan: setattr(plan, "status", "dry_run_succeeded") or plan,
    )

    assert updated is not None
    loaded = store.get_plan("s1", "approval-plan-1")
    assert loaded is not None
    assert loaded.status == "dry_run_succeeded"


def test_plan_store_marks_expired_plan_when_loaded(tmp_path: Path) -> None:
    store = ApprovalPlanStore(tmp_path / "approval-plans")
    expired_plan = _build_plan(expires_at=(datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"))
    store.save_plan(expired_plan)

    loaded = store.get_plan("s1", "approval-plan-1")

    assert loaded is not None
    assert loaded.status == "expired"
