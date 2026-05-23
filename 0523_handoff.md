# 0523 Handoff: Anthropic-to-nanoGPT Proxy 2.1 & Claude Code Integration SPEC

본 문서는 `Claude Code v2.1.71` CLI와 `nanoGPT (DeepSeek v4 Pro/Flash)` API 간의 완벽한 E2E E2E 툴-유즈(Tool-use) 연동을 완성한 로컬 중계 프록시 2.1의 설계 아키텍처와, 이를 우리 `agent-bridge` 프로젝트의 OpenCode 하네스에 안전하고 영리하게 통합하기 위한 차기 세션 에이전트용 설계 핸드오프 명세입니다.

---

## 1. E2E 연동 현재 상황 & 성과 요약

- **현상**: 오리지널 Claude Code CLI는 Anthropic 계정 밴(Ban) 위험성과 비싼 가격 부담이 존재하나, Grep/Read/Edit/Write/Bash 등 파일 시스템 및 셸 실행을 넘나드는 에이전트 자가 치유 능력이 현존 최강 수준입니다.
- **해결책**:
  * 사용자의 Anthropic 본계정 이메일 결합을 CLI 내에서 완벽하게 로그아웃(`Auth token: none`)하여 안전하게 격리시켰습니다.
  * 외부 라이브러리 의존성 없이 파이썬 내장 라이브러리만으로 기동되는 **로컬 번역 프록시 2.1(포트 9001)**을 띄우고, 클라이언트 환경 변수 `ANTHROPIC_BASE_URL="http://localhost:9001/v1"`를 지정해 모든 Messages API 요청을 가로챘습니다.
  * 가로챈 요청은 nanoGPT의 `deepseek-v4-pro` 및 `deepseek-v4-flash` API 호출로 실시간 변환/중계하고, 수신된 OpenAI 스트림 패킷을 Anthropic SSE 스펙에 맞춰 실시간으로 역번역하여 제공합니다.
- **결과**: 브라우저 OAuth 로그인 팝업을 원천 우회(Skip)하고, CLI 내부에서 nanoGPT의 무제한 쿼터로 `Gitifying...` 인덱싱 및 다중 도구 호출(`Bash`, `Glob`, `Read`) 대화 루프가 끊김 없이 무정체로 흐르도록 E2E 연동을 실증하는 데 완벽히 성공했습니다.

---

## 2. 로컬 중계 프록시 2.1 핵심 설계 및 메커니즘

프록시 소스 코드 파일: `C:\Users\Harry\.gemini\antigravity\brain\c9448787-ac07-4f65-bb83-5eda99069412\scratch\anthropic_proxy.py`

### 2.1 Contiguous 0-Indexed Sequential Stream Mapping (중요)
- **문제점**: 텍스트 대답 없이 모델이 즉시 도구 호출(`tool_calls`)만 3개 연달아 쏘는 경우, 프록시가 텍스트 블록(index 0)을 생략한 채 `index 1`, `index 2`로 `content_block_start`를 전송하면 인덱스에 공백(gap)이 발생합니다. 이 경우 Node.js 기반의 Claude CLI 스트림 레이어에서 파싱 예외가 터져 무한 멈춤(`Whirlpooling...`, `Zesting...`) 상태에 빠집니다.
- **해결책 (2.1)**: 스트림에서 텍스트가 먼저 오든 도구가 먼저 오든 상관없이, 프록시 단에서 새로운 블록이 처음 빌드될 때마다 **순차적 누적 카운터(`next_anthropic_index = 0, 1, 2...`)**를 동적으로 바인딩하여 Anthropic CLI에 무조건 Contiguous(연속적인) 인덱스를 보장하도록 설계했습니다.
  ```python
  # 텍스트 또는 도구 사용 시작 시마다 next_anthropic_index를 동적으로 할당하고 1씩 가산
  if text_block_index is None:
      text_block_index = next_anthropic_index
      next_anthropic_index += 1
  ```

### 2.2 Connection Close 강제 물리 결속 해제
- **문제점**: HTTP `Connection: keep-alive` 헤더 설정 시, 스트림 송신이 완료(`[DONE]`)되어 `message_stop` 이벤트를 정상 전송했음에도 소켓이 닫히지 않아 CLI가 응답 대기 상태에서 해제되지 않고 멈춰 있었습니다.
- **해결책 (2.1)**: 스트리밍 및 일반 JSON 전송 헤더에 명시적으로 `Connection: close`를 내려주고, 프록시 내부적으로 SSE 전송이 끝나는 시점에 `self.close_connection = True` 플래그를 설정하여 소켓을 즉시 닫아 클라이언트의 대기를 강제 해제합니다.

### 2.3 OpenAI Strict Sequence Auto-Recovery (자가 치유 메시지 정렬)
- **문제점**: OpenAI / nanoGPT API는 assistant의 `tool_calls` 메시지가 나타난 직후, **반드시** 해당 `tool_calls`의 `id`와 정확히 일치하는 `role: "tool"` 메시지들이 연달아 수록되어야 하는 극단적으로 엄격한 정렬 제약(Constraint Validation)이 있습니다. 만약 히스토리 관리 상 이 순서가 깨지면 즉각 400 Bad Request 에러나 API 행(Hang)이 유발됩니다.
- **해결책 (2.1)**: 누적 대화 기록 번역 시, user의 `tool_result`들이 수집되었는데 바로 직전 메시지가 해당 `id`를 가진 assistant `tool_calls`가 아닌 경우, 프록시가 내부적으로 **더미 `tool_calls`를 포함한 가상 assistant 메시지를 동적으로 자동 조립/주입**하여 E2E 파이프라인의 불통을 완전히 방어했습니다.
  ```python
  if not has_preceding_assistant_call:
      # virtual assistant message with dummy functions auto-injection
      virtual_calls = [{"id": tr["tool_call_id"], "type": "function", ...}]
      openai_messages.append({"role": "assistant", "tool_calls": virtual_calls})
  ```

### 2.4 Defensive tool_result Pre-formatting
- **해결책 (2.1)**: `tool_result`가 실패(`is_error=True`)했거나 빈 값으로 들어오는 경우, 빈 문자열로 인해 OpenAI 검증 필터에서 거절당하는 것을 방지하기 위해 `"Error: Tool execution failed with empty response."` 등 안전한 디폴트 문자열로 치환하여 전송 정합성을 지켜냅니다.

---

## 3. 로컬 샌드박스 구동 환경 설정

현재 로컬 샌드박스는 사용자의 OAuth 로그인 씬을 완벽하게 스킵하고 anonymous API 빌링 모드로 기동하기 위해 다음과 같이 구성되어 있습니다.

1. **설정 파일 (`C:\Users\Harry\.claude\settings.json`)**
   ```json
   {
     "apiKeyHelper": "powershell -NoProfile -Command \"[Console]::Write($Env:ANTHROPIC_API_KEY)\""
   }
   ```
   * 이 `apiKeyHelper` 설정 덕분에 브라우저 로그인 요구를 원천 패스하고, 셸 환경 변수의 API Key를 읽어 가동됩니다.
2. **필수 기동 환경 변수**
   ```powershell
   $env:ANTHROPIC_BASE_URL="http://localhost:9001/v1"
   $env:ANTHROPIC_API_KEY="sk-nano-..." # W:\Projects\agent-bridge\.env에 있는 nanoGPT API Key 사용
   $env:ANTHROPIC_DEFAULT_SONNET_MODEL="deepseek/deepseek-v4-flash" # 또는 deepseek/deepseek-v4-pro
   ```

---

## 4. `agent-bridge` 프로젝트 내 OpenCode 에이전트 통합 설계 SPEC (중요)

새로운 세션의 에이전트는 기존의 수동적이고 단순한 공식 API 호출 설계를 즉각 기각하고, 로컬 프록시 우회를 내장한 **진짜 고성능 OpenCode 통합 하네스**를 아래 명세에 맞춰 설계 및 구현해야 합니다.

### 4.1 수동적 설계의 한계 극복
이전 에이전트는 아래와 같이 설계해 버렸습니다:
```toml
[agents.claude_readonly]
runner = "cli_adapter"
provider = "anthropic"
model = "claude-opus" # ◀ 오류! 로컬 프록시와 nanoGPT를 무시하고 비싼 공식 API와 구형 모델 명시
```
이 방식은 로컬 프록시의 nanoGPT 결합 메커니즘을 완전히 활용하지 못하며 계정 밴 위험에 무방비로 노출됩니다.

### 4.2 올바른 OpenCode TOML 설정 명세
로컬 프록시 2.1 및 Claude Code v2.1.71 CLI 기반의 격리형 샌드박스 실행을 위해 `agent-bridge` 에이전트 프로필을 다음과 같이 재설계해야 합니다.

```toml
# docs/plan/roadmap.md 또는 config/agents.toml 구성 시 아래 설계 준수

[agents.opencode_deepseek_flash]
runner = "cli_adapter"
provider = "anthropic"            # CLI가 Anthropic 클라이언트로 동작하므로 anthropic 명시
model = "deepseek/deepseek-v4-flash" # 실질적인 구동 모델은 nanoGPT의 deepseek-v4-flash 지정
role = "implementation"
default_mode = "execute"          # 파일 쓰기 및 셸 실행을 허용하는 모드
max_cost_usd = 1.0                # nanoGPT 쿼터이므로 실질 비용은 매우 낮음
output_contract = "adapter.v0.1"
adapter_id = "opencode_sandbox"

[agents.opencode_deepseek_flash.env]
# 하네스가 CLI 구동 시 자동으로 로컬 프록시 엔드포인트와 API Key를 주입하도록 구성
ANTHROPIC_BASE_URL = "http://localhost:9001/v1"
ANTHROPIC_API_KEY = "sk-nano-..." # .env에서 로드된 nanoGPT 키 자동 주입
ANTHROPIC_DEFAULT_SONNET_MODEL = "deepseek/deepseek-v4-flash"
```

### 4.3 통합 실행 라이프사이클 설계 가이드
차기 세션에서 하네스/어댑터(`src/agent_bridge/cli_adapter.py` 또는 신규 어댑터)를 개발할 때 반드시 고려해야 할 라이프사이클은 다음과 같습니다:

1. **프록시 자동 가동 (Proxy Lifecycle Daemon)**
   * `agent-bridge run --agent opencode_deepseek_flash` 실행 시, 어댑터는 백그라운드에서 포트 9001에 로컬 프록시 서버(`anthropic_proxy.py`)가 켜져 있는지 감지합니다.
   * 만약 프록시가 꺼져 있다면, 어댑터가 내부적으로 `subprocess.Popen`을 통해 백그라운드 데몬으로 프록시 서버 스크립트를 즉시 자동 기동(Self-Hosting)해야 합니다.
2. **샌드박스 셸 주입 및 실행**
   * 그 후 환경 변수(`ANTHROPIC_BASE_URL`, `apiKeyHelper` 설정)를 격리 주입한 뒤 `claude` CLI 프로세스를 생성하여 작업을 수행시킵니다.
   * 작업 완료 후 CLI가 종료되면, 기동했던 로컬 프록시 백그라운드 프로세스를 함께 정리(Clean-up)하여 시스템 포트 누수를 방지합니다.

---

## 5. 차기 에이전트 검증 체크리스트

새로운 에이전트인 너는 작업을 시작할 때 반드시 이 체크리스트를 통과해야 한다.

- [ ] `C:\Users\Harry\.gemini\antigravity\brain\c9448787-ac07-4f65-bb83-5eda99069412\scratch\anthropic_proxy.py` 파일의 실제 0-indexed contiguous 변환 코드를 정확하게 읽고 숙지하였는가?
- [ ] 구형 `claude-opus` API를 직접 호출하도록 정의된 레거시 TOML 설계를 거부하고, `http://localhost:9001/v1` 로컬 프록시가 자동 결합되는 `opencode_deepseek_flash` 스펙을 설계 문서와 TOML에 안전하게 반영하였는가?
- [ ] 실행 하네스 라이프사이클 작동 중 포트 9001 프록시 데몬의 백그라운드 자동 기동 및 정리(Clean-up) 로직의 실현 계획을 정립하였는가?
