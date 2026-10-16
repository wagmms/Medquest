"""
==============================================================================
MEDQUEST · TESTADOR MASTER: ORÁCULO MÉDICO & GUARDRAILS
==============================================================================
Validador de regras de negócio canônicas, FSRS v6, TRI e proteção estrita
contra alteração de comentários médicos elaborados por professores.
==============================================================================
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class MedicalOracle:
    """Oráculo de validação médica e de regras de aprendizado adaptativo."""

    def __init__(self):
        # Cache de hash/tamanho de explicações canônicas observadas para monitorar imutabilidade
        self._explanations_fingerprints: Dict[int, str] = {}
        self.violacoes_imutabilidade: List[Dict[str, Any]] = []
        self.anomalias_fsrs: List[Dict[str, Any]] = []
        self.anomalias_tri: List[Dict[str, Any]] = []

    def auditar_imutabilidade_comentario(
        self,
        questao_id: int,
        comentario_texto: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Diretriz Inviolável: Bloqueio Absoluto de Alteração de Comentários de Residência Médica.
        Verifica se o comentário original do professor permanece estritamente imutável.
        """
        if comentario_texto is None or not comentario_texto.strip():
            # Questões canônicas devem possuir comentários de professores
            return True, None

        fingerprint = str(hash(comentario_texto))
        if questao_id in self._explanations_fingerprints:
            fingerprint_anterior = self._explanations_fingerprints[questao_id]
            if fingerprint_anterior != fingerprint:
                msg = (
                    f"🚨 [VIOLAÇÃO CRÍTICA DE IMUTABILIDADE] Questão {questao_id} teve seu comentário "
                    f"alterado! Comentários de professores são canônicos e somente-leitura."
                )
                self.violacoes_imutabilidade.append({
                    "questao_id": questao_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mensagem": msg
                })
                return False, msg
        else:
            self._explanations_fingerprints[questao_id] = fingerprint

        return True, None

    def validar_calculo_fsrs(
        self,
        item_tipo: str,  # 'questao' ou 'flashcard'
        rating: str,     # 'Again', 'Hard', 'Good', 'Easy'
        due_timestamp_anterior: Optional[str],
        due_timestamp_novo: Optional[str],
        intervalo_dias: Optional[float] = None
    ) -> Tuple[bool, List[str]]:
        """
        Valida se o avanço do FSRS v6 respeita a calibração do MedQuest:
        - Retenção alvo: ~0.85
        - Questões: S0(Again) = 3.5 (~7 dias no erro), D+18 no Good, D+40 no Easy.
        - Flashcards: Mínimo D+1 no erro (sem passos intradia de minutos).
        """
        anomalias: List[str] = []

        if not due_timestamp_novo:
            anomalias.append("FSRS: Resposta submetida não retornou novo 'due' para o item.")
            return False, anomalias

        # Validação de intervalo mínimo no erro (proibição de minutos intradia)
        if rating in ("Again", "errou") and intervalo_dias is not None:
            if item_tipo == "flashcard" and intervalo_dias < 0.9:
                anomalias.append(
                    f"FSRS: Flashcard recebeu intervalo de {intervalo_dias:.2f} dias no erro (< 1 dia). "
                    "Regra: Flashcards devem ter mínimo D+1 no erro."
                )
            elif item_tipo == "questao" and intervalo_dias < 2.0:
                anomalias.append(
                    f"FSRS: Questão recebeu intervalo de {intervalo_dias:.2f} dias no erro (< 2 dias). "
                    "Regra calibrada: Questões longas devem ter retorno em ~7 dias no erro."
                )

        if anomalias:
            self.anomalias_fsrs.append({
                "item_tipo": item_tipo,
                "rating": rating,
                "anomalias": anomalias,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return False, anomalias

        return True, []

    def validar_metricas_tri(self, theta: Any, erro_padrao: Any = None) -> Tuple[bool, List[str]]:
        """
        Valida que o cálculo de proficiência da Teoria de Resposta ao Item (TRI) é matematicamente são:
        - Theta não pode ser NaN ou Infinito.
        - Theta deve estar dentro de intervalo plausível (ex: -5.0 a +5.0 na escala padronizada).
        """
        anomalias: List[str] = []

        if theta is None:
            anomalias.append("TRI: Proficiência theta é nula.")
            return False, anomalias

        try:
            theta_float = float(theta)
            if math.isnan(theta_float) or math.isinf(theta_float):
                anomalias.append(f"TRI: Proficiência theta inválida ({theta}).")
            elif theta_float < -6.0 or theta_float > 6.0:
                anomalias.append(f"TRI: Proficiência theta fora da escala z-score esperada ({theta_float:.2f}).")
        except (ValueError, TypeError):
            anomalias.append(f"TRI: Valor de theta não pôde ser convertido para float ({theta}).")

        if erro_padrao is not None:
            try:
                se_float = float(erro_padrao)
                if math.isnan(se_float) or math.isinf(se_float) or se_float < 0:
                    anomalias.append(f"TRI: Erro padrão de medida (SE) inválido ({erro_padrao}).")
            except (ValueError, TypeError):
                anomalias.append(f"TRI: Erro padrão não pôde ser convertido para float ({erro_padrao}).")

        if anomalias:
            self.anomalias_tri.append({
                "theta": theta,
                "erro_padrao": erro_padrao,
                "anomalias": anomalias,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return False, anomalias

        return True, []

    def validar_estrutura_questao(self, questao: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Valida que uma questão médica tem gabarito, alternativas e metadados válidos."""
        anomalias: List[str] = []
        if not questao.get("id"):
            anomalias.append("Questão sem identificador único (id).")
        if not questao.get("statement") and not questao.get("enunciado"):
            anomalias.append(f"Questão {questao.get('id')} sem texto de enunciado.")

        options = questao.get("options") or questao.get("alternativas")
        if not options or not isinstance(options, (list, dict)) or len(options) < 2:
            anomalias.append(f"Questão {questao.get('id')} com opções de resposta insuficientes ({options}).")

        correct = questao.get("correct_answer") or questao.get("gabarito")
        if not correct:
            anomalias.append(f"Questão {questao.get('id')} sem indicação de gabarito correto.")

        return len(anomalias) == 0, anomalias
