"""Tool efficiency metric."""

def evaluate_efficiency(case: dict, trace: dict, judge) -> dict:
    """Check if agent used tools efficiently."""
    # Count tool calls
    tool_calls = []
    for msg in trace.get("messages", []):
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                tool_calls.append(tc["name"])

    total_calls = len(tool_calls)
    # Unnecessary calls: fetch_url without preceding web_search? etc.
    # Simple heuristic: if no web_search but fetch_url exists, it's inefficient
    has_search = "web_search" in tool_calls
    has_fetch = "fetch_url" in tool_calls
    if has_fetch and not has_search:
        return {"pass": False, "reason": "Fetched URL without searching first"}

    # Check for redundant fetch (same URL fetched twice)
    fetched_urls = []
    for msg in trace.get("messages", []):
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                if tc["name"] == "fetch_url":
                    url = tc.get("args", {}).get("url")
                    if url in fetched_urls:
                        return {"pass": False, "reason": f"Duplicate fetch of {url}"}
                    fetched_urls.append(url)

    # Check max steps bound
    if trace.get("stopped_reason") == "max_steps":
        return {"pass": False, "reason": "Exceeded max steps"}

    return {"pass": True, "reason": "Tool usage appears efficient"}