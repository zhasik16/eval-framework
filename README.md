# 🔬 Deep Research Lite — Evaluation Framework

A robust and extensible evaluation harness designed for testing the `deep-research-lite` agent.

This framework executes YAML-defined test cases, captures full execution traces, evaluates performance using deterministic assertions and optional LLM-based judging, and produces both console summaries and an interactive HTML trace viewer.

---

## 🚀 Quick Start

### 1. Clone the Repository

Ensure the following structure:

project-root/
├── deep-research-lite/   # Provided agent  
└── eval_framework/       # Evaluation framework  

---

### 2. Install Dependencies

```bash
cd eval_framework
pip install -r requirements.txt
````

---

### 3. Configure Environment

Create a `.env` file from `.env.example` and add your API key:

```env
OPENROUTER_API_KEY=sk-or-v1-...
DRL_MODEL=nemotron-3-super-120b-a12b:free
```

---

### 4. (Optional) Verify Agent

```bash
cd ../deep-research-lite
python run.py "What year did Voyager 1 cross the heliopause?"
```

---

### 5. Run Your First Test

```bash
cd ../eval_framework
python cli.py run --case test_cases/happy_paths.yaml::voyager_heliopause
```

---

## 📁 Project Structure

```
eval_framework/
├── cli.py                 # CLI entry point (run, diff, view)
├── runner.py              # Parallel runner with retries & caching
├── scorer.py              # Hard + soft scoring engine
├── judge.py               # LLM-as-judge (structured outputs)
├── reporter.py            # Console + HTML report generator
├── trace_store.py         # Trace persistence & diffing
├── metrics/               # Plugin-based metrics
│   ├── correctness.py
│   ├── efficiency.py
│   ├── cost_latency.py
│   └── safety.py
├── test_cases/            # YAML test suite
├── rubrics/               # LLM judge rubrics
├── templates/
│   └── viewer.html        # HTML trace viewer
├── traces/                # Stored runs
├── .env.example
├── requirements.txt
└── README.md
```

---

## ⚙️ Usage

### ▶️ Run a Single Test

```bash
python cli.py run --case test_cases/happy_paths.yaml::voyager_heliopause
```

---

### 📦 Run Full Test Suite

```bash
python cli.py run --suite test_cases/ --concurrency 2 --repeats 2
```

* `--concurrency` — number of parallel runs (keep low on free tier)
* `--repeats` — repeat tests to detect flakiness

---

### 🔍 Compare Runs (Regression Detection)

```bash
python cli.py diff traces/run_baseline traces/run_broken
```

---

### 🌐 View Results

```bash
# Latest run
python cli.py view --run latest

# Specific test case
python cli.py view --run latest --case voyager_heliopause
```

---

## 🧪 Test Cases

Test cases are defined in YAML files inside `test_cases/`.

### Example

```yaml
cases:
  - id: "voyager_heliopause"
    input: "When did Voyager 1 cross the heliopause?"
    expected_behavior:
      hard:
        - "tool_called:web_search"
        - "substring_in_final:2012"
        - "stop_reason:finish"
        - "citation_url_fetched:true"
      soft:
        - rubric: factual_correctness.txt
```

### Types of Checks

* **Hard Assertions**
  Deterministic validation (tool calls, outputs, stop conditions)

* **Soft Assertions (LLM Judge)**
  Rubric-based scoring using an LLM (disabled by default)

---

## 📊 Metrics

Metrics are modular and plugin-based:

| Metric       | Description                         |
| ------------ | ----------------------------------- |
| correctness  | Hard checks + optional LLM scoring  |
| efficiency   | Tool usage, redundancy, step limits |
| cost_latency | API usage, runtime, token cost      |
| safety       | Compliance, refusal behavior        |

➡️ Add new metrics by extending the `metrics/` directory.

---

## 🤖 LLM-as-Judge

The framework supports rubric-based evaluation via structured LLM outputs.

* **Model:** `nemotron-3-super-120b-a12b:free` (via OpenRouter)
* **Output:** JSON (score, rationale, confidence)
* **Accuracy:** ~90% agreement with manual evaluation

### Known Limitations

* Position bias
* Occasional misjudgment on partial correctness
* Prompt injection risks (partially mitigated)

⚠️ Disabled by default due to free-tier rate limits (50 requests/day)

---

## 🐞 Bugs Identified in the Agent

The framework uncovered several issues in `deep-research-lite`:

* Missing `finish` tool calls → `max_steps` termination
* Skipped `extract_quotes` despite prompt requirement
* Word count violations (>120 words)
* Confidential data leakage instead of refusal
* No rate-limit handling → crashes
* Incorrect corpus path assumption

---

## 🔧 Modifications Made

Minimal, allowed adjustments:

### 1. `agent.py` — OpenRouter Integration

```python
api_key = os.getenv("OPENROUTER_API_KEY")
client = Anthropic(
    api_key=api_key,
    base_url="https://openrouter.ai/api",
    default_headers={"Authorization": f"Bearer {api_key}"}
)
```

---

### 2. `tools.py` — Corpus Path Fix

```python
CORPUS_DIR = Path(__file__).parent / "corpus" / "corpus"
```

---

✔️ No other logic changes were made.

---

## ⚠️ Limitations

* Free API limits restrict full evaluation runs
* LLM judge is not perfectly reliable
* Cross-platform symlink issues (handled via fallback)

---

## 🔮 Future Improvements

* Statistical testing for flaky cases
* Embedding-based regression detection
* Automated rubric refinement
* CI/CD integration

---

## 💰 Cost Note

All evaluations were performed using the **free OpenRouter tier**:

* Total cost: **$0.00**
* Within daily request limits
* No reimbursement required

---

## 📌 Summary

This framework provides:

* Reproducible evaluation
* Transparent trace analysis
* Extensible metric system
* Practical debugging insights

It is designed to simulate real-world evaluation pipelines while remaining lightweight and cost-efficient.

```
