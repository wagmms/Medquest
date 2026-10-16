#!/usr/bin/env python3
"""
Aplica a taxonomia canônica oficial dos 170 temas no banco de dados MedQuest.
Utiliza os mapeamentos gerados pelo Gemini 4 Argon e corrige tópicos incongruentes.
"""

import sqlite3
import json
import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "backend")
DB_PATH = os.path.join(BACKEND_DIR, "medquest.db")
TAXONOMY_PATH = os.path.join(BACKEND_DIR, "data", "taxonomy.json")
MAPPING_PATH = os.path.join(BACKEND_DIR, "data", "legacy_subtemas_mapping.json")

def main():
    print("🚀 Iniciando aplicação da taxonomia canônica oficial dos 170 temas...")
    
    with open(TAXONOMY_PATH) as f:
        tax = json.load(f)
    
    canonical_themes = set()
    for entry in tax:
        for mt in entry["macroThemes"]:
            canonical_themes.add(mt["theme"].strip())
            
    with open(MAPPING_PATH) as f:
        mapping = json.load(f)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Inicia transação
    conn.execute("BEGIN TRANSACTION")
    try:
        # 1. Atualiza subtemas legados usando o mapeamento do Gemini 4 Argon
        updated_subtemas = 0
        for legacy_sub, canonical_target in mapping.items():
            if canonical_target in canonical_themes:
                cursor.execute("""
                    UPDATE questions 
                    SET subtema_orig = COALESCE(subtema_orig, subtema),
                        subtema = ?
                    WHERE subtema = ?
                """, (canonical_target, legacy_sub))
                updated_subtemas += cursor.rowcount
                
        print(f"📊 Questões com subtema normalizado para tema canônico: {updated_subtemas}")
        
        # 2. Corrige anomalias severas de topic descolado do subtema clínico
        # Ex: questões onde topic era 'Sala de Parto' ou 'Gestação' em Clínica Médica ou Preventiva
        cursor.execute("""
            UPDATE questions
            SET topic = subtema
            WHERE (
                (area = 'Medicina Preventiva' AND (topic LIKE '%Parto%' OR topic LIKE '%Gestação%' OR topic LIKE '%Puerpério%'))
                OR (area = 'Clínica Médica' AND (topic LIKE '%Parto%' OR topic LIKE '%Puerpério%' OR topic LIKE '%Cesariana%'))
                OR (area = 'Cirurgia' AND (topic = 'Sala de Parto' OR topic = 'Puerpério'))
            )
        """)
        fixed_topics = cursor.rowcount
        print(f"🩺 Tópicos severamente desvirtuados alinhados ao subtema clínico: {fixed_topics}")
        
        # 3. Estatísticas Finais de Aderência
        cursor.execute("SELECT subtema, count(*) FROM questions GROUP BY subtema")
        sub_counts = cursor.fetchall()
        
        canonical_count = 0
        total_questions = 0
        for s, cnt in sub_counts:
            total_questions += cnt
            if s and s.strip() in canonical_themes:
                canonical_count += cnt
                
        pct = (canonical_count / total_questions) * 100
        print(f"\n=======================================================")
        print(f"✅ Total de Questões: {total_questions}")
        print(f"🎯 Questões em Temas Canônicos Oficiais: {canonical_count} ({pct:.2f}%)")
        print(f"=======================================================\n")
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao aplicar taxonomia canônica. Rollback executado: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
