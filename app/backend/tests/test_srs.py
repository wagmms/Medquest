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


def test_review_recupera_json_corrompido_ou_invalido():
    """Garante que payloads malformados ou esquemas corrompidos não gerem exceção."""
    # 1. String JSON inválida/truncada
    card_json_1, due_iso_1 = review("{corrompido: true", True, "certeza")
    assert card_json_1 is not None
    assert due_iso_1 is not None
    dict_1 = json.loads(card_json_1)
    assert "due" in dict_1
    assert "state" in dict_1

    # 2. JSON válido mas tipo não-objeto (array ou número)
    card_json_2, due_iso_2 = review("[1, 2, 3]", False, None)
    assert card_json_2 is not None
    assert due_iso_2 is not None

    # 3. Dicionário com chaves incompatíveis
    card_json_3, due_iso_3 = review('{"chave_aleatoria": 42}', True, "duvida")
    assert card_json_3 is not None
    assert due_iso_3 is not None

    # 4. String vazia
    card_json_4, due_iso_4 = review("", True, "chutei")
    assert card_json_4 is not None
    assert due_iso_4 is not None


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


class TestFSRSValidation:
    """Suíte de testes de estresse e validação de invariantes do motor FSRS v6.

    Garante que:
    1. A retenção desejada está estritamente calibrada em 0.85 para questões de prova.
    2. Passos intradia (learning_steps e relearning_steps) estão desabilitados (tupla vazia).
    3. Intervalos nunca retornam valores negativos em nenhum cenário ou transição.
    4. Nenhuma revisão gera agendamento intradia (< 24 horas).
    5. Sequências extremas de falhas consecutivas (Again repetidos) ou lapsos pós-maturidade
       mantêm a integridade temporal do scheduler.
    """

    def test_scheduler_calibration_and_invariants(self):
        from api.srs import _QUESTION_PARAMS, _flashcard_scheduler, _question_scheduler

        # 1. Retenção alvo calibrada para questões médicas
        assert _question_scheduler.desired_retention == 0.85

        # 2. Ausência estrita de passos intradia em ambos os agendadores
        assert _question_scheduler.learning_steps == ()
        assert _question_scheduler.relearning_steps == ()
        assert _flashcard_scheduler.learning_steps == ()
        assert _flashcard_scheduler.relearning_steps == ()

        # 3. Parâmetros iniciais calibrados para questões longas (Opção 2: mínimo 7 dias no erro)
        assert _QUESTION_PARAMS[0] == 3.5  # S0(Again) ~7d
        assert _QUESTION_PARAMS[1] == 8.0  # S0(Hard) ~15d
        assert _QUESTION_PARAMS[2] == 18.0  # S0(Good) ~34d
        assert _QUESTION_PARAMS[3] == 40.0  # S0(Easy) ~76d

    def test_stress_consecutive_failures_questions(self):
        """Simula 25 falhas consecutivas em questão médica garantindo >= 24h e delta positivo."""
        card_json = None
        now = datetime.now(timezone.utc)

        for i in range(25):
            card_json, due_iso = review(card_json, False, None, is_flashcard=False)
            assert card_json is not None
            assert due_iso is not None

            due = datetime.fromisoformat(due_iso)
            diff_seconds = (due - now).total_seconds()

            # Invariante 1: Intervalo estritamente positivo (nunca negativo)
            assert diff_seconds > 0, f"Intervalo negativo detectado na iteração {i + 1}: {diff_seconds}s"

            # Invariante 2: Sem passos intradia (< 24 horas)
            # Tolerância de 60s para execução do teste
            assert diff_seconds >= 86400 - 60, (
                f"Passo intradia indesejado (< 24h) na iteração {i + 1}: {diff_seconds / 3600:.2f}h"
            )

            # Invariante 3: Integridade do payload serializado
            card_dict = json.loads(card_json)
            assert card_dict["stability"] > 0
            assert card_dict["difficulty"] > 0

            # Na 1ª falha de questão nova, intervalo deve ser ~7 dias
            if i == 0:
                diff_days = diff_seconds / 86400
                assert 6.5 <= diff_days <= 7.5, f"Intervalo inicial de erro inesperado: {diff_days:.2f} dias"

    def test_stress_consecutive_failures_flashcards(self):
        """Simula 25 falhas consecutivas em flashcard garantindo piso mínimo D+1 (>= 24h)."""
        card_json = None
        now = datetime.now(timezone.utc)

        for i in range(25):
            card_json, due_iso = review(card_json, False, "errei", is_flashcard=True)
            assert card_json is not None
            assert due_iso is not None

            due = datetime.fromisoformat(due_iso)
            diff_seconds = (due - now).total_seconds()

            # Invariante: Intervalo positivo e sem passos intradia
            assert diff_seconds > 0, f"Intervalo negativo detectado no flashcard {i + 1}: {diff_seconds}s"
            assert diff_seconds >= 86400 - 60, (
                f"Passo intradia (< 24h) detectado no flashcard {i + 1}: {diff_seconds / 3600:.2f}h"
            )

            card_dict = json.loads(card_json)
            assert card_dict["stability"] > 0

    def test_stress_simulated_timeline_mixed_trajectory(self):
        """Simula linha do tempo de 64 revisões alternadas com passagem real de tempo."""
        from api.srs import _question_scheduler
        from fsrs import Card

        current_time = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
        card = Card()

        # Padrão misto estressante: erros repetidos, chutes, dúvidas, acertos fáceis
        ratings_pattern = [
            Rating.Good,
            Rating.Again,
            Rating.Again,
            Rating.Hard,
            Rating.Again,
            Rating.Good,
            Rating.Easy,
            Rating.Again,
        ] * 8

        for idx, rating in enumerate(ratings_pattern):
            card, _log = _question_scheduler.review_card(card, rating, review_datetime=current_time)
            diff_seconds = (card.due - current_time).total_seconds()

            # Invariantes a cada ponto da jornada
            assert diff_seconds > 0, f"Revisão {idx + 1} gerou intervalo negativo ({diff_seconds}s)"
            assert diff_seconds >= 86400, (
                f"Revisão {idx + 1} gerou agendamento intradia < 24h: {diff_seconds / 3600:.2f}h"
            )

            # Avança a simulação temporal para a data agendada
            current_time = card.due

    def test_stress_high_stability_lapse_and_recovery(self):
        """Verifica que lapso em card de alta estabilidade nunca gera agendamento negativo ou intradia."""
        card_json = None

        # 1. Constrói alta estabilidade com acertos consecutivos fáceis
        for _ in range(5):
            card_json, _ = review(card_json, True, "certeza", is_flashcard=False)

        card_dict = json.loads(card_json)
        assert card_dict["stability"] > 50

        # 2. Simula lapso crítico (erro na revisão)
        card_json_lapse, due_lapse_iso = review(card_json, False, None, is_flashcard=False)
        due_lapse = datetime.fromisoformat(due_lapse_iso)
        now = datetime.now(timezone.utc)
        diff_seconds = (due_lapse - now).total_seconds()

        assert diff_seconds > 0, "Lapso gerou intervalo negativo"
        assert diff_seconds >= 86400 - 60, f"Lapso gerou agendamento intradia: {diff_seconds / 3600:.2f}h"

        # 3. Simula recuperação pós-lapso (relearning)
        card_json_rec, due_rec_iso = review(card_json_lapse, True, "duvida", is_flashcard=False)
        due_rec = datetime.fromisoformat(due_rec_iso)
        diff_rec_seconds = (due_rec - now).total_seconds()

        assert diff_rec_seconds > 0, "Recuperação gerou intervalo negativo"
        assert diff_rec_seconds >= 86400 - 60, "Recuperação gerou agendamento intradia"

    def test_all_confidence_and_correctness_combinations_no_intraday(self):
        """Varre todas as combinações de acerto e confiança garantindo integridade temporal."""
        confidences = [None, "chutei", "duvida", "certeza", "desconhecido"]
        now = datetime.now(timezone.utc)

        for is_flashcard in (False, True):
            for is_correct in (True, False):
                for conf in confidences:
                    card_json, due_iso = review(None, is_correct, conf, is_flashcard=is_flashcard)
                    due = datetime.fromisoformat(due_iso)
                    diff_seconds = (due - now).total_seconds()

                    assert diff_seconds > 0, (
                        f"Combinação (correct={is_correct}, conf={conf}, flashcard={is_flashcard}) "
                        f"gerou intervalo negativo: {diff_seconds}s"
                    )
                    assert diff_seconds >= 86400 - 60, (
                        f"Combinação (correct={is_correct}, conf={conf}, flashcard={is_flashcard}) "
                        f"gerou agendamento intradia: {diff_seconds / 3600:.2f}h"
                    )

    def test_defensive_clamp_forces_minimum_d_plus_one(self, monkeypatch):
        """Assegura que qualquer agendamento menor que 24h ou no passado é clampado para D+1."""
        from datetime import timedelta
        import api.srs as srs_mod
        from fsrs import Card

        fixed_now = datetime(2026, 10, 11, 10, 0, 0, tzinfo=timezone.utc)
        expected_min_due = fixed_now + timedelta(days=1)

        # 1. Simula cenário hipotético onde o scheduler interno agendaria para apenas 2 horas à frente
        class MockSchedulerIntraday:
            def review_card(self, card, rating, review_datetime=None):
                card.due = (review_datetime or fixed_now) + timedelta(hours=2)
                return card, None

        monkeypatch.setattr(srs_mod, "_question_scheduler", MockSchedulerIntraday())

        card_json, due_iso = review(None, False, None, is_flashcard=False, now=fixed_now)
        due_dt = datetime.fromisoformat(due_iso)

        assert due_dt == expected_min_due, (
            f"Esperado clamp para {expected_min_due.isoformat()}, mas obteve {due_iso}"
        )
        # O payload serializado do Card também deve refletir o clamp
        card_dict = json.loads(card_json)
        assert datetime.fromisoformat(card_dict["due"]) == expected_min_due

        # 2. Simula cenário anômalo de retorno com data no passado (drift de relógio / erro de scheduler)
        class MockSchedulerPast:
            def review_card(self, card, rating, review_datetime=None):
                card.due = (review_datetime or fixed_now) - timedelta(days=10)
                return card, None

        monkeypatch.setattr(srs_mod, "_flashcard_scheduler", MockSchedulerPast())

        card_json_past, due_iso_past = review(None, False, "errei", is_flashcard=True, now=fixed_now)
        due_dt_past = datetime.fromisoformat(due_iso_past)

        assert due_dt_past == expected_min_due
        card_dict_past = json.loads(card_json_past)
        assert datetime.fromisoformat(card_dict_past["due"]) == expected_min_due

    def test_defensive_clamp_preserves_longer_intervals(self):
        """Assegura que intervalos legítimos (> 24h) são preservados sem corte indevido."""
        from datetime import timedelta

        fixed_now = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)

        # Questão com erro: ~7 dias (> 1 dia)
        _, due_err = review(None, False, None, is_flashcard=False, now=fixed_now)
        diff_err_days = (datetime.fromisoformat(due_err) - fixed_now).total_seconds() / 86400
        assert 6.5 <= diff_err_days <= 7.5

        # Questão com certeza: ~78 dias (> 1 dia)
        _, due_easy = review(None, True, "certeza", is_flashcard=False, now=fixed_now)
        diff_easy_days = (datetime.fromisoformat(due_easy) - fixed_now).total_seconds() / 86400
        assert 76 <= diff_easy_days <= 80

        # Flashcard com certeza: ~7-8 dias (> 1 dia)
        _, due_fc_easy = review(None, True, "certeza", is_flashcard=True, now=fixed_now)
        diff_fc_days = (datetime.fromisoformat(due_fc_easy) - fixed_now).total_seconds() / 86400
        assert 6.0 <= diff_fc_days <= 8.5


