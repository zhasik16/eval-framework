"""LLM-as-judge with structured output."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any
import time
import random

from anthropic import Anthropic


class LLMJudge:
    def __init__(self, model: str = "nemotron-3-super-120b-a12b:free"):
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("No API key found for judge. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.")
        
        # Use OpenRouter configuration if OPENROUTER_API_KEY is set
        if os.getenv("OPENROUTER_API_KEY"):
            self.client = Anthropic(
                api_key=api_key,
                base_url="https://openrouter.ai/api",
                default_headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "Deep Research Lite Judge",
                },
            )
        else:
            self.client = Anthropic(api_key=api_key)
        self.model = model

    def evaluate(self, rubric_path: Path, context: Dict[str, Any]) -> Dict[str, Any]:
        rubric = rubric_path.read_text()
        prompt = self._build_prompt(rubric, context)

        max_retries = 8
        base_delay = 5.0  # seconds

        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}]
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    delay = base_delay * (1.5 ** attempt) + random.uniform(0, 2)
                    print(f"Rate limited, waiting {delay:.1f}s...", file=sys.stderr)
                    time.sleep(delay)
                    continue
                raise

        text_blocks = [block.text for block in response.content if block.type == "text"]
        if not text_blocks:
            raw = str(response.content)
        else:
            raw = "".join(text_blocks) 

        # Parse JSON from response
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Attempt to extract JSON from markdown code block
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            # Try to find any JSON object
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            # Fallback
            return {
                "score": 0.0,
                "rationale": f"Failed to parse judge output: {raw[:100]}",
                "confidence": 0.0,
            }

    def _build_prompt(self, rubric: str, context: Dict[str, Any]) -> str:
        """Construct the judge prompt."""
        return f"""You are an evaluator. Given a rubric and the agent's output, provide a structured assessment.

RUBRIC:
{rubric}

CONTEXT:
Question: {context['question']}
Agent's Answer: {context['answer']}
Citations: {context['citations']}
Tool Usage: {context['trace_summary']}

Evaluate the answer according to the rubric. Return a JSON object with:
- "score": float between 0.0 and 1.0
- "rationale": string explaining your scoring
- "confidence": float between 0.0 and 1.0 (how confident you are in this assessment)

Return ONLY the JSON object, no other text."""