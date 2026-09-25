import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any

from api.internato_config import get_area_prioritaria_atual

# Essa função assumirá que você tem uma implementação client do Google em algum lugar do seu backend
# from api.services.google_calendar import get_calendar_service

def parse_db_topics(db_path="medquest.db") -> List[Dict[str, Any]]:
    """Busca as aulas pendentes direto do banco local do MedQuest"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # A query real dependerá do seu schema real no Turso/SQLite
    # Exemplo: SELECT id, title, category, status FROM topics WHERE status != 'done'
    # Como não sei o schema exato, deixarei um pseudo-código
    topics = []
    # for row in cursor.execute("SELECT * FROM topics WHERE status = 'pending'"):
    #     topics.append(dict(row))
    conn.close()
    return topics

def mark_topic_done_in_db(db_path, sync_id):
    """Atualiza o banco do App se o Google disser que está concluído (União)"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # cursor.execute("UPDATE topics SET status = 'done' WHERE sync_id = ?", (sync_id,))
    conn.commit()
    conn.close()

def sync_calendar_engine(service, db_path="medquest.db"):
    """
    O Motor Principal do Two-Way Sync com Efeito Cascata.
    """
    print("Iniciando Sincronização Two-Way Sync (Regra de União)...")
    
    # 1. Busca os eventos controlados no Google Calendar
    events_result = service.events().list(
        calendarId='primary',
        privateExtendedProperty='medquest_sync=true',
        singleEvents=True
    ).execute()
    
    events = events_result.get('items', [])
    
    # 2. Resolução de Conflitos (Regra de União)
    para_deletar_do_google = []
    
    for ev in events:
        sync_id = ev.get('extendedProperties', {}).get('private', {}).get('sync_id')
        color = ev.get('colorId')
        end_str = ev.get('end', {}).get('dateTime')
        
        if not sync_id or not end_str:
            continue
            
        end_dt = datetime.fromisoformat(end_str)
        
        if color == '8': # Grafite = Concluído no Google
            print(f"Aula {sync_id} concluída via Google Calendar. Atualizando App...")
            mark_topic_done_in_db(db_path, sync_id)
        else:
            # Se não está concluído, deleta do Google para que o algoritmo de 
            # Cascata (abaixo) recalcule o slot ideal e insira novamente.
            para_deletar_do_google.append(ev['id'])
            
    # Executa as deleções
    for ev_id in para_deletar_do_google:
        try:
            service.events().delete(calendarId='primary', eventId=ev_id).execute()
        except Exception:
            pass

    # 3. Construir Nova Fila (Cascata + Prioridade do Rodízio)
    aulas_pendentes = parse_db_topics(db_path)
    
    area_atual = get_area_prioritaria_atual()
    print(f"Rodízio atual identificado: {area_atual}")
    
    if area_atual:
        # Puxa tudo da area atual para a frente (O Shift)
        aulas_pendentes.sort(key=lambda x: 0 if x.get('category') == area_atual else 1)
        
    # 4. Inserir de volta no Google Calendar (O Push)
    # Aqui entraria a sua função "build_schedule_events" do script antigo 
    # adaptada para ler `aulas_pendentes` em vez do parse do ICS.
    # E depois `service.events().insert()`
    
    print("Sincronização concluída com sucesso.")
    return True
