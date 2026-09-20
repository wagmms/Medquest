"""Repetição espaçada com FSRS (estado da arte), substituindo o SM-2 simplificado.

Mapeia a resposta da questão para uma nota FSRS:
  - errou               -> Again
  - acertou + "chutei"  -> Hard
  - acertou + "duvida"  -> Good
  - acertou + "certeza" -> Easy
  - acertou (sem info)  -> Good
"""
import json
from datetime import timezone

from fsrs import Card, Rating, Scheduler

# Parâmetros padrão do FSRS v6
_DEFAULT_PARAMS = list(Scheduler().parameters)

# Parâmetros calibrados para questões médicas longas (Opção 2: ciclo semanal, mínimo 7 dias no erro)
# S0(Again) = 3.5 (~7d), S0(Hard) = 8.0 (~15d), S0(Good) = 18.0 (~34d), S0(Easy) = 40.0 (~76d)
_QUESTION_PARAMS = list(_DEFAULT_PARAMS)
_QUESTION_PARAMS[0] = 3.5
_QUESTION_PARAMS[1] = 8.0
_QUESTION_PARAMS[2] = 18.0
_QUESTION_PARAMS[3] = 40.0

# Scheduler para questões de prova (sem passos intradia, retenção alvo 85%, intervalos longos)
_question_scheduler = Scheduler(
    parameters=_QUESTION_PARAMS,
    desired_retention=0.85,
    learning_steps=(),
    relearning_steps=(),
    enable_fuzzing=True,
)

# Scheduler para flashcards atômicos (sem passos intradia de minutos; mínimo D+1 no erro)
_flashcard_scheduler = Scheduler(
    learning_steps=(),
    relearning_steps=(),
    enable_fuzzing=True,
)

_CONFIDENCE_MAP = {
    "chutei": Rating.Hard,
    "duvida": Rating.Good,
    "certeza": Rating.Easy,
}


def _rating(is_correct, confidence):
    if not is_correct:
        return Rating.Again
    return _CONFIDENCE_MAP.get((confidence or "").lower(), Rating.Good)


def review(card_json, is_correct, confidence=None, is_flashcard=False):
    """Recebe o estado do card (JSON ou None) e devolve (novo_json, próxima_revisão_iso)."""
    scheduler = _flashcard_scheduler if is_flashcard else _question_scheduler
    card = Card.from_dict(json.loads(card_json)) if card_json else Card()
    card, _log = scheduler.review_card(card, _rating(is_correct, confidence))
    due_iso = card.due.astimezone(timezone.utc).isoformat()
    return json.dumps(card.to_dict()), due_iso
