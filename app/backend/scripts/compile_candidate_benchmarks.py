import glob
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path("app/backend")
EXAMS_DIR = BACKEND_DIR / "data" / "medway_extracted" / "exams"
OUTPUT_FILE = BACKEND_DIR / "data" / "institution_candidate_benchmarks.json"

INSTITUTION_MAP = {
    "USP-SP": ["USP-SP", "USP SP"],
    "USP-RP": ["USP-RP", "USP RP"],
    "UNICAMP": ["UNICAMP"],
    "UNIFESP": ["UNIFESP"],
    "SUS-SP": ["SUS-SP", "SUS", "SUS SP"],
    "ENARE": ["ENARE"],
}

reverse_inst_map = {}
for canon, aliases in INSTITUTION_MAP.items():
    for a in aliases:
        reverse_inst_map[a.upper()] = canon

conn = sqlite3.connect(BACKEND_DIR / "medquest.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Carregando questões do banco com fonte de track...")
cursor.execute("""
    SELECT q.id, q.source_file, q.source_number, q.institution_code, q.area, q.correct_letter
    FROM questions q
    WHERE q.source_file LIKE '%[%]' AND q.area IS NOT NULL
""")
all_q = cursor.fetchall()
print(f"Total de questões avaliadas: {len(all_q)}")

re_tid = re.compile(r"\[(\d+)\]")

track_cache = {}
def get_track(tid):
    if tid not in track_cache:
        p = EXAMS_DIR / f"track_{tid}.json"
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    track_cache[tid] = json.load(f)
            except Exception:
                track_cache[tid] = None
        else:
            track_cache[tid] = None
    return track_cache[tid]

banca_area_scores = defaultdict(list)
banca_scores = defaultdict(list)
banca_diff_counts = defaultdict(lambda: defaultdict(int))
question_benchmarks = {}

for q in all_q:
    raw_inst = (q["institution_code"] or "").strip().upper()
    canon_inst = reverse_inst_map.get(raw_inst, raw_inst)
    area = q["area"]
    c_let = q["correct_letter"]
    qid = q["id"]
    
    m = re_tid.search(q["source_file"])
    if not m:
        continue
    tdata = get_track(m.group(1))
    if not tdata or not isinstance(tdata, dict):
        continue
    tqs = tdata.get("questions", [])
    sn = q["source_number"]
    if not sn or sn < 1 or sn > len(tqs):
        continue
    cand = tqs[sn - 1]
    det = cand.get("detail", {})
    opts = det.get("options", [])
    ans_count = det.get("answer_count", 0)
    
    cand_pct = None
    for o in opts:
        if o.get("letter") == c_let and o.get("response_percentage") is not None:
            cand_pct = float(o["response_percentage"])
            break
            
    if cand_pct is not None:
        cand_acc = round(cand_pct / 100.0, 4)
        diff_tier = "facil" if cand_acc >= 0.75 else ("media" if cand_acc >= 0.50 else "dificil")
        question_benchmarks[str(qid)] = {
            "p": cand_acc,
            "tier": diff_tier,
            "n": ans_count
        }
        banca_area_scores[(canon_inst, area)].append(cand_acc)
        banca_scores[canon_inst].append(cand_acc)
        banca_diff_counts[canon_inst][diff_tier] += 1
        
        # Também acumula no geral
        banca_area_scores[("GERAL", area)].append(cand_acc)
        banca_scores["GERAL"].append(cand_acc)
        banca_diff_counts["GERAL"][diff_tier] += 1

# Compilar resumo por instituição
benchmarks_summary = {}
CANONICAL_AREAS = [
    "Clínica Médica",
    "Cirurgia",
    "Ginecologia e Obstetrícia",
    "Pediatria",
    "Medicina Preventiva",
]

for b in ["USP-SP", "USP-RP", "UNICAMP", "UNIFESP", "SUS-SP", "ENARE", "GERAL"]:
    scores = banca_scores.get(b, [])
    if not scores:
        continue
    tot = len(scores)
    avg = round(sum(scores) / tot, 4)
    diffs = banca_diff_counts[b]
    
    area_dict = {}
    for area in CANONICAL_AREAS:
        a_scores = banca_area_scores.get((b, area), [])
        if a_scores:
            a_avg = round(sum(a_scores) / len(a_scores), 4)
            area_dict[area] = {
                "candidate_accuracy": a_avg,
                "question_count": len(a_scores)
            }
        else:
            # Fallback para média geral da área
            g_scores = banca_area_scores.get(("GERAL", area), [])
            g_avg = round(sum(g_scores) / len(g_scores), 4) if g_scores else 0.70
            area_dict[area] = {
                "candidate_accuracy": g_avg,
                "question_count": 0
            }
            
    benchmarks_summary[b] = {
        "institution_code": b,
        "overall_candidate_accuracy": avg,
        "total_questions": tot,
        "difficulty_distribution": {
            "facil": round(diffs["facil"] / tot, 4),
            "media": round(diffs["media"] / tot, 4),
            "dificil": round(diffs["dificil"] / tot, 4)
        },
        "areas": area_dict
    }

output_data = {
    "generated_at": "2026-10-07T13:15:00Z",
    "institutions": benchmarks_summary,
    "question_benchmarks": question_benchmarks
}

print(f"Salvando em {OUTPUT_FILE}...")
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False)

print(f"Sucesso! Gerados benchmarks para {len(benchmarks_summary)} instituições e {len(question_benchmarks)} questões.")
