from .correctness import evaluate_correctness
from .efficiency import evaluate_efficiency
from .cost_latency import evaluate_cost_latency
from .safety import evaluate_safety

METRICS = {
    "correctness": evaluate_correctness,
    "efficiency": evaluate_efficiency,
    "cost_latency": evaluate_cost_latency,
    "safety": evaluate_safety,
}