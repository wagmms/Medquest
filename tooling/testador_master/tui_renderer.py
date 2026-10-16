"""
==============================================================================
MEDQUEST · TESTADOR MASTER: RENDERIZADOR TUI AO VIVO
==============================================================================
Interface rica de terminal (Anti-UI-Slop) com cores ANSI de alto contraste,
acompanhamento de personas médicas, telemetria em tempo real e grafo vivo.
==============================================================================
"""

import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

# Paleta ANSI de Alto Contraste
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"

BLUE = "\033[38;5;39m"
CYAN = "\033[38;5;51m"
GREEN = "\033[38;5;82m"
YELLOW = "\033[38;5;220m"
RED = "\033[38;5;196m"
MAGENTA = "\033[38;5;201m"
WHITE = "\033[38;5;255m"
GRAY = "\033[38;5;244m"
BG_DARK = "\033[48;5;236m"


class TUIRenderer:
    """Renderizador de painel de controle no terminal com atualização contínua."""

    def __init__(self, largura_max: int = 90):
        self.largura_max = largura_max

    def obter_largura(self) -> int:
        try:
            colunas = shutil.get_terminal_size((90, 24)).columns
            return min(self.largura_max, max(65, colunas - 2))
        except Exception:
            return self.largura_max

    def limpar_tela(self):
        """Limpa o terminal para renderização fluida."""
        print("\033[H\033[J", end="", flush=True)

    def _barra_progresso(self, pct: float, largura: int = 16) -> str:
        """Gera barra de progresso em blocos Unicode."""
        preenchidos = int(round((pct / 100.0) * largura))
        preenchidos = max(0, min(largura, preenchidos))
        vazios = largura - preenchidos
        return f"{GREEN}{'█' * preenchidos}{GRAY}{'░' * vazios}{RESET} {BOLD}{pct:5.1f}%{RESET}"

    def renderizar_cabecalho(
        self,
        persona: Any,
        ciclo_atual: int,
        ciclos_total: int,
        modo: str,
        cobertura_pct: float,
        tempo_decorrido: str,
    ):
        largura = self.obter_largura()
        linha = "═" * largura

        print(f"{CYAN}{linha}{RESET}")
        titulo = f" 🩺 MEDQUEST · TESTADOR MASTER OSTENSIVO (E2E & API) "
        print(f"{BOLD}{WHITE}{titulo.center(largura)}{RESET}")
        print(f"{CYAN}{linha}{RESET}")

        # Informações da sessão
        info_esq = f"Modo: {YELLOW}{modo.upper()}{RESET} | Ciclo: {BOLD}{ciclo_atual}{RESET}/{ciclos_total if ciclos_total > 0 else '∞'}"
        info_dir = f"Tempo: {WHITE}{tempo_decorrido}{RESET} | Cobertura: {self._barra_progresso(cobertura_pct, 12)}"
        print(f" {info_esq:<45} {info_dir:>30}")

        # Box da Persona Médica
        print(f"{GRAY}─{RESET}" * largura)
        print(
            f" {persona.icone} {BOLD}{persona.nome}{RESET} "
            f"({BLUE}{persona.titulo}{RESET}) | "
            f"Ritmo: {WHITE}{persona.ritmo_segundos:.1f}s{RESET} | "
            f"Taxa Alvo: {GREEN}{persona.taxa_acerto_esperada*100:.0f}%{RESET}"
        )
        print(f"   {DIM}{persona.descricao}{RESET}")
        print(f"{GRAY}─{RESET}" * largura)

    def renderizar_pensamento_clinico(self, pensamento: str):
        """Exibe o balão de raciocínio da persona simulada."""
        largura = self.obter_largura()
        print(f"{YELLOW}💭 Raciocínio Clínico / Intenção de Estudo:{RESET}")
        print(f"   {ITALIC}{WHITE}\"{pensamento}\"{RESET}")
        print(f"{GRAY}─{RESET}" * largura)

    def renderizar_acao_em_curso(self, acao: str, alvo: str, latencia_ms: float, status_code: Optional[int], sucesso: bool):
        """Exibe detalhes da ação médica executada."""
        cor_status = GREEN if sucesso else RED
        icone_status = "✅" if sucesso else "❌"
        status_txt = f"{status_code}" if status_code else ("OK" if sucesso else "FAIL")

        print(f"▶ {BOLD}Ação:{RESET} {CYAN}{acao}{RESET}  →  {WHITE}{alvo}{RESET}")
        print(
            f"   {icone_status} Status: {cor_status}{status_txt}{RESET} | "
            f"Latência: {YELLOW}{latencia_ms:.1f}ms{RESET}"
        )

    def renderizar_telemetria(
        self,
        total_acoes: int,
        taxa_sucesso: float,
        latencia_media: float,
        violacoes_imutabilidade: int,
        anomalias_fsrs: int,
        anomalias_tri: int,
    ):
        """Exibe o painel de métricas clínicas e de guardrails."""
        largura = self.obter_largura()
        print(f"{GRAY}─{RESET}" * largura)
        print(f"{BOLD}📊 TELEMETRIA EM TEMPO REAL:{RESET}")

        cor_imut = GREEN if violacoes_imutabilidade == 0 else RED
        cor_fsrs = GREEN if anomalias_fsrs == 0 else YELLOW
        cor_tri = GREEN if anomalias_tri == 0 else YELLOW

        linha_telemetria = (
            f" Ações: {WHITE}{total_acoes}{RESET} | "
            f"Sucesso: {GREEN}{taxa_sucesso:.1f}%{RESET} | "
            f"Latência Média: {WHITE}{latencia_media:.1f}ms{RESET} | "
            f"Imutabilidade: {cor_imut}{violacoes_imutabilidade} viol.{RESET}"
        )
        print(linha_telemetria)

        linha_guardrails = (
            f" Guardrails SRS: {cor_fsrs}{anomalias_fsrs} anom.{RESET} | "
            f"TRI Math: {cor_tri}{anomalias_tri} anom.{RESET}"
        )
        print(linha_guardrails)
        print(f"{CYAN}{'═' * largura}{RESET}\n")

    def renderizar_anomalia(self, mensagem: str):
        """Exibe destaque visual para anomalias ou falhas de contrato."""
        print(f" {RED}⚠️  [ALERTA DE ANOMALIA]{RESET} {YELLOW}{mensagem}{RESET}")
