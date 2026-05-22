리뷰 의견
1. Task Gate Artifact Check vs Run Contract
현재 run contract는 patch.diff와 worktree.json을 전혀 요구하지 않습니다.
DEFAULT_EXPECTED_ARTIFACTS(task_spec.py:35-48)에는 12개 artifact만 있고, worktree.json과 patch.diff는 없습니다. 또한 agent-bridge run CLI 명령어에는 아예 worktree wiring이 없습니다. Worktree helper 함수들은 worktrees.py에 구현되어 있지만, 누군가 직접 호출하지 않는 한 사용되지 않습니다.
즉, 현재 gate는 write-capable run을 제대로 검증할 수 없는 상태입니다.
- Task gate: artifact 존재 여부 확인하지만, patch.diff/worktree.json이 없어도 통과
- Result gate (check-result): 아예 active workspace의 git status를 체크함 → worktree에서 실행했다면 엉뚱한 workspace를 검사하는 꼴
2. 누락된 Failure Mode
누락된 항목	영향
Worktree 미적용 상태로 write-capable run 허용	gate를 통과했지만 실제로 write하지 않았거나, 작업물이 증발할 수 있음
patch.diff/worktree.json 미생성 시 조용한 실패	artifact gate는 기본적으로 이것들을 요구하지 않음
Tool-use checker가 OpenCode 전용	다른 adapter(Antigravity, raw API)는 검증되지 않음
Result gate가 worktree diff가 아닌 active workspace git status 검사	worktree run에서 잘못된 결과 보고
No timeout propagation	bridge-level timeout과 adapter-level timeout 불일치 가능
Adapter stdout preview truncation(12KB)	tool_use_summary가 없는 adapter에서 violation 누락 가능
Benchmark verdict 비체계적 저장	.agent/benchmarks/ 없음, process log에만 기록
Dirty workspace baseline 정책 부재	check-result가 사용자의 미관련 변경사항을 위반으로 오탐 가능
3. Write-Capable Worktree에서 patch.diff / worktree.json 요구 방식
제 의견은 다음과 같습니다:
A. run contract 수준에서 요구해야 함
DEFAULT_EXPECTED_ARTIFACTS에 조건부로 patch.diff / worktree.json을 추가하는 것이 아니라, write-capable mode라는 개념 자체를 run contract에 도입해야 합니다. 예:
mode: "readonly" | "write_capable"
- readonly → 현재 artifact set 유지
- write_capable → patch.diff + worktree.json을 필수 artifact로 요구, gate에서 강제 검증
B. task spec에 mode 필드 추가
현재 task spec(.toml)에는 write-capable 여부를 명시하는 필드가 없습니다. mode = "worktree" 혹은 worktree = true 같은 필드를 도입해서:
1. agent-bridge run이 자동으로 worktree를 생성하고, 그 안에서 agent를 실행
2. 실행 완료 후 자동으로 patch.diff + worktree.json export
3. Task gate가 mode에 따라 다른 artifact set 검사
C. Result gate는 worktree diff를 기준으로 검증해야 함
현재 check-result는 active_workspace의 git status를 검사하는데, worktree mode에서는:
- Worktree 내부의 collect_worktree_changed_files() 결과로 대체
- patch.diff 내용을 파싱하여 write_scope/forbidden_files 위반 확인
D. patch.diff 검증 추가
게이트는 patch.diff에 대해:
- 빈 파일이어도 괜찮음 (읽기만 한 경우)
- binary-safe한지 (--binary flag 사용했는지)
- untracked files가 포함되었는지
- 크기가 적정한지 (비정상적으로 크면 경고)
를 검증해야 합니다.
요약
지금 당장 가장 큰 문제는 "worktree 기능이 구현되어 있지만, run lifecycle과 gate에 전혀 통합되지 않았다"는 것입니다. Worktree helper 함수들은 127라인의 독립된 유틸리티로 존재할 뿐, agent-bridge run CLI, task gate, result gate 그 어디에도 연결되지 않았습니다. 이 상태에서 task gate artifact check는 write-capable run에 대해 무의미합니다 — patch.diff 없이도 "PASS"가 나오기 때문입니다.
수정 방향:
1. worktree: bool 필드를 task spec에 추가
2. agent-bridge run이 worktree=true일 때 자동으로 worktree 생성/실행/정리
3. DEFAULT_EXPECTED_ARTIFACTS 대신 mode-aware artifact validation 도입
4. Task gate가 mode별로 다른 artifact set 검사
5. Result gate가 active workspace 대신 worktree diff 기준 검사
도움이 되셨길 바랍니다. 더 깊이 보고 싶은 부분이 있다면 말씀해주세요.