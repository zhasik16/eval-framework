"""Report generation and HTML trace viewer."""

import json
import statistics
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from jinja2 import Template

from trace_store import TraceStore


class Reporter:
    def __init__(self):
        self.viewer_template = (Path(__file__).parent / "templates" / "viewer.html").read_text()

    def generate_run_report(self, scored_results: List[tuple], repeats: int = 1) -> str:
        """Generate console report with pass rates and metrics."""
        # Group by case id, handle repeats
        case_results = {}
        for res, scores in scored_results:
            case_id = res.case["id"]
            if case_id not in case_results:
                case_results[case_id] = []
            case_results[case_id].append((res, scores))

        lines = []
        lines.append("=" * 80)
        lines.append(f"EVALUATION REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 80)

        total_passes = 0
        total_cases = len(case_results)
        all_latencies = []
        all_costs = []
        all_tool_counts = []

        for case_id, results in case_results.items():
            passes = sum(1 for _, scores in results if scores.get("overall_pass", False))
            total_passes += passes
            latencies = [r.wall_time_ms for r, _ in results if r.trace]
            costs = [r.trace.get("cost_usd", 0) for r, _ in results if r.trace]
            tool_counts = [self._count_tool_calls(r.trace) for r, _ in results if r.trace]

            all_latencies.extend(latencies)
            all_costs.extend(costs)
            all_tool_counts.extend(tool_counts)

            pass_rate = f"{passes}/{len(results)}"
            if repeats > 1:
                lines.append(f"\n[Case: {case_id}] {pass_rate} passed")
            else:
                status = "✅ PASS" if passes else "❌ FAIL"
                lines.append(f"\n[Case: {case_id}] {status}")

            # Show failure reasons
            for res, scores in results:
                if not scores.get("overall_pass", False):
                    reasons = self._failure_reasons(scores)
                    if reasons:
                        lines.append(f"  ↳ {reasons}")

        # Aggregate stats
        lines.append("\n" + "-" * 40)
        lines.append("AGGREGATE METRICS")
        lines.append("-" * 40)
        lines.append(f"Pass rate: {total_passes}/{total_cases * repeats} ({100*total_passes/(total_cases*repeats):.1f}%)")
        
        if all_latencies:
            if len(all_latencies) >= 2:
                lines.append(f"Latency p50: {statistics.median(all_latencies):.0f}ms, p95: {statistics.quantiles(all_latencies, n=20)[18]:.0f}ms")
            else:
                lines.append(f"Latency: {all_latencies[0]:.0f}ms (only 1 data point)")
        if all_costs:
            lines.append(f"Total cost: ${sum(all_costs):.4f}")
        if all_tool_counts:
            lines.append(f"Mean tool calls: {statistics.mean(all_tool_counts):.1f}")

        return "\n".join(lines)

    def generate_diff(self, store: TraceStore, run_a: str, run_b: str) -> str:
        """Compare two runs and show regressions."""
        cases_a = store.list_cases(run_a)
        cases_b = store.list_cases(run_b)
        common_cases = set(cases_a) & set(cases_b)

        regressions = []
        improvements = []
        for case_id in common_cases:
            trace_a = store.load_trace(run_a, case_id)
            trace_b = store.load_trace(run_b, case_id)
            score_a = trace_a.get("scores", {}).get("overall_pass", False)
            score_b = trace_b.get("scores", {}).get("overall_pass", False)
            if score_a and not score_b:
                regressions.append(case_id)
            elif not score_a and score_b:
                improvements.append(case_id)

        lines = []
        lines.append(f"Diff: {run_a} → {run_b}")
        lines.append("-" * 40)
        if regressions:
            lines.append(f"❌ REGRESSIONS ({len(regressions)}):")
            for c in regressions:
                lines.append(f"  - {c}")
        else:
            lines.append("✅ No regressions detected.")
        if improvements:
            lines.append(f"🎉 IMPROVEMENTS ({len(improvements)}):")
            for c in improvements:
                lines.append(f"  - {c}")
        return "\n".join(lines)

    def generate_html_viewer(self, scored_results: List[tuple], output_path: Path):
        """Generate an interactive HTML report for a run."""
        cases_data = []
        for res, scores in scored_results:
            # Count tool calls safely
            tool_count = 0
            for msg in res.trace.get("messages", []):
                if msg.get("role") == "assistant":
                    tool_count += len(msg.get("tool_calls", []))
            
            cases_data.append({
                "case_id": res.case["id"],
                "input": res.case["input"],
                "trace": res.trace,
                "scores": scores,
                "pass": scores.get("overall_pass", False),
                "tool_count": tool_count,
            })

        template_str = """<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Deep Research Lite - Evaluation Report</title>
        <style>
            body { font-family: system-ui, sans-serif; margin: 20px; background: #f5f5f5; }
            h1 { color: #333; }
            .run-info { margin-bottom: 20px; color: #666; }
            .case { background: white; border-radius: 8px; margin-bottom: 20px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            .case-header { display: flex; align-items: center; gap: 10px; cursor: pointer; }
            .case-id { font-weight: bold; font-size: 1.2em; }
            .pass-badge { padding: 4px 8px; border-radius: 12px; font-size: 0.8em; }
            .pass { background: #d4edda; color: #155724; }
            .fail { background: #f8d7da; color: #721c24; }
            .question { color: #555; margin: 10px 0; }
            .answer { background: #e9ecef; padding: 10px; border-radius: 4px; margin: 10px 0; }
            .timeline { margin-top: 15px; border-top: 1px solid #dee2e6; padding-top: 10px; display: none; }
            .case.expanded .timeline { display: block; }
            .message { margin: 10px 0; padding: 8px; border-left: 3px solid #ccc; }
            .assistant { border-left-color: #007bff; }
            .tool { border-left-color: #28a745; margin-left: 20px; }
            .tool-call { background: #f8f9fa; padding: 5px; margin: 5px 0; }
            pre { background: #f1f3f5; padding: 8px; overflow-x: auto; }
            .metrics { display: flex; gap: 15px; margin: 10px 0; }
            .metric { background: #e2e6ea; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; }
            .failure-reason { color: #dc3545; margin-top: 5px; }
        </style>
    </head>
    <body>
        <h1>🧪 Deep Research Lite Evaluation</h1>
        <div class="run-info">Run: {{ run_time }}</div>

        {% for case in cases %}
        <div class="case" onclick="this.classList.toggle('expanded')">
            <div class="case-header">
                <span class="case-id">{{ case.case_id }}</span>
                <span class="pass-badge {{ 'pass' if case.pass else 'fail' }}">
                    {{ '✅ PASS' if case.pass else '❌ FAIL' }}
                </span>
            </div>
            <div class="question"><strong>Q:</strong> {{ case.input }}</div>
            <div class="answer"><strong>A:</strong> {{ case.trace.final_answer or '[No answer]' }}</div>
            {% if not case.pass %}
            <div class="failure-reason">
                <strong>Failure:</strong> 
                {% if case.scores.hard %}
                    {% for check, passed in case.scores.hard.items() if not passed %}
                        {{ check }}; 
                    {% endfor %}
                {% endif %}
                {% if case.scores.soft %}
                    {% for rubric, result in case.scores.soft.items() if result.score < 0.7 %}
                        {{ rubric }}: {{ result.rationale }}; 
                    {% endfor %}
                {% endif %}
            </div>
            {% endif %}
            <div class="metrics">
                <span class="metric">💰 ${{ "%.4f"|format(case.trace.cost_usd) }}</span>
                <span class="metric">⏱️ {{ case.trace.wall_time_ms }}ms</span>
                <span class="metric">🔧 {{ case.tool_count }} tools</span>
                <span class="metric">📊 {{ case.trace.total_tokens.input + case.trace.total_tokens.output }} tokens</span>
            </div>
            <div class="timeline">
                <h4>Timeline</h4>
                {% for msg in case.trace.messages %}
                    {% if msg.role == 'system' or msg.role == 'user' %}
                        <div class="message"><strong>{{ msg.role|upper }}</strong>: {{ msg.content }}</div>
                    {% elif msg.role == 'assistant' %}
                        <div class="message assistant">
                            <strong>ASSISTANT</strong> ({{ msg.latency_ms }}ms)<br>
                            {% if msg.text %}{{ msg.text }}<br>{% endif %}
                            {% for tc in msg.tool_calls %}
                                <div class="tool-call">🔧 {{ tc.name }}: <pre>{{ tc.args|tojson(indent=2) }}</pre></div>
                            {% endfor %}
                        </div>
                    {% elif msg.role == 'tool' %}
                        <div class="message tool">
                            <strong>TOOL: {{ msg.name }}</strong> ({{ msg.latency_ms }}ms)<br>
                            <pre>{{ msg.content|tojson(indent=2) }}</pre>
                        </div>
                    {% endif %}
                {% endfor %}
            </div>
        </div>
        {% endfor %}
        <script>
            document.querySelectorAll('.case').forEach(c => {
                if (c.querySelector('.fail')) {
                    c.classList.add('expanded');
                }
            });
        </script>
    </body>
    </html>"""

        template = Template(template_str)
        html = template.render(
            run_time=datetime.now().isoformat(),
            cases=cases_data,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

    @staticmethod
    def render_single_trace(trace_data: dict) -> str:
        """Render a single trace as HTML snippet."""
        # Simple inline viewer (could use same template with single case)
        trace = trace_data.get("trace", {})
        scores = trace_data.get("scores", {})
        html = f"""
        <html><head><title>Trace {trace.get('run_id', '')}</title>
        <style>body{{font-family:monospace;margin:20px}} .tool{{margin-left:20px}}</style>
        </head><body>
        <h2>Question: {trace.get('question','')}</h2>
        <h3>Answer: {trace.get('final_answer','')}</h3>
        <h4>Pass: {scores.get('overall_pass',False)}</h4>
        <div id="timeline">
        """
        for msg in trace.get("messages", []):
            if msg.get("role") == "assistant":
                html += f"<div><b>Assistant</b> ({msg.get('latency_ms',0)}ms)<br>"
                if msg.get("text"):
                    html += f"Text: {msg['text']}<br>"
                for tc in msg.get("tool_calls", []):
                    html += f"🔧 {tc['name']}: {tc.get('args',{})}<br>"
                html += "</div>"
            elif msg.get("role") == "tool":
                html += f"<div class='tool'>📦 {msg['name']}: <pre>{json.dumps(msg.get('content',''), indent=2)}</pre></div>"
        html += "</div></body></html>"
        return html

    def _count_tool_calls(self, trace: dict) -> int:
        if not trace:
            return 0
        count = 0
        for msg in trace.get("messages", []):
            if msg.get("role") == "assistant":
                count += len(msg.get("tool_calls", []))
        return count

    def _failure_reasons(self, scores: dict) -> str:
        reasons = []
        hard = scores.get("hard", {})
        for check, passed in hard.items():
            if not passed:
                reasons.append(f"Hard check failed: {check}")
        soft = scores.get("soft", {})
        for rubric, result in soft.items():
            if result.get("score", 0) < 0.7:
                reasons.append(f"Soft check '{rubric}' score {result['score']:.2f}: {result.get('rationale','')[:50]}")
        for metric, result in scores.items():
            if metric in ("hard", "soft", "overall_pass"):
                continue
            if isinstance(result, dict) and not result.get("pass", True):
                reasons.append(f"Metric '{metric}' failed: {result.get('reason','')}")
        return "; ".join(reasons) if reasons else "Unknown failure"