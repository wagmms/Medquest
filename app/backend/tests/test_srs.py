import json
from datetime import datetime, timezone

from fsrs import Rating

from api.srs import _rating, review


def test_rating_mapping():
    assert _rating(False, "certeza") == Rating.Again
    assert _rating(False, None) == Rating.Again
    assert _rating(True, "chutei") == Rating.Hard
    assert _rating(True, "duvida") == Rating.Good
    assert _rating(True, "certeza") == Rating.Easy
    assert _rating(True, None) == Rating.Good
    assert _rating(True, "unknown_value") == Rating.Good

def test_review_new_card():
    # Simulando primeira resposta (Acerto com duvida -> Good)
    card_json, due_iso = review(None, True, "duvida")
    
    assert card_json is not None
    assert due_iso is not None
    
    card_dict = json.loads(card_json)
    # A initial review with "Good" usually pushes due date a few minutes/days forward
    assert "due" in card_dict
    assert "state" in card_dict

def test_review_existing_card():
    # Cria estado inicial
    card_json_1, _ = review(None, True, "certeza")
    
    # Simula erro na proxima revisao
    card_json_2, due_iso_2 = review(card_json_1, False, None)
    card_dict_2 = json.loads(card_json_2)
    
    # State deve refletir aprendizado
    assert "due" in card_dict_2
    
    # Erro em questão médica que já tinha alta estabilidade -> agendamento de revisão espaçado
    due_date_2 = datetime.fromisoformat(due_iso_2)
    assert due_date_2 > datetime.now(timezone.utc)
    diff_days = (due_date_2 - datetime.now(timezone.utc)).total_seconds() / 86400
    assert diff_days >= 6.5


def test_review_question_intervals(monkeypatch):
    import api.srs as srs_mod
    monkeypatch.setattr(srs_mod._question_scheduler, "enable_fuzzing", False)

    # Errou questão -> 7 dias
    _, due_err = review(None, False, None)
    err_days = round((datetime.fromisoformat(due_err) - datetime.now(timezone.utc)).total_seconds() / 86400)
    assert 6 <= err_days <= 8

    # Chutei questão -> ~16 dias
    _, due_hard = review(None, True, "chutei")
    hard_days = round((datetime.fromisoformat(due_hard) - datetime.now(timezone.utc)).total_seconds() / 86400)
    assert 15 <= hard_days <= 17

    # Dúvida / Bom -> ~35 dias
    _, due_good = review(None, True, "duvida")
    good_days = round((datetime.fromisoformat(due_good) - datetime.now(timezone.utc)).total_seconds() / 86400)
    assert 34 <= good_days <= 36

    # Certeza / Fácil -> ~78 dias
    _, due_easy = review(None, True, "certeza")
    easy_days = round((datetime.fromisoformat(due_easy) - datetime.now(timezone.utc)).total_seconds() / 86400)
    assert 76 <= easy_days <= 80


def test_review_flashcard_intervals(monkeypatch):
    import api.srs as srs_mod
    monkeypatch.setattr(srs_mod._flashcard_scheduler, "enable_fuzzing", False)

    # Erro em flashcard -> 1 dia (mínimo D+1, sem passos em minutos)
    _, due_err = review(None, False, "errei", is_flashcard=True)
    err_days = round((datetime.fromisoformat(due_err) - datetime.now(timezone.utc)).total_seconds() / 86400)
    assert err_days == 1

    # Acerto fácil em flashcard -> ~7 dias
    _, due_easy = review(None, True, "certeza", is_flashcard=True)
    easy_days = round((datetime.fromisoformat(due_easy) - datetime.now(timezone.utc)).total_seconds() / 86400)
    assert 6 <= easy_days <= 8
