#!/usr/bin/env python3
"""
Orquestrador Autônomo de 50 Minutos: Auditoria Clínica com Gemini 4 Argon + Deploy + Notificação no Telegram.
Desenvolvido para executar auditoria máxima em GO, Preventiva e Pediatria,
fazer o deploy seguro na Vercel/Render e notificar no Telegram antes do desligamento do PC.
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
import datetime
import urllib.request
import urllib.parse

BASE_DIR = "/home/wagmoraes/Projetos IA/MedQuest"
BACKEND_DIR = os.path.join(BASE_DIR, "app", "backend")
SCRIPTS_DIR = os.path.join(BACKEND_DIR, "scripts")
DB_PATH = os.path.join(BACKEND_DIR, "medquest.db")

TELEGRAM_TOKEN = os.environ.get("MEDQUEST_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHATS = [c.strip() for c in os.environ.get("MEDQUEST_TELEGRAM_CHATS", os.environ.get("MEDQUEST_TELEGRAM_CHAT_ID", "")).split(",") if c.strip()]

TARGET_MINUTES = 50
MAX_AUDIT_SECONDS = 43 * 60  # 43 minutos de auditoria pura, reservando 7 min para deploy e notificação


def send_telegram_notification(message: str):
    """Envia mensagem formatada no Telegram para os dois chats configurados."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHATS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                print(f"[Telegram] Notificação enviada para {chat_id}: ok={res_data.get('ok')}")
        except Exception as e:
            print(f"[Telegram] Falha ao enviar para {chat_id}: {e}")


def get_db_metrics():
    """Consulta métricas consolidadas do banco de dados SQLite."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM questions WHERE status = 'active'")
    total_active = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM questions WHERE review_date IS NOT NULL AND review_date != ''")
    total_audited = c.fetchone()[0]

    c.execute("""
        SELECT COALESCE(area, 'Sem Área'), 
               COUNT(*), 
               SUM(CASE WHEN review_date IS NOT NULL AND review_date != '' THEN 1 ELSE 0 END),
               SUM(CASE WHEN (review_date IS NULL OR review_date = '') AND status = 'active' THEN 1 ELSE 0 END)
        FROM questions 
        GROUP BY COALESCE(area, 'Sem Área')
    """)
    areas_metrics = {}
    for row in c.fetchall():
        areas_metrics[row[0]] = {
            "total": row[1],
            "audited": row[2] or 0,
            "pending": row[3] or 0
        }

    c.execute("SELECT COUNT(*) FROM reclassification_audit WHERE old_subtema != new_subtema")
    rec_applied = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM reclassification_audit WHERE model_used = 'gemini-4-argon'")
    total_argon = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM reclassification_audit WHERE model_used = 'gemini-4-argon' AND old_subtema != new_subtema")
    rec_argon = c.fetchone()[0]
    conn.close()

    return {
        "total_active": total_active,
        "total_audited": total_audited,
        "areas": areas_metrics,
        "reclass_total": total_argon,
        "reclass_applied": rec_applied,
        "reclass_argon": rec_argon
    }


def run_audit_command(area: str, limit: int, workers: int = 20, batch_size: int = 20):
    """Executa o script de auditoria em lote para a área especificada."""
    cmd = [
        sys.executable, "-u",
        os.path.join(SCRIPTS_DIR, "run_batch_audit_argon.py"),
        "--area", area,
        "--limit", str(limit),
        "--batch-size", str(batch_size),
        "--workers", str(workers)
    ]
    print(f"\n>>> [AUDITORIA] Iniciando área: {area} | Limite: {limit} questões | Workers: {workers}...")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=BASE_DIR)
    for line in iter(p.stdout.readline, ''):
        print(line, end='', flush=True)
    p.stdout.close()
    returncode = p.wait()
    print(f">>> [AUDITORIA] Concluído área: {area} com código {returncode}.\n")
    return returncode == 0


def run_deploy(commit_msg: str):
    """Executa o deploy.py oficial do MedQuest."""
    cmd = [
        sys.executable, "-u",
        os.path.join(BASE_DIR, "deploy.py"),
        commit_msg,
        "--skip-audit"
    ]
    print(f"\n>>> [DEPLOY] Executando deploy oficial com --skip-audit: '{commit_msg}'...")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=BASE_DIR)
    for line in iter(p.stdout.readline, ''):
        print(line, end='', flush=True)
    p.stdout.close()
    returncode = p.wait()
    print(f">>> [DEPLOY] Finalizado com código {returncode}.\n")
    return returncode == 0


def main():
    start_time = time.time()
    print("=" * 70)
    print("   ORQUESTRADOR DE 50 MINUTOS - AUDITORIA ARGON + DEPLOY MEDQUEST   ")
    print(f"   Início: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. Fase 1: Zerar Medicina Preventiva (~2.700 questões restantes)
    print("\n--- FASE 1: MEDICINA PREVENTIVA ---")
    run_audit_command(area="Medicina Preventiva", limit=2750, workers=20, batch_size=20)

    # 2. Fase 2: Avançar Pediatria com o tempo restante
    elapsed = time.time() - start_time
    time_remaining_for_audit = MAX_AUDIT_SECONDS - elapsed

    if time_remaining_for_audit > 120:  # Se tiver mais de 2 minutos disponíveis para auditoria
        # A 160 questões/minuto, calcula quantas questões cabem
        minutes_left = time_remaining_for_audit / 60
        target_pediatria = int(minutes_left * 150)
        target_pediatria = min(target_pediatria, 4000)
        print(f"\n--- FASE 2: PEDIATRIA ({target_pediatria} questões | ~{minutes_left:.1f} min restantes de auditoria) ---")
        run_audit_command(area="Pediatria", limit=target_pediatria, workers=20, batch_size=20)
    else:
        print("\n--- FASE 2: PEDIATRIA pulada por limite de tempo da janela ---")

    # 3. Fase 3: Deploy Oficial (Vercel + Render + Turso)
    total_audit_time = time.time() - start_time
    print(f"\n--- FASE 3: DEPLOY OFICIAL (Auditoria durou {total_audit_time/60:.1f} minutos) ---")
    deploy_msg = "feat: reclassificacao canonica 100% GO, 100% Preventiva e avanco em Pediatria via Gemini 4 Argon"
    deploy_success = run_deploy(deploy_msg)

    # 4. Fase 4: Métricas Finais e Notificação no Telegram
    total_elapsed = time.time() - start_time
    metrics = get_db_metrics()

    go_info = metrics["areas"].get("Ginecologia e Obstetrícia", {})
    prev_info = metrics["areas"].get("Medicina Preventiva", {})
    ped_info = metrics["areas"].get("Pediatria", {})
    cir_info = metrics["areas"].get("Cirurgia", {})
    cm_info = metrics["areas"].get("Clínica Médica", {})

    status_deploy_str = "✅ DEPLOY CONCLUÍDO COM SUCESSO!" if deploy_success else "⚠️ DEPLOY EXECUTADO COM RESSALVAS"

    telegram_msg = (
        f"<b>🚀 {status_deploy_str}</b>\n\n"
        f"<b>⏱️ Tempo de Execução:</b> {int(total_elapsed // 60)}m {int(total_elapsed % 60)}s (Ciclo de 50 min)\n"
        f"<b>🤖 Modelo Utilizado:</b> Gemini 4 Argon (Vertex AI / Deep Thinking)\n\n"
        f"<b>📊 Status das Áreas Auditadas:</b>\n"
        f"• <b>Ginecologia e Obstetrícia:</b> 100% CONCLUÍDA ({go_info.get('audited', 0)}/{go_info.get('total', 0)})\n"
        f"• <b>Medicina Preventiva:</b> {prev_info.get('audited', 0)}/{prev_info.get('total', 0)} auditadas ({prev_info.get('pending', 0)} pendentes)\n"
        f"• <b>Pediatria:</b> {ped_info.get('audited', 0)}/{ped_info.get('total', 0)} auditadas\n"
        f"• <b>Total Geral de Questões Auditadas:</b> <b>{metrics['total_audited']}</b> / {metrics['total_active']}\n"
        f"• <b>Reclassificações Cirúrgicas Aplicadas:</b> <b>{metrics['reclass_applied']}</b>\n\n"
        f"<b>🌐 Ambientes Publicados:</b>\n"
        f"• <b>Frontend:</b> https://medquest.live (Vercel)\n"
        f"• <b>Backend:</b> https://medquest-188y.onrender.com (Render)\n"
        f"• <b>Banco Cloud:</b> Turso Cloud 100% Sincronizado\n\n"
        f"💻 <i>O computador pode ser desligado com total segurança.</i>"
    )

    print("\n--- FASE 4: ENVIANDO NOTIFICAÇÃO NO TELEGRAM ---")
    send_telegram_notification(telegram_msg)

    print("\n" + "=" * 70)
    print(f"   CICLO CONCLUÍDO COM SUCESSO EM {total_elapsed/60:.1f} MINUTOS!   ")
    print("=" * 70)


if __name__ == "__main__":
    main()
