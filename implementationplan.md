XML 통신 프로토콜을 통한 Commander-Worker 파이프라인 구현 계획
본 계획은 Commander와 Worker(하위 에이전트) 간의 기계적 소통(M2M) 시 자연어 텍스트와 마크다운의 파싱 불확실성을 해소하기 위해, **구조화된 XML 응답 프로토콜(response.xml)**을 도입하고 이를 E2E 스모크 테스트로 검증하기 위한 구현 방안을 명시합니다.

User Review Required
IMPORTANT

하위 호환성 및 어댑터 확장 전략

기존의 단순 스모크 테스트와의 하위 호환성을 유지하기 위해, antigravity_smoke.py 어댑터를 리팩토링하여 AGENT_BRIDGE_ANTIGRAVITY_FORMAT = "xml" 환경 변수 활성화 시 XML 전용 가이드 주입 및 자가 치유(Self-healing) XML 파싱 모드로 유연하게 전환되도록 구현합니다.
에이전트가 간혹 XML 태그를 정상적으로 닫지 못하는 상황(Token Limit 등)을 대비하여, Python의 정규식(Regex)과 문자열 치환 기법을 이용한 자가 치유 XML 복구기를 기본 탑재합니다.
Open Questions
NOTE

XML 구조 내 CDATA 사용 여부

하위 에이전트가 돌려주는 소스 코드 패치(diff)나 상세 명령 로그 등에는 특수 기호(<, >, &)가 반드시 포함되므로, 이를 감싸는 <artifact> 태그 내부에는 <![CDATA[ ... ]]> 구문을 사용하도록 Worker에게 강력히 권고할 예정입니다.
혹시 에이전트가 CDATA 구문 자체를 잘 이해하지 못하고 생략할 경우를 대비하여 어댑터 측에서도 안전한 문자열 치환(HTML entity escape) 보정 처리를 적용하려 하는데, 이에 동의하시는지 확인하고 싶습니다.
Proposed Changes
1. Adapter Layer (어댑터 고도화)
[MODIFY] 
antigravity_smoke.py
XML 가이드라인 프롬프트 추가:
AGENT_BRIDGE_ANTIGRAVITY_FORMAT == "xml" 일 때, 에이전트 브릿지가 내려보내는 작업 프롬프트에 XML 스펙 정의서(가이드라인)를 자동으로 덧붙입니다.
가이드라인은 최종 응답을 반드시 scratch 폴더 아래에 response.xml로 생성하고, <agent_response> 루트 엘리먼트로 감싸도록 요구합니다.
자가 치유 XML 파서 도입:
_read_new_scratch_text에서 긁어온 텍스트가 XML 형태인지 우선 파악합니다.
XML의 깨진 닫는 태그를 스스로 찾아 닫아주거나, 정규표현식을 사용해 <status>, <summary>, <artifacts> 등의 블록 데이터를 안정적으로 캡처하는 복구 로직을 구현합니다.
파싱된 결과를 브릿지 통신 규격(data.result_summary, data.artifacts)으로 자동 매핑하여 최종 _emit_response합니다.
2. Configuration & Specs Layer (환경 및 태스크 스펙)
[MODIFY] 
runners.toml
antigravity_smoke 어댑터 환경 변수 그룹에 다음 설정을 추가로 지원합니다.
toml

AGENT_BRIDGE_ANTIGRAVITY_FORMAT = "xml"
AGENT_BRIDGE_ANTIGRAVITY_DIRECT_SMOKE = "false" # 실제 XML 에이전트 호출을 유도하기 위해 direct smoke 단축 응답을 끕니다.
[NEW] 
phase5b_antigravity_xml.toml
XML 통신 및 응답 구조의 정상 작동을 테스트하기 위한 전용 E2E 스모크 태스크 스펙입니다.
필수 검증 조건으로 scratch/response.xml 파일 생성을 선언하고, AGENT_BRIDGE_ANTIGRAVITY_SMOKE_OK 토큰의 존재 여부를 통과 기준으로 삼습니다.
[NEW] 
phase5b_antigravity_xml.md
phase5b_antigravity_xml.toml을 렌더링한 실제 하위 에이전트 주입용 프롬프트 명세입니다.
Verification Plan
Automated Tests
태스크 규격 검증 및 렌더링:
powershell

uv run agent-bridge task validate --spec .agent/tasks/phase5b_antigravity_xml.toml
uv run agent-bridge task render --spec .agent/tasks/phase5b_antigravity_xml.toml --out .agent/tasks/phase5b_antigravity_xml.md
XML 어댑터 모드 E2E 실행 및 캡처:
powershell

uv run agent-bridge run --agent antigravity_smoke --task .agent/tasks/phase5b_antigravity_xml.md --workspace .
결과 확인 및 게이트 통과 검증:
실행 결과 캡처된 raw/stdout.txt 내부 data.artifacts 및 result_summary에 XML로부터 정교하게 발췌된 결과물이 올바르게 탑재되었는지 확인합니다.
uv run agent-bridge task gate 및 check-result를 통해 XML 스모크의 게이트 패스를 입증합니다.