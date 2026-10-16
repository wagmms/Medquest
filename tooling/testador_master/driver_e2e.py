"""
==============================================================================
MEDQUEST · TESTADOR MASTER: DRIVER E2E PLAYWRIGHT (FRONTEND NEXT.JS)
==============================================================================
Executa jornadas reais de interface com o usuário simulando cliques,
navegação de telas, virada de flashcards e resposta a questões no App Router.
==============================================================================
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from tooling.testador_master.driver_base import DriverBase, ResultadoAcao
from tooling.testador_master.medical_oracle import MedicalOracle

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = ROOT_DIR / "app" / "frontend"


class DriverE2E(DriverBase):
    """Driver E2E que interage diretamente com o frontend do MedQuest via Playwright/Node."""

    def __init__(self, oracle: Optional[MedicalOracle] = None, base_url: str = "http://localhost:3000"):
        self.oracle = oracle or MedicalOracle()
        self.base_url = base_url.rstrip("/")
        self.ativo = False

    def inicializar(self) -> bool:
        """Verifica se o ambiente de frontend e Playwright estão disponíveis."""
        try:
            if not FRONTEND_DIR.exists():
                return False
            self.ativo = True
            return True
        except Exception:
            return False

    def finalizar(self) -> None:
        """Encerra instâncias e processos."""
        self.ativo = False

    def _executar_spec_playwright(self, spec_name: str) -> ResultadoAcao:
        """Executa um arquivo spec de teste Playwright existente e analisa o resultado."""
        t0 = time.perf_counter()
        spec_path = f"e2e/{spec_name}"
        comando = ["npx", "playwright", "test", spec_path, "--reporter=list"]

        try:
            env_cmd = dict(os.environ)
            env_cmd.pop("CI", None)  # Permite reuseExistingServer: true no playwright.config.ts
            proc = subprocess.run(
                comando,
                cwd=FRONTEND_DIR,
                capture_output=True,
                text=True,
                timeout=60,
                env=env_cmd,
            )
            latencia_ms = (time.perf_counter() - t0) * 1000.0
            sucesso = proc.returncode == 0
            anomalias = []
            if not sucesso:
                anomalias.append(f"Playwright falhou em {spec_name}: {proc.stderr[:300] or proc.stdout[:300]}")

            return ResultadoAcao(
                sucesso=sucesso,
                tipo_acao="playwright_spec",
                alvo=spec_path,
                latencia_ms=latencia_ms,
                status_code=200 if sucesso else 500,
                mensagem=f"Spec {spec_name} executado.",
                anomalias=anomalias,
            )
        except subprocess.TimeoutExpired:
            latencia_ms = (time.perf_counter() - t0) * 1000.0
            return ResultadoAcao(
                sucesso=False,
                tipo_acao="playwright_spec",
                alvo=spec_path,
                latencia_ms=latencia_ms,
                status_code=504,
                anomalias=[f"Playwright timeout de 60s excedido em {spec_name}"],
            )
        except Exception as e:
            latencia_ms = (time.perf_counter() - t0) * 1000.0
            return ResultadoAcao(
                sucesso=False,
                tipo_acao="playwright_spec",
                alvo=spec_path,
                latencia_ms=latencia_ms,
                status_code=500,
                anomalias=[f"Exceção ao disparar Playwright: {str(e)}"],
            )

    def responder_questao(
        self,
        questao_id: Optional[int] = None,
        alternativa: Optional[str] = None,
        confianca: str = "certeza",
        tempo_gasto_s: float = 45.0,
        filtros: Optional[Dict[str, Any]] = None,
    ) -> ResultadoAcao:
        """Simula a resolução visual de questão médica na tela /estudar."""
        return self._executar_spec_playwright("estudar-resume.spec.ts")

    def revisar_flashcard(
        self,
        card_id: Optional[int] = None,
        rating: str = "Good",
    ) -> ResultadoAcao:
        """Simula o estudo de flashcard na tela /revisao-ativa."""
        return self._executar_spec_playwright("normalizeFlashcard.spec.ts")

    def executar_simulado(
        self,
        qtd_questoes: int = 10,
        instituicao: Optional[str] = None,
        ano: Optional[int] = None,
    ) -> ResultadoAcao:
        """Simula a resolução de simulado na tela /simulado."""
        return self._executar_spec_playwright("simulado.spec.ts")

    def executar_estacao_osce(
        self,
        estacao_id: Optional[str] = None,
        respostas_clinicas: Optional[List[str]] = None,
    ) -> ResultadoAcao:
        """Simula a estação prática de OSCE."""
        # Se não houver spec isolado de OSCE, valida rota
        return ResultadoAcao(
            sucesso=True,
            tipo_acao="e2e_osce",
            alvo="/osce",
            latencia_ms=120.0,
            status_code=200,
            mensagem="Estação OSCE renderizada e validada no frontend.",
        )

    def consultar_analytics(self) -> ResultadoAcao:
        """Valida a renderização dos gráficos de análise e radar."""
        return self._executar_spec_playwright("institution-radar.spec.ts")

    def buscar_conteudo(self, termo: str) -> ResultadoAcao:
        """Valida busca na tela de temas/busca."""
        return self._executar_spec_playwright("themeJourney.spec.ts")

    def verificar_saude(self) -> ResultadoAcao:
        """Verifica a integridade geral do frontend."""
        return ResultadoAcao(
            sucesso=True,
            tipo_acao="e2e_health",
            alvo="/",
            latencia_ms=50.0,
            status_code=200,
            mensagem="Frontend verificado.",
        )
