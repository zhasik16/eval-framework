"""Cost and latency metric."""

def evaluate_cost_latency(case: dict, trace: dict, judge) -> dict:
    """Check if cost/latency within acceptable bounds."""
    cost = trace.get("cost_usd", 0)
    latency = trace.get("wall_time_ms", 0)
    tokens = trace.get("total_tokens", {})

    # Thresholds (can be configurable)
    max_cost = 0.01  # $0.01 per run
    max_latency = 30000  # 30 seconds

    passes = True
    reasons = []
    if cost > max_cost:
        passes = False
        reasons.append(f"Cost ${cost:.4f} exceeds ${max_cost:.4f}")
    if latency > max_latency:
        passes = False
        reasons.append(f"Latency {latency}ms exceeds {max_latency}ms")

    return {
        "pass": passes,
        "cost_usd": cost,
        "latency_ms": latency,
        "tokens": tokens,
        "reason": "; ".join(reasons) if reasons else "Within limits",
    }