from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class ProcessedState:
    processed_files: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: str) -> "ProcessedState":
        if not path or not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(processed_files=set(data.get("processed_files", [])))

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"processed_files": sorted(self.processed_files)}, f, indent=2)

