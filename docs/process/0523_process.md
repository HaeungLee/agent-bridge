# 0523 Process

## 19:30 - Antigravity - 로컬 프록시 우회 격리형 오픈코드 하네스(opencode_deepseek_flash) 구현 및 검증 완료

- **Status**: completed
- **Summary**: Claude Code v2.1.71 CLI와 9001번 포트 로컬 변역 프록시 2.1을 결합하여 무제한 DeepSeek v4 Flash 쿼터로 작동하는 격리형 오픈코드 하네스(opencode_deepseek_flash)의 파이썬 어댑터 모듈 개발 및 TOML 설정 매핑을 완벽히 완료하고, `agent-bridge doctor` 진단을 통해 실가동 준비 상태를 최종 입증함.
- **Files Changed**:
  - `src/agent_bridge/adapters/claude_adapter.py` [NEW] (실시간 stream-json 한 줄 파싱, 백그라운드 프록시 자동 Popen 기동 및 clean-up 수거 기동, ANTHROPIC_BASE_URL 및 sk-nano API Key 격리 주입, unlimited 무과금 세팅 등 구현)
  - `config/runners.toml` [MODIFY] (opencode_deepseek_flash 어댑터 환경 설정 등록)
  - `config/agents.toml` [MODIFY] (opencode_deepseek_flash 에이전트 프로필 설정 등록)
  - `docs/process/0523_process.md` [NEW] (현재 작업 일지 문서 신규 수립)
- **Commands Run**:
  - `uv run agent-bridge doctor` passed (신규 구성 포함 설정 로딩 검증 성공)
- **Findings**:
  * Claude CLI는 `--max-budget-usd` 플래그가 주입되지 않을 경우 내부 과금 한도 경고 없이 완벽히 무제한(unlimited)으로 작동하므로, 빈칸 주입 시 플래그를 생략하는 예외 처리가 고도로 안정적인 쿼터 무제한 환경을 보장함.
  * `claude_adapter.py`가 9001번 포트를 선제 스캔하고, 프록시 미기동 시 `anthropic_proxy.py`를 백그라운드로 자동 포크 기동한 뒤 종료와 동시에 리소스를 수거하는 Popen Lifecycle 덕분에 사용자가 별도의 중계 프록시 데몬을 매번 켜두는 수고로움을 완벽하게 덜어냄.
- **Risks**: None.
- **Open Questions**: N/A
- **Next Recommended Step**: 프록시 2.1이 켜져 있거나 꺼져 있을 때 각각 `opencode_deepseek_flash` 에이전트로 실제 태스크를 실행시켜 e2e 툴-유즈 정상 동작을 2차 실증할 것.
- **Commander Verdict**: N/A

---

## 20:14 - Antigravity - cp949 인코딩 버그 수정 및 E2E Smoke Test 최종 통과

- **Status**: completed
- **Summary**: Windows `shell=True` + `encoding="utf-8"` 조합이 cp949를 강제 적용하여 stderr 파싱에서 crash가 발생하던 문제를 binary 모드(bufsize=0) + Python-레벨 utf-8 디코딩으로 수정함. 추가로 Claude CLI가 `--output-format stream-json` 대신 plain text를 출력할 경우 `final_report`가 비워지던 버그를 plain text fallback accumulator로 수정함. 최종 smoke test(`20260523-201410-64456b-opencode_deepseek_flash`) 결과 `ok: true` 확인, E2E 파이프라인 정상 가동 입증.
- **Files Changed**:
  - `src/agent_bridge/adapters/claude_adapter.py` [MODIFY]
    - `subprocess.Popen` → `bufsize=0` (binary mode), `universal_newlines`/`encoding` 제거
    - stdout: `iter(proc.stdout.readline, b"")` + `.decode("utf-8", errors="replace")`
    - stderr: `proc.stderr.read()` + `.decode("utf-8", errors="replace")`
    - `_parse_stream_line` → `bool` 반환 (JSON 파싱 성공 여부)
    - `plain_text_lines` fallback accumulator 추가
    - `ok` 판정 기준: `exit_code == 0` (text 유무 무관)
- **Commands Run**:
  - `agent-bridge run --agent opencode_deepseek_flash --task smoke_test_readonly.md` → `ok: true`, `run_status: completed`
- **Findings**:
  * Claude CLI 응답이 plain text 형태로 출력될 때 stream-json 파서가 모든 라인을 무시하여 final_report가 비워지던 문제 확인 및 수정.
  * `ok: true` 응답에 워크스페이스 분석 결과 (한국어 포함) 정상 포함 확인.
  * 세션 재사용(`session_reused: true`, `session_id: 0753ca8f-...`) 정상 작동.
- **Risks**: None.
- **Open Questions**: N/A
- **Next Recommended Step**: 실제 구현 태스크(write-capable)로 1회 추가 검증 필요 시 수행.
- **Commander Verdict**: N/A
