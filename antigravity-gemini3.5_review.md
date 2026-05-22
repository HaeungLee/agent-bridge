# Read-Only Review: Task Gate Artifact Check & Write-Capable Worktree Integration
**Model**: Gemini 3.5 Flash (Antigravity)  
**Date**: 2026-05-22  
**Target Project**: Agent Bridge (`w:\Projects\agent-bridge`)  

본 검토 보고서는 `agent-bridge` 컨트롤 플레인 내에서 **Task Gate Artifact Check**가 현재 설계된 **Run Contract**와 정합성을 이루는지 진단하고, Isolated Worktree Execution 도입 시 발생 가능한 **누락된 실패 모드(Failure Modes)**를 정의하며, Write-Capable 에이전트 실행 환경에서 `patch.diff`와 `worktree.json`을 강제화하고 검증하기 위한 구체적인 요구사항 및 설계 방향을 제시합니다.

---

## 1. Task Gate Artifact Check vs. Current Run Contract

현재 `agent-bridge`가 구현하고 있는 검증 메커니즘과 설계 사양을 분석한 결과, **Task Gate**와 **Run Contract** 사이에는 심각한 기능적 불일치(Mismatch)와 공백이 존재합니다.

### A. Run Contract와 `DEFAULT_EXPECTED_ARTIFACTS` 간의 괴리
* **현재 구현**: `src/agent_bridge/task_spec.py` 파일의 35-48라인에는 12가지 필수 아티팩트(`summary.md`, `decision_report.json`, `diffstat.txt`, `touched_files.json`, `tests.md`, `risks.md`, `process.md`, `metrics.json`, `request.json`, `completed.marker`, `raw/stdout.txt`, `raw/stderr.txt`)가 `DEFAULT_EXPECTED_ARTIFACTS`로 정의되어 있습니다.
* **불일치점**: 이 목록에는 isolated worktree 연산 결과로 당연히 생성되어야 하는 `patch.diff`와 `worktree.json`이 **전혀 포함되어 있지 않습니다**. 
* **결과**: `agent-bridge task gate`를 실행할 때, 에이전트가 Write-Capable 모드로 실행되었음에도 불구하고 `patch.diff`나 `worktree.json`이 누락된 상태에서 게이트가 무조건 **"PASS"** 판정을 내리는 구조적인 허점이 발생합니다.

### B. `agent-bridge run` CLI와 Worktree 기능의 유기적 연동 결여
* **현재 구현**: `src/agent_bridge/worktrees.py`에는 `create_isolated_worktree` 등 훌륭한 격리 연산 유틸리티들이 128라인에 걸쳐 완비되어 있습니다. 
* **불일치점**: 하지만 정작 에이전트 런타임을 오케스트레이션하는 `src/agent_bridge/runs.py`와 `src/agent_bridge/cli.py`는 **이 worktree 모듈을 전혀 호출하거나 연동하고 있지 않습니다**. `agent-bridge run` 명령은 오로지 mock_subprocess나 cli_adapter를 활성 작업 트리(Active Workspace) 또는 단순 서브프로세스로 바로 실행해버립니다.
* **결과**: 현재의 런 구조에서는 격리 환경(Isolated Worktree) 내에서의 코드 수정과 패치 추출 흐름이 CLI의 전체 라이프사이클에 자연스럽게 흡수되지 못한 단절된 상태입니다.

---

## 2. 누락된 Failure Mode (실패 모드) 분석

`docs/worktree_execution_v0.md`에 기술된 기본적인 예외 상황 외에도, 실제 다중 에이전트(Multi-agent) 런 및 실전 통합(Write-Capable Production Run) 환경에서 발생할 수 있는 치명적인 **누락된 실패 모드**는 다음과 같습니다.

| 누락된 실패 모드 | 발생 시나리오 | 미치는 영향 및 위험성 |
| :--- | :--- | :--- |
| **Worktree Cleanup 실패 및 누출 (Orphan Worktrees)** | 에이전트 실행 중에 강제 종료(SIGINT/SIGTERM), OOM(Memory), 혹은 런타임 타임아웃 발생 시 제거 훅(`remove_isolated_worktree`)이 미호출됨 | 시스템 임시 폴더에 고아 git worktree가 잔존하여 디스크를 잠식하고, 이후 동일 run_id로 런을 재시도할 때 git refs 충돌 또는 디렉토리 충돌 유발 |
| **Dirty Active Workspace 간섭 및 컨텍스트 유실** | 사용자가 활성 작업 트리(Active Workspace)에서 커밋하지 않은 로컬 변경 사항(staged, unstaged)이 있는 상태로 `HEAD` 기반 worktree를 생성함 | 사용자의 최신 로컬 코드가 배제된 채 과거 커밋된 `HEAD` 기준으로 에이전트가 실행되므로, 에이전트가 사용자의 최근 의도를 파악하지 못해 엉뚱한 결론을 도출하거나 빌드 실패 |
| **Git Index Lock 경합 및 데드락** | 에이전트가 백그라운드 런으로 여러 개 병렬 실행 중이거나, 사용자가 동시에 CLI 연산을 할 때 `.git/index.lock` 파일이 잠김 | `git worktree add` 및 `git add -A` 등의 파일 추가/스테이징 연산이 즉각 실패하며 전체 런이 `BLOCKED` 상태로 중단됨 |
| **바이너리/개행문자 변환 오류로 인한 패치 훼손** | 에이전트가 바이너리 파일을 수정하거나 플랫폼 전용 개행문자(LF vs CRLF) 또는 UTF-8이 아닌 파일을 생성했을 때 바이너리 세이프하지 않은 diff가 수행됨 | `patch.diff` 파일이 훼손(corrupt)되거나 유실되어, 사후에 커맨더가 패치를 검토하고 활성 트리에 병합할 때 패치 어플리케이션(`git apply`) 실패 |
| **`check-result` 및 `check-tool-use` 오탐 (False Positives)** | `check-result`가 여전히 활성 작업 트리의 `git status`를 조회해 변경 파일을 수집하도록 설계됨 | 에이전트가 isolated worktree 내에서 안전하게 변경을 마쳤더라도 활성 트리가 정상이면 변경 없음(Empty)으로 판정되거나, 사용자가 수동 편집해 둔 무관한 파일 때문에 오탐으로 에이전트의 런을 실패 처리 |

---

## 3. Write-Capable Worktree에서 `patch.diff` / `worktree.json` 요구 및 검증 방안

격리된 작업 공간(Write-Capable Worktree) 환경에서 무결성을 입증하기 위해, `patch.diff`와 `worktree.json`을 정식 **런 계약(Run Contract)**의 일환으로 요구하고 엄격히 검증하는 구체적인 방안입니다.

### A. Task Spec에 실행 모드(`mode`) 속성 추가
* `task_spec.v0` TOML 스펙에 에이전트의 동작 성격을 규정하는 `execution_mode` 필드를 도입합니다.
  ```toml
  # 예시: task_spec.v0
  schema_version = "task_spec.v0"
  task_id = "task_001"
  ...
  execution_mode = "write_capable" # "readonly" (기본값) | "write_capable"
  ```
* `execution_mode = "write_capable"`일 경우, `task_spec.py` 내부에서 이를 감지하여 `DEFAULT_EXPECTED_ARTIFACTS`에 **`patch.diff`와 `worktree.json`을 동적으로 필수 아티팩트 목록으로 추가**합니다.

### B. Task Gate 단계에서의 정밀 정적 검증 프로세스
단순히 파일이 디스크에 존재하는지를 검사하는 `check_run_artifacts`를 넘어, `task gate` 수행 시 다음 두 가지 파일의 **정합성(Semantic Integrity)**을 함께 입증해야 합니다.

1. **`worktree.json` 메타데이터 무결성 검증**
   * JSON 파싱을 통해 `run_id`, `repo_root`, `base_sha` 값을 추출합니다.
   * `run_id`가 현재 수명 주기의 `run_id`와 정확히 일치하는지 확인합니다.
   * 기록된 `base_sha`가 실제 런이 기동될 당시의 부모 Git 커밋 SHA와 완벽히 대조되는지 검증합니다.

2. **`patch.diff` 정적 분석 및 Scope Validation 연계**
   * `patch.diff` 파일이 존재할 경우, 이를 라인 단위로 파싱하여 수정/추가/삭제된 파일 경로 목록을 직접 추출합니다.
   * 추출한 모든 경로가 task spec에 등록된 `write_scope` (또는 `allowed_files`)의 화이트리스트 규칙 내에 철저히 존재하는지 검사합니다.
   * 만약 `write_scope` 범위를 벗어난 경로가 diff 헤더(`--- a/...` 또는 `+++ b/...`)에서 발견된다면, 즉각 `task gate`를 rejected(`FAIL`) 처리합니다.

### C. `check-result` 및 `check-tool-use` 로직의 Worktree-Aware 재설계
* **`check-result`**: `collect_git_changed_files(workspace_path)` 대신, `worktree.json`을 읽어 에이전트가 격리되어 작업했던 `worktree_path` 내부의 `collect_worktree_changed_files(info)` 결과 또는 `patch.diff` 자체의 내용을 입력 소스로 대체하여 변경 사항을 비교하도록 대대적으로 변경합니다.
* **`check-tool-use`**: 에이전트가 API나 CLI를 통해 수행한 도구 사용의 타겟 경로를 추적할 때, active workspace 기준의 절대 경로를 격리된 `worktree_path`로 리맵핑하여 분석한 후 상대 경로화하여 scope 위반 여부를 가려내야 합니다.

---

## 4. 구체적인 설계 변경 권고 (Action Items)

1. **`contracts.py` 고도화**:
   * `DecisionReport` 내에 `execution_mode`가 저장되도록 스키마를 동기화하고, `tests` 결과와 더불어 `patch.diff` 생성 여부를 요약 필드에 기재할 것을 강력히 권고합니다.
2. **`cli.py` & `runs.py` 오케스트레이션 연동**:
   * `agent-bridge run` 시 에이전트 설정(config)과 task spec의 실행 모드가 `write_capable`인 경우, `runs.py` 내부에서 자동으로 `worktrees.py`를 활용해 격리 디렉토리를 생성하게 설계합니다.
   * 실행 완료 혹은 오류 발생 시에 **안전한 cleanup 블록(`try-finally`)**을 보장하여 임시 worktree를 강제 파괴하고, 변경된 파일들을 바탕으로 `patch.diff`를 자동으로 빌드 및 검증하여 `.agent/runs/<run_id>/`에 안전하게 배치하도록 코드를 조율해야 합니다.
