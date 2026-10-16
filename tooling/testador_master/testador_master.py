#!/usr/bin/env python3
"""
==============================================================================
MEDQUEST · TESTADOR MASTER (MASTER TESTER E2E & API AUTÔNOMO)
==============================================================================
Robô testador ostensivo de alta fidelidade para a plataforma MedQuest.
Simula personas médicas reais (internato, R1, revisor FSRS, candidato OSCE),
explora todas as rotas e telas, audita a imutabilidade das explicações médicas
e gera relatórios vivos com reprodução automática de falhas.
==============================================================================
"""

import argparse
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Adiciona o diretório raiz ao PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tooling.testador_master.crawler_engine import MedQuestGraph
from tooling.testador_master.dashboard_generator import DashboardGenerator
from tooling.testador_master.driver_api import DriverAPI
from tooling.testador_master.driver_e2e import DriverE2E
from tooling.testador_master.medical_oracle import MedicalOracle
from tooling.testador_master.personas import obter_catalogo_personas
from tooling.testador_master.reporter import MasterReporter
from tooling.testador_master.repro_generator import ReproGenerator
from tooling.testador_master.tui_renderer import TUIRenderer


def criar_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="MedQuest · Testador Master Ostensivo (E2E & API)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "api", "e2e"],
        default="auto",
        help=(
            "Modo de execução:\n"
            "  auto : Alterna estresse ultrarrápido de API com validação E2E\n"
            "  api  : Executa exclusivamente via Driver de API (in-memory / rápido)\n"
            "  e2e  : Executa via Playwright navegando no frontend Next.js"
        ),
    )
    parser.add_argument(
        "--persona",
        type=str,
        default="todas",
        help="Persona médica a simular ('todas', ou nomes separados por vírgula como 'internato_generalista,r1_residencia_elite')",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=0,
        help="Quantidade de ciclos/ações a executar (0 para rodar indefinidamente, padrão: 0)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Tempo máximo de execução em minutos (0 para sem limite de tempo)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        help="Intervalo de espera humano entre ações em segundos (padrão: 1.2s)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Não limpa a tela do terminal a cada turno (mantém histórico contínuo)",
    )
    parser.add_argument(
        "--offline",
        "--no-ai",
        dest="offline",
        action="store_true",
        default=False,
        help="Execução 100% offline: desativa qualquer chamada a APIs externas (Gemini/Vision/OSCE)",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default=str(ROOT_DIR / "docs" / "RELATORIO_TESTADOR_MASTER.md"),
        help="Caminho do relatório executivo em Markdown",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=str(ROOT_DIR / "data" / "testador_master_relatorio.json"),
        help="Caminho dos dados estruturados em JSON",
    )
    parser.add_argument(
        "--output-html",
        type=str,
        default=str(ROOT_DIR / "docs" / "dashboard_grafo.html"),
        help="Caminho do dashboard visual interativo em HTML",
    )
    parser.add_argument(
        "--graph-path",
        type=str,
        default=str(ROOT_DIR / "data" / "testador_master_grafo.json"),
        help="Caminho de persistência do grafo de cobertura",
    )
    parser.add_argument(
        "--repro-dir",
        type=str,
        default=str(ROOT_DIR / "tests" / "repros"),
        help="Diretório para salvar testes de reprodução isolados (.py)",
    )
    return parser


def formatar_tempo(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def main():
    parser = criar_argument_parser()
    args = parser.parse_args()

    # 1. Instanciação dos Subsistemas Centrais
    oracle = MedicalOracle()
    grafo = MedQuestGraph(caminho_persistente=args.graph_path)
    grafo.carregar_de_disco()

    tui = TUIRenderer()
    reporter = MasterReporter(output_md=args.output_md, output_json=args.output_json)
    repro = ReproGenerator(output_dir=Path(args.repro_dir))
    dashboard_gen = DashboardGenerator(
        output_html=Path(args.output_html),
        grafo_json_path=Path(args.graph_path),
        relatorio_json_path=Path(args.output_json),
    )

    catalogo_personas = obter_catalogo_personas(offline=args.offline)
    driver_api = DriverAPI(oracle=oracle, offline=args.offline)
    driver_e2e = DriverE2E(oracle=oracle)

    driver_api.inicializar()
    driver_e2e.inicializar()

    # Gerenciamento de encerramento gracioso (Ctrl+C)
    executando = True

    def tratar_sinal(sig, frame):
        nonlocal executando
        executando = False
        print("\n\n🛑 [INTERRUPÇÃO] Finalizando graciosamente o Testador Master...")

    signal.signal(signal.SIGINT, tratar_sinal)
    signal.signal(signal.SIGTERM, tratar_sinal)

    ciclo_atual = 0
    t_inicio = time.time()
    if args.persona == "todas":
        personas_keys = list(catalogo_personas.keys())
    else:
        personas_keys = [p.strip() for p in args.persona.split(",") if p.strip() in catalogo_personas]
        if not personas_keys:
            print(f"⚠️ Nenhuma persona válida encontrada em '{args.persona}'. Alternando entre todas.")
            personas_keys = list(catalogo_personas.keys())

    modo_desc = args.mode.upper()
    if args.offline:
        modo_desc += " [100% OFFLINE / ZERO CONSUMO DE IA]"

    print("\n" + "=" * 75)
    print("🚀 INICIALIZANDO MEDQUEST · TESTADOR MASTER OSTENSIVO")
    print(f"• Modo: {modo_desc} | Personas: {', '.join(personas_keys)}")
    print(f"• Ciclos: {'Infinitos (0)' if args.cycles == 0 else args.cycles} | Delay: {args.delay}s")
    print("=" * 75)
    time.sleep(1.0)

    try:
        while executando:
            ciclo_atual += 1
            if args.cycles > 0 and ciclo_atual > args.cycles:
                break

            tempo_decorrido = time.time() - t_inicio
            if args.duration > 0 and (tempo_decorrido / 60.0) >= args.duration:
                break

            # Seleciona persona da rodada
            pid = personas_keys[(ciclo_atual - 1) % len(personas_keys)]
            persona = catalogo_personas[pid]

            # Escolhe ação da persona
            acao = persona.escolher_acao()
            pensamento = persona.gerar_pensamento_clinico(acao)

            # Determina qual driver utilizar
            usar_e2e = (args.mode == "e2e") or (args.mode == "auto" and (ciclo_atual % 5 == 0))
            driver_ativo = driver_e2e if usar_e2e else driver_api

            # Executa a ação
            resultado = None
            origem_node = "tela:/estudar" if usar_e2e else "api:/api/questions"

            if acao == "responder_questao":
                resultado = driver_ativo.responder_questao()
            elif acao == "revisar_flashcard":
                resultado = driver_ativo.revisar_flashcard()
            elif acao == "executar_simulado":
                resultado = driver_ativo.executar_simulado(qtd_questoes=5)
            elif acao == "executar_estacao_osce":
                resultado = driver_ativo.executar_estacao_osce()
            elif acao == "consultar_analytics":
                resultado = driver_ativo.consultar_analytics()
            elif acao == "analisar_exame_imagem":
                if hasattr(driver_ativo, "analisar_exame_imagem"):
                    resultado = driver_ativo.analisar_exame_imagem(modalidade="ecg")
                else:
                    resultado = driver_ativo.verificar_saude()
            elif acao == "buscar_conteudo":
                resultado = driver_ativo.buscar_conteudo("tromboembolismo")
            elif acao == "fuzzing":
                if hasattr(driver_ativo, "fuzzing"):
                    resultado = driver_ativo.fuzzing()
                else:
                    resultado = driver_ativo.verificar_saude()
            else:
                resultado = driver_ativo.verificar_saude()

            resultado.pensamento = pensamento

            # Registro no Grafo de Cobertura
            tipo_no = "tela_frontend" if usar_e2e else "rota_api"
            node_alvo = f"{'tela:' if usar_e2e else 'api:'}{resultado.alvo}"
            grafo.registrar_visita(node_alvo, sucesso=resultado.sucesso, latencia_ms=resultado.latencia_ms, tipo_padrao=tipo_no)
            grafo.registrar_transicao(origem_node, node_alvo, acao)

            # Registro no Reporter
            reporter.registrar_acao(persona_id=pid, resultado=resultado, pensamento=pensamento)

            # Geração automática de repro se houver falha
            if not resultado.sucesso or resultado.anomalias:
                if not usar_e2e and resultado.status_code and resultado.status_code >= 500:
                    repro.gerar_repro_api(
                        acao=acao,
                        endpoint=resultado.alvo,
                        metodo="POST" if "attempt" in resultado.alvo or "review" in resultado.alvo else "GET",
                        payload=resultado.dados,
                        headers=driver_api._obter_headers(),
                        status_code=resultado.status_code,
                        resposta_erro=resultado.mensagem,
                        anomalias=resultado.anomalias,
                    )

            # Renderização TUI
            if not args.no_clear:
                tui.limpar_tela()

            cobertura_info = grafo.calcular_cobertura()
            tempo_str = formatar_tempo(tempo_decorrido)

            tui.renderizar_cabecalho(
                persona=persona,
                ciclo_atual=ciclo_atual,
                ciclos_total=args.cycles,
                modo=args.mode,
                cobertura_pct=cobertura_info["percentual_geral"],
                tempo_decorrido=tempo_str,
            )

            tui.renderizar_pensamento_clinico(pensamento)
            tui.renderizar_acao_em_curso(
                acao=acao,
                alvo=resultado.alvo,
                latencia_ms=resultado.latencia_ms,
                status_code=resultado.status_code,
                sucesso=resultado.sucesso,
            )

            for anom in resultado.anomalias:
                tui.renderizar_anomalia(anom)

            # Métricas consolidadas
            total_acoes = len(reporter.historico_acoes)
            sucessos = sum(1 for a in reporter.historico_acoes if a["sucesso"])
            taxa_sucesso = (sucessos / total_acoes * 100.0) if total_acoes > 0 else 100.0
            latencia_media = (
                sum(a["latencia_ms"] for a in reporter.historico_acoes) / total_acoes
                if total_acoes > 0
                else 0.0
            )

            oracle_stats = {
                "violacoes_imutabilidade": len(oracle.violacoes_imutabilidade),
                "anomalias_fsrs": len(oracle.anomalias_fsrs),
                "anomalias_tri": len(oracle.anomalias_tri),
            }

            tui.renderizar_telemetria(
                total_acoes=total_acoes,
                taxa_sucesso=taxa_sucesso,
                latencia_media=latencia_media,
                violacoes_imutabilidade=oracle_stats["violacoes_imutabilidade"],
                anomalias_fsrs=oracle_stats["anomalias_fsrs"],
                anomalias_tri=oracle_stats["anomalias_tri"],
            )

            # Salva dados parciais em disco periodicamente
            if ciclo_atual % 5 == 0:
                grafo.salvar_em_disco()
                reporter.salvar_dados_json(cobertura_info, oracle_stats)
                reporter.gerar_relatorio_markdown(cobertura_info, oracle_stats, catalogo_personas)
                dashboard_gen.gerar_dashboard()

            # Atraso humano configurável
            if args.delay > 0:
                time.sleep(args.delay)

    finally:
        # Encerramento, limpeza e salvamento final
        driver_api.finalizar()
        driver_e2e.finalizar()

        cobertura_info = grafo.calcular_cobertura()
        oracle_stats = {
            "violacoes_imutabilidade": len(oracle.violacoes_imutabilidade),
            "anomalias_fsrs": len(oracle.anomalias_fsrs),
            "anomalias_tri": len(oracle.anomalias_tri),
        }

        grafo.salvar_em_disco()
        reporter.salvar_dados_json(cobertura_info, oracle_stats)
        reporter.gerar_relatorio_markdown(cobertura_info, oracle_stats, catalogo_personas)
        dashboard_gen.gerar_dashboard()

        print("\n" + "=" * 75)
        print("🎉 MEDQUEST · TESTADOR MASTER CONCLUÍDO COM SUCESSO!")
        print(f"• Total de Ações: {len(reporter.historico_acoes)}")
        print(f"• Relatório Markdown: {args.output_md}")
        print(f"• Dashboard Interativo: {args.output_html}")
        print(f"• Dados Estruturados: {args.output_json}")
        print(f"• Grafo de Cobertura: {args.graph_path}")
        print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
