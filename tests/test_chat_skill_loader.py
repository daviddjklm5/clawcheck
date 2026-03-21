from __future__ import annotations

from pathlib import Path

from automation.chat.skill_loader import SkillLoader


def _write_skill(
    root_dir: Path,
    directory_name: str,
    *,
    frontmatter: str,
    body: str,
    references: dict[str, str] | None = None,
) -> None:
    skill_dir = root_dir / directory_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    if references:
        reference_dir = skill_dir / "references"
        reference_dir.mkdir(parents=True, exist_ok=True)
        for reference_name, reference_text in references.items():
            (reference_dir / f"{reference_name}.md").write_text(reference_text, encoding="utf-8")


def test_skill_loader_builds_active_index_and_snapshot(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "clawcheck-project",
        frontmatter=(
            "name: clawcheck-project\n"
            "description: Active skill\n"
            "status: active\n"
            "references:\n"
            "  - process-workbench\n"
        ),
        body="项目级实时查询规则",
        references={"process-workbench": "正式来源：process-workbench"},
    )
    _write_skill(
        tmp_path,
        "deprecated-skill",
        frontmatter=(
            "name: deprecated-skill\n"
            "description: Deprecated skill\n"
            "status: deprecated\n"
        ),
        body="Deprecated body",
    )
    snapshot_path = tmp_path / "runtime" / "skill-index.json"
    loader = SkillLoader(root_dir=tmp_path, runtime_snapshot_path=snapshot_path)

    router_metadata = loader.list_router_metadata()
    index = loader.get_index()

    assert [item["name"] for item in router_metadata] == ["clawcheck-project"]
    assert "deprecated-skill" in index.entries
    assert snapshot_path.exists()

    loaded = loader.load_skill_context("clawcheck-project", references=["process-workbench"])
    assert loaded.skill_name == "clawcheck-project"
    assert "正式来源" in loaded.references["process-workbench"]


def test_skill_loader_skips_duplicate_names_and_warns_on_missing_reference(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "skill-a",
        frontmatter=(
            "name: duplicate-skill\n"
            "description: First skill\n"
            "status: active\n"
            "references:\n"
            "  - exists\n"
            "  - missing\n"
        ),
        body="A body",
        references={"exists": "exists"},
    )
    _write_skill(
        tmp_path,
        "skill-b",
        frontmatter=(
            "name: duplicate-skill\n"
            "description: Second skill\n"
            "status: active\n"
        ),
        body="B body",
    )

    loader = SkillLoader(root_dir=tmp_path, runtime_snapshot_path=tmp_path / "runtime" / "skill-index.json")
    index = loader.get_index()

    assert list(index.entries) == ["duplicate-skill"]
    assert any("missing file" in warning for warning in index.warnings)
    assert any("duplicate skill name" in warning for warning in index.warnings)
