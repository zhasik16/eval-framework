"""Parallel test runner with retries and caching."""

import asyncio
import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import sys

# Add the deep-research-lite directory to sys.path so we can import agent
AGENT_DIR = Path(__file__).parent.parent / "higgsfield-deep-research-hometask"
sys.path.insert(0, str(AGENT_DIR))

from agent import run_agent


@dataclass
class RunConfig:
    concurrency: int = 3
    repeats: int = 1
    max_retries: int = 3
    base_delay: float = 1.0
    output_dir: Path = Path("traces")
    use_cache: bool = True


@dataclass
class RunResult:
    case: dict
    repeat_idx: int
    run_id: str
    trace: Optional[dict] = None
    error: Optional[str] = None
    wall_time_ms: int = 0


class AgentRunner:
    def __init__(self, config: RunConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.concurrency)
        self.cache_dir = config.output_dir / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def run_batch(self, cases: list[dict]) -> list[RunResult]:
        """Run all cases with repeats in parallel."""
        tasks = []
        for case in cases:
            for repeat_idx in range(self.config.repeats):
                tasks.append(self._run_with_retry(case, repeat_idx))
        return await asyncio.gather(*tasks)

    async def _run_with_retry(self, case: dict, repeat_idx: int) -> RunResult:
        """Run a single case with retries on transient errors."""
        cache_key = self._cache_key(case, repeat_idx)
        if self.config.use_cache:
            cached = self._load_cache(cache_key)
            if cached:
                return cached

        for attempt in range(self.config.max_retries):
            try:
                async with self.semaphore:
                    result = await self._run_once(case, repeat_idx)
                if result.trace:
                    self._save_cache(cache_key, result)
                return result
            except Exception as e:
                if self._is_transient(e) and attempt < self.config.max_retries - 1:
                    delay = self.config.base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
                    continue
                return RunResult(
                    case=case,
                    repeat_idx=repeat_idx,
                    run_id="",
                    error=str(e),
                )

    async def _run_once(self, case: dict, repeat_idx: int) -> RunResult:
        """Execute the agent (in thread pool since it's synchronous)."""
        loop = asyncio.get_event_loop()
        start = time.time()

        def _sync_run():
            return run_agent(case["input"])

        try:
            result = await loop.run_in_executor(None, _sync_run)
            trace = result.to_dict()
            return RunResult(
                case=case,
                repeat_idx=repeat_idx,
                run_id=result.run_id,
                trace=trace,
                wall_time_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            return RunResult(
                case=case,
                repeat_idx=repeat_idx,
                run_id="",
                error=str(e),
                wall_time_ms=int((time.time() - start) * 1000),
            )

    def _is_transient(self, e: Exception) -> bool:
        """Check if error is transient (rate limit, network, 5xx)."""
        msg = str(e).lower()
        return any(x in msg for x in ["429", "rate", "5", "connection", "timeout"])

    def _cache_key(self, case: dict, repeat_idx: int) -> str:
        """Generate cache key from case input and repeat index."""
        data = json.dumps({"input": case["input"], "repeat": repeat_idx}, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    def _load_cache(self, key: str) -> Optional[RunResult]:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
            return RunResult(
                case={"id": data["case_id"], "input": data["input"]},
                repeat_idx=data["repeat_idx"],
                run_id=data["run_id"],
                trace=data["trace"],
                error=None,
            )
        return None

    def _save_cache(self, key: str, result: RunResult):
        cache_file = self.cache_dir / f"{key}.json"
        data = {
            "case_id": result.case["id"],
            "input": result.case["input"],
            "repeat_idx": result.repeat_idx,
            "run_id": result.run_id,
            "trace": result.trace,
        }
        with open(cache_file, "w") as f:
            json.dump(data, f)