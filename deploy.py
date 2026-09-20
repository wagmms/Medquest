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
import os
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


def main():
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

    args = parser.parse_args()
    start_time = time.time()

    print("\n" + "=" * 60)
    print("             MEDQUEST - DEPLOY AUTOMATIZADO                 ")
    print("=" * 60 + "\n")

    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir:
        os.chdir(root_dir)

    # 1. BANCO DE DADOS (LOCAL -> TURSO CLOUD ONLINE)
    if not args.skip_db:
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
                print("  [AVISO] Sincronizacao com o Turso finalizada com avisos.\n")
        except Exception as e:
            print(f"  [AVISO] Nao foi possivel sincronizar o banco com Turso: {e}\n")
    else:
        print("[1/3] Sincronizacao do banco de dados pulada (--skip-db).\n")

    if args.db_only:
        elapsed = int(time.time() - start_time)
        print("=" * 60)
        print("        ATUALIZACAO DO BANCO CONCLUIDA COM SUCESSO!         ")
        print("=" * 60)
        print(f"Tempo total : {elapsed}s")
        print("Banco Cloud : Turso (Online)")
        print()
        return

    # 2. GIT LOCAL & DEPLOY NUVEM (Vercel + Render)
    if not args.skip_git:
        print("[2/3] Processando alteracoes no repositorio local (Git)...")
        status_proc = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        has_changes = bool(status_proc.stdout.strip())

        if has_changes:
            msg = args.message
            if not msg:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                if sys.stdin.isatty():
                    user_input = input(f"  Digite a mensagem do commit (Enter para '[deploy] {timestamp}'): ").strip()
                    msg = user_input if user_input else f"[deploy] Atualizacao {timestamp}"
                else:
                    msg = f"[deploy] Atualizacao {timestamp}"
            
            print(f"  [i] Adicionando arquivos e realizando commit: '{msg}'")
            run_command(["git", "add", "-A"])
            run_command(["git", "commit", "-m", msg])
        else:
            print("  [i] Nenhuma alteracao pendente de commit local.")

        print("  [i] Enviando commits para origin main...")
        run_command(["git", "push", "origin", "main"])
        print("  [OK] Git push concluido com sucesso!")
        print(f"  [i] Vercel : Deploy automatico do Frontend iniciado -> {FRONTEND_PROD_URL}")
        print(f"  [i] Render : Deploy automatico do Backend iniciado  -> {BACKEND_PROD_URL}\n")
    else:
        print("[2/3] Etapa Git local pulada (--skip-git).\n")

    # 3. DEPLOY REMOTO VIA SSH (OPCIONAL - APENAS SE --vps FOR ESPECIFICADO)
    enable_vps = args.vps and not args.skip_remote
    if enable_vps:
        print(f"[3/3] Conectando a VPS ({args.user}@{args.host}) e executando deploy Docker...")
        key_path = resolve_ssh_key(args.key)
        
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
        
        ssh_cmd.append(f"{args.user}@{args.host}")
        ssh_cmd.append(remote_script)

        run_command(ssh_cmd)
        print("  [OK] Deploy remoto na VPS concluido com sucesso!\n")
    else:
        print("[3/3] Deploy em Nuvem concluido com sucesso (Vercel + Render via GitHub).")
        if not args.vps:
            print("  (Dica: caso queira atualizar uma VPS dedicada via SSH, utilize a flag --vps)\n")

    elapsed = int(time.time() - start_time)
    minutes = elapsed // 60
    seconds = elapsed % 60

    print("=" * 60)
    print("              DEPLOY CONCLUIDO COM SUCESSO!                 ")
    print("=" * 60)
    print(f"Tempo total : {minutes}m {seconds}s")
    print(f"Frontend    : {FRONTEND_PROD_URL}")
    print(f"Backend     : {BACKEND_PROD_URL}")
    if enable_vps:
        print(f"VPS Host    : {args.host}")
    print()


if __name__ == "__main__":
    main()
