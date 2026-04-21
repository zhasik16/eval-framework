"""Correctness metric combining hard facts and LLM judgment."""

def evaluate_correctness(case: dict, trace: dict, judge) -> dict:
    """Evaluate factual correctness."""
    # Use hard checks if defined
    hard_checks = case.get("expected_behavior", {}).get("hard", [])
    hard_pass = True
    for check in hard_checks:
        if "substring_in_final" in str(check):
            # This will be handled by scorer's hard pass; here we just note
            pass

    # For soft, we rely on the LLM judge score from soft assertions
    # This metric aggregates: overall correctness pass if all soft scores >=0.7
    soft = case.get("expected_behavior", {}).get("soft", [])
    if not soft:
        # No explicit correctness rubric; assume pass
        return {"pass": True, "score": 1.0, "reason": "No soft correctness checks"}

    # The actual LLM scores are computed in scorer; here we just return placeholder
    # The overall pass will be determined by scorer combining everything.
    return {"pass": None, "note": "evaluated via soft assertions"}