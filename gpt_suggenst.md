지금 병목이 “모델 성능”보다 “CLI harness / stdout streaming / proxy hop / registry 갱신” 쪽이라, 판단 기준을 속도 개선과 통제 가능성으로 나눠서 볼게. 최신 CLI/프록시 쪽은 변동이 잦아서 확인하고 정리하겠다.

15s 동안 생각함

결론부터 말하면, LiteLLM proxy 경유는 “속도 개선” 목적이면 1순위가 아니다.
다만 nanoGPT 최신 모델을 CLI가 못 물 때 / 모델 라우팅·fallback·비용 로깅·통합 API가 필요할 때는 의미가 있다.

현재 구조에서 내가 추천하는 우선순위는 이거다.

1. Codex 직접 호출은 그대로 “상위 commander”로 유지

지금 네 구조에서 Codex가 CLI를 직접 호출하는 방식은 유지하는 게 맞다.
이유는 단순하다.

직접 호출 > proxy 경유 > CLI harness 경유 proxy 순으로 통제 지연이 늘어난다.

특히 지금 병목은 모델 자체보다:

Claude Code harness가 느림
Antigravity CLI 출력/streaming이 불안정
nanoGPT 자체 API proxy가 느림
opencode registry에 최신 모델이 없음
stdout streaming이 안 되는 경우 Moonlight가 “멈춘 것처럼” 보임

이쪽이다.

그래서 proxy를 붙이면 빨라지는 게 아니라, 대부분은 더 느려진다. LiteLLM 자체는 OpenAI 호환 게이트웨이, provider 통합, retry/fallback, budget/cost tracking을 제공하는 쪽이지, CLI latency를 줄이는 도구는 아니다. 공식 문서도 Proxy Server를 “중앙 AI gateway”와 multi-provider access/cost tracking 용도로 설명한다.

2. LiteLLM은 “속도용”이 아니라 “호환성/라우팅용”으로만 써라

LiteLLM을 쓰는 의미가 있는 경우는 딱 이거다.

A. opencode/aider가 nanoGPT 최신 모델을 못 물 때 OpenAI-compatible endpoint로 우회
Aider는 OpenAI-compatible API endpoint에 붙을 수 있고, OPENAI_API_BASE, OPENAI_API_KEY, aider --model openai/<model-name> 구조를 공식 지원한다.

B. 모델 이름 normalize / fallback / retry / timeout / stream_timeout 관리
LiteLLM은 per-model timeout과 stream_timeout 설정을 지원한다. 이건 “느린 provider를 빨리 포기하고 다른 모델로 넘기는” 용도로는 좋다.

C. nanoGPT API key 여러 개를 라우팅하고, 모델별 실패율/비용을 로그로 남기기
이건 Moonlight/agent bridge 관점에서 꽤 가치 있다.

하지만 속도 개선용으로 LiteLLM을 기대하면 실망할 가능성이 높다. 실제 운영 경험 쪽에서도 LiteLLM이 streaming latency를 몇 ms 단위로 추가하고, multi-turn/tool-call agent에서는 이게 누적된다는 보고가 있다. 다만 이건 Reddit 사례라 공식 벤치마크는 아니고, “네가 이미 체감한 느려짐”과 방향성이 맞는 참고 정도로 보면 된다.

내 판단은:

LiteLLM은 “느린 CLI를 빠르게 만드는 도구”가 아니라, “느린/불안정한 provider를 정책적으로 버리거나 우회하는 router”다.

즉, Moonlight에서는 이렇게 쓰는 게 맞다.

Codex commander
  ├─ Direct CLI adapters: codex / opencode / aider / claude / antigravity
  ├─ Proxy route: LiteLLM or faster Go proxy
  └─ Policy:
      - direct first
      - proxy only when model registry/API compatibility requires it
      - stream_timeout 초과 시 fallback
      - slow provider quarantine
3. Aider CLI는 지금 상황에서 가치 있음

Aider는 네가 말한 대안 중 가장 실용적이다.

이유는 세 가지다.

첫째, OpenAI-compatible API에 직접 붙을 수 있다. 그래서 nanoGPT 최신 모델을 opencode registry가 못 물어도 Aider가 바로 물 가능성이 있다.

둘째, Aider는 “코드 변경 특화 harness”라서 Claude Code/Antigravity보다 단순하고, agent bridge 하위 worker로 쓰기 좋다.

셋째, Moonlight 철학과 맞다.
Aider를 “main brain”으로 쓰는 게 아니라:

Commander: Codex / GPT-5.5
Executor: Aider + cheap model
Reviewer: Claude / GPT

이렇게 두면 좋다.

추천 역할은:

Aider + nanoGPT cheap model:
- 작은 파일 수정
- 테스트 실패 수정
- 명확한 patch task
- refactor 범위가 닫힌 작업

Claude Code:
- 구조 이해
- 복잡한 코드베이스 탐색
- 리뷰
- 위험한 변경 전 분석

Antigravity:
- Google/Firebase/Android/AI Studio 연동 실험
- 병렬 agent 실험
- 직접 UI에서 쓸 때만 우선
4. Claude Code 속도 개선은 stream-json + partial messages부터 봐라

Claude Code는 공식 CLI에서 --print, --output-format stream-json, --include-partial-messages, --max-turns, --permission-mode, --dangerously-skip-permissions 등을 제공한다.

네 bridge에서 Claude를 물릴 때는 interactive mode보다 이쪽이 낫다.

claude -p "TASK..." \
  --output-format stream-json \
  --include-partial-messages \
  --max-turns 3

이걸 Moonlight에서 JSONL stream으로 읽으면 된다.
핵심은 “전체 응답 완료까지 기다리지 말고 partial message를 narrative/status로 바로 뿌리는 것”이다.

추가로 task가 작으면:

claude -p "TASK..." \
  --output-format stream-json \
  --include-partial-messages \
  --max-turns 1

--max-turns를 줄이면 agent loop가 줄어서 체감 속도가 좋아질 수 있다. Claude Code가 느린 이유 중 하나는 단순 completion이 아니라, 내부적으로 tool loop / permission / context / compaction / session management를 돌리기 때문이다. 최근 Claude Code 구조 분석 논문도 Claude Code의 핵심 loop 외에 permission system, context compaction, MCP/plugins/skills/hooks, subagent delegation, session storage 같은 주변 시스템이 크다고 설명한다.

즉, Claude Code를 빠르게 쓰려면:

하지 말 것:
- 자유롭게 분석하고 구현해줘
- 알아서 필요한 파일 찾아서 고쳐줘

할 것:
- 이 파일만 읽어라
- 이 함수만 수정해라
- max-turns 1~3
- output-format stream-json
- partial messages 사용
- 허용 tool 제한
5. Antigravity CLI는 “직접 사용 빠름 / CLI 자동화 느림”이면 보조 worker로 내려라

Antigravity CLI는 Google이 Antigravity 2.0과 함께 낸 terminal-first surface이고, 공식 소개에서는 lightweight CLI, same Antigravity harness, settings 공유, subagent, slash command, config 등을 강조한다.

그런데 네가 말한 것처럼 직접 쓰면 빠른데 CLI 자동화에서는 느리고 stdout이 불안정하다면, 이건 네 bridge의 문제가 아니라 Antigravity가 아직 “human terminal UX” 중심으로 설계됐을 가능성이 높다.

특히 stdout이 안정적으로 stream되지 않고 XML 보고를 받아야 한다면, Moonlight worker로는 불리하다.

내 추천:

Antigravity CLI:
- MVP 핵심 worker에서 제외
- Google 생태계 작업 전용 adapter로 격하
- 직접 TUI/CLI 사용은 허용
- 자동화 route에서는 “slow/unstructured worker”로 분류

Moonlight 내부 verdict로는:

{
  "engine": "antigravity-cli",
  "class": "interactive_agent",
  "automation_grade": "low",
  "streaming_grade": "poor",
  "use_for": ["google_stack", "manual_parallel_agent"],
  "avoid_for": ["fast_patch", "stdout_required", "strict_json_worker"]
}

이렇게 박아도 될 것 같다.

6. opencode 최신 모델 미등록 문제는 “registry 우회 adapter”가 필요함

opencode가 빠른데 registry에 deepseek v4 pro / mimo v2.5 pro가 없어서 못 쓴다면, 해결 방향은 셋 중 하나다.

1. opencode registry PR / local provider patch
2. OpenAI-compatible custom provider 지원 여부 확인 후 base_url 주입
3. opencode는 유지하되, 최신 nanoGPT 모델은 Aider/LiteLLM route로 분리

내 추천은 3번이다.

opencode를 억지로 고치기보다:

Fast path:
opencode + 등록된 모델

Fresh model path:
aider + nanoGPT direct API or LiteLLM

Controlled path:
Codex direct

Review path:
Claude Code direct

이게 가장 현실적이다.

7. Proxy를 쓴다면 LiteLLM보다 “초경량 gateway”도 후보

네가 진짜 latency에 민감하면 LiteLLM은 기능이 많은 대신 무겁다.
Reddit 쪽이긴 하지만, Bifrost 같은 Go 기반 gateway가 LiteLLM보다 streaming latency가 낮았다는 운영 경험이 있다.

다만 나는 당장 Bifrost로 갈아타라고 보진 않는다.
이유는 LiteLLM은 provider coverage와 문서/생태계가 강하고, 네 목적이 아직 “MVP worker 연결 실험”이기 때문이다.

추천 순서는:

Phase 1:
LiteLLM으로 compatibility test

Phase 2:
느린 게 확정되면 LiteLLM logging/DB/dashboard 끄고 최소 config

Phase 3:
그래도 streaming latency가 문제면 Go proxy/Bifrost류 검토

Phase 4:
Moonlight 전용 commander gateway 직접 구현

결국 장기적으로는 네가 말한 대로 Moonlight 전용 commander harness/gateway가 맞다.

8. 속도 측정은 “총 시간” 말고 4개로 쪼개야 함

지금 느리다는 감각을 제대로 판단하려면 이렇게 봐야 한다.

T0: process spawn time
T1: request sent
T2: first stdout chunk / first token
T3: final response
T4: parsed verdict ready

그리고 지표는:

spawn_ms
ttft_ms
stream_duration_ms
total_ms
tokens_per_sec
stdout_chunk_count
parse_fail_rate
tool_turn_count
retry_count

LLM latency는 TTFT, inter-token latency, total time으로 나눠 보는 게 정석이고, streaming은 total time이 같아도 체감 latency를 크게 바꾼다.

Moonlight 쪽에서는 이게 중요하다.

사용자가 느끼는 속도 = total_ms가 아니라 ttft_ms + progress visibility

그래서 Antigravity가 총 시간은 괜찮아도 stdout이 없으면 “느린 worker”로 분류해야 한다.

9. 내가 추천하는 최종 구조

지금 단계에서는 이렇게 가는 게 가장 좋다.

Tier 0 - Commander
Codex / GPT-5.5
- plan freeze
- task delegation
- final validation
- risky change gate

Tier 1 - Reliable executor
Aider CLI
- OpenAI-compatible endpoint
- nanoGPT 최신 모델 실험
- small/medium patch
- 빠른 실행

Tier 2 - Fast executor
opencode CLI
- registry에 있는 모델만
- 빠른 patch task
- cheap worker

Tier 3 - Deep reviewer
Claude Code
- slow but high-quality
- stream-json + partial messages
- max-turns 제한
- review / architecture / complex bug

Tier 4 - Special worker
Antigravity CLI
- Google/Firebase/Android/AI Studio 계열
- manual or semi-manual
- stdout 의존 작업에서는 제외

Gateway
LiteLLM
- compatibility/fallback/cost logging
- speed 기대 X
- direct route가 안 될 때만 사용
10. 실전 판단

네 질문에 직접 답하면:

Q. local에서 Codex가 CLI 직접 호출하는데 느리다. LiteLLM proxy 경유가 의미 있나?

속도 목적이면 거의 없다.
오히려 한 hop 늘어난다.

의미 있는 경우는:

- CLI가 최신 모델을 못 물 때
- nanoGPT 모델명을 OpenAI-compatible하게 normalize해야 할 때
- timeout/fallback/retry 정책을 중앙화할 때
- API key 여러 개 라우팅할 때
- 비용/실패율/latency 로그를 쌓을 때

즉, 성능 최적화 도구가 아니라 control-plane 도구로 봐야 한다.

Q. Claude / Antigravity CLI 출력을 더 빠르게 할 방법 있나?

Claude는 가능성이 있다.

claude -p "..." \
  --output-format stream-json \
  --include-partial-messages \
  --max-turns 1

이걸 기본 route로 잡아라.
그리고 작업 단위를 더 작게 쪼개야 한다.

Antigravity는 현재 네 증상 기준으로는 어렵다. 공식적으로는 lightweight CLI라고 하지만, 실제 자동화에서는 stdout streaming이 안정적이지 않으면 bridge worker로 치명적이다.
Antigravity는 “빠른 자동 worker”가 아니라 “특수 목적 semi-manual worker”로 두는 게 맞다.

내 최종 추천

지금은 Aider CLI를 바로 붙여서 nanoGPT 최신 모델 path를 확보하는 게 1순위다.

그 다음:

1. Claude Code: stream-json + partial + max-turns 제한
2. Aider: nanoGPT direct 또는 LiteLLM 경유 비교
3. LiteLLM: speed 목적 금지, compatibility/fallback 목적만
4. opencode: registry 되는 모델만 fast worker로 유지
5. Antigravity: 자동화 핵심에서 제외, Google stack 전용
6. Moonlight: latency telemetry를 worker별로 축적해서 자동 라우팅

한 문장으로 정리하면:

Codex commander + Aider/nanoGPT executor + opencode fast path + Claude reviewer가 현재 최적이고, LiteLLM은 “빠르게 하기 위해서”가 아니라 “못 붙는 모델을 붙이고 실패를 정책적으로 처리하기 위해서”만 써야 한다.