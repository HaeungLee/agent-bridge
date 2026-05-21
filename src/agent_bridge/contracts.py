from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

@dataclass
class TestSummary:
    status: str = "unknown"  # pass | fail | not_run | unknown
    summary: str = ""

@dataclass
class DecisionReport:
    run_id: str
    agent: str
    runner: str
    provider: str
    model: str
    role: str
    mode: str
    status: str = "completed"  # completed | failed | timeout | blocked
    verdict: str = "NEEDS_DECISION"  # PASS | FIX_REQUIRED | NEEDS_DECISION | BLOCKED
    summary: str = ""
    files_inspected: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    commands_run: List[str] = field(default_factory=list)
    tests: TestSummary = field(default_factory=TestSummary)
    risks: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    next_action: str = ""
    confidence: Optional[float] = None
    schema_version: str = "decision_report.v0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def validate_decision_report(report_dict: dict) -> None:
    """
    Validates that the provided dictionary contains all fields required for decision_report.v0.
    Raises ValueError if any field is missing, has incorrect structure, type, or value.
    """
    required_fields = {
        "schema_version", "run_id", "agent", "runner", "provider", "model", 
        "role", "mode", "status", "verdict", "summary", "files_inspected", 
        "files_changed", "commands_run", "tests", "risks", "open_questions", 
        "next_action", "confidence"
    }
    
    if not isinstance(report_dict, dict):
        raise ValueError("Report must be a dictionary")
        
    missing = required_fields - set(report_dict.keys())
    if missing:
        raise ValueError(f"Missing required fields for decision_report.v0: {missing}")
        
    # Verify schema_version
    schema_version = report_dict.get("schema_version")
    if schema_version != "decision_report.v0":
        raise ValueError(f"Invalid schema_version '{schema_version}'. Expected 'decision_report.v0'")
        
    # Verify string fields
    str_fields = [
        "run_id", "agent", "runner", "provider", "model", 
        "role", "mode", "summary", "next_action"
    ]
    for field in str_fields:
        val = report_dict.get(field)
        if not isinstance(val, str):
            raise ValueError(f"Field '{field}' must be a string, got {type(val).__name__}")
            
    # Verify status enum
    valid_statuses = {"completed", "failed", "timeout", "blocked"}
    status = report_dict.get("status")
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Expected one of {valid_statuses}")
        
    # Verify verdict enum
    valid_verdicts = {"PASS", "FIX_REQUIRED", "NEEDS_DECISION", "BLOCKED"}
    verdict = report_dict.get("verdict")
    if verdict not in valid_verdicts:
        raise ValueError(f"Invalid verdict '{verdict}'. Expected one of {valid_verdicts}")
        
    # Verify confidence bounds
    confidence = report_dict.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, (int, float)):
            raise ValueError(f"Field 'confidence' must be float, int or None, got {type(confidence).__name__}")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Field 'confidence' must be between 0.0 and 1.0, got {confidence}")
            
    # Verify list fields
    list_fields = [
        "files_inspected", "files_changed", "commands_run", "risks", "open_questions"
    ]
    for field in list_fields:
        val = report_dict.get(field)
        if not isinstance(val, list):
            raise ValueError(f"Field '{field}' must be a list, got {type(val).__name__}")
        for idx, item in enumerate(val):
            if not isinstance(item, str):
                raise ValueError(f"Element at index {idx} in field '{field}' must be a string, got {type(item).__name__}")
                
    # Verify sub-structure for tests
    tests_field = report_dict.get("tests")
    if not isinstance(tests_field, dict):
        raise ValueError("Field 'tests' must be a dictionary")
    if "status" not in tests_field or "summary" not in tests_field:
        raise ValueError("Field 'tests' must contain 'status' and 'summary' keys")
        
    test_status = tests_field.get("status")
    valid_test_statuses = {"pass", "fail", "not_run", "unknown"}
    if test_status not in valid_test_statuses:
        raise ValueError(f"Invalid test status '{test_status}'. Expected one of {valid_test_statuses}")
        
    test_summary = tests_field.get("summary")
    if not isinstance(test_summary, str):
        raise ValueError(f"Field 'tests.summary' must be a string, got {type(test_summary).__name__}")
