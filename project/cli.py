#!/usr/bin/env python3
"""Evaluation framework CLI for Deep Research Lite."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
import yaml
from dotenv import load_dotenv

from runner import AgentRunner, RunConfig
from scorer import Scorer
from judge import LLMJudge
from reporter import Reporter
from trace_store import TraceStore
from metrics import METRICS

load_dotenv()


@click.group()
def cli():
    """Deep Research Lite Evaluation Framework"""
    pass


@cli.command()
@click.option("--case", "-c", help="Single case file or 'file.yaml::case_id'")
@click.option("--suite", "-s", help="Directory containing test cases")
@click.option("--concurrency", "-j", default=3, help="Number of parallel runs")
@click.option("--repeats", "-n", default=1, help="Repeat each case N times")
@click.option("--output-dir", default="traces", help="Directory to store traces")
@click.option("--no-cache", is_flag=True, help="Ignore cached traces")
def run(case, suite, concurrency, repeats, output_dir, no_cache):
    """Run evaluation on test cases."""
    # Load cases
    cases = []
    if case:
        cases = _load_case(case)
    elif suite:
        cases = _load_suite(suite)
    else:
        click.echo("Must specify --case or --suite", err=True)
        sys.exit(1)

    config = RunConfig(
        concurrency=concurrency,
        repeats=repeats,
        output_dir=Path(output_dir),
        use_cache=not no_cache,
    )

    judge = LLMJudge(model="nemotron-3-super-120b-a12b:free")
    scorer = Scorer(METRICS, judge)
    runner = AgentRunner(config)
    store = TraceStore(config.output_dir)

    # Run async
    async def _run():
        results = await runner.run_batch(cases)
        # Score each result
        scored = []
        for res in results:
            if res.trace:
                scores = scorer.score(res.case, res.trace)
                scored.append((res, scores))
                store.save_run(res.run_id, res.case["id"], res.trace, scores)
        return scored

    scored_results = asyncio.run(_run())

    # Generate report
    reporter = Reporter()
    report = reporter.generate_run_report(scored_results, repeats=repeats)
    click.echo(report)

    # Save HTML viewer
    viewer_path = config.output_dir / "latest" / "report.html"
    reporter.generate_html_viewer(scored_results, viewer_path)
    click.echo(f"\nHTML report: {viewer_path}")


@cli.command()
@click.argument("run_a")
@click.argument("run_b")
@click.option("--output-dir", default="traces", help="Traces directory")
def diff(run_a, run_b, output_dir):
    """Compare two runs and show regressions."""
    store = TraceStore(Path(output_dir))
    reporter = Reporter()
    diff_report = reporter.generate_diff(store, run_a, run_b)
    click.echo(diff_report)


@cli.command()
@click.option("--run", "-r", default="latest", help="Run ID or 'latest'")
@click.option("--case", "-c", help="Case ID to view")
@click.option("--output-dir", default="traces", help="Traces directory")
def view(run, case, output_dir):
    """Open trace viewer in browser."""
    store = TraceStore(Path(output_dir))
    if run == "latest":
        latest = store.get_latest_run_id()
        if latest:
            run = latest
        else:
            runs = store.list_runs()
            if not runs:
                click.echo("No runs found", err=True)
                sys.exit(1)
            run = sorted(runs)[-1]

    if case:
        # Single case viewer
        trace_data = store.load_trace(run, case)
        html = Reporter.render_single_trace(trace_data)
        temp_file = Path(f"/tmp/trace_{run}_{case}.html")
        temp_file.write_text(html)
        click.launch(str(temp_file))
    else:
        # Run summary viewer
        viewer_path = store.base_dir / run / "report.html"
        if viewer_path.exists():
            click.launch(str(viewer_path))
        else:
            click.echo(f"No report.html found for run {run}")


def _load_case(spec: str) -> list[dict]:
    """Load a single case. Format: 'file.yaml::case_id' or just file."""
    if "::" in spec:
        file_path, case_id = spec.split("::", 1)
        with open(file_path) as f:
            data = yaml.safe_load(f)
        for case in data.get("cases", []):
            if case["id"] == case_id:
                return [case]
        raise ValueError(f"Case {case_id} not found in {file_path}")
    else:
        with open(spec) as f:
            data = yaml.safe_load(f)
        return data.get("cases", [])


def _load_suite(dir_path: str) -> list[dict]:
    """Load all YAML files from directory."""
    cases = []
    for yaml_file in Path(dir_path).glob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
            cases.extend(data.get("cases", []))
    return cases


if __name__ == "__main__":
    cli()