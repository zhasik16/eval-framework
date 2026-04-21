"""Scoring engine for hard and soft assertions."""

from typing import Dict, List, Any, Callable
from pathlib import Path

from judge import LLMJudge


class Scorer:
    def __init__(self, metrics_registry: Dict[str, Callable], judge: LLMJudge):
        self.metrics = metrics_registry
        self.judge = judge

    def score(self, case: dict, trace: dict) -> Dict[str, Any]:
        """Compute all scores for a case."""
        scores = {}
        expected = case.get("expected_behavior", {})

        # Hard assertions (deterministic)
        if "hard" in expected:
            scores["hard"] = self._evaluate_hard(expected["hard"], trace)

        # Soft assertions (LLM judge)
        if "soft" in expected:
            scores["soft"] = self._evaluate_soft(expected["soft"], case, trace)

        # Core metrics (always computed)
        for metric_name, metric_fn in self.metrics.items():
            scores[metric_name] = metric_fn(case, trace, self.judge)

        # Overall pass/fail based on all components
        scores["overall_pass"] = self._determine_pass(scores, case)
        return scores

    def _evaluate_hard(self, checks: List[Any], trace: dict) -> Dict[str, Any]:
        """Evaluate deterministic checks against trace."""
        results = {}
        for check in checks:
            if isinstance(check, str):
                # Simple string check format: "tool_called:web_search"
                if ":" in check:
                    op, val = check.split(":", 1)
                    results[check] = self._hard_check(op.strip(), val.strip(), trace)
                else:
                    # Assume substring check in final answer
                    results[f"substring_{check}"] = check in trace.get("final_answer", "")
            elif isinstance(check, dict):
                for op, val in check.items():
                    results[f"{op}:{val}"] = self._hard_check(op, val, trace)
        return results

    def _hard_check(self, op: str, val: str, trace: dict) -> bool:
        """Perform a single hard check."""
        if op == "tool_called":
            # Check if tool name appears in any tool call
            return any(
                msg.get("role") == "assistant" and
                any(tc.get("name") == val for tc in msg.get("tool_calls", []))
                for msg in trace.get("messages", [])
            )
        elif op == "substring_in_final":
            return val in trace.get("final_answer", "")
        elif op == "stop_reason":
            return trace.get("stopped_reason") == val
        elif op == "tool_call_count_le":
            # Count total tool calls
            count = sum(
                len(msg.get("tool_calls", []))
                for msg in trace.get("messages", [])
                if msg.get("role") == "assistant"
            )
            return count <= int(val)
        elif op == "citation_url_fetched":
            # Every citation URL must have been fetched
            citations = trace.get("citations", [])
            fetched_urls = set()
            for msg in trace.get("messages", []):
                if msg.get("role") == "tool" and msg.get("name") == "fetch_url":
                    # Extract URL from tool call? We need to look at previous assistant message
                    pass
            # More robust: look for fetch_url tool calls in assistant messages
            for msg in trace.get("messages", []):
                if msg.get("role") == "assistant":
                    for tc in msg.get("tool_calls", []):
                        if tc.get("name") == "fetch_url":
                            fetched_urls.add(tc.get("args", {}).get("url"))
            return all(url in fetched_urls for url in citations)
        elif op == "max_word_count":
            words = len(trace.get("final_answer", "").split())
            return words <= int(val)
        else:
            return False

    def _evaluate_soft(self, soft_assertions: List[dict], case: dict, trace: dict) -> Dict[str, Any]:
        """Evaluate LLM-judge assertions."""
        results = {}
        for assertion in soft_assertions:
            rubric_file = assertion.get("rubric")
            if not rubric_file:
                continue
            rubric_path = Path("rubrics") / rubric_file
            context = {
                "question": case["input"],
                "answer": trace.get("final_answer", ""),
                "citations": trace.get("citations", []),
                "trace_summary": self._trace_summary(trace),
            }
            judgment = self.judge.evaluate(rubric_path, context)
            results[rubric_file] = judgment
        return results

    def _trace_summary(self, trace: dict) -> str:
        """Create a concise summary of tool usage for judge context."""
        tools_used = []
        for msg in trace.get("messages", []):
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls", []):
                    tools_used.append(f"{tc['name']}({tc.get('args', {})})")
        return "; ".join(tools_used) if tools_used else "No tools used"

    def _determine_pass(self, scores: dict, case: dict) -> bool:
        """Determine overall pass/fail based on expected behavior."""
        # Hard checks must all pass
        hard_checks = scores.get("hard", {})
        if not all(hard_checks.values()):
            return False

        # Soft checks: each rubric result must have score >= threshold
        soft = scores.get("soft", {})
        for rubric_result in soft.values():
            if rubric_result.get("score", 0) < 0.7:  # threshold
                return False

        # Core metrics must pass
        for metric, result in scores.items():
            if metric in ("hard", "soft", "overall_pass"):
                continue
            if isinstance(result, dict) and not result.get("pass", True):
                return False

        return True