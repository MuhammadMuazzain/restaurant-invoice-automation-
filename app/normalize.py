from __future__ import annotations

import csv
import os
from dataclasses import dataclass

from rapidfuzz import fuzz, process


def _clean(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


@dataclass(frozen=True)
class NormalizationResult:
    normalized_name: str
    score: float
    matched_alias: str


class ItemNormalizer:
    def __init__(self, aliases_csv_path: str, *, min_score: float = 88.0) -> None:
        self.aliases_csv_path = aliases_csv_path
        self.min_score = min_score
        self._alias_to_norm: dict[str, str] = {}
        self._aliases: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self.aliases_csv_path or not os.path.exists(self.aliases_csv_path):
            self._alias_to_norm = {}
            self._aliases = []
            return

        alias_to_norm: dict[str, str] = {}
        with open(self.aliases_csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                norm = _clean(row.get("normalized_name", ""))
                alias = _clean(row.get("alias", ""))
                if norm and alias:
                    alias_to_norm[alias] = norm

        self._alias_to_norm = alias_to_norm
        self._aliases = list(alias_to_norm.keys())

    def normalize(self, raw_item_name: str) -> NormalizationResult:
        raw_clean = _clean(raw_item_name)
        if not raw_clean:
            return NormalizationResult(normalized_name="", score=0.0, matched_alias="")

        if raw_clean in self._alias_to_norm:
            return NormalizationResult(
                normalized_name=self._alias_to_norm[raw_clean],
                score=100.0,
                matched_alias=raw_clean,
            )

        if not self._aliases:
            return NormalizationResult(normalized_name=raw_clean, score=0.0, matched_alias="")

        match = process.extractOne(raw_clean, self._aliases, scorer=fuzz.token_sort_ratio)
        if not match:
            return NormalizationResult(normalized_name=raw_clean, score=0.0, matched_alias="")

        alias, score, _idx = match
        if score >= self.min_score:
            return NormalizationResult(
                normalized_name=self._alias_to_norm[alias],
                score=float(score),
                matched_alias=alias,
            )

        return NormalizationResult(normalized_name=raw_clean, score=float(score), matched_alias=alias)

