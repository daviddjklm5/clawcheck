from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".sql",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".csv",
    ".tsv",
    ".xml",
}

SPECIAL_TEXT_FILES = {"AGENTS.md", ".editorconfig", ".gitattributes"}
CJK_RE = re.compile(r"[㐀-鿿]")
REPLACEMENT_CHAR = chr(0xFFFD)
RECOVERED_KEYWORDS = (
    "申请",
    "角色",
    "查看",
    "详情",
    "权限",
    "组织",
    "审批",
    "单据",
    "列表",
    "工号",
    "名称",
    "编码",
    "日期",
    "状态",
    "类型",
    "人员",
    "花名册",
    "采集",
    "处理",
    "评估",
    "分析",
    "配置",
    "运行",
    "当前",
    "路径",
    "模块",
    "报表",
    "中心",
    "阶段",
    "服务站",
    "浏览器",
    "数据库",
    "摘要",
    "安全",
    "说明",
    "自动",
    "批量",
    "保存",
    "刷新",
    "范围",
    "计划",
    "工作台",
    "流程",
    "入口",
    "导出",
)


@dataclass
class Finding:
    path: str
    line: int
    reason: str
    content: str
    recovered: str | None = None


def safe_print(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        sys.stdout.buffer.write((message + "\n").encode(encoding, errors="backslashreplace"))


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in SPECIAL_TEXT_FILES


def iter_tracked_text_files(repo_root: Path) -> Iterable[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files"],
            cwd=repo_root,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        for path in repo_root.rglob("*"):
            if path.is_file() and is_text_file(path):
                yield path
        return

    for rel in output.splitlines():
        path = repo_root / rel
        if path.is_file() and is_text_file(path):
            yield path


def detect_mojibake(line: str) -> str | None:
    try:
        recovered = line.encode("gb18030").decode("utf-8")
    except UnicodeError:
        return None

    if recovered == line:
        return None

    # Normal Chinese can occasionally "decode" into non-Chinese symbols.
    # Skip those cases to avoid false positives.
    if not CJK_RE.search(recovered):
        return None

    # Require strict reversibility to reduce random collisions.
    try:
        round_trip = recovered.encode("utf-8").decode("gb18030")
    except UnicodeError:
        return None
    if round_trip != line:
        return None

    if not any(keyword in recovered for keyword in RECOVERED_KEYWORDS):
        return None

    return recovered


def scan_file(path: Path, repo_root: Path) -> list[Finding]:
    rel_path = path.relative_to(repo_root).as_posix()
    findings: list[Finding] = []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        findings.append(Finding(rel_path, 0, f"read error: {exc}", ""))
        return findings

    if b"\x00" in raw:
        return findings

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        findings.append(Finding(rel_path, 0, "non-UTF-8 text file", str(exc)))
        return findings

    for line_no, line in enumerate(text.splitlines(), 1):
        if REPLACEMENT_CHAR in line:
            findings.append(Finding(rel_path, line_no, "replacement character found", line.strip()))

        recovered = detect_mojibake(line)
        if recovered:
            findings.append(
                Finding(
                    rel_path,
                    line_no,
                    "possible GBK/GB18030 mojibake",
                    line.strip(),
                    recovered.strip(),
                )
            )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check repository text files for encoding issues.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to scan. Defaults to the current working directory.",
    )
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    findings: list[Finding] = []
    for path in iter_tracked_text_files(repo_root):
        findings.extend(scan_file(path, repo_root))

    if not findings:
        print(f"OK: no encoding issues found under {repo_root}")
        return 0

    safe_print("Encoding issues detected:")
    for finding in findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        safe_print(f"- {location}: {finding.reason}")
        if finding.content:
            safe_print(f"  content: {finding.content}")
        if finding.recovered:
            safe_print(f"  recovered: {finding.recovered}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
