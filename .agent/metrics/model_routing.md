# Model Routing Notes

이 문서는 각 에이전트/모델 조합의 실행 및 평가 결과(결함 유형, 점수 평균 등)를 동적으로 집계하여 생성한 라우팅 메모리 파일입니다.

## glm-5.2 (via nanogpt/opencode)

- **Recent score average**: 100.0 (기반 평가 횟수: 1)
- **Best task types**: code_review
- **Strong (Best use case)**: code review
- **Weak (Avoid)**: large refactors
- **Commander notes**:
  - `[20260521-130451-5d0ccd-glm_review]` Excellent manual verification mock run.

## mock (via local/mock_subprocess)

- **Recent score average**: 50.0 (기반 평가 횟수: 2)
- **Best task types**: implementation
- **Strong (Best use case)**: smoke, smoke testing
- **Weak (Avoid)**: complex logic, risky
- **Commander notes**:
  - `[20260521-130447-592d98-mock_impl]` Some syntax and style warnings found.
  - `[20260521-130858-8bb04f-mock_impl]` partial-test
