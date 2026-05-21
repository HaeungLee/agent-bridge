# Agent Bridge

Agent Bridge is a CLI-first control plane that lets a commander agent delegate expensive or repetitive development work to cheaper coding agents while preserving final decision quality.

## Core Features

- **Doctor Command**: Standard workspace and system diagnostics to verify runtime readiness.
- **Delegated Runner Interface**: Delegate tasks with isolated workspaces and zero context leakage.
- **Decision Contract**: Standardized structured report formats (`decision_report.json`) and readable summaries.

## Getting Started

This project is built and managed with [uv](https://github.com/astral-sh/uv).

### 1. Synchronize Virtual Environment

```bash
uv sync
```

### 2. Run Diagnostics

```bash
uv run agent-bridge doctor
```
