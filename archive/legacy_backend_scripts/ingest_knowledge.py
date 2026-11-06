#!/usr/bin/env python3
"""Script de Ingestão e Destilação Médica para o Data Store do MedQuest.

Varre o acervo de materiais de estudo (priorizando Fichas Resumo via pdftotext e
Revisões Rápidas em texto puro), quebra em blocos clínicos semânticos e indexa
no SQLite FTS5 para Grounding do Preceptor IA.
"""

import argparse
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Adiciona o diretório backend ao sys.path para importar api.knowledge
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from api.knowledge import get_knowledge_connection, init_knowledge_schema

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_knowledge")

DEFAULT_SOURCE_DIR = Path("/home/wagmoraes/Documents/Apostilas/Extensivo R1 2027 [Bônus 2026]")
DEFAULT_DB_FILE = BACKEND_DIR / "medknowledge.db"


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extrai texto puro de um PDF usando pdftotext (Poppler) com latência mínima."""
    try:
        res = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout
    except Exception as exc:
        logger.warning("Falha ao extrair texto do PDF %s: %s", pdf_path.name, exc)
        return ""


def chunk_medical_text(
    text: str,
    source_name: str,
    specialty: str,
    topic: str,
    source_type: str,
    max_words: int = 500
) -> List[Dict[str, str]]:
    """
    Divide o texto em blocos semânticos clínicos inteligentes baseados em
    parágrafos, páginas ou cabeçalhos de tópicos.
    """
    if not text.strip():
        return []

    # Divide por quebra de página (form feed do pdftotext) ou blocos duplos de nova linha
    raw_sections = re.split(r'\x0c|\n{3,}', text)
    chunks = []
    current_block: List[str] = []
    current_word_count = 0
    current_title = f"{topic} - Conceitos Gerais"

    for section in raw_sections:
        cleaned_sec = section.strip()
        if not cleaned_sec or len(cleaned_sec) < 50:
            continue

        lines = cleaned_sec.split("\n")
        first_line = lines[0].strip()
        if len(first_line) < 80 and not first_line.endswith((".", ",")):
            potential_title = first_line
        else:
            potential_title = current_title

        sec_words = len(cleaned_sec.split())

        if current_word_count + sec_words > max_words and current_block:
            chunk_content = "\n\n".join(current_block).strip()
            chunks.append({
                "source_file": source_name,
                "source_type": source_type,
                "specialty": specialty,
                "topic": topic,
                "subtopic": current_title,
                "title": current_title,
                "content": chunk_content,
                "word_count": len(chunk_content.split()),
            })
            current_block = [cleaned_sec]
            current_word_count = sec_words
            current_title = potential_title
        else:
            current_block.append(cleaned_sec)
            current_word_count += sec_words
            if potential_title != current_title:
                current_title = potential_title

    if current_block:
        chunk_content = "\n\n".join(current_block).strip()
        chunks.append({
            "source_file": source_name,
            "source_type": source_type,
            "specialty": specialty,
            "topic": topic,
            "subtopic": current_title,
            "title": current_title,
            "content": chunk_content,
            "word_count": len(chunk_content.split()),
        })

    return chunks


def ingest_materials(
    source_root: Path,
    db_path: Path,
    include_apostilas: bool = False,
    specialty_filter: str = ""
) -> Tuple[int, int]:
    """Varre as pastas de estudo e indexa Fichas Resumo e Revisões Rápidas no SQLite FTS5."""
    if not source_root.exists():
        logger.error("Diretório fonte não encontrado: %s", source_root)
        return 0, 0

    conn = get_knowledge_connection(str(db_path))
    init_knowledge_schema(conn)

    total_files = 0
    total_chunks = 0

    # Especialidades (pastas principais: Clínica Médica, Cirurgia Geral, Pediatria, etc.)
    for specialty_dir in sorted(source_root.iterdir()):
        if not specialty_dir.is_dir() or specialty_dir.name.startswith((".", "_", "00")):
            continue

        specialty_name = specialty_dir.name
        if specialty_filter and specialty_filter.lower() not in specialty_name.lower():
            continue

        logger.info("=== Processando Especialidade: %s ===", specialty_name)

        # 1. Processar Fichas Resumo (Prioridade 1)
        fichas_dir = specialty_dir / "Fichas Resumo"
        if not fichas_dir.exists():
            # Alguns diretórios aninham por submódulos (ex: Clínica Médica/Cardiologia/Fichas Resumo)
            for sub_dir in specialty_dir.iterdir():
                if sub_dir.is_dir():
                    sub_fichas = sub_dir / "Fichas Resumo"
                    if sub_fichas.exists():
                        files, chunks = _process_folder(conn, sub_fichas, specialty_name, sub_dir.name, "ficha_resumo")
                        total_files += files
                        total_chunks += chunks
        else:
            files, chunks = _process_folder(conn, fichas_dir, specialty_name, specialty_name, "ficha_resumo")
            total_files += files
            total_chunks += chunks

        # 2. Processar Revisões Rápidas / Transcrições (Prioridade 2)
        transcricoes_dir = specialty_dir / "Transcrições"
        if not transcricoes_dir.exists():
            for sub_dir in specialty_dir.iterdir():
                if sub_dir.is_dir():
                    sub_transc = sub_dir / "Transcrições"
                    if sub_transc.exists():
                        files, chunks = _process_transcriptions(conn, sub_transc, specialty_name, sub_dir.name)
                        total_files += files
                        total_chunks += chunks
        else:
            files, chunks = _process_transcriptions(conn, transcricoes_dir, specialty_name, specialty_name)
            total_files += files
            total_chunks += chunks

        # 3. Apostilas completas (opcional)
        if include_apostilas:
            apostilas_dir = specialty_dir / "Apostilas"
            if not apostilas_dir.exists():
                for sub_dir in specialty_dir.iterdir():
                    if sub_dir.is_dir():
                        sub_apos = sub_dir / "Apostilas"
                        if sub_apos.exists():
                            files, chunks = _process_folder(conn, sub_apos, specialty_name, sub_dir.name, "apostila")
                            total_files += files
                            total_chunks += chunks
            else:
                files, chunks = _process_folder(conn, apostilas_dir, specialty_name, specialty_name, "apostila")
                total_files += files
                total_chunks += chunks

    conn.close()
    return total_files, total_chunks


def _process_folder(conn, folder: Path, specialty: str, topic: str, source_type: str) -> Tuple[int, int]:
    """Processa arquivos PDF em uma pasta específica."""
    f_count = 0
    c_count = 0
    for pdf_file in sorted(folder.glob("*.pdf")):
        # Evita reindexar se o arquivo já existir no banco
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM knowledge_chunks WHERE source_file = ?", (pdf_file.name,))
        if cur.fetchone()[0] > 0:
            continue

        logger.info("Extraindo [%s]: %s", source_type, pdf_file.name)
        text = extract_text_from_pdf(pdf_file)
        if not text:
            continue

        chunks = chunk_medical_text(text, pdf_file.name, specialty, topic, source_type)
        if chunks:
            with conn:
                for c in chunks:
                    conn.execute(
                        """
                        INSERT INTO knowledge_chunks (
                            source_file, source_type, specialty, topic, subtopic,
                            title, content, word_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c["source_file"], c["source_type"], c["specialty"],
                            c["topic"], c["subtopic"], c["title"], c["content"],
                            c["word_count"]
                        )
                    )
            f_count += 1
            c_count += len(chunks)

    return f_count, c_count


def _process_transcriptions(conn, folder: Path, specialty: str, topic: str) -> Tuple[int, int]:
    """Processa arquivos de texto de Revisão Rápida (.txt) em árvores de transcrição."""
    f_count = 0
    c_count = 0
    # Procura arquivos .txt com foco especial em revisões rápidas
    for txt_file in sorted(folder.rglob("*.txt")):
        filename = txt_file.name
        # Prioriza arquivos identificados como 'Revisão rápida'
        is_revisao = "revisão rápida" in filename.lower() or "revisao rapida" in filename.lower()
        if not is_revisao:
            continue

        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) FROM knowledge_chunks WHERE source_file = ?", (filename,))
        if cur.fetchone()[0] > 0:
            continue

        try:
            content = txt_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        if not content.strip():
            continue

        logger.info("Indexando [revisão rápida]: %s", filename)
        chunks = chunk_medical_text(content, filename, specialty, topic, "revisao_rapida")
        if chunks:
            with conn:
                for c in chunks:
                    conn.execute(
                        """
                        INSERT INTO knowledge_chunks (
                            source_file, source_type, specialty, topic, subtopic,
                            title, content, word_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c["source_file"], c["source_type"], c["specialty"],
                            c["topic"], c["subtopic"], c["title"], c["content"],
                            c["word_count"]
                        )
                    )
            f_count += 1
            c_count += len(chunks)

    return f_count, c_count


def main():
    parser = argparse.ArgumentParser(description="Ingestão de Materiais Médicos no Data Store FTS5.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Diretório raiz com as apostilas/fichas"
    )
    parser.add_argument(
        "--db-file",
        type=Path,
        default=DEFAULT_DB_FILE,
        help="Caminho do arquivo SQLite de destino (ex: medknowledge.db)"
    )
    parser.add_argument(
        "--specialty",
        type=str,
        default="",
        help="Filtrar especialidade específica (ex: 'Clínica Médica' ou 'Cardiologia')"
    )
    parser.add_argument(
        "--include-apostilas",
        action="store_true",
        help="Inclui apostilas completas além de fichas resumo e revisões"
    )

    args = parser.parse_args()

    logger.info("Iniciando ingestão médica...")
    logger.info("Fonte: %s", args.source_dir)
    logger.info("Destino: %s", args.db_file)

    files_indexed, chunks_created = ingest_materials(
        source_root=args.source_dir,
        db_path=args.db_file,
        include_apostilas=args.include_apostilas,
        specialty_filter=args.specialty
    )

    logger.info("✅ Concluído! %d arquivos processados, %d blocos clínicos indexados.", files_indexed, chunks_created)


if __name__ == "__main__":
    main()
