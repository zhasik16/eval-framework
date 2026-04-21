"""Persistent storage for trace files."""

import json
from pathlib import Path
from typing import Dict, List, Optional


class TraceStore:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def save_run(self, run_id: str, case_id: str, trace: dict, scores: dict) -> Path:
        """Save trace and scores for a case within a run."""
        run_dir = self.base_dir / run_id
        run_dir.mkdir(exist_ok=True)
        file_path = run_dir / f"{case_id}.json"
        with open(file_path, "w") as f:
            json.dump({"trace": trace, "scores": scores}, f, indent=2, default=str)
        
        # Instead of symlink, write the latest run ID to a simple file
        latest_file = self.base_dir / "LATEST_RUN.txt"
        latest_file.write_text(run_id)
        
        return file_path

    def get_latest_run_id(self) -> Optional[str]:
        """Return the ID of the most recent run."""
        latest_file = self.base_dir / "LATEST_RUN.txt"
        if latest_file.exists():
            return latest_file.read_text().strip()
        return None

    def load_trace(self, run_id: str, case_id: str) -> Dict:
        """Load a stored trace."""
        path = self.base_dir / run_id / f"{case_id}.json"
        with open(path) as f:
            return json.load(f)

    def list_runs(self) -> List[str]:
        """List all run directories (excluding cache)."""
        return [
            d.name for d in self.base_dir.iterdir()
            if d.is_dir() and d.name not in (".cache",)
        ]

    def list_cases(self, run_id: str) -> List[str]:
        """List case IDs in a run."""
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return []
        return [p.stem for p in run_dir.glob("*.json")]