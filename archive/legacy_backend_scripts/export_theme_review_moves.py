"""Render the moved questions from a theme-review plan as a readable Markdown file."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PLAN = ROOT / "docs" / "audits" / "theme_abdome_agudo_inflamatorio_review_plan.json"
DEFAULT_DB = ROOT / "app" / "backend" / "medquest.db"
DEFAULT_OUTPUT = ROOT / "docs" / "audits" / "theme_abdome_agudo_inflamatorio_redistribuidas.md"


def render(plan: dict, connection: sqlite3.Connection) -> str:
    source = plan["source"]
    moves = plan.get("moves", [])
    lines = [
        "# Questões redistribuídas — revisão para validação",
        "",
        f"Tema revisado: **{source['area']} · {source['subtema']}**.",
        "",
        f"Foram redistribuídas **{len(moves)} questões**. Esta é uma visualização somente de leitura; o banco não é alterado por este relatório.",
        "",
        "| Questão | Novo tema | Motivo resumido |",
        "| --- | --- | --- |",
    ]
    for move in moves:
        lines.append(f"| {move['question_id']} | {move['area']} · {move['subtema']} | {move['rationale']} |")

    for position, move in enumerate(moves, start=1):
        question = connection.execute(
            """SELECT id, area, subtema, topic, subtema_orig, stem, correct_letter
               FROM questions WHERE id = ?""",
            (move["question_id"],),
        ).fetchone()
        alternatives = connection.execute(
            "SELECT letter, text FROM alternatives WHERE question_id = ? ORDER BY letter",
            (move["question_id"],),
        ).fetchall()
        lines.extend([
            "",
            f"## {position}. Questão {question[0]}",
            "",
            f"- Classificação antes da revisão: `{source['area']} · {source['subtema']}`",
            f"- Classificação proposta: `{move['area']} · {move['subtema']}`",
            f"- Justificativa: {move['rationale']}",
            f"- Tema-fonte informado no banco: {question[3] or '—'}",
            f"- Subtema-fonte informado no banco: {question[4] or '—'}",
            f"- Gabarito registrado: **{question[6] or '—'}**",
            "",
            "### Enunciado",
            "",
            question[5] or "—",
            "",
            "### Alternativas",
            "",
        ])
        for letter, text in alternatives:
            correct = " **(gabarito)**" if letter == question[6] else ""
            lines.append(f"- **{letter}.** {text}{correct}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    with sqlite3.connect(args.db) as connection:
        text = render(plan, connection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(f"Relatório criado: {args.output}")


if __name__ == "__main__":
    main()
