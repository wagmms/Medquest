"""
==============================================================================
MEDQUEST · TESTADOR MASTER: DRIVER BASE
==============================================================================
Contrato abstrato de execução para os drivers de teste (API e E2E Playwright).
==============================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ResultadoAcao:
    """Resultado padronizado de uma ação executada por uma persona."""
    sucesso: bool
    tipo_acao: str
    alvo: str  # URL, endpoint ou seletor
    latencia_ms: float
    status_code: Optional[int] = None
    dados: Dict[str, Any] = field(default_factory=dict)
    mensagem: str = ""
    anomalias: List[str] = field(default_factory=list)
    pensamento: str = ""


class DriverBase(ABC):
    """Interface abstrata obrigatória para todos os drivers do Testador Master."""

    @abstractmethod
    def inicializar(self) -> bool:
        """Inicializa conexões, clientes ou instâncias necessárias."""
        pass

    @abstractmethod
    def finalizar(self) -> None:
        """Limpa recursos, fecha navegadores ou conexões de teste."""
        pass

    @abstractmethod
    def responder_questao(
        self,
        questao_id: Optional[int] = None,
        alternativa: Optional[str] = None,
        confianca: str = "certeza",  # certeza, duvida, chute, erro
        tempo_gasto_s: float = 45.0,
        filtros: Optional[Dict[str, Any]] = None,
    ) -> ResultadoAcao:
        """Simula a resolução de uma questão médica com registro FSRS."""
        pass

    @abstractmethod
    def revisar_flashcard(
        self,
        card_id: Optional[int] = None,
        rating: str = "Good",  # Again, Hard, Good, Easy
    ) -> ResultadoAcao:
        """Simula a revisão de um flashcard médico com agendamento FSRS."""
        pass

    @abstractmethod
    def executar_simulado(
        self,
        qtd_questoes: int = 10,
        instituicao: Optional[str] = None,
        ano: Optional[int] = None,
    ) -> ResultadoAcao:
        """Simula a criação e submissão de caderno de simulado cronometrado."""
        pass

    @abstractmethod
    def executar_estacao_osce(
        self,
        estacao_id: Optional[str] = None,
        respostas_clinicas: Optional[List[str]] = None,
    ) -> ResultadoAcao:
        """Simula a realização de uma estação prática clínica OSCE."""
        pass

    @abstractmethod
    def consultar_analytics(self) -> ResultadoAcao:
        """Consulta métricas de proficiência, TRI e radar institucional."""
        pass

    @abstractmethod
    def buscar_conteudo(self, termo: str) -> ResultadoAcao:
        """Executa busca semântica/FTS em questões ou temas."""
        pass

    @abstractmethod
    def verificar_saude(self) -> ResultadoAcao:
        """Verifica a integridade das rotas principais e do banco."""
        pass
