from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, text.strip()

    end_marker = "\n---\n"
    end_index = normalized.find(end_marker, 4)
    if end_index < 0:
        return {}, text.strip()

    raw_frontmatter = normalized[4:end_index]
    body = normalized[end_index + len(end_marker) :].strip()
    payload = yaml.safe_load(raw_frontmatter) or {}
    if not isinstance(payload, dict):
        raise ValueError("Skill frontmatter must be a YAML object.")
    return payload, body


def _derive_description(body: str) -> str:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line[:160]
    return ""


@dataclass(frozen=True)
class SkillIndexEntry:
    skill_name: str
    skill_dir: Path
    description: str
    status: str
    owner: str
    domain: str
    references: list[str]
    mtime: float
    content_hash: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "name": self.skill_name,
            "description": self.description,
            "status": self.status,
            "owner": self.owner,
            "domain": self.domain,
            "references": list(self.references),
        }


@dataclass(frozen=True)
class LoadedSkillContext:
    skill_name: str
    description: str
    body: str
    references: dict[str, str]


@dataclass(frozen=True)
class SkillIndex:
    entries: dict[str, SkillIndexEntry]
    warnings: list[str]
    built_at: str

    def active_entries(self) -> list[SkillIndexEntry]:
        return sorted(
            (entry for entry in self.entries.values() if entry.status != "deprecated"),
            key=lambda entry: entry.skill_name,
        )


class SkillLoader:
    def __init__(
        self,
        *,
        root_dir: Path | None = None,
        runtime_snapshot_path: Path | None = None,
    ) -> None:
        self._root_dir = root_dir or Path(__file__).resolve().parent / "skills"
        self._snapshot_path = runtime_snapshot_path or (
            Path(__file__).resolve().parents[1] / "runtime" / "chat" / "skill-index.json"
        )
        self._index: SkillIndex | None = None
        self._signature: tuple[tuple[str, int], ...] | None = None

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def get_index(self) -> SkillIndex:
        signature = self._compute_signature()
        if self._index is None or signature != self._signature:
            self._index = self._build_index()
            self._signature = signature
            self._write_snapshot(self._index)
        return self._index

    def list_router_metadata(self) -> list[dict[str, Any]]:
        return [entry.to_summary() for entry in self.get_index().active_entries()]

    def load_skill_context(
        self,
        skill_name: str,
        *,
        references: list[str] | None = None,
    ) -> LoadedSkillContext:
        index = self.get_index()
        entry = index.entries.get(skill_name)
        if entry is None:
            raise KeyError(f"Skill not found: {skill_name}")
        if entry.status == "deprecated":
            raise ValueError(f"Skill is deprecated: {skill_name}")

        skill_path = entry.skill_dir / "SKILL.md"
        metadata, body = _split_frontmatter(skill_path.read_text(encoding="utf-8"))
        allowed_references = set(entry.references)
        selected_references = references or []
        loaded_references: dict[str, str] = {}
        for reference_name in selected_references:
            if reference_name not in allowed_references:
                raise ValueError(f"Reference '{reference_name}' is not allowed for skill '{skill_name}'.")
            reference_path = entry.skill_dir / "references" / f"{reference_name}.md"
            loaded_references[reference_name] = reference_path.read_text(encoding="utf-8").strip()

        description = str(metadata.get("description") or entry.description).strip() or entry.description
        return LoadedSkillContext(
            skill_name=entry.skill_name,
            description=description,
            body=body.strip(),
            references=loaded_references,
        )

    def _compute_signature(self) -> tuple[tuple[str, int], ...]:
        if not self._root_dir.exists():
            return ()

        rows: list[tuple[str, int]] = []
        for path in sorted(self._root_dir.rglob("*")):
            if path.is_dir():
                continue
            if path.name == "SKILL.md" or path.suffix.lower() == ".md":
                stat = path.stat()
                rows.append((str(path.relative_to(self._root_dir)).replace("\\", "/"), stat.st_mtime_ns))
        return tuple(rows)

    def _build_index(self) -> SkillIndex:
        entries: dict[str, SkillIndexEntry] = {}
        warnings: list[str] = []
        built_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not self._root_dir.exists():
            return SkillIndex(entries=entries, warnings=warnings, built_at=built_at)

        for skill_dir in sorted(path for path in self._root_dir.iterdir() if path.is_dir()):
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.exists():
                warnings.append(f"Skip skill directory without SKILL.md: {skill_dir.name}")
                continue

            try:
                raw_text = skill_path.read_text(encoding="utf-8")
                metadata, body = _split_frontmatter(raw_text)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Skip invalid skill '{skill_dir.name}': {exc}")
                continue

            skill_name = str(metadata.get("name") or skill_dir.name).strip() or skill_dir.name
            if skill_name in entries:
                warnings.append(f"Skip duplicate skill name: {skill_name}")
                continue

            description = str(metadata.get("description") or _derive_description(body)).strip()
            status = str(metadata.get("status") or "active").strip() or "active"
            owner = str(metadata.get("owner") or "").strip()
            domain = str(metadata.get("domain") or "").strip()

            reference_dir = skill_dir / "references"
            discovered_reference_names = (
                sorted(path.stem for path in reference_dir.glob("*.md")) if reference_dir.exists() else []
            )
            configured_references = metadata.get("references")
            if configured_references is None:
                reference_names = discovered_reference_names
            elif isinstance(configured_references, list):
                reference_names = []
                for item in configured_references:
                    reference_name = str(item).strip()
                    if not reference_name:
                        continue
                    reference_path = reference_dir / f"{reference_name}.md"
                    if not reference_path.exists():
                        warnings.append(
                            f"Skill '{skill_name}' references missing file: references/{reference_name}.md"
                        )
                        continue
                    reference_names.append(reference_name)
            else:
                warnings.append(f"Skill '{skill_name}' has invalid references metadata.")
                reference_names = discovered_reference_names

            content_hasher = hashlib.sha256()
            content_hasher.update(raw_text.encode("utf-8"))
            for reference_name in reference_names:
                reference_path = reference_dir / f"{reference_name}.md"
                content_hasher.update(reference_path.read_bytes())

            entry_mtime = max(
                [skill_path.stat().st_mtime, *[
                    (reference_dir / f"{reference_name}.md").stat().st_mtime for reference_name in reference_names
                ]],
                default=skill_path.stat().st_mtime,
            )
            entries[skill_name] = SkillIndexEntry(
                skill_name=skill_name,
                skill_dir=skill_dir,
                description=description,
                status=status,
                owner=owner,
                domain=domain,
                references=reference_names,
                mtime=entry_mtime,
                content_hash=content_hasher.hexdigest()[:16],
            )

        return SkillIndex(entries=entries, warnings=warnings, built_at=built_at)

    def _write_snapshot(self, index: SkillIndex) -> None:
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "builtAt": index.built_at,
            "warnings": list(index.warnings),
            "skills": [
                {
                    "skillName": entry.skill_name,
                    "skillDir": str(entry.skill_dir),
                    "description": entry.description,
                    "status": entry.status,
                    "owner": entry.owner,
                    "domain": entry.domain,
                    "references": list(entry.references),
                    "mtime": entry.mtime,
                    "contentHash": entry.content_hash,
                }
                for entry in sorted(index.entries.values(), key=lambda item: item.skill_name)
            ],
        }
        self._snapshot_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
