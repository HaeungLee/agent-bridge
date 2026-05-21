import fnmatch
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "task_spec.v0"

REQUIRED_STRING_FIELDS = [
    "schema_version",
    "task_id",
    "phase",
    "slice",
    "title",
    "owner",
    "objective",
]

REQUIRED_LIST_FIELDS = [
    "allowed_files",
    "forbidden_files",
    "required_commands",
    "acceptance_criteria",
    "hard_rules",
    "expected_report_sections",
]

REQUIRED_FORBIDDEN_PATTERNS = ["agent_bridge_mvp.md", ".git/**"]
REQUIRED_HARD_RULES = ["Do not commit.", "Do not implement the next phase."]


@dataclass
class TaskSpecValidation:
    spec: dict[str, Any]
    warnings: list[str]


@dataclass
class ResultCheck:
    changed_files: list[str]
    forbidden_matches: list[str]
    out_of_scope_files: list[str]

    @property
    def passed(self) -> bool:
        return not self.forbidden_matches and not self.out_of_scope_files


def load_task_spec(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Task spec does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Task spec path is not a file: {path}")
    with path.open("rb") as f:
        return tomllib.load(f)


def validate_task_spec(spec: dict[str, Any]) -> TaskSpecValidation:
    if not isinstance(spec, dict):
        raise ValueError("Task spec must be a TOML table")

    warnings: list[str] = []
    _validate_required_strings(spec)
    _validate_required_lists(spec)
    _validate_schema_version(spec)
    _validate_file_patterns(spec["allowed_files"], "allowed_files")
    _validate_file_patterns(spec["forbidden_files"], "forbidden_files")
    _validate_no_pattern_overlap(spec["allowed_files"], spec["forbidden_files"])
    warnings.extend(_validate_recommended_guardrails(spec))
    return TaskSpecValidation(spec=spec, warnings=warnings)


def render_task_prompt(spec: dict[str, Any]) -> str:
    validation = validate_task_spec(spec)
    spec = validation.spec

    lines: list[str] = [
        f"# Task: {spec['title']}",
        "",
        "## Metadata",
        "",
        f"- Schema: {spec['schema_version']}",
        f"- Task ID: {spec['task_id']}",
        f"- Phase: {spec['phase']}",
        f"- Slice: {spec['slice']}",
        f"- Owner: {spec['owner']}",
        "",
        "## Objective",
        "",
        spec["objective"].strip(),
        "",
        "## Allowed Files",
        "",
        *_bullet_lines(spec["allowed_files"]),
        "",
        "## Forbidden Files",
        "",
        *_bullet_lines(spec["forbidden_files"]),
        "",
        "## Required Commands",
        "",
        *_bullet_lines(spec["required_commands"]),
        "",
        "## Acceptance Criteria",
        "",
        *_bullet_lines(spec["acceptance_criteria"]),
        "",
        "## Hard Rules",
        "",
        *_bullet_lines(spec["hard_rules"]),
        "",
        "## Expected Report",
        "",
        *_bullet_lines(spec["expected_report_sections"]),
        "",
        "## Execution Boundary",
        "",
        "Implement only the task described above. Do not implement future phases, adjacent features, or optional integrations.",
        "If a required change appears to exceed the allowed files or hard rules, stop and report the blocker.",
        "",
    ]

    if validation.warnings:
        lines.extend(["## Validation Warnings", ""])
        lines.extend(_bullet_lines(validation.warnings))
        lines.append("")

    return "\n".join(lines)


def write_rendered_task(spec_path: Path, output_path: Path) -> None:
    spec = load_task_spec(spec_path)
    prompt = render_task_prompt(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")


def check_task_result(spec: dict[str, Any], workspace_path: Path) -> ResultCheck:
    validation = validate_task_spec(spec)
    spec = validation.spec
    changed_files = collect_git_changed_files(workspace_path)
    allowed = [_normalize_pattern(item) for item in spec["allowed_files"]]
    forbidden = [_normalize_pattern(item) for item in spec["forbidden_files"]]

    forbidden_matches: list[str] = []
    out_of_scope_files: list[str] = []

    for changed_file in changed_files:
        if _matches_any(changed_file, forbidden):
            forbidden_matches.append(changed_file)
        elif not _matches_any(changed_file, allowed):
            out_of_scope_files.append(changed_file)

    return ResultCheck(
        changed_files=changed_files,
        forbidden_matches=forbidden_matches,
        out_of_scope_files=out_of_scope_files,
    )


def collect_git_changed_files(workspace_path: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(workspace_path), "status", "--porcelain=v1", "--untracked-files=all"],
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip()}")

    changed_files: list[str] = []
    for line in result.stdout.splitlines():
        path = _parse_porcelain_path(line)
        if path:
            changed_files.append(_normalize_pattern(path))
    return sorted(set(changed_files))


def _validate_required_strings(spec: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_STRING_FIELDS if field not in spec]
    if missing:
        raise ValueError(f"Missing required string fields: {missing}")
    for field in REQUIRED_STRING_FIELDS:
        value = spec[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Field '{field}' must be a non-empty string")


def _validate_required_lists(spec: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_LIST_FIELDS if field not in spec]
    if missing:
        raise ValueError(f"Missing required list fields: {missing}")
    for field in REQUIRED_LIST_FIELDS:
        value = spec[field]
        if not isinstance(value, list) or not value:
            raise ValueError(f"Field '{field}' must be a non-empty list")
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Field '{field}' item {index} must be a non-empty string")


def _validate_schema_version(spec: dict[str, Any]) -> None:
    if spec["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"Invalid schema_version '{spec['schema_version']}'. Expected '{SCHEMA_VERSION}'"
        )


def _validate_file_patterns(patterns: list[str], field_name: str) -> None:
    for pattern in patterns:
        normalized = _normalize_pattern(pattern)
        path = PurePosixPath(normalized)
        if path.is_absolute():
            raise ValueError(f"Field '{field_name}' contains absolute path: {pattern}")
        if ".." in path.parts:
            raise ValueError(f"Field '{field_name}' contains parent traversal: {pattern}")


def _validate_no_pattern_overlap(allowed: list[str], forbidden: list[str]) -> None:
    normalized_allowed = {_normalize_pattern(item) for item in allowed}
    normalized_forbidden = {_normalize_pattern(item) for item in forbidden}
    direct_overlap = sorted(normalized_allowed & normalized_forbidden)
    if direct_overlap:
        raise ValueError(f"Patterns appear in both allowed_files and forbidden_files: {direct_overlap}")

    for allow_pattern in normalized_allowed:
        for forbid_pattern in normalized_forbidden:
            if fnmatch.fnmatch(allow_pattern, forbid_pattern):
                raise ValueError(
                    f"Allowed pattern '{allow_pattern}' is matched by forbidden pattern '{forbid_pattern}'"
                )


def _validate_recommended_guardrails(spec: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    forbidden = {_normalize_pattern(item) for item in spec["forbidden_files"]}
    hard_rules = {item.strip().lower() for item in spec["hard_rules"]}

    for pattern in REQUIRED_FORBIDDEN_PATTERNS:
        if _normalize_pattern(pattern) not in forbidden:
            warnings.append(f"Recommended forbidden pattern missing: {pattern}")

    for rule in REQUIRED_HARD_RULES:
        if rule.lower() not in hard_rules:
            warnings.append(f"Recommended hard rule missing: {rule}")

    return warnings


def _normalize_pattern(pattern: str) -> str:
    return pattern.strip().replace("\\", "/").strip("/")


def _bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(path == pattern or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _parse_porcelain_path(line: str) -> str:
    if not line or len(line) < 4:
        return ""
    raw_path = line[3:]
    if " -> " in raw_path:
        raw_path = raw_path.split(" -> ", 1)[1]
    return raw_path.strip().strip('"')
