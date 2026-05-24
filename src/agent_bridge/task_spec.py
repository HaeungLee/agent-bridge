import fnmatch
import json
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = "task_spec.v0"
DEFAULT_EXECUTION_MODE = "report"
EXECUTION_MODES = {"report", "worktree_patch"}

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

REQUIRED_FORBIDDEN_PATTERNS = [".git/**"]
REQUIRED_HARD_RULES = ["Do not commit.", "Do not implement the next phase."]
OPTIONAL_SCOPE_FIELDS = ["read_scope", "write_scope"]
OPTIONAL_FILE_LIST_FIELDS = [*OPTIONAL_SCOPE_FIELDS, "expected_artifacts"]
DEFAULT_EXPECTED_ARTIFACTS = [
    "summary.md",
    "decision_report.json",
    "diffstat.txt",
    "touched_files.json",
    "tests.md",
    "risks.md",
    "process.md",
    "metrics.json",
    "request.json",
    "completed.marker",
    "raw/stdout.txt",
    "raw/stderr.txt",
]
WORKTREE_PATCH_ARTIFACTS = ["patch.diff", "worktree.json"]
WRITE_TOOLS = {"edit", "write", "patch", "multiedit"}


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


@dataclass
class ToolUseCheck:
    tool_uses: list[dict[str, Any]]
    forbidden_matches: list[str]
    out_of_scope_paths: list[str]
    outside_workspace_paths: list[str]
    write_tool_uses: list[str]

    @property
    def passed(self) -> bool:
        return (
            not self.forbidden_matches
            and not self.out_of_scope_paths
            and not self.outside_workspace_paths
            and not self.write_tool_uses
        )


@dataclass
class ArtifactCheck:
    expected_artifacts: list[str]
    missing_artifacts: list[str]

    @property
    def passed(self) -> bool:
        return not self.missing_artifacts


@dataclass
class PatchCheck:
    patch_path: Path
    worktree_metadata_path: Path
    changed_files: list[str]
    forbidden_matches: list[str]
    out_of_scope_files: list[str]
    metadata_errors: list[str]
    patch_errors: list[str]

    @property
    def passed(self) -> bool:
        return (
            not self.forbidden_matches
            and not self.out_of_scope_files
            and not self.metadata_errors
            and not self.patch_errors
        )


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
    _validate_execution_mode(spec)
    _validate_file_patterns(spec["allowed_files"], "allowed_files")
    _validate_file_patterns(spec["forbidden_files"], "forbidden_files")
    for field in OPTIONAL_FILE_LIST_FIELDS:
        if field in spec:
            _validate_optional_file_list(spec, field)
    _validate_no_pattern_overlap(spec["allowed_files"], spec["forbidden_files"])
    if "read_scope" in spec:
        _validate_no_pattern_overlap(spec["read_scope"], spec["forbidden_files"])
    if "write_scope" in spec:
        _validate_no_pattern_overlap(spec["write_scope"], spec["forbidden_files"])
    if _execution_mode(spec) == "worktree_patch" and "write_scope" not in spec:
        raise ValueError("Field 'write_scope' is required when execution_mode is 'worktree_patch'")
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
        f"- Execution Mode: {_execution_mode(spec)}",
        "",
        "## Objective",
        "",
        spec["objective"].strip(),
        "",
        "## Allowed Files",
        "",
        *_bullet_lines(spec["allowed_files"]),
        "",
    ]

    if "read_scope" in spec:
        lines.extend([
            "## Read Scope",
            "",
            *_bullet_lines(spec["read_scope"]),
            "",
        ])

    if "write_scope" in spec:
        lines.extend([
            "## Write Scope",
            "",
            *_bullet_lines(spec["write_scope"]),
            "",
        ])

    if "expected_artifacts" in spec:
        lines.extend([
            "## Expected Artifacts",
            "",
            *_bullet_lines(spec["expected_artifacts"]),
            "",
        ])

    lines.extend([
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
    ])

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
    allowed = _scope_patterns(spec, "write_scope")
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


def check_run_tool_use(spec: dict[str, Any], run_dir: Path, workspace_path: Path) -> ToolUseCheck:
    validation = validate_task_spec(spec)
    spec = validation.spec
    workspace = workspace_path.resolve()
    raw_stdout_path = run_dir / "raw" / "stdout.txt"
    if not raw_stdout_path.exists():
        raise FileNotFoundError(f"Missing raw stdout artifact: {raw_stdout_path}")

    tool_uses = extract_tool_uses(raw_stdout_path.read_text(encoding="utf-8"))
    read_allowed = _scope_patterns(spec, "read_scope")
    write_allowed = _scope_patterns(spec, "write_scope")
    forbidden = [_normalize_pattern(item) for item in spec["forbidden_files"]]
    execution_mode = _execution_mode(spec)

    forbidden_matches: list[str] = []
    out_of_scope_paths: list[str] = []
    outside_workspace_paths: list[str] = []
    write_tool_uses: list[str] = []

    for tool_use in tool_uses:
        tool = str(tool_use.get("tool") or "")
        is_write_tool = tool.lower() in WRITE_TOOLS
        for raw_path in _tool_use_paths(tool_use):
            rel_path = _normalize_tool_path(raw_path, workspace)
            if not rel_path:
                outside_workspace_paths.append(raw_path)
                continue
            if _matches_any(rel_path, forbidden):
                forbidden_matches.append(rel_path)
            elif is_write_tool and not _matches_any(rel_path, write_allowed):
                out_of_scope_paths.append(rel_path)
            elif not is_write_tool and not _matches_any(rel_path, read_allowed):
                out_of_scope_paths.append(rel_path)
        if execution_mode == "report" and is_write_tool and not _tool_use_paths(tool_use):
            write_tool_uses.append(tool)

    return ToolUseCheck(
        tool_uses=tool_uses,
        forbidden_matches=sorted(set(forbidden_matches)),
        out_of_scope_paths=sorted(set(out_of_scope_paths)),
        outside_workspace_paths=sorted(set(outside_workspace_paths)),
        write_tool_uses=sorted(set(write_tool_uses)),
    )


def check_run_artifacts(spec: dict[str, Any], run_dir: Path) -> ArtifactCheck:
    validation = validate_task_spec(spec)
    spec = validation.spec
    expected = _expected_artifacts(spec)
    missing = [artifact for artifact in expected if not (run_dir / artifact).exists()]
    return ArtifactCheck(expected_artifacts=expected, missing_artifacts=missing)


def check_run_patch(spec: dict[str, Any], run_dir: Path) -> PatchCheck:
    validation = validate_task_spec(spec)
    spec = validation.spec
    patch_path = run_dir / "patch.diff"
    metadata_path = run_dir / "worktree.json"
    forbidden = [_normalize_pattern(item) for item in spec["forbidden_files"]]
    allowed = _scope_patterns(spec, "write_scope")

    metadata_errors = _validate_worktree_metadata(metadata_path, run_dir.name)
    patch_errors: list[str] = []
    changed_files: list[str] = []

    if not patch_path.exists():
        patch_errors.append("Missing patch.diff")
    elif not patch_path.is_file():
        patch_errors.append("patch.diff is not a file")
    else:
        try:
            changed_files = _extract_patch_changed_files(patch_path.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            patch_errors.append(f"Failed to parse patch.diff: {exc}")
        if not changed_files:
            patch_errors.append("patch.diff contains no changed files")

    forbidden_matches: list[str] = []
    out_of_scope_files: list[str] = []
    for changed_file in changed_files:
        if _matches_any(changed_file, forbidden):
            forbidden_matches.append(changed_file)
        elif not _matches_any(changed_file, allowed):
            out_of_scope_files.append(changed_file)

    return PatchCheck(
        patch_path=patch_path,
        worktree_metadata_path=metadata_path,
        changed_files=sorted(set(changed_files)),
        forbidden_matches=sorted(set(forbidden_matches)),
        out_of_scope_files=sorted(set(out_of_scope_files)),
        metadata_errors=metadata_errors,
        patch_errors=patch_errors,
    )


def extract_tool_uses(raw_stdout: str) -> list[dict[str, Any]]:
    tool_uses: list[dict[str, Any]] = []
    for line in raw_stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except json.JSONDecodeError:
            continue
        tool_uses.extend(_extract_tool_uses_from_frame(frame))
    return tool_uses


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


def _extract_tool_uses_from_frame(frame: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if frame.get("type") == "tool_use":
        normalized = _normalize_tool_use_frame(frame)
        if normalized:
            found.append(normalized)

    data = frame.get("data")
    if isinstance(data, dict):
        for artifact in data.get("artifacts", []) or []:
            if not isinstance(artifact, dict):
                continue
            if artifact.get("kind") == "tool_use_summary":
                found.extend(_extract_tool_uses_from_summary_artifact(artifact))
                continue
            if artifact.get("kind") != "stdout_preview":
                continue
            text = artifact.get("text")
            if isinstance(text, str):
                found.extend(extract_tool_uses(text))
    return found


def _extract_tool_uses_from_summary_artifact(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    items = artifact.get("items")
    if not isinstance(items, list):
        return []
    found: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        paths = item.get("paths")
        if not isinstance(paths, list):
            paths = []
        clean_paths = [path for path in paths if isinstance(path, str) and path.strip()]
        input_data: dict[str, Any] = {}
        if clean_paths:
            input_data["filePath"] = clean_paths[0]
            input_data["paths"] = clean_paths
        found.append(
            {
                "tool": item.get("tool") or "",
                "status": item.get("status") or "",
                "input": input_data,
            }
        )
    return found


def _normalize_tool_use_frame(frame: dict[str, Any]) -> dict[str, Any]:
    part = frame.get("part")
    if not isinstance(part, dict):
        return {}
    state = part.get("state")
    if not isinstance(state, dict):
        state = {}
    input_data = state.get("input")
    if not isinstance(input_data, dict):
        input_data = {}
    return {
        "tool": part.get("tool") or frame.get("tool") or "",
        "status": state.get("status") or "",
        "input": input_data,
    }


def _tool_use_paths(tool_use: dict[str, Any]) -> list[str]:
    input_data = tool_use.get("input")
    if not isinstance(input_data, dict):
        return []
    paths: list[str] = []
    for key in ("filePath", "filepath", "path", "target_file", "targetPath"):
        value = input_data.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    value = input_data.get("paths")
    if isinstance(value, list):
        paths.extend(item.strip() for item in value if isinstance(item, str) and item.strip())
    return paths


def _normalize_tool_path(raw_path: str, workspace: Path) -> str:
    try:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = workspace / candidate
        resolved = candidate.resolve()
        rel = resolved.relative_to(workspace)
    except Exception:
        return ""
    return _normalize_pattern(rel.as_posix())


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


def _validate_optional_file_list(spec: dict[str, Any], field: str) -> None:
    value = spec[field]
    if not isinstance(value, list) or not value:
        raise ValueError(f"Field '{field}' must be a non-empty list when present")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Field '{field}' item {index} must be a non-empty string")
    _validate_file_patterns(value, field)


def _validate_schema_version(spec: dict[str, Any]) -> None:
    if spec["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"Invalid schema_version '{spec['schema_version']}'. Expected '{SCHEMA_VERSION}'"
        )


def _validate_execution_mode(spec: dict[str, Any]) -> None:
    mode = spec.get("execution_mode", DEFAULT_EXECUTION_MODE)
    if not isinstance(mode, str) or not mode.strip():
        raise ValueError("Field 'execution_mode' must be a non-empty string when present")
    if mode.strip() not in EXECUTION_MODES:
        raise ValueError(
            f"Invalid execution_mode '{mode}'. Expected one of: {sorted(EXECUTION_MODES)}"
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

    if "write_scope" in spec:
        write_scope = {_normalize_pattern(item) for item in spec["write_scope"]}
        if _normalize_pattern("docs/plan/agent_bridge_mvp.md") in write_scope:
            warnings.append("Canonical plan should not be in write_scope unless explicitly requested")

    for rule in REQUIRED_HARD_RULES:
        if rule.lower() not in hard_rules:
            warnings.append(f"Recommended hard rule missing: {rule}")

    return warnings


def _normalize_pattern(pattern: str) -> str:
    return pattern.strip().replace("\\", "/").strip("/")


def _scope_patterns(spec: dict[str, Any], field: str) -> list[str]:
    values = spec.get(field)
    if not isinstance(values, list) or not values:
        values = spec["allowed_files"]
    return [_normalize_pattern(item) for item in values]


def _expected_artifacts(spec: dict[str, Any]) -> list[str]:
    values = spec.get("expected_artifacts")
    if not isinstance(values, list) or not values:
        values = DEFAULT_EXPECTED_ARTIFACTS
    expected = [_normalize_pattern(item) for item in values]
    if _execution_mode(spec) == "worktree_patch":
        for artifact in WORKTREE_PATCH_ARTIFACTS:
            if artifact not in expected:
                expected.append(artifact)
    return expected


def _execution_mode(spec: dict[str, Any]) -> str:
    value = spec.get("execution_mode", DEFAULT_EXECUTION_MODE)
    return str(value).strip() or DEFAULT_EXECUTION_MODE


def _validate_worktree_metadata(path: Path, run_id: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return ["Missing worktree.json"]
    if not path.is_file():
        return ["worktree.json is not a file"]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [f"worktree.json is not valid JSON: {exc}"]
    if not isinstance(data, dict):
        return ["worktree.json must contain a JSON object"]

    required = ["schema_version", "run_id", "repo_root", "worktree_path", "base_ref", "base_sha"]
    for field in required:
        if not isinstance(data.get(field), str) or not str(data.get(field)).strip():
            errors.append(f"worktree.json missing non-empty string field: {field}")
    if data.get("schema_version") != "worktree.v0":
        errors.append("worktree.json schema_version must be 'worktree.v0'")
    if data.get("run_id") != run_id:
        errors.append(f"worktree.json run_id does not match run directory: {data.get('run_id')} != {run_id}")
    return errors


def _extract_patch_changed_files(patch_text: str) -> list[str]:
    changed: set[str] = set()
    for line in patch_text.splitlines():
        path = ""
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                path = _patch_path_to_repo_path(parts[3])
        elif line.startswith("+++ "):
            value = line[4:].strip()
            if value != "/dev/null":
                path = _patch_path_to_repo_path(value)
        if path:
            changed.add(path)
    return sorted(changed)


def _patch_path_to_repo_path(path: str) -> str:
    path = path.strip().strip('"')
    if path.startswith("a/") or path.startswith("b/"):
        path = path[2:]
    return _normalize_pattern(path)


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
