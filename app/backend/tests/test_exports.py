"""Testes de exportações externas (Anki e iCalendar .ics)."""
import pytest


def test_export_anki_header_and_format(client):
    res = client.get("/api/flashcards/export/anki")
    assert res.status_code == 200
    assert "text/plain" in res.headers.get("Content-Type", "")
    text = res.get_data(as_text=True)
    assert "#separator:tab" in text
    assert "#deck:MedQuest::Revisão_Ativa" in text
    assert "#notetype:Cloze" in text


def test_export_anki_with_generated_card(client):
    # Gera um flashcard para teste
    gen_res = client.post("/api/flashcards/generate", json={"question_id": 1, "wrong_letter": "A"})
    assert gen_res.status_code == 200

    res = client.get("/api/flashcards/export/anki")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "{{c1::" in text
    assert "MedQuest" in text
    assert "Area::" in text or "Subtema::" in text


def test_export_anki_includes_unlinked_cards_and_custom_tags(client):
    # Import unlinked card with custom deck and tags
    imported = client.post("/api/flashcards/import/batch", json={
        "deck_name": "Infectologia",
        "cards": [{
            "front": "Qual o patógeno de {{c1::Doença de Chagas}}?",
            "back": "Trypanosoma cruzi",
            "tags": ["parasitologia", "chagas"],
            "anki_nid": 88812,
        }, {
            "front": "Card reportado que não deve sair no export",
            "back": "Gabarito errado",
            "anki_nid": 88813,
        }]
    })
    assert imported.status_code == 200

    # Report the second card
    cards = client.get("/api/flashcards/review?deck=Infectologia").get_json()
    rep_card = next(c for c in cards if "Card reportado" in c["front"])
    r_rep = client.post(f"/api/flashcards/{rep_card['id']}/report", json={"reason": "Erro"})
    assert r_rep.status_code == 200

    # Export to Anki text
    res = client.get("/api/flashcards/export/anki")
    assert res.status_code == 200
    text = res.get_data(as_text=True)

    # Must contain the unlinked card and its tags
    assert "Qual o patógeno de {{c1::Doença de Chagas}}?" in text
    assert "Trypanosoma cruzi" in text
    assert "Baralho::Infectologia" in text
    assert "parasitologia" in text
    assert "chagas" in text

    # Must NOT contain the reported card
    assert "Card reportado que não deve sair no export" not in text



def test_export_ics_calendar(client):
    # Salva configuração de teste
    client.post("/api/planner/config", json={
        "start_date": "2026-08-24T12:00:00Z",
        "exam_date": "2026-11-15T12:00:00Z",
        "days_per_week": 6,
        "hours_per_day": 4,
        "target_score": 78
    })

    res = client.get("/api/planner/export/ics")
    assert res.status_code == 200
    assert "text/calendar" in res.headers.get("Content-Type", "")
    text = res.get_data(as_text=True)
    assert "BEGIN:VCALENDAR" in text
    assert "VERSION:2.0" in text
    assert "BEGIN:VEVENT" in text
    assert "📖" in text or "Aula:" in text or "Semana" in text
    # As revisões são geradas dinamicamente pelo FSRS e não devem poluir a agenda com eventos estáticos
    assert "Revisão 24h" not in text
    assert "Revisão 7d" not in text
    assert "Revisão 30d" not in text
    assert "END:VCALENDAR" in text


def test_calendar_feed_endpoint(client):
    res = client.get("/api/planner/calendar/feed")
    assert res.status_code == 200
    assert "text/calendar" in res.headers.get("Content-Type", "")
    text = res.get_data(as_text=True)
    assert "BEGIN:VCALENDAR" in text
    assert "END:VCALENDAR" in text


def test_calendar_feed_ignores_user_id_query_parameter(client, monkeypatch):
    from api import plan

    captured = {}

    def fake_calendar_content(_db, user_id):
        captured["user_id"] = user_id
        return "BEGIN:VCALENDAR\r\nEND:VCALENDAR"

    monkeypatch.setattr(plan, "_generate_calendar_ics_content", fake_calendar_content)
    res = client.get("/api/planner/calendar/feed?user_id=another-user")

    assert res.status_code == 200
    assert captured["user_id"] == "1"
