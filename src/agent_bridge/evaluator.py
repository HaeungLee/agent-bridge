import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 1. Error Taxonomy Definition (MVP Plan 11.2)
ERROR_TAXONOMY = [
    "none",
    "compile_error",
    "test_failure",
    "wrong_requirement",
    "over_editing",
    "under_editing",
    "hallucinated_file",
    "bad_api_assumption",
    "style_mismatch",
    "unsafe_change",
    "poor_explanation",
    "format_violation",
    "timeout",
    "tool_failure",
    "unknown"
]

# 2. Quality Score Penalty Matrix (MVP Plan 11.3)
PENALTIES = {
    "compile_error": 40,
    "test_failure": 30,
    "wrong_requirement": 35,
    "unsafe_change": 35,
    "hallucinated_file": 25,
    "over_editing": 20,
    "under_editing": 15,
    "style_mismatch": 10,
    "format_violation": 10,
    "poor_explanation": 5
}

def calculate_quality_score(error_categories: List[str]) -> int:
    """
    Calculates the quality score out of 100 based on error categories.
    Each distinct error subtracts a predefined penalty score. Minimum score is 0.
    If 'none' is in the categories, no penalties are applied (returns 100).
    """
    if "none" in error_categories:
        return 100
        
    score = 100
    for err in error_categories:
        # Ignore empty categories or unregistered categories
        if not err.strip():
            continue
        score -= PENALTIES.get(err.strip(), 0)
        
    return max(0, score)

def update_model_routing_memory(root_path: Path) -> None:
    """
    Scans all run directories under .agent/runs/, parses any commander 'verdict.json'
    accompanied by 'decision_report.json', computes cumulative routing metrics per model,
    and dynamically regenerates .agent/metrics/model_routing.md.
    """
    runs_dir = root_path / ".agent" / "runs"
    metrics_dir = root_path / ".agent" / "metrics"
    os.makedirs(metrics_dir, exist_ok=True)
    
    if not runs_dir.exists():
        # Nothing to scan, write empty routing notes
        write_empty_routing_md(metrics_dir / "model_routing.md")
        return
        
    # Group runs by (model, provider, runner)
    model_stats: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    
    # Iterate through all run directories sorted alphabetically/chronologically to preserve notes order
    for run_dir in sorted(runs_dir.iterdir(), key=lambda x: x.name):
        if not run_dir.is_dir():
            continue
            
        verdict_path = run_dir / "verdict.json"
        report_path = run_dir / "decision_report.json"
        
        if verdict_path.exists() and report_path.exists():
            try:
                with open(verdict_path, "r", encoding="utf-8") as f:
                    verdict_data = json.load(f)
                with open(report_path, "r", encoding="utf-8") as f:
                    report_data = json.load(f)
                    
                model = report_data.get("model", "unknown")
                provider = report_data.get("provider", "unknown")
                runner = report_data.get("runner", "unknown")
                role = report_data.get("role", "unknown")
                run_id = report_data.get("run_id", run_dir.name)
                
                key = (model, provider, runner)
                if key not in model_stats:
                    model_stats[key] = {
                        "scores": [],
                        "best_use_cases": set(),
                        "avoid_fors": set(),
                        "roles": set(),
                        "notes": []
                    }
                    
                stats = model_stats[key]
                score = verdict_data.get("score", 100)
                stats["scores"].append(score)
                
                best_use = verdict_data.get("best_use_case", "")
                if best_use:
                    stats["best_use_cases"].add(best_use)
                    
                avoid = verdict_data.get("avoid_for", "")
                if avoid:
                    stats["avoid_fors"].add(avoid)
                    
                if role and role != "unknown":
                    stats["roles"].add(role)
                    
                note = verdict_data.get("notes", "")
                if note:
                    stats["notes"].append((run_id, note))
                    
            except Exception:
                # Silently skip corrupted directories to maintain robust E2E scan
                continue
                
    if not model_stats:
        write_empty_routing_md(metrics_dir / "model_routing.md")
        return
        
    # Generate Markdown content
    lines = []
    lines.append("# Model Routing Notes\n")
    lines.append("This document dynamically aggregates agent/model execution and evaluation results (error categories, score averages, etc.) as a routing memory.\n")
    
    for (model, provider, runner), stats in sorted(model_stats.items()):
        lines.append(f"## {model} (via {provider}/{runner})\n")
        
        avg_score = round(sum(stats["scores"]) / len(stats["scores"]), 1) if stats["scores"] else 100.0
        lines.append(f"- **Recent score average**: {avg_score} (Based on {len(stats['scores'])} evaluations)")
        
        roles_str = ", ".join(sorted(stats["roles"])) if stats["roles"] else "None"
        lines.append(f"- **Best task types**: {roles_str}")
        
        best_str = ", ".join(sorted(stats["best_use_cases"])) if stats["best_use_cases"] else "None"
        lines.append(f"- **Strong (Best use case)**: {best_str}")
        
        avoid_str = ", ".join(sorted(stats["avoid_fors"])) if stats["avoid_fors"] else "None"
        lines.append(f"- **Weak (Avoid)**: {avoid_str}")
        
        lines.append("- **Commander notes**:")
        if stats["notes"]:
            for run_id, note in stats["notes"]:
                lines.append(f"  - `[{run_id}]` {note}")
        else:
            lines.append("  - None")
        lines.append("") # Spacer
        
    with open(metrics_dir / "model_routing.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def write_empty_routing_md(path: Path) -> None:
    content = (
        "# Model Routing Notes\n\n"
        "This document dynamically aggregates agent/model execution and evaluation results (error categories, score averages, etc.) as a routing memory.\n\n"
        "(No completed evaluation records found.)\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
