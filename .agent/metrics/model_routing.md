# Model Routing Notes

This document dynamically aggregates agent/model execution and evaluation results (error categories, score averages, etc.) as a routing memory.

## glm-5.2 (via nanogpt/opencode)

- **Recent score average**: 100.0 (Based on 2 evaluations)
- **Best task types**: code_review
- **Strong (Best use case)**: code review
- **Weak (Avoid)**: large refactors
- **Commander notes**:
  - `[20260521-130451-5d0ccd-glm_review]` Excellent manual verification mock run.
  - `[20260521-130859-37c0b1-glm_review]` Evaluated via CLI arguments.

## mock (via local/mock_subprocess)

- **Recent score average**: 75.0 (Based on 4 evaluations)
- **Best task types**: implementation
- **Strong (Best use case)**: latest-safety, smoke, smoke testing
- **Weak (Avoid)**: complex logic, incomplete-runs, risky
- **Commander notes**:
  - `[20260521-130447-592d98-mock_impl]` Some syntax and style warnings found.
  - `[20260521-130858-8bb04f-mock_impl]` partial-test
  - `[20260521-132537-b06365-mock_impl]` sequential-status-check
  - `[20260521-134512-ae7caf-mock_impl]` completed-marker-check
