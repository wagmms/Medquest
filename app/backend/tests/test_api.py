"""Testes de integração da API (blueprints + validação + stats)."""


def test_meta(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    assert r.get_json()["total_questions"] == 3


def test_meta_cache_preserva_filtros_repetidos(client):
    usp = client.get("/api/meta?institution=USP-SP")
    ambas = client.get("/api/meta?institution=USP-SP&institution=USP-RP")
    assert usp.get_json()["total_questions"] == 1
    assert ambas.get_json()["total_questions"] == 2


def test_v1_alias(client):
    assert client.get("/api/v1/meta").status_code == 200


def test_attempt_correto(client):
    r = client.post("/api/questions/1/attempt",
                    json={"selected_letter": "B", "confidence": "certeza", "time_spent_ms": 12000})
    assert r.status_code == 200
    body = r.get_json()
    assert body["is_correct"] is True
    assert body["next_review_date"]
    assert body["explanation"] == "explicação da 1"


def test_attempt_errado(client):
    r = client.post("/api/questions/2/attempt", json={"selected_letter": "B"})  # correto é A
    assert r.get_json()["is_correct"] is False


def test_validacao_letra_invalida(client):
    r = client.post("/api/questions/1/attempt", json={"selected_letter": "Z"})
    assert r.status_code == 400


def test_overview_conta_tentativa(client):
    client.post("/api/questions/1/attempt", json={"selected_letter": "B"})
    ov = client.get("/api/stats/overview").get_json()
    assert ov["total_questions"] == 3
    assert ov["distinct_answered"] == 1
    assert ov["accuracy_latest_attempt"] == 1.0


def test_coverage(client):
    cov = client.get("/api/coverage").get_json()
    # Coverage is catalog-driven and must expose the five canonical study areas,
    # including areas for which the current database has no questions yet.
    assert len(cov["areas"]) == 5
    assert {area["area"] for area in cov["areas"]} >= {"Clínica Médica", "Cirurgia", "Pediatria"}


def test_planner_config_roundtrip(client):
    assert client.post("/api/planner/config",
                       json={"exam_date": "2026-11-15", "days_per_week": 6, "hours_per_day": 5}).status_code == 200
    cfg = client.get("/api/planner/config").get_json()
    assert cfg["hours_per_day"] == 5


def test_planner_config_validacao(client):
    r = client.post("/api/planner/config", json={"days_per_week": 99})  # > 7
    assert r.status_code == 400


def test_questions_limit_invalido_usa_padrao(client):
    r = client.get("/api/questions?limit=nao-e-numero")
    assert r.status_code == 200
    assert len(r.get_json()) == 3


def test_questions_limit_negativo_nao_fura_limite(client):
    r = client.get("/api/questions?limit=-1")
    assert r.status_code == 200
    assert len(r.get_json()) == 1


def test_review_rejeita_confianca_invalida(client):
    client.post("/api/questions/1/attempt", json={"selected_letter": "B"})
    r = client.post("/api/questions/1/review", json={"confidence": "qualquer-coisa"})
    assert r.status_code == 400


def test_weak_topics_aceita_min_attempts_invalido(client):
    r = client.get("/api/stats/weak-topics?min_attempts=abc")
    assert r.status_code == 200


def test_simulado_custom_rejeita_quantidade_invalida(client):
    r = client.post("/api/simulado/custom", json={"questions_per_area": "abc"})
    assert r.status_code == 400


def test_request_bodies_reject_unknown_fields(client):
    attempt = client.post(
        "/api/questions/1/attempt",
        json={"selected_letter": "B", "user_id": "another-user"},
    )
    assert attempt.status_code == 400

    simulado = client.post(
        "/api/simulado/custom",
        json={"questions_per_area": 10, "unexpected": True},
    )
    assert simulado.status_code == 400


def test_question_batch_validates_and_deduplicates_ids(client):
    invalid = client.post("/api/questions/batch", json={"ids": [1, -2]})
    assert invalid.status_code == 400

    response = client.post("/api/questions/batch", json={"ids": [1, 1]})
    assert response.status_code == 200
    assert [question["id"] for question in response.get_json()["questions"]] == [1]


def test_filters_status_new_e_unanswered(client):
    # Inicialmente as 3 questões não foram respondidas
    r_unanswered = client.get("/api/questions?status=unanswered")
    r_new = client.get("/api/questions?status=new")
    assert len(r_unanswered.get_json()) == 3
    assert len(r_new.get_json()) == 3

    # Responde à questão 1
    client.post("/api/questions/1/attempt", json={"selected_letter": "B"})

    # Ambas as queries agora devem retornar as questões restantes (2 e 3)
    r_unanswered_after = client.get("/api/questions?status=unanswered")
    r_new_after = client.get("/api/questions?status=new")
    assert len(r_unanswered_after.get_json()) == 2
    assert len(r_new_after.get_json()) == 2


def test_discursive_question_detail_and_self_assessment(client):
    # 1. Verifica flag is_discursive
    res_q1 = client.get("/api/questions/1")
    assert res_q1.status_code == 200
    assert res_q1.get_json()["is_discursive"] is False

    res_q3 = client.get("/api/questions/3")
    assert res_q3.status_code == 200
    assert res_q3.get_json()["is_discursive"] is True

    # 2. Revela resposta discursiva com defer -> is_correct deve vir None para autoavaliação
    attempt = client.post(
        "/api/questions/3/attempt",
        json={"selected_letter": "A", "confidence": "defer", "user_answer_text": "Raquitismo por falta de vit D"}
    )
    assert attempt.status_code == 200
    data = attempt.get_json()
    assert data["is_discursive"] is True
    assert data["is_correct"] is None
    assert data["explanation"] is not None

    # 3. Autoavaliação de erro (Errei)
    review = client.post(
        "/api/questions/3/review",
        json={"confidence": "duvida", "is_correct": False}
    )
    assert review.status_code == 200
    review_data = review.get_json()
    assert review_data["success"] is True
    assert review_data["is_correct"] is False
    assert review_data["next_review_date"] is not None

    # 4. Autoavaliação de acerto explícito em novo attempt
    attempt2 = client.post(
        "/api/questions/3/attempt",
        json={"selected_letter": "A", "confidence": "certeza", "is_correct": True}
    )
    assert attempt2.status_code == 200
    assert attempt2.get_json()["is_correct"] is True


def test_attempt_gabarito_duplo_e_anulada(client):
    from api.db import get_db
    with client.application.app_context():
        db = get_db()
        # Questão com recurso deferido e gabarito duplo (B ou C)
        db.execute("INSERT INTO questions(id, correct_letter, stem) VALUES (4, 'B, C', 'Questão dupla')")
        db.execute("INSERT INTO alternatives(question_id, letter, text, is_correct) VALUES (4, 'A', 'alt a', 0), (4, 'B', 'alt b', 1), (4, 'C', 'alt c', 1), (4, 'D', 'alt d', 0)")
        
        # Questão anulada pela banca
        db.execute("INSERT INTO questions(id, correct_letter, stem) VALUES (5, 'ANULADA', 'Questão anulada')")
        db.execute("INSERT INTO alternatives(question_id, letter, text, is_correct) VALUES (5, 'A', 'alt a', 1), (5, 'B', 'alt b', 1)")
        db.commit()

    # Tentativa na questão 4 com letra B (deve ser correta)
    r_b = client.post("/api/questions/4/attempt", json={"selected_letter": "B"})
    assert r_b.status_code == 200
    assert r_b.get_json()["is_correct"] is True

    # Tentativa na questão 4 com letra C (também deve ser correta)
    r_c = client.post("/api/questions/4/attempt", json={"selected_letter": "C"})
    assert r_c.status_code == 200
    assert r_c.get_json()["is_correct"] is True

    # Tentativa na questão 4 com letra A (deve ser incorreta)
    r_a = client.post("/api/questions/4/attempt", json={"selected_letter": "A"})
    assert r_a.status_code == 200
    assert r_a.get_json()["is_correct"] is False

    # Tentativa na questão 5 anulada (qualquer alternativa pontua como correta)
    r_anulada = client.post("/api/questions/5/attempt", json={"selected_letter": "A"})
    assert r_anulada.status_code == 200
    assert r_anulada.get_json()["is_correct"] is True


def test_pulo_do_gato_extraction_preserves_depth():
    from api.ai import _extract_pulo_do_gato, _extract_why_wrong
    explanation = """**Gabarito Oficial**: Letra A

**Pulo do Gato**: A otite média aguda requer identificação de abaulamento da membrana timpânica.
- Âncoras: início agudo (< 48h), febre e otalgia.
- Conduta: amoxicilina 90 mg/kg/dia se menor de 2 anos ou otite grave.

**Raciocínio Clínico**:
O quadro clínico detalhado aborda...

**Análise dos Distratores**:
- **Alternativa (B)**: Não se faz conduta expectante em lactente menor de 6 meses.
- **Alternativa (C)**: Ciprofloxacino não é a primeira linha em otite aguda não supurada.
"""
    pulo = _extract_pulo_do_gato(explanation)
    assert "abaulamento da membrana" in pulo
    assert "- Âncoras:" in pulo
    assert "- Conduta: amoxicilina 90 mg/kg/dia" in pulo
    assert "Raciocínio Clínico" not in pulo

    why_b = _extract_why_wrong(explanation, "B", "")
    assert "Não se faz conduta expectante" in why_b
    assert "Alternativa (C)" not in why_b


def test_unanswered_only_filter(client):
    # Inicialmente, nenhuma questão respondida
    res_all = client.get("/api/questions?unanswered_only=true")
    assert res_all.status_code == 200
    ids_initial = [q["id"] for q in res_all.get_json()]
    assert 1 in ids_initial

    # Responde a questão 1
    client.post("/api/questions/1/attempt", json={"selected_letter": "B"})

    # Com unanswered_only=true, questão 1 não deve vir
    res_unanswered = client.get("/api/questions?unanswered_only=true")
    assert res_unanswered.status_code == 200
    ids_after = [q["id"] for q in res_unanswered.get_json()]
    assert 1 not in ids_after

    # Com unanswered_only=false, questão 1 deve vir
    res_with_answered = client.get("/api/questions?unanswered_only=false")
    assert res_with_answered.status_code == 200
    ids_with_answered = [q["id"] for q in res_with_answered.get_json()]
    assert 1 in ids_with_answered


def test_questions_filter_by_area_year_and_subtema(client):
    # Filtro por área específica
    res_clinica = client.get("/api/questions?area=Clínica Médica")
    assert res_clinica.status_code == 200
    ids_clinica = [q["id"] for q in res_clinica.get_json()]
    assert ids_clinica == [1]

    res_ped = client.get("/api/questions?area=Pediatria")
    assert res_ped.status_code == 200
    ids_ped = [q["id"] for q in res_ped.get_json()]
    assert set(ids_ped) == {2, 3}

    # Filtro por ano
    res_2021 = client.get("/api/questions?year=2021")
    assert res_2021.status_code == 200
    assert [q["id"] for q in res_2021.get_json()] == [3]

    # Múltiplos anos
    res_mult_year = client.get("/api/questions?year=2021&year=2025")
    assert res_mult_year.status_code == 200
    assert set(q["id"] for q in res_mult_year.get_json()) == {1, 2, 3}

    # Ano sem questões
    res_vazio = client.get("/api/questions?year=1999")
    assert res_vazio.status_code == 200
    assert res_vazio.get_json() == []

    # Filtro por subtema
    res_sub = client.get("/api/questions?subtema=Imunização (PNI)")
    assert res_sub.status_code == 200
    assert [q["id"] for q in res_sub.get_json()] == [2]


def test_questions_filter_status_wrong_and_answered_progression(client):
    # Inicialmente nenhuma respondida ou errada
    assert client.get("/api/questions?status=wrong").get_json() == []
    assert client.get("/api/questions?status=answered").get_json() == []

    # Usuário erra a questão 2 (correta é A, envia B)
    attempt_errado = client.post("/api/questions/2/attempt", json={"selected_letter": "B"})
    assert attempt_errado.status_code == 200
    assert attempt_errado.get_json()["is_correct"] is False

    # Deve constar em wrong e answered
    res_wrong = client.get("/api/questions?status=wrong")
    assert [q["id"] for q in res_wrong.get_json()] == [2]

    res_answered = client.get("/api/questions?status=answered")
    assert [q["id"] for q in res_answered.get_json()] == [2]

    # Agora o usuário acerta a questão 2 (envia A)
    attempt_certo = client.post("/api/questions/2/attempt", json={"selected_letter": "A"})
    assert attempt_certo.status_code == 200
    assert attempt_certo.get_json()["is_correct"] is True

    # Como a última tentativa é acerto, não deve mais aparecer em status=wrong
    res_wrong_after = client.get("/api/questions?status=wrong")
    assert res_wrong_after.get_json() == []

    # Mas continua em status=answered
    res_answered_after = client.get("/api/questions?status=answered")
    assert [q["id"] for q in res_answered_after.get_json()] == [2]


def test_questions_favorite_toggle_and_filter(client):
    # Sem favoritos inicialmente
    assert client.get("/api/questions?favorite=1").get_json() == []

    # Alterna favorito para a questão 1 (toggle padrão ativa favorito)
    fav_on = client.post("/api/questions/1/favorite")
    assert fav_on.status_code == 200
    assert fav_on.get_json()["is_favorite"] is True

    # Filtro favorite=1 agora inclui a questão 1
    res_fav = client.get("/api/questions?favorite=1")
    assert [q["id"] for q in res_fav.get_json()] == [1]

    # Detalhe da questão reflete status favorito
    detail = client.get("/api/questions/1")
    assert detail.status_code == 200
    assert detail.get_json()["is_favorite"] is True

    # Desfavorita explicitamente
    fav_off = client.post("/api/questions/1/favorite", json={"is_favorite": False})
    assert fav_off.status_code == 200
    assert fav_off.get_json()["is_favorite"] is False

    # Filtro favorite=1 deve voltar a ser vazio
    assert client.get("/api/questions?favorite=1").get_json() == []


def test_question_detail_and_attempt_not_found(client):
    # Detalhe de questão inexistente retorna 404
    r_detail = client.get("/api/questions/99999")
    assert r_detail.status_code == 404
    assert r_detail.get_json()["error"] == "not found"

    # Tentativa em questão inexistente retorna 404
    r_attempt = client.post("/api/questions/99999/attempt", json={"selected_letter": "A"})
    assert r_attempt.status_code == 404
    assert r_attempt.get_json()["error"] == "not found"

    # Review em questão sem tentativa retorna 400
    r_review = client.post("/api/questions/99999/review", json={"confidence": "certeza"})
    assert r_review.status_code == 400
    assert r_review.get_json()["error"] == "No attempt found"


def test_questions_count_with_filters(client):
    # Total geral
    c_all = client.get("/api/questions/count")
    assert c_all.status_code == 200
    assert c_all.get_json()["count"] == 3

    # Por grande área
    c_ped = client.get("/api/questions/count?area=Pediatria")
    assert c_ped.status_code == 200
    assert c_ped.get_json()["count"] == 2

    # Por instituição
    c_usp = client.get("/api/questions/count?institution=USP-SP")
    assert c_usp.status_code == 200
    assert c_usp.get_json()["count"] == 1

    # Por área sem questões
    c_cir = client.get("/api/questions/count?area=Cirurgia")
    assert c_cir.status_code == 200
    assert c_cir.get_json()["count"] == 0


def test_stats_overview_zero_state_and_tz_offset(client):
    # Estado inicial sem respostas
    ov = client.get("/api/stats/overview")
    assert ov.status_code == 200
    body = ov.get_json()
    assert body["total_questions"] == 3
    assert body["distinct_answered"] == 0
    assert body["total_attempts"] == 0
    assert body["accuracy_all_attempts"] is None

    # Parâmetro tz_offset inválido deve cair em fallback seguro
    ov_invalid_tz = client.get("/api/stats/overview?tz_offset=invalid_offset")
    assert ov_invalid_tz.status_code == 200
    assert ov_invalid_tz.get_json()["total_questions"] == 3


def test_stats_breakdown_all_dimensions_and_invalid(client):
    # Registra uma tentativa para alimentar estatísticas
    client.post("/api/questions/1/attempt", json={"selected_letter": "B"})

    for dimension in ["area", "institution", "subtema", "year"]:
        r = client.get(f"/api/stats/breakdown?by={dimension}")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    # Dimensão inválida deve retornar 400
    r_invalida = client.get("/api/stats/breakdown?by=hacker_column")
    assert r_invalida.status_code == 400
    assert r_invalida.get_json()["error"] == "invalid 'by'"


def test_stats_timeline_and_distractors_with_attempts(client):
    # Sem erros inicialmente, distratores retorna lista vazia
    assert client.get("/api/stats/distractors").get_json() == []

    # Submete tentativa incorreta na questão 1 (seleciona A, gabarito B)
    client.post("/api/questions/1/attempt", json={"selected_letter": "A"})

    # Distratores agora deve listar o erro
    dist = client.get("/api/stats/distractors")
    assert dist.status_code == 200
    data = dist.get_json()
    assert len(data) >= 1
    assert data[0]["subtema"] == "Hipertensão Arterial Sistêmica"
    assert any(c["letter"] == "A" for c in data[0]["wrong_choices"])

    # Timeline registra o dia de estudo
    tl = client.get("/api/stats/timeline")
    assert tl.status_code == 200
    assert len(tl.get_json()) >= 1

    # Timeline aceita parâmetro days
    assert client.get("/api/stats/timeline?days=7").status_code == 200
    assert client.get("/api/stats/timeline?days=invalid").status_code == 200


def test_adaptive_focus_modes_and_fallback(client):
    # Testa os três perfis de foco adaptativo
    for focus in ["balanced", "retention", "coverage"]:
        r = client.get(f"/api/questions?mode=adaptive&adaptive_focus={focus}&limit=2")
        assert r.status_code == 200
        items = r.get_json()
        assert len(items) <= 2
        for item in items:
            assert "id" in item
            assert "adaptive_score" in item
            assert "adaptive_reasons" in item

    # Foco inválido deve fazer fallback seguro para 'balanced' sem falhar
    r_fallback = client.get("/api/questions?mode=adaptive&adaptive_focus=desconhecido&limit=2")
    assert r_fallback.status_code == 200
    assert len(r_fallback.get_json()) <= 2


def test_questions_remediation_endpoints(client):
    # Fila de remediação sem erros do aluno cai no fallback de tópicos de alto impacto
    rem_geral = client.get("/api/questions/remediation")
    assert rem_geral.status_code == 200
    assert isinstance(rem_geral.get_json(), list)

    # Remediação com limite abaixo do mínimo respeita o limitador
    rem_limit = client.get("/api/questions/remediation?limit=-5")
    assert rem_limit.status_code == 200
    assert len(rem_limit.get_json()) >= 1

    # Remediação via rota principal com subtema
    rem_mode = client.get("/api/questions?mode=remediation&subtema=Hipertensão+Arterial+Sistêmica")
    assert rem_mode.status_code == 200
    assert isinstance(rem_mode.get_json(), list)


