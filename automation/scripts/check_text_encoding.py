from __future__ import annotations

import argparse
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
SUSPICIOUS_MOJIBAKE_CHARS = set("鐢鏂鍚鍙缁璇瑙鏌ョ湅绫诲瀷壊缂栫爜鎻忚堪斂粐璇︽儏")
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
)


@dataclass
class Finding:
    path: str
    line: int
    reason: str
    content: str
    recovered: str | None = None


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
    if not any(ch in SUSPICIOUS_MOJIBAKE_CHARS for ch in line):
        return None

    try:
        recovered = line.encode("gb18030").decode("utf-8")
    except UnicodeError:
        return None

    if recovered == line:
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
        if "\ufffd" in line:
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

    print("Encoding issues detected:")
    for finding in findings:
        location = f"{finding.path}:{finding.line}" if finding.line else finding.path
        print(f"- {location}: {finding.reason}")
        if finding.content:
            print(f"  content: {finding.content}")
        if finding.recovered:
            print(f"  recovered: {finding.recovered}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
