"""Testes de integração herméticos para o blueprint de flashcards."""


def test_flashcards_generate_and_review(client):
    # Gera flashcard a partir do erro na questão 1 (resposta certa B, marcou A)
    r = client.post("/api/flashcards/generate", json={
        "question_id": 1,
        "wrong_letter": "A"
    })
    assert r.status_code == 200
    data = r.get_json()
    assert "id" in data
    assert data["question_id"] == 1
    assert "front" in data
    assert "back" in data
    fid = data["id"]

    # Consulta flashcards vencidos
    r_due = client.get("/api/flashcards/review")
    assert r_due.status_code == 200
    due_list = r_due.get_json()
    assert len(due_list) >= 1
    assert any(card["id"] == fid for card in due_list)

    # Executa revisão do flashcard com 'certeza'
    r_rev = client.post(f"/api/flashcards/{fid}/review", json={
        "confidence": "certeza"
    })
    assert r_rev.status_code == 200
    rev_data = r_rev.get_json()
    assert rev_data["id"] == fid
    assert "next_review_date" in rev_data

    # A fila diária não pode reapresentar um cartão recém-agendado.
    due_after_review = client.get("/api/flashcards/review").get_json()
    assert not any(card["id"] == fid for card in due_after_review)

    # Reporta flashcard
    r_rep = client.post(f"/api/flashcards/{fid}/report", json={
        "reason": "Erro de digitação no enunciado"
    })
    assert r_rep.status_code == 200
    assert r_rep.get_json()["success"] is True
    all_visible = client.get("/api/flashcards/review?all=true").get_json()
    assert not any(card["id"] == fid for card in all_visible)


def test_flashcards_validation_errors(client):
    # Campos obrigatórios ausentes
    r = client.post("/api/flashcards/generate", json={})
    assert r.status_code == 400

    # Questão inexistente
    r = client.post("/api/flashcards/generate", json={
        "question_id": 9999,
        "wrong_letter": "A"
    })
    assert r.status_code == 404

    # Confiança inválida no review
    r = client.post("/api/flashcards/1/review", json={
        "confidence": "invalido"
    })
    assert r.status_code == 400

    # Flashcard inexistente
    r = client.post("/api/flashcards/9999/review", json={
        "confidence": "certeza"
    })
    assert r.status_code == 404

    # Report sem motivo
    r = client.post("/api/flashcards/1/report", json={})
    assert r.status_code == 400

    # Campos desconhecidos não podem atravessar a whitelist do schema.
    r = client.post("/api/flashcards/save", json={
        "question_id": 1,
        "front": "card",
        "user_id": "another-user",
    })
    assert r.status_code == 400


def test_flashcards_duplicate_prevention(client):
    # Gera primeira vez
    r1 = client.post("/api/flashcards/generate", json={
        "question_id": 1,
        "wrong_letter": "A"
    })
    assert r1.status_code == 200
    fid1 = r1.get_json()["id"]

    # Gera novamente para a mesma questão
    r2 = client.post("/api/flashcards/generate", json={
        "question_id": 1,
        "wrong_letter": "A"
    })
    assert r2.status_code == 200
    fid2 = r2.get_json()["id"]

    # Deve reutilizar o mesmo ID sem duplicar o cartão
    assert fid1 == fid2


def test_imported_anki_cards_do_not_require_a_medquest_question(client):
    payload = {
        "deck_name": "Revisão Anki",
        "cards": [{
            "front": "Pergunta importada",
            "back": "Resposta importada",
            "deck_name": "Revisão Anki",
            "tags": ["anki", "teste"],
            "anki_nid": 123456,
        }],
    }

    imported = client.post("/api/flashcards/import/batch", json=payload)
    assert imported.status_code == 200
    assert imported.get_json()["new_cards"] == 1

    # Reimportar a mesma nota deve atualizar o cartão, sem criar duplicata.
    payload["cards"][0]["back"] = "Resposta atualizada"
    updated = client.post("/api/flashcards/import/batch", json=payload)
    assert updated.status_code == 200
    assert updated.get_json()["new_cards"] == 0
    cards = client.get("/api/flashcards/review?all=true").get_json()
    imported_card = next(card for card in cards if card["front"] == "Pergunta importada")
    assert imported_card["back"] == "Resposta atualizada"


def test_simulado_session_is_saved(client):
    response = client.post("/api/simulado/sessions", json={
        "client_session_id": "session-test-123",
        "planned_duration_seconds": 5400,
        "elapsed_seconds": 5100,
        "total_questions": 50,
        "answered_count": 48,
        "correct_count": 34,
        "filters": {"institutions": ["USP-SP"]},
        "area_results": [{"area": "Pediatria", "correct": 8, "total": 10}],
    })
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_flashcards_generate_batch(client):
    r = client.post("/api/flashcards/generate-batch", json={
        "items": [
            {"question_id": 1, "wrong_letter": "A"},
            {"question_id": 2, "wrong_letter": "B"},
            {"question_id": 9999, "wrong_letter": "A"}  # Questão inválida ignorada graciosamente
        ]
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert data["count"] >= 1
    assert len(data["flashcards"]) >= 1


def test_flashcards_batch_rejects_duplicates_and_avoids_n_plus_one(client, monkeypatch):
    duplicate = client.post("/api/flashcards/generate-batch", json={
        "items": [
            {"question_id": 1, "wrong_letter": "A"},
            {"question_id": 1, "wrong_letter": "A"},
        ]
    })
    assert duplicate.status_code == 400

    from api import db as db_module
    from api import flashcards as flashcards_module

    select_count = 0

    class CountingConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=()):
            nonlocal select_count
            if sql.lstrip().upper().startswith("SELECT"):
                select_count += 1
            return self.connection.execute(sql, parameters)

        def commit(self):
            self.connection.commit()

        def rollback(self):
            self.connection.rollback()

    monkeypatch.setattr(
        flashcards_module,
        "get_db",
        lambda: CountingConnection(db_module.get_db()),
    )
    response = client.post("/api/flashcards/generate-batch", json={
        "items": [
            {"question_id": 1, "wrong_letter": "A"},
            {"question_id": 2, "wrong_letter": "B"},
        ]
    })
    assert response.status_code == 200
    assert response.get_json()["count"] == 2
    assert select_count == 3


def test_bounded_int():
    from api.flashcards import _bounded_int

    # Normal cases
    assert _bounded_int(50, 10, 1, 100) == 50
    assert _bounded_int(1, 10, 1, 100) == 1
    assert _bounded_int(100, 10, 1, 100) == 100

    # String numbers
    assert _bounded_int("50", 10, 1, 100) == 50
    assert _bounded_int("1", 10, 1, 100) == 1
    assert _bounded_int("100", 10, 1, 100) == 100

    # Floats (cast to int by int())
    assert _bounded_int(50.5, 10, 1, 100) == 50

    # Out of bounds
    assert _bounded_int(-10, 10, 1, 100) == 1
    assert _bounded_int(0, 10, 1, 100) == 1
    assert _bounded_int(101, 10, 1, 100) == 100
    assert _bounded_int(500, 10, 1, 100) == 100

    # Invalid inputs
    assert _bounded_int(None, 10, 1, 100) == 10
    assert _bounded_int("invalid", 10, 1, 100) == 10
    assert _bounded_int("", 10, 1, 100) == 10
    assert _bounded_int([], 10, 1, 100) == 10


def test_anki_sync_state_batch_and_no_n_plus_one(client, monkeypatch):
    # Import 2 cards via batch import
    imported = client.post("/api/flashcards/import/batch", json={
        "deck_name": "Test Deck",
        "cards": [
            {
                "front": "Front 1",
                "back": "Back 1",
                "anki_cid": 1001,
                "anki_nid": 2001,
            },
            {
                "front": "Front 2",
                "back": "Back 2",
                "anki_cid": 1002,
                "anki_nid": 2002,
            },
        ]
    })
    assert imported.status_code == 200

    from api import db as db_module
    from api import flashcards as flashcards_module

    select_count = 0

    class CountingConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=()):
            nonlocal select_count
            if sql.lstrip().upper().startswith("SELECT"):
                select_count += 1
            return self.connection.execute(sql, parameters)

        def executemany(self, sql, seq_of_parameters=()):
            nonlocal select_count
            if sql.lstrip().upper().startswith("SELECT"):
                select_count += len(list(seq_of_parameters))
            return self.connection.executemany(sql, seq_of_parameters)

        def commit(self):
            self.connection.commit()

        def rollback(self):
            self.connection.rollback()

    monkeypatch.setattr(
        flashcards_module,
        "get_db",
        lambda: CountingConnection(db_module.get_db()),
    )

    # Sync state for both cards + one non-existent card
    # Card 1 and 2 match by anki_cid. Card 3 (9999) fails anki_cid and triggers a single bulk fallback SELECT for anki_nid (8888).
    sync_resp = client.post("/api/flashcards/anki/sync-state", json={
        "cards": [
            {"anki_cid": 1001, "anki_nid": 2001, "interval": 10, "reps": 1, "lapses": 0},
            {"anki_cid": 1002, "anki_nid": 2002, "interval": -600, "reps": 2, "lapses": 1},
            {"anki_cid": 9999, "anki_nid": 8888, "interval": 1, "reps": 0, "lapses": 0},
        ]
    })
    assert sync_resp.status_code == 200
    data = sync_resp.get_json()
    assert data["success"] is True
    assert data["updated"] == 2
    # Exactly 2 bulk SELECTs: 1 for anki_cid chunk, 1 for unmatched anki_nid fallback chunk
    assert select_count == 2

    select_count = 0
    # Sync state when all cards match by anki_cid -> requires only 1 bulk SELECT query
    sync_resp2 = client.post("/api/flashcards/anki/sync-state", json={
        "cards": [
            {"anki_cid": 1001, "anki_nid": 2001, "interval": 12, "reps": 2, "lapses": 0},
            {"anki_cid": 1002, "anki_nid": 2002, "interval": 15, "reps": 3, "lapses": 0},
        ]
    })
    assert sync_resp2.status_code == 200
    assert sync_resp2.get_json()["updated"] == 2
    assert select_count == 1


def test_anki_import_batch_no_n_plus_one(client, monkeypatch):
    from api import db as db_module
    from api import flashcards as flashcards_module

    select_count = 0

    class CountingConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=()):
            nonlocal select_count
            if sql.lstrip().upper().startswith("SELECT"):
                select_count += 1
            return self.connection.execute(sql, parameters)

        def commit(self):
            self.connection.commit()

        def rollback(self):
            self.connection.rollback()

    monkeypatch.setattr(
        flashcards_module,
        "get_db",
        lambda: CountingConnection(db_module.get_db()),
    )

    # Import 5 cards in a single batch
    cards_payload = [
        {"front": f"Front {i}", "back": f"Back {i}", "anki_nid": 3000 + i, "anki_cid": 4000 + i}
        for i in range(5)
    ]
    resp = client.post("/api/flashcards/import/batch", json={"deck_name": "Bulk Deck", "cards": cards_payload})
    assert resp.status_code == 200
    assert resp.get_json()["new_cards"] == 5
    # Should perform only 1 bulk SELECT for existing anki_nids, rather than 5 individual SELECT queries
    assert select_count == 1
