# Operating Rules for Gemini and Antigravity Agents

This document defines the strict operational boundaries and rule hardening policies for all Gemini, Antigravity, and peer subordinate coding agents executing tasks within this repository. Adherence to these rules is a **correctness requirement**.

---

## 1. Strict Phase and Scope Isolation

- **Do Not Implement Adjacent Features**: Subagents must focus exclusively on the specific, narrow milestone or slice currently assigned. Proactive implementation of future phases (e.g. Phase 6 planning, next milestones) or optional features is strictly forbidden.
- **Do Not Guess Design Direction**: Even if a design decision seems obvious or easy, do not proceed with changes not explicitly detailed in the assigned task spec.
- **Stop and Report Blockers**: If a task cannot be completed within the boundaries of the allowed files or hard rules:
  1. Do not unilaterally expand the task scope or modify forbidden files.
  2. Stop execution immediately.
  3. Report the blocker clearly to the human commander or supervisor.

---

## 2. Prohibition of Self-Evaluation

- **No Self-Declared PASS**: Subagents must never write or auto-assign a `"Commander Verdict": "PASS"` or any equivalent positive evaluation verdict in process logs (`mmdd_process.md`), walkthroughs (`walkthrough.md`), or run reports (`decision_report.json`).
- **Reserved Decisional Rights**: The role of "Commander" and "Supervisor" belongs exclusively to the human operator or the primary orchestrating model under explicit human validation.
- **Blank or N/A Status**: Always set the verdict to `"N/A"` or leave it empty for human evaluation.
- **No Self-Scoring**: Do not add self-evaluation scores such as `Correctness: 5/5`, `Confidence: 5/5`, or similar subjective grades. Report concrete commands, results, risks, and blockers only.

---

## 3. Strict Execution Lifecycle

- **Stop After Log Update**: After completing the assigned unit, the agent must record the work log inside `docs/process/YYYYMMDD_process.md` and then **stop execution immediately**.
- **Process Logs Are Append-Only**: Never overwrite, recreate, truncate, or replace an existing file under `docs/process/`. Before editing a process log, verify its current contents with a direct file read and append only a new section at the end.
- **No Blind File Creation**: If a shared file appears missing from a tool result, verify with a second method before creating it. Prefer failing closed and reporting uncertainty over using an overwrite-capable write.
- **No Direct Commits**: Git commits and repository initialization are entirely restricted unless explicitly instructed by the human supervisor.
- **No Unsolicited Artifact Updates**: Do not update planning or walkthrough files (`implementation_plan.md`, `walkthrough.md`, `task.md`) unless the user explicitly requested them in the prompt.

---

## 4. Path and Environment Sanitization

- **No Hardcoded Absolute Paths**: All workspace absolute paths or system executable paths (such as `agy.exe` paths) must never be hardcoded into python adapters or codebase sources. They must be managed strictly via environment variables or loaded through the `config/` TOML parameters.
- **Global State Is Read-Only Evidence**: Session directories or user-home state may be inspected only when explicitly assigned. Never mutate global state, create mocks in global directories, or treat global scans as proof of correctness without command output and run artifacts.
