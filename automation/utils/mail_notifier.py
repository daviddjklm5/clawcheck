from __future__ import annotations

import json
import mimetypes
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any

from automation.utils.config_loader import MailSettings


def send_action_notification(
    *,
    mail_settings: MailSettings,
    action: str,
    success: bool,
    started_at: datetime,
    finished_at: datetime,
    summary: dict[str, Any],
    error_message: str | None = None,
    attachment_paths: list[Path] | None = None,
) -> bool:
    if not mail_settings.enabled:
        return False

    if success:
        allowed_actions = {item.strip() for item in mail_settings.send_on_success if item.strip()}
        if allowed_actions and action not in allowed_actions:
            return False
    elif not mail_settings.send_on_failure:
        return False

    from_addr = (mail_settings.from_addr or mail_settings.username).strip()
    to_addrs = [addr.strip() for addr in mail_settings.to_addrs if addr.strip()]
    cc_addrs = [addr.strip() for addr in mail_settings.cc_addrs if addr.strip()]

    if not mail_settings.host.strip():
        raise ValueError("Mail host is required when mail.enabled is true")
    if not from_addr:
        raise ValueError("Mail from_addr or mail.username is required when mail.enabled is true")
    if not to_addrs:
        raise ValueError("Mail to_addrs is required when mail.enabled is true")
    if not mail_settings.username.strip() or not mail_settings.password.strip():
        raise ValueError("Mail username/password is required when mail.enabled is true")

    msg = EmailMessage()
    msg["Subject"] = _build_subject(action=action, success=success, finished_at=finished_at)
    msg["From"] = formataddr((mail_settings.from_name or from_addr, from_addr))
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)

    msg.set_content(
        _build_body(
            action=action,
            success=success,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary,
            error_message=error_message,
        )
    )

    for path in attachment_paths or []:
        if not path.exists() or not path.is_file():
            continue
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )

    recipients = to_addrs + cc_addrs
    timeout = max(float(mail_settings.timeout_sec), 1.0)
    if mail_settings.use_ssl:
        with smtplib.SMTP_SSL(mail_settings.host, mail_settings.port, timeout=timeout) as server:
            server.login(mail_settings.username, mail_settings.password)
            server.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(mail_settings.host, mail_settings.port, timeout=timeout) as server:
            if mail_settings.use_starttls:
                server.starttls()
            server.login(mail_settings.username, mail_settings.password)
            server.send_message(msg, to_addrs=recipients)
    return True


def _build_subject(*, action: str, success: bool, finished_at: datetime) -> str:
    status = "SUCCESS" if success else "FAILED"
    return f"[clawcheck][{action}][{status}] {finished_at.strftime('%Y-%m-%d %H:%M:%S')}"


def _build_body(
    *,
    action: str,
    success: bool,
    started_at: datetime,
    finished_at: datetime,
    summary: dict[str, Any],
    error_message: str | None,
) -> str:
    lines = [
        f"action: {action}",
        f"status: {'SUCCESS' if success else 'FAILED'}",
        f"started_at: {started_at.isoformat(timespec='seconds')}",
        f"finished_at: {finished_at.isoformat(timespec='seconds')}",
        f"duration_seconds: {(finished_at - started_at).total_seconds():.1f}",
    ]

    if error_message:
        lines.append(f"error: {error_message}")

    if summary:
        lines.append("")
        lines.append("summary:")
        for key, value in summary.items():
            if value in ("", None, [], {}):
                continue
            lines.append(f"- {key}: {_format_summary_value(value)}")
    return "\n".join(lines)


def _format_summary_value(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
