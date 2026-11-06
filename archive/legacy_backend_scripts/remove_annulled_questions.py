"""Inspect and remove explicitly annulled questions, keeping a recovery archive."""
import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def inspect(query):
    rows = query("""SELECT q.*, e.explanation_text FROM questions q
                    LEFT JOIN explanations e ON e.question_id=q.id""")
    selected = []
    for row in rows:
        header = (row.get("explanation_text") or "").strip().split("\n")[0]
        if (str(row.get("correct_letter", "")).strip().upper() == "ANULADA"
                or re.search(r"^\*\*Gabarito\*\*\s*:.*\bANULADA\b", header, re.I)):
            selected.append(row)
    tables = query("SELECT name, sql FROM sqlite_master WHERE type='table'")
    related = [r['name'] for r in query("""SELECT DISTINCT m.name
        FROM sqlite_master m JOIN pragma_table_info(m.name) p
        WHERE m.type='table' AND p.name='question_id'""")]
    return selected, related, tables


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--remote', action='store_true')
    parser.add_argument('--schema', action='store_true')
    parser.add_argument('--finish-local-archive', type=Path)
    args = parser.parse_args()
    if args.remote:
        import requests
        from sync_database_turso import run_pipeline_query
        session = requests.Session()
        query = lambda sql: run_pipeline_query(session, sql)
        conn = None
        label = 'turso'
    else:
        conn = sqlite3.connect(ROOT / 'medquest.db')
        conn.row_factory = sqlite3.Row
        query = lambda sql: [dict(r) for r in conn.execute(sql).fetchall()]
        label = 'local'
    if args.finish_local_archive:
        assert conn is not None and args.apply
        archive = json.loads(args.finish_local_archive.read_text(encoding='utf-8'))
        assert archive['database'] == 'local'
        proposal_ids = ','.join(str(int(r['id'])) for r in archive['tables']['classification_proposals'])
        reviews = query(f'SELECT * FROM classification_reviews WHERE proposal_id IN ({proposal_ids})')
        if reviews:
            archive['tables']['classification_reviews'] = reviews
            args.finish_local_archive.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding='utf-8')
            with conn:
                conn.execute(f'DELETE FROM classification_reviews WHERE proposal_id IN ({proposal_ids})')
        assert not query(f'SELECT * FROM classification_reviews WHERE proposal_id IN ({proposal_ids})')
        print(json.dumps({'archived_and_removed_classification_reviews': len(reviews)}))
        return
    if args.schema:
        print(json.dumps(query("""SELECT m.name, f.* FROM sqlite_master m
            JOIN pragma_foreign_key_list(m.name) f WHERE m.type='table'""")))
        return
    selected, related, tables = inspect(query)
    print(json.dumps({'database': label, 'count': len(selected),
                      'related_tables': related,
                      'fts_tables': [t for t in tables if 'fts' in t['name']],
                      'examples': [{'id': r['id'], 'correct_letter': r['correct_letter'],
                                    'header': (r['explanation_text'] or '').split('\n')[0]} for r in selected[:8]]}, ensure_ascii=True))
    if args.apply:
        if not selected:
            print('Nothing to delete.')
            return
        ids = ','.join(str(int(row['id'])) for row in selected)
        archive = {'database': label, 'tables': {}}
        archive['tables']['questions'] = query(f'SELECT * FROM questions WHERE id IN ({ids})')
        for table in related:
            archive['tables'][table] = query(f'SELECT * FROM {quote(table)} WHERE question_id IN ({ids})')
        proposal_ids = ','.join(str(int(r['id'])) for r in archive['tables'].get('classification_proposals', []))
        has_reviews = any(t['name'] == 'classification_reviews' for t in tables)
        if proposal_ids and has_reviews:
            archive['tables']['classification_reviews'] = query(
                f'SELECT * FROM classification_reviews WHERE proposal_id IN ({proposal_ids})')
        folder = ROOT / 'backups'
        folder.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = folder / f'annulled-questions-{label}-{stamp}.json'
        backup.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding='utf-8')
        total_before = int(query('SELECT COUNT(*) AS n FROM questions')[0]['n'])
        statements = [f'DELETE FROM {quote(t)} WHERE question_id IN ({ids})' for t in related]
        if proposal_ids and has_reviews:
            statements.insert(0, f'DELETE FROM classification_reviews WHERE proposal_id IN ({proposal_ids})')
        fts = next((t for t in tables if t['name'] == 'questions_fts'), None)
        if fts and "content='questions'" not in fts['sql']:
            statements.append(f'DELETE FROM questions_fts WHERE rowid IN ({ids})')
        statements.append(f'DELETE FROM questions WHERE id IN ({ids})')
        if fts and "content='questions'" in fts['sql']:
            statements.append("INSERT INTO questions_fts(questions_fts) VALUES ('rebuild')")
        if conn is not None:
            with conn:
                for sql in statements:
                    conn.execute(sql)
        else:
            from sync_database_turso import PIPELINE_URL, HEADERS
            sqls = ['BEGIN IMMEDIATE', *statements, 'COMMIT']
            steps = []
            for index, sql in enumerate(sqls):
                step = {'stmt': {'sql': sql}}
                if index:
                    step['condition'] = {'type': 'ok', 'step': index - 1}
                steps.append(step)
            response = session.post(PIPELINE_URL, headers=HEADERS, json={
                'requests': [{'type': 'batch', 'batch': {'steps': steps}}, {'type': 'close'}]
            }, timeout=60)
            response.raise_for_status()
            result = response.json()['results'][0]
            if result['type'] == 'error':
                raise RuntimeError(result['error'])
            errors = result['response']['result']['step_errors']
            if any(errors):
                raise RuntimeError(errors)
        remaining = int(query(f'SELECT COUNT(*) AS n FROM questions WHERE id IN ({ids})')[0]['n'])
        total_after = int(query('SELECT COUNT(*) AS n FROM questions')[0]['n'])
        assert remaining == 0
        assert total_before - total_after == len(selected)
        for table in related:
            assert int(query(f'SELECT COUNT(*) AS n FROM {quote(table)} WHERE question_id IN ({ids})')[0]['n']) == 0
        print(json.dumps({'deleted': len(selected), 'total_before': total_before,
                          'total_after': total_after, 'remaining_selected': remaining,
                          'backup': str(backup)}))


if __name__ == '__main__':
    main()
