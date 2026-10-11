#!/usr/bin/env python3
"""
MedQuest - Script de Deploy Automatizado (Python)

Uso padrao (Deploy na Nuvem: Vercel + Render):
    python deploy.py
    python deploy.py "Minha mensagem de commit"

Deploy opcional em servidor VPS (Docker Compose via SSH):
    python deploy.py --vps
    python deploy.py "Hotfix" --vps --host 136.248.114.130

Outras opcoes:
    python deploy.py --skip-git
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

HOST_DEFAULT = os.environ.get("MEDQUEST_DEPLOY_HOST", "136.248.114.130")
USER_DEFAULT = os.environ.get("MEDQUEST_DEPLOY_USER", "ubuntu")
REMOTE_DIR_DEFAULT = os.environ.get("MEDQUEST_DEPLOY_DIR", "~/MedQuest")
FRONTEND_PROD_URL = "https://medquest.live"
BACKEND_PROD_URL = "https://medquest-188y.onrender.com"


def run_command(cmd, shell=False, check=True):
    try:
        result = subprocess.run(cmd, shell=shell, check=check)
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\n[ERRO] Falha ao executar comando: {cmd}")
        sys.exit(e.returncode)


def resolve_ssh_key(custom_key=None):
    if custom_key and os.path.exists(custom_key):
        return custom_key

    env_key = os.environ.get("MEDQUEST_DEPLOY_KEY") or os.environ.get("SSH_KEY_PATH")
    if env_key and os.path.exists(env_key):
        return env_key

    home_medquest_key = os.path.expanduser("~/.ssh/medquest_deploy.key")
    if os.path.exists(home_medquest_key):
        return home_medquest_key

    home_medquest = os.path.expanduser("~/.ssh/medquest_deploy")
    if os.path.exists(home_medquest):
        return home_medquest

    home_ssh = os.path.expanduser("~/.ssh/id_rsa")
    if os.path.exists(home_ssh):
        return home_ssh

    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_key = os.path.join(script_dir, "sua-chave.key")
    if os.path.exists(local_key):
        return local_key

    return None


def parse_args(cli_args=None):
    parser = argparse.ArgumentParser(description="Deploy automatizado do MedQuest")
    parser.add_argument("message", nargs="?", help="Mensagem do commit")
    parser.add_argument(
        "--vps",
        "--remote",
        dest="vps",
        action="store_true",
        help="Executar deploy remoto via SSH na VPS (padrao: desativado, usa Vercel + Render)",
    )
    parser.add_argument("--host", default=HOST_DEFAULT, help="IP da VPS (quando usado com --vps)")
    parser.add_argument("--user", default=USER_DEFAULT, help="Usuario SSH da VPS")
    parser.add_argument("--key", default=None, help="Caminho da chave SSH para a VPS")
    parser.add_argument("--skip-git", action="store_true", help="Pular commit e push local")
    parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Pular execucao remota na VPS (padrao ja eh desativado)",
    )
    parser.add_argument("--skip-db", action="store_true", help="Pular sincronizacao do banco com o Turso Cloud")
    parser.add_argument("--db-only", action="store_true", help="Executar apenas a sincronizacao do banco (sem commit/deploy)")
    parser.add_argument("--skip-audit", action="store_true", help="Pular verificacao de auditoria cruzada do commit")

    return parser.parse_args(cli_args)


# Importação canônica do módulo compartilhado de auditoria
core_path = os.path.expanduser("~/.local/lib/autoloop_core")
if core_path not in sys.path:
    sys.path.insert(0, core_path)

try:
    from audit_validator import (
        avaliar_parecer_auditoria,
        VEREDITOS_VALIDOS,
        SEVERIDADES_VALIDAS,
        CAMPOS_OBRIGATORIOS_PARECER as CAMPOS_OBRIGATORIOS_SCHEMA,
        CAMPOS_OBRIGATORIOS_FINDING
    )
except ImportError as exc:
    _erro_importacao_validador = str(exc)

    def avaliar_parecer_auditoria(dados, sha_esperado):
        return False, f"FALHA CRÍTICA DE CONFIGURAÇÃO: Componente obrigatório 'audit_validator' indisponível ({_erro_importacao_validador}). Deploy bloqueado fatalmente."

try:
    from model_router import classificar_perfil_release, selecionar_modelo_auditoria, eh_projeto_habitflow
except ImportError:
    def classificar_perfil_release(base_sha=None, candidate_sha=None, repo_dir=None):
        return "CLINICO_ROBUSTEZ_PRO"

    def selecionar_modelo_auditoria(perfil_tarefa, repo_dir=None):
        return {"model": "gpt-6-astra", "effort": "high", "tier": "Tier 4 - Clínico", "justificativa": "Fallback"}



def adquirir_lock_deploy(root_dir):
    """Garante exclusão mútua física para que apenas um publicador atue por vez."""
    lock_path = os.path.join(root_dir, "data", ".deploy.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_file = open(lock_path, "a+")
    try:
        import fcntl
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except (BlockingIOError, IOError):
        try:
            lock_file.close()
        except Exception:
            pass
        print("  [ERRO CRITICO] Bloqueio de exclusao mutua: outro processo de deploy ja esta ativo para este repositorio.\n")
        sys.exit(1)


def audit_and_checks_phase(skip_audit, root_dir, message=None):
    """0. VERIFICACOES E AUDITORIA (ANTES DE QUALQUER MUTACAO NO BANCO OU GIT)"""
    print("[0/3] Executando verificacoes de qualidade e auditoria preliminar...")
    
    # 0.1 Consolidação prévia do commit candidato para garantir que o SHA auditado seja exatamente o publicado
    status_proc = subprocess.run(["git", "status", "--porcelain"], cwd=root_dir, capture_output=True, text=True)
    if status_proc.stdout.strip():
        print("  [i] Consolidando alteracoes locais pendentes antes da auditoria...")
        subprocess.run(["git", "add", "-A"], cwd=root_dir, check=True)
        msg = message or f"[deploy] Release {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", msg], cwd=root_dir, check=True)

    # 0.2 Executa bateria de testes locais
    tests_dir = os.path.join(root_dir, "tests")
    if os.path.exists(tests_dir):
        import shutil
        test_cmd = [sys.executable, "-m", "pytest", "tests"] if shutil.which("pytest") else [sys.executable, "-m", "unittest", "discover", "tests"]
        res_test = subprocess.run(test_cmd, cwd=root_dir, capture_output=True, text=True)
        if res_test.returncode != 0:
            print(f"  [ERRO CRITICO] Testes automatizados reprovados (codigo {res_test.returncode}).")
            print(f"  {res_test.stderr.strip()[:300] or res_test.stdout.strip()[:300]}")
            print("  Abortando deploy ANTES de qualquer sincronizacao de banco ou push.\n")
            sys.exit(1)
        print("  [OK] 100% dos testes automatizados aprovados.")

    # 0.3 Resolução rigorosa do SHA candidato de 40 caracteres
    res_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root_dir, capture_output=True, text=True)
    head_sha = res_head.stdout.strip()
    if res_head.returncode != 0 or len(head_sha) != 40 or not all(c in "0123456789abcdefABCDEF" for c in head_sha):
        print(f"  [ERRO CRITICO] Falha ao resolver SHA de 40 digitos do commit candidato: '{head_sha}'. Abortando.\n")
        sys.exit(1)

    # 0.4 Gate Obrigatório de Auditoria Cruzada (Padrão: ATIVO em produção)
    exigir_auditoria = not skip_audit and (os.environ.get("MEDQUEST_CODEX_AUDIT", "1").strip().lower() in ["1", "true", "yes"])
    if exigir_auditoria:
        perfil_release = classificar_perfil_release(repo_dir=root_dir)
        cfg_modelo_info = selecionar_modelo_auditoria(perfil_release, repo_dir=root_dir)
        print(f"  [i] Verificando parecer de auditoria cruzada para {head_sha[:10]} (Perfil: {perfil_release} -> Modelo: {cfg_modelo_info['model']} [{cfg_modelo_info['effort']}])...")
        audit_file = os.path.join(root_dir, "data", "auditorias_codex", f"audit_{head_sha}.json")
        permitir_fallback_cota = os.environ.get("MEDQUEST_CODEX_FALLBACK_ON_QUOTA", "0").strip().lower() in ["1", "true", "yes"]
        if not os.path.exists(audit_file):
            if permitir_fallback_cota:
                print(f"  [AVISO] Parecer de auditoria ausente para {head_sha[:10]} (cota esgotada). Prosseguindo deploy baseado em 100% de testes locais aprovados.")
                print("  [OK] Verificacoes preliminares concluidas com sucesso!\n")
                return head_sha
            else:
                print(f"  [ERRO CRITICO] Parecer de auditoria obrigatorio ausente para {head_sha[:10]}. Abortando deploy.\n")
                sys.exit(1)

        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                dados_parecer = json.load(f)
        except Exception as e:
            print(f"  [ERRO CRITICO] Parecer de auditoria com JSON corrompido ou invalido ({e}). Abortando.\n")
            sys.exit(1)

        aprovado, motivo_bloqueio = avaliar_parecer_auditoria(dados_parecer, sha_esperado=head_sha)
        if not aprovado:
            print(f"  [ERRO CRITICO] DEPLOY REPROVADO NA AUDITORIA: {motivo_bloqueio}. Abortando deploy.\n")
            sys.exit(1)

        print(f"  [OK] Parecer de auditoria APROVADO sem ressalvas para {head_sha[:10]}.")

    print("  [OK] Verificacoes preliminares concluidas com sucesso!\n")
    return head_sha


def sync_database_phase(skip_db, root_dir):
    """1. BANCO DE DADOS (LOCAL -> TURSO CLOUD ONLINE)"""
    if not skip_db:
        print("[1/3] Sincronizando banco de dados local com Turso Cloud (Online)...")
        try:
            backend_path = os.path.join(root_dir, "app", "backend")
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            from scripts.sync_db_turso import sync_database
            sync_ok = sync_database(verbose=True)
            if sync_ok:
                print("  [OK] Banco de dados online (Turso) em sincronia total com o local!\n")
            else:
                print("  [ERRO CRITICO] Sincronizacao com o Turso falhou! Abortando deploy para proteger producao.\n")
                sys.exit(1)
        except Exception as e:
            print(f"  [ERRO CRITICO] Falha fatal ao sincronizar banco com Turso: {e}. Abortando deploy.\n")
            sys.exit(1)
    else:
        print("[1/3] Sincronizacao do banco de dados pulada (--skip-db).\n")


def deploy_git_phase(skip_git, candidate_sha=None):
    """2. GIT LOCAL & DEPLOY NUVEM (Vercel + Render)"""
    if not skip_git:
        print("[2/3] Processando publicacao no repositorio remoto (Git)...")
        status_proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if status_proc.stdout.strip():
            print("  [ERRO CRITICO] Alteracoes nao auditadas detectadas apos a fase de auditoria! Abortando deploy.\n")
            sys.exit(1)

        branch_proc = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
        branch_atual = branch_proc.stdout.strip()
        if branch_atual != "main":
            print(f"  [ERRO CRITICO] Branch atual '{branch_atual}' nao e 'main'. Abortando deploy.\n")
            sys.exit(1)

        sha_atual = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if candidate_sha and sha_atual != candidate_sha:
            print(f"  [ERRO CRITICO] Mudanca concorrente detectada: o commit HEAD atual '{sha_atual[:10]}' difere do candidato auditado '{candidate_sha[:10]}'. Abortando deploy.\n")
            sys.exit(1)

        print("  [i] Enviando commits aprovados para origin main...")
        run_command(["git", "push", "origin", "main"])
        print("  [OK] Git push concluido com sucesso!")
        print(f"  [i] Vercel : Deploy automatico do Frontend iniciado -> {FRONTEND_PROD_URL}")
        print(f"  [i] Render : Deploy automatico do Backend iniciado  -> {BACKEND_PROD_URL}\n")
    else:
        print("[2/3] Etapa Git local pulada (--skip-git).\n")


def deploy_vps_phase(vps, skip_remote, user, host, key):
    """3. DEPLOY REMOTO VIA SSH (OPCIONAL - APENAS SE --vps FOR ESPECIFICADO)"""
    enable_vps = vps and not skip_remote
    if enable_vps:
        print(f"[3/3] Conectando a VPS ({user}@{host}) e executando deploy Docker...")
        key_path = resolve_ssh_key(key)

        remote_script = (
            "set -e && "
            "echo '  [VPS 1/4] Atualizando codigo do MedQuest via Git...' && "
            f"cd {REMOTE_DIR_DEFAULT} && git pull origin main && "
            "echo '  [VPS 2/4] Reconstruindo e subindo containers Docker...' && "
            "sudo docker-compose up -d --build --force-recreate && "
            "echo '  [VPS 3/4] Limpando imagens antigas...' && "
            "sudo docker image prune -f > /dev/null 2>&1 || true && "
            "echo '  [VPS 4/4] Status atual dos servicos:' && "
            "sudo docker-compose ps"
        )

        ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15"]
        if key_path:
            print(f"  [i] Usando chave SSH: {key_path}")
            ssh_cmd.extend(["-i", key_path])

        ssh_cmd.append(f"{user}@{host}")
        ssh_cmd.append(remote_script)

        run_command(ssh_cmd)
        print("  [OK] Deploy remoto na VPS concluido com sucesso!\n")
    else:
        print("[3/3] Deploy em Nuvem concluido com sucesso (Vercel + Render via GitHub).")
        if not vps:
            print("  (Dica: caso queira atualizar uma VPS dedicada via SSH, utilize a flag --vps)\n")

    return enable_vps


def print_summary(start_time, db_only=False, enable_vps=False, host=HOST_DEFAULT):
    """Print the final summary of the deploy process."""
    elapsed = int(time.time() - start_time)

    if db_only:
        print("=" * 60)
        print("        ATUALIZACAO DO BANCO CONCLUIDA COM SUCESSO!         ")
        print("=" * 60)
        print(f"Tempo total : {elapsed}s")
        print("Banco Cloud : Turso (Online)")
        print()
        return

    minutes = elapsed // 60
    seconds = elapsed % 60

    print("=" * 60)
    print("              DEPLOY CONCLUIDO COM SUCESSO!                 ")
    print("=" * 60)
    print(f"Tempo total : {minutes}m {seconds}s")
    print(f"Frontend    : {FRONTEND_PROD_URL}")
    print(f"Backend     : {BACKEND_PROD_URL}")
    if enable_vps:
        print(f"VPS Host    : {host}")
    print()


def main(cli_args=None):
    args = parse_args(cli_args)
    start_time = time.time()

    print("\n" + "=" * 60)
    print("             MEDQUEST - DEPLOY AUTOMATIZADO                 ")
    print("=" * 60 + "\n")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir:
        os.chdir(root_dir)

    # Bloqueio físico de exclusão mútua por projeto
    _lock_handle = adquirir_lock_deploy(root_dir)
    try:
        # 0. VERIFICACOES E AUDITORIA PRELIMINAR (BLOQUEANTE)
        candidate_sha = audit_and_checks_phase(args.skip_audit, root_dir, message=args.message)

        # 1. BANCO DE DADOS (LOCAL -> TURSO CLOUD ONLINE)
        sync_database_phase(args.skip_db, root_dir)

        if args.db_only:
            print_summary(start_time, db_only=True)
            return

        # 2. GIT LOCAL & DEPLOY NUVEM (Vercel + Render)
        deploy_git_phase(args.skip_git, candidate_sha=candidate_sha)

        # 3. DEPLOY REMOTO VIA SSH (OPCIONAL - APENAS SE --vps FOR ESPECIFICADO)
        enable_vps = deploy_vps_phase(args.vps, args.skip_remote, args.user, args.host, args.key)

        print_summary(start_time, db_only=False, enable_vps=enable_vps, host=args.host)
    finally:
        if _lock_handle:
            try:
                _lock_handle.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
