"""Create a complete, read-only review queue for the 170 canonical themes.

The manifest is deliberately based on the repository's canonical 170-theme
catalogue rather than the application's live catalogue.  It gives each
question one explicit pending review record in the theme where it currently
resides, while separately exposing questions currently attached to labels
outside that catalogue.  No database content is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "app" / "backend" / "medquest.db"
DEFAULT_TAXONOMY = ROOT / "canonical_taxonomy_170.json"
DEFAULT_OUTPUT = ROOT / "docs" / "audits" / "theme_review_manifest_170.json"


def load_taxonomy(path: Path) -> dict[str, list[str]]:
    taxonomy = json.loads(path.read_text(encoding="utf-8"))
    count = sum(len(themes) for themes in taxonomy.values())
    if count != 170:
        raise ValueError(f"A taxonomia informada contém {count} temas; esperados 170.")
    return taxonomy


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def question_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "question_id": row["id"],
        "current_area": row["area"],
        "current_subtema": row["subtema"],
        "source_topic": row["topic"] or "",
        "source_subtema": row["subtema_orig"] or "",
        "review_status": "pending",
        "final_area": None,
        "final_subtema": None,
        "rationale": None,
    }


def build_manifest(db_path: Path, taxonomy_path: Path) -> dict[str, object]:
    taxonomy = load_taxonomy(taxonomy_path)
    valid_destinations = {(area, theme) for area, themes in taxonomy.items() for theme in themes}

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        questions = connection.execute(
            """
            SELECT id, area, subtema, topic, subtema_orig
            FROM questions
            ORDER BY area, subtema, id
            """
        ).fetchall()
    finally:
        connection.close()

    by_destination: dict[tuple[str, str], list[sqlite3.Row]] = {}
    out_of_catalogue: list[sqlite3.Row] = []
    for row in questions:
        destination = (row["area"], row["subtema"])
        if destination in valid_destinations:
            by_destination.setdefault(destination, []).append(row)
        else:
            out_of_catalogue.append(row)

    themes = []
    for area, area_themes in taxonomy.items():
        for theme in area_themes:
            rows = by_destination.get((area, theme), [])
            themes.append(
                {
                    "area": area,
                    "theme": theme,
                    "question_count": len(rows),
                    "review_status": "not_started",
                    "questions": [question_record(row) for row in rows],
                }
            )

    out_of_catalogue_by_label = Counter((row["area"], row["subtema"]) for row in out_of_catalogue)
    return {
        "purpose": "Fila de revisão humana, tema por tema, de todas as questões.",
        "generated_at": datetime.now(UTC).isoformat(),
        "database": str(db_path.relative_to(ROOT)),
        "canonical_taxonomy": str(taxonomy_path.relative_to(ROOT)),
        "canonical_taxonomy_sha256": digest(taxonomy_path),
        "canonical_theme_count": 170,
        "database_question_count": len(questions),
        "questions_in_canonical_queue": sum(theme["question_count"] for theme in themes),
        "questions_outside_canonical_catalogue": len(out_of_catalogue),
        "out_of_catalogue_labels": [
            {"area": area, "subtema": subtema, "question_count": count}
            for (area, subtema), count in sorted(out_of_catalogue_by_label.items())
        ],
        "review_rules": [
            "Ler enunciado e alternativas antes de decidir.",
            "Escolher exatamente um dos 170 temas canônicos.",
            "Não concluir um tema enquanto alguma questão permanecer pending.",
            "Registrar justificativa clínica curta para cada mudança ou caso limítrofe.",
        ],
        "themes": themes,
        "out_of_catalogue_questions": [question_record(row) for row in out_of_catalogue],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = build_manifest(args.db, args.taxonomy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Manifesto criado: {args.output}\n"
        f"Temas: {manifest['canonical_theme_count']}\n"
        f"Questões na fila: {manifest['questions_in_canonical_queue']}\n"
        f"Questões fora do catálogo: {manifest['questions_outside_canonical_catalogue']}"
    )


if __name__ == "__main__":
    main()
