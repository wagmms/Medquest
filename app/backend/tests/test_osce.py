"""Testes unitários e de integração para o Simulador de OSCE / 2ª Fase."""
import json
import pytest

from api import osce
from api.db import get_db


def test_seed_osce_stations_idempotent(app):
    with app.app_context():
        db = get_db()
        count1 = osce.seed_osce_stations(db)
        assert count1 >= 10, "Deve inserir pelo menos 10 estações canônicas"

        # Segunda chamada não duplica estações
        count2 = osce.seed_osce_stations(db)
        assert count2 == 0, "Seed subsequente deve ser idempotente"

        rows = db.execute("SELECT COUNT(*) as total FROM osce_stations").fetchone()
        assert rows["total"] >= 10


def test_list_osce_stations_filters(app):
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        # Sem filtros
        all_stations = osce.list_osce_stations(db, user_id="test_user")
        assert len(all_stations) >= 10

        # Filtro por Instituição
        unicamp_stations = osce.list_osce_stations(db, user_id="test_user", institution="UNICAMP")
        assert len(unicamp_stations) >= 3
        for st in unicamp_stations:
            assert st["institution"] == "UNICAMP"

        usprp_stations = osce.list_osce_stations(db, user_id="test_user", institution="USP-RP")
        assert len(usprp_stations) >= 6, f"Esperado >= 6 estações da USP-RP, obtido {len(usprp_stations)}"
        for st in usprp_stations:
            assert st["institution"] == "USP-RP"

        # Filtro por Grande Área
        ped_stations = osce.list_osce_stations(db, user_id="test_user", area="Pediatria")
        assert len(ped_stations) >= 2
        for st in ped_stations:
            assert st["area"] == "Pediatria"


def test_get_osce_station_hides_barema_during_exam(app):
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        station = db.execute("SELECT id FROM osce_stations WHERE code = 'UNICAMP-2024-CM-SCA'").fetchone()
        assert station is not None

        # include_barema=False (modo aluno na sala de prova)
        view_student = osce.get_osce_station(db, station["id"], include_barema=False)
        assert "checklist_barema" not in view_student
        assert "critical_errors" not in view_student
        assert "patient_persona" in view_student
        assert "lab_imaging_catalog" in view_student

        # include_barema=True (modo auditoria de espelho)
        view_audit = osce.get_osce_station(db, station["id"], include_barema=True)
        assert "checklist_barema" in view_audit
        assert len(view_audit["checklist_barema"]) >= 8
        assert "critical_errors" in view_audit


def test_osce_session_lifecycle_and_barema(app):
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        station = db.execute("SELECT id FROM osce_stations WHERE code = 'UNICAMP-2024-CM-SCA'").fetchone()
        station_id = station["id"]
        user_id = "test_resident_01"

        # 1. Início de Sessão
        session = osce.start_osce_session(db, station_id, user_id)
        session_id = session["session_id"]
        assert session_id is not None
        assert session["duration_seconds"] == 480
        assert len(session["transcript"]) == 1

        # 2. Interação com o Paciente (Anamnese)
        r1 = osce.interact_osce_session(
            db, session_id, user_id,
            message="Olá, bom dia seu Antônio Carlos. Sou o médico plantonista e vou cuidar do senhor. Onde dói e quando começou?",
            elapsed_seconds=30
        )
        assert r1["sender"] == "paciente"
        assert len(r1["reply"]) > 5

        # 3. Solicitação de Sinais Vitais
        act_vitals = osce.execute_osce_action(
            db, session_id, user_id,
            action_type="vitals",
            action_target="vitals",
            elapsed_seconds=60
        )
        assert "140x90" in act_vitals["examiner_message"]

        # 4. Exame Físico (Ausculta Pulmonar com Estetoscópio)
        act_pulm = osce.execute_osce_action(
            db, session_id, user_id,
            action_type="physical_exam",
            action_target="respiratorio",
            elapsed_seconds=90
        )
        assert "murmúrio" in act_pulm["examiner_message"].lower()

        # 5. Solicitação de Exame Complementar (ECG 12 derivações)
        act_ecg = osce.execute_osce_action(
            db, session_id, user_id,
            action_type="lab_imaging",
            action_target="ecg",
            elapsed_seconds=120
        )
        assert "supradesnivelamento" in act_ecg["examiner_message"].lower()

        # 6. Finalização e Conduta (Verbalização)
        finish_res = osce.finish_osce_session(
            db, session_id, user_id,
            conduct_notes=(
                "Paciente com IAM com supra de ST anterior. Solicito monitorização contínua e dois acessos venosos calibrosos. "
                "Prescrevo dose de ataque de AAS 300 mg mastigável associado a Ticagrelor 180 mg VO. "
                "Prescrevo Enoxaparina plena 1 mg/kg SC. "
                "Aciono imediatamente a equipe de hemodinâmica para angioplastia primária em tempo porta-balão menor que 90 minutos."
            )
        )

        assert finish_res["status"] == "completed"
        assert finish_res["final_score"] >= 7.0, f"Score obtido {finish_res['final_score']} deveria ser >= 7.0 com conduta correta"
        assert len(finish_res["evaluated_items"]) >= 8
        assert "preceptor_feedback" in finish_res
        assert finish_res["preceptor_feedback"]["approved"] is True

        # 7. Recuperação do Relatório Oficial
        report = osce.get_osce_session_report(db, session_id, user_id)
        assert report is not None
        assert report["code"] == "UNICAMP-2024-CM-SCA"
        assert report["final_score"] == finish_res["final_score"]


def test_osce_api_routes(client):
    # GET /api/osce/stations
    resp = client.get("/api/osce/stations")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "stations" in data
    assert len(data["stations"]) >= 10

    station_id = data["stations"][0]["id"]

    # GET /api/osce/stations/<id>
    resp_st = client.get(f"/api/osce/stations/{station_id}")
    assert resp_st.status_code == 200
    st_data = resp_st.get_json()
    assert "title" in st_data
    assert "scenario_door_markdown" in st_data

    # POST /api/osce/sessions/start
    resp_start = client.post("/api/osce/sessions/start", json={"station_id": station_id})
    assert resp_start.status_code == 201
    sess_data = resp_start.get_json()
    session_id = sess_data["session_id"]

    # POST /api/osce/sessions/<id>/interact
    resp_interact = client.post(
        f"/api/osce/sessions/{session_id}/interact",
        json={"message": "Olá, sou o médico. O que você está sentindo?", "elapsed_seconds": 15}
    )
    assert resp_interact.status_code == 200
    assert "reply" in resp_interact.get_json()

    # POST /api/osce/sessions/<id>/finish
    resp_fin = client.post(
        f"/api/osce/sessions/{session_id}/finish",
        json={"conduct_notes": "Prescrevo monitorização, oxigênio e conduta inicial."}
    )
    assert resp_fin.status_code == 200
    fin_data = resp_fin.get_json()
    assert "final_score" in fin_data

    # GET /api/osce/sessions/<id>/report
    resp_rep = client.get(f"/api/osce/sessions/{session_id}/report")
    assert resp_rep.status_code == 200
    assert resp_rep.get_json()["session_id"] == session_id

    # POST /api/osce/sessions/<id>/export_cards
    resp_exp = client.post(f"/api/osce/sessions/{session_id}/export_cards")
    assert resp_exp.status_code == 200
    assert resp_exp.get_json()["success"] is True


def test_usp_rp_cad_station_lifecycle(app):
    """Testa estação oficial da USP-RP de Cetoacidose Diabética no HC-UE."""
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        station = db.execute("SELECT id FROM osce_stations WHERE code = 'USP-RP-2024-CM-CAD'").fetchone()
        assert station is not None, "Estação USP-RP de CAD deve existir no banco"
        station_id = station["id"]
        user_id = "resident_usp_rp_01"

        # 1. Início de Sessão
        session = osce.start_osce_session(db, station_id, user_id)
        session_id = session["session_id"]
        assert session["institution"] == "USP-RP"

        # 2. Interação com a Acompanhante / Paciente
        r1 = osce.interact_osce_session(
            db, session_id, user_id,
            message="Olá dona Maria, sou o médico do HC-UE. O que aconteceu com o Lucas? Ele parou a insulina?",
            elapsed_seconds=25
        )
        assert r1["sender"] == "paciente"
        assert len(r1["reply"]) > 5

        # 3. Solicitação de Vinais Vitais e Exame Físico
        vitals = osce.execute_osce_action(
            db, session_id, user_id,
            action_type="vitals",
            action_target="vitals",
            elapsed_seconds=60
        )
        assert "Kussmaul" in vitals["examiner_message"] or "90x60" in vitals["examiner_message"]

        # 4. Solicitação de Exames Complementares (Gasometria e Eletrólitos)
        gaso = osce.execute_osce_action(
            db, session_id, user_id,
            action_type="lab_imaging",
            action_target="gasometria",
            elapsed_seconds=90
        )
        assert "acidose metabólica" in gaso["examiner_message"].lower()

        eletro = osce.execute_osce_action(
            db, session_id, user_id,
            action_type="lab_imaging",
            action_target="eletrolitos",
            elapsed_seconds=120
        )
        assert "4.2" in eletro["examiner_message"]

        # 5. Conduta Protocolar do HC-UE da USP Ribeirão Preto
        finish_res = osce.finish_osce_session(
            db, session_id, user_id,
            conduct_notes=(
                "Diagnóstico: Cetoacidose Diabética descompensada por omissão de dose e provável infecção. "
                "Conduta de emergência: Monitorização contínua, acesso venoso calibroso e cateter de oxigênio se necessário. "
                "Expansão volêmica vigorosa com Soro Fisiológico 0,9% 1000 mL na primeira hora (15 a 20 mL/kg). "
                "Checagem formal do potássio sérico (K+ = 4.2 mEq/L, seguro entre 3,3 e 5,2). "
                "Início de Insulina Regular em bomba de infusão contínua a 0,1 U/kg/h após início da hidratação venosa. "
                "Reposição profilática de cloreto de potássio KCl a 20 mEq por litro de soro. "
                "Ao atingir glicemia de 250 mg/dL, introduzir Soro Glicosado SG 5% mantendo a insulina para fechar o ânion gap. "
                "Coleta de culturas (urina e sangue) e antibioticoterapia empírica para foco infeccioso deflagrador. "
                "Monitoramento de glicemia capilar horária e gasometria com eletrólitos a cada 2 a 4 horas."
            )
        )

        assert finish_res["status"] == "completed"
        assert finish_res["final_score"] >= 8.0, f"Score obtido {finish_res['final_score']} deveria ser >= 8.0"
        assert finish_res["preceptor_feedback"]["approved"] is True

        # 6. Exportação de Flashcards de Choque
        export_res = osce.export_osce_flashcards(db, session_id, user_id)
        assert export_res["success"] is True
        assert export_res["cards_created"] >= 1

