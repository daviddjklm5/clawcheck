from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ApprovalAction = Literal["approve", "reject"]
ApprovalOpinionSource = Literal[
    "user_input",
    "suggested_from_109",
    "user_override_after_suggestion",
]
ApprovalPlanStatus = Literal[
    "pending_confirmation",
    "dry_run_succeeded",
    "submit_requested",
    "submitted",
    "failed",
    "canceled",
    "expired",
]
ApprovalCommandType = Literal["confirm", "verify", "cancel"]

TERMINAL_APPROVAL_PLAN_STATUSES: set[str] = {"submitted", "failed", "canceled", "expired"}
ACTIVE_APPROVAL_PLAN_STATUSES: set[str] = {"pending_confirmation", "dry_run_succeeded"}


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentNo: str = ""
    action: ApprovalAction | None = None
    approvalOpinion: str = ""
    dryRun: bool = False


class ApprovalPlanSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    todoProcessStatus: str = ""
    documentStatus: str = ""
    riskSummary: str = ""
    assessmentBatchNo: str = ""


class ApprovalPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planId: str = Field(min_length=1)
    sessionId: str = Field(min_length=1)
    documentNo: str = Field(min_length=1)
    action: ApprovalAction
    approvalOpinion: str = ""
    approvalOpinionSource: ApprovalOpinionSource = "user_input"
    requestedDryRun: bool = False
    status: ApprovalPlanStatus = "pending_confirmation"
    snapshot: ApprovalPlanSnapshot
    confirmCommand: str = ""
    dryRunCommand: str = ""
    cancelCommand: str = ""
    createdAt: str = ""
    updatedAt: str = ""
    expiresAt: str = ""

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.expiresAt.strip():
            return False
        current = now or datetime.now()
        expires_at = datetime.strptime(self.expiresAt, "%Y-%m-%d %H:%M:%S")
        return current >= expires_at


class ApprovalCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commandType: ApprovalCommandType
    planId: str = Field(min_length=1)
