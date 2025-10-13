from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

import typer

from config.settings import get_settings
from src.rag_engine import ask_question, load_vector_store

app = typer.Typer(help="Evaluacion offline del asistente.")


@dataclass
class TestCase:
    question: str
    expected_answer: str


def load_test_cases(path: Path) -> List[TestCase]:
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el dataset de evaluacion: {path}")

    with path.open("r", encoding="utf-8") as fp:
        raw_cases = json.load(fp)

    return [TestCase(**case) for case in raw_cases]


def compute_overlap(expected: str, actual: str) -> float:
    expected_tokens = set(expected.lower().split())
    actual_tokens = set(actual.lower().split())
    if not expected_tokens:
        return 0.0
    return len(expected_tokens & actual_tokens) / len(expected_tokens)


@app.command()
def evaluate(dataset: Path | None = None) -> None:
    settings = get_settings()
    dataset_path = dataset or (settings.knowledge_base_path / "eval_dataset.json")
    test_cases = load_test_cases(dataset_path)

    vector_store = load_vector_store()

    scores = []
    for case in test_cases:
        response = ask_question(vector_store, case.question)
        answer = response.get("answer", "")
        overlap = compute_overlap(case.expected_answer, answer)
        scores.append(overlap)
        typer.echo(f"Q: {case.question}\nOverlap: {overlap:.2f}\n")

    average_score = sum(scores) / len(scores) if scores else 0.0
    typer.echo(f"Puntaje promedio: {average_score:.2f}")


if __name__ == "__main__":
    app()
