# Option B: Roadmap Cleanup & Utility Plan

이 문서는 Phase 5 마일스톤 중 남아있는 클린업 요건들과 사용성 향상을 위한 **런 비교 및 프로세스 자동화 유틸리티**의 구현 계획을 정의합니다.

---

## 1. 주요 과제 및 해결 방안

### A. 모델 라우팅 이력 정리 및 템플릿화
* **현상**: `.agent/metrics/model_routing.md`에 일부 mock 데이터 및 placeholder 데이터가 섞여 있어, 형상 관리에 혼선을 줍니다.
* **해결책**: 
  1. 기존 `model_routing.md`를 소스 코드 트래킹(`.gitignore` 등록)에서 제외하여 각 로컬 구동 시 동적으로 갱신되는 로컬 지표 파일로 전환합니다.
  2. 대신 `docs/model_observations.md`와 같은 고정 정적 관찰기록을 명확히 하고, `.agent/metrics/model_routing.md.example` 과 같은 템플릿 샘플 파일을 레포지토리에 보관하여 초기 구동 시 복사되어 생성되도록 설계합니다.

### B. `agent-bridge compare` 유틸리티 설계
두 개 이상의 에이전트 구동 런 결과를 일목요연하게 비교 분석하여 Commander가 최적의 결정을 내릴 수 있도록 돕는 CLI 기능입니다.

```powershell
uv run agent-bridge compare --runs 20260522-115819-7a0293-opencode_kimi_report 20260522-125546-675340-opencode_deepseek_flash_free
```

* **출력 데이터 아키텍처**:
  * 두 런의 `decision_report.json` 및 `metrics.json`을 병렬로 로드합니다.
  * Markdown 비교 테이블을 표준 출력(stdout) 및 요약 아티팩트로 출력합니다.
  * **비교 필드**:
    * **Status / Verdict** (성공 여부 및 승인 대기 상태)
    * **Execution Time** (`runtime_seconds` 비교)
    * **Files Touched / Inspected** (탐색 및 수정 범위의 조밀함 비교)
    * **Token Costs** (입/출력 토큰 및 달러 비용 요약)
    * **Summary Differ** (두 모델의 최종 요약문 대조)

### C. Daily Process Rollup & 800라인 자동 롤오버
* **Daily Process Rollup**: 하루 동안 수행된 에이전트 런들의 성공율, 소요 비용, 탐색 파일 범위 등을 집계하여 `YYYYMMDD_process.md` 하단에 요약 리포트를 자동 덧붙임해주는 CLI 기능입니다.
* **Process Line-Count Rollover**: 프로세스 파일의 크기가 과대하게 커지는 것을 막기 위해 800라인 한계치 도달 시, 자동으로 `docs/process/YYYYMMDD_process_part2.md` 형태로 신규 분할 생성하는 정밀 파이프라인을 구축합니다.

---

## 2. 작업 순서 및 타임라인

1. **1단계**: `.agent/metrics/model_routing.md`를 `.gitignore`에 등록하고 `.example` 샘플 템플릿화 적용.
2. **2단계**: `src/agent_bridge/cli.py`에 `compare` 서브 커맨드 추가 및 마크다운 테이블 빌더 구현.
3. **3단계**: 라인 카운트 기반 롤오버 및 일일 롤업 집계 스크립트 작성.
