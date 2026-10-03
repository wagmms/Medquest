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


def test_osce_speech_dispatcher(app, client):
    """Testa o Dispatcher Clínico de Voz para o Modo Hands-Free."""
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        station = db.execute("SELECT id FROM osce_stations WHERE code = 'USP-RP-2024-CM-SCA'").fetchone()
        assert station is not None
        station_id = station["id"]
        user_id = "test_hands_free_user"

        session = osce.start_osce_session(db, station_id, user_id)
        session_id = session["session_id"]

        # 1. Comando de Voz: Sinais Vitais para o Examinador
        res_vitals = osce.dispatch_osce_speech(
            db, session_id, user_id,
            message="Examinador, solicito sinais vitais completos e PA",
            elapsed_seconds=30
        )
        assert len(res_vitals["actions_executed"]) >= 1
        assert res_vitals["actions_executed"][0]["action_type"] == "vitals"
        assert any(sq["speaker"] == "examinador" for sq in res_vitals["spoken_queue"])

        # 2. Comando de Voz: Exame Complementar (ECG 12 derivações)
        res_ecg = osce.dispatch_osce_speech(
            db, session_id, user_id,
            message="Examinador, por favor traga o eletrocardiograma de 12 derivações",
            elapsed_seconds=60
        )
        assert any(a["action_type"] == "lab_imaging" for a in res_ecg["actions_executed"])
        assert any("ecg" in a["target"] for a in res_ecg["actions_executed"])

        # 3. Comando de Voz: Diálogo com a Paciente Simulado
        res_patient = osce.dispatch_osce_speech(
            db, session_id, user_id,
            message="Olá dona Neusa, me conta quando começou essa dor e para onde ela irradia?",
            elapsed_seconds=90
        )
        assert res_patient["is_patient_dialogue"] is True
        assert len(res_patient["patient_reply"]) > 5
        assert any(sq["speaker"] == "paciente" for sq in res_patient["spoken_queue"])

        # 4. Rota HTTP POST /api/osce/sessions/<id>/dispatch_speech
        resp_http = client.post(
            f"/api/osce/sessions/{session_id}/dispatch_speech",
            json={"message": "Examinador, sinais vitais imediatos", "elapsed_seconds": 100}
        )
        assert resp_http.status_code == 200
        http_data = resp_http.get_json()
        assert "spoken_queue" in http_data
        assert "actions_executed" in http_data


def test_emergency_drugs_and_procedures_catalog(client):
    """Testa se os catálogos oficiais de drogas de emergência e procedimentos estão disponíveis via API."""
    # 1. Catálogo de Medicamentos
    resp_drugs = client.get("/api/osce/drugs")
    assert resp_drugs.status_code == 200
    data_drugs = resp_drugs.get_json()
    assert "drugs" in data_drugs
    assert len(data_drugs["drugs"]) >= 15
    assert any(d["id"] == "adrenalina" for d in data_drugs["drugs"])
    assert any(d["id"] == "tranexamico" for d in data_drugs["drugs"])

    # 2. Catálogo de Procedimentos
    resp_proc = client.get("/api/osce/procedures")
    assert resp_proc.status_code == 200
    data_proc = resp_proc.get_json()
    assert "procedures" in data_proc
    assert len(data_proc["procedures"]) >= 8
    assert any(p["site"] == "morrison" for p in data_proc["procedures"])
    assert any(p["site"] == "thoracocentesis" for p in data_proc["procedures"])


def test_osce_prescription_and_procedure_engines(app, client):
    """Testa a Prancheta de Prescrição Estruturada e o Manequim com E-FAST e Descompressão."""
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        # 1. Teste de Prescrição na Estação de Politrauma USP-RP
        st_fast = db.execute("SELECT id FROM osce_stations WHERE code = 'USP-RP-2023-CG-FAST'").fetchone()
        assert st_fast is not None
        session = osce.start_osce_session(db, st_fast["id"], "test_medic_user")
        session_id = session["session_id"]

        # Prescrição de Ácido Tranexâmico 1g IV e Ringer Lactato
        presc_res = client.post(
            f"/api/osce/sessions/{session_id}/prescribe",
            json={
                "prescription": [
                    {
                        "drug_name": "Ácido Tranexâmico",
                        "dose": "1",
                        "unit": "g",
                        "route": "EV em bólus de 10 min",
                        "notes": "protocolo CRASH-2 / ATLS"
                    },
                    {
                        "drug_name": "Ringer Lactato",
                        "dose": "1000",
                        "unit": "ml",
                        "route": "EV rápido",
                        "notes": "ressuscitação volêmica balanceada restritiva"
                    }
                ],
                "elapsed_seconds": 120
            }
        )
        assert presc_res.status_code == 200
        p_data = presc_res.get_json()
        assert p_data["success"] is True
        assert "Ácido Tranexâmico" in p_data["prescription_text"]
        assert len(p_data["matched_criteria"]) >= 1, "Deveria pontuar critério de Ácido Tranexâmico"
        assert len(p_data["spoken_queue"]) >= 1

        # 2. Teste do Manequim Interativo: E-FAST na janela esplenorrenal (recesso de Koller)
        proc_fast = client.post(
            f"/api/osce/sessions/{session_id}/procedure",
            json={
                "procedure_type": "efast",
                "anatomical_site": "splenorenal",
                "elapsed_seconds": 150
            }
        )
        assert proc_fast.status_code == 200
        fast_data = proc_fast.get_json()
        assert fast_data["success"] is True
        assert "esplenorrenal" in fast_data["findings"].lower()
        assert "líquido livre" in fast_data["findings"].lower()
        assert any(sq["speaker"] == "examinador" for sq in fast_data["spoken_queue"])

        # 3. Teste do Manequim Interativo: Janela Hepatorrenal (Morrison)
        proc_morrison = client.post(
            f"/api/osce/sessions/{session_id}/procedure",
            json={
                "procedure_type": "efast",
                "anatomical_site": "morrison",
                "elapsed_seconds": 180
            }
        )
        assert proc_morrison.status_code == 200
        morrison_data = proc_morrison.get_json()
        assert "morrison" in morrison_data["findings"].lower()

        # 4. Teste de Toracocentese de Alívio na Estação de Pneumotórax do Einstein
        st_pneumo = db.execute("SELECT id FROM osce_stations WHERE code = 'EINSTEIN-2023-CG-PNEUMO'").fetchone()
        assert st_pneumo is not None
        sess_pneumo = osce.start_osce_session(db, st_pneumo["id"], "test_medic_user")
        sess_pneumo_id = sess_pneumo["session_id"]

        proc_relief = client.post(
            f"/api/osce/sessions/{sess_pneumo_id}/procedure",
            json={
                "procedure_type": "puncture",
                "anatomical_site": "thoracocentesis",
                "elapsed_seconds": 90
            }
        )
        assert proc_relief.status_code == 200
        relief_data = proc_relief.get_json()
        assert relief_data["success"] is True
        assert "pressão" in relief_data["findings"].lower()
        assert "descompressão" in relief_data["findings"].lower()


def test_osce_guided_mode_ghost_preceptor(app, client):
    """Testa o Modo Treino Guiado com Preceptor Fantasma e HUD ao vivo."""
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        st = db.execute("SELECT id FROM osce_stations WHERE code = 'USP-RP-2024-CM-SCA'").fetchone()
        assert st is not None
        station_id = st["id"]

        # 1. Inicia sessão explicitamente no modo 'guided'
        resp_start = client.post(
            "/api/osce/sessions/start",
            json={"station_id": station_id, "mode": "guided"}
        )
        assert resp_start.status_code == 201
        start_data = resp_start.get_json()
        assert start_data["mode"] == "guided"
        assert "guided_feedback" in start_data
        assert start_data["guided_feedback"]["percentage"] == 0
        assert len(start_data["guided_feedback"]["items_status"]) >= 5

        session_id = start_data["session_id"]

        # 2. Executa ação clínica de sinais vitais
        act_res = client.post(
            f"/api/osce/sessions/{session_id}/action",
            json={"action_type": "vitals", "action_target": "vitals", "elapsed_seconds": 60}
        )
        assert act_res.status_code == 200
        act_data = act_res.get_json()
        assert "guided_feedback" in act_data
        assert act_data["guided_feedback"]["mode"] == "guided"

        # 3. Prescreve AAS e Ticagrelor e valida atualização dos marcos
        presc_res = client.post(
            f"/api/osce/sessions/{session_id}/prescribe",
            json={
                "prescription": [
                    {"drug_name": "AAS mastigável", "dose": "200", "unit": "mg", "route": "VO mastigado"},
                    {"drug_name": "Ticagrelor", "dose": "180", "unit": "mg", "route": "VO"}
                ],
                "elapsed_seconds": 120
            }
        )
        assert presc_res.status_code == 200
        p_data = presc_res.get_json()
        assert "guided_feedback" in p_data
        assert p_data["guided_feedback"]["current_score"] > 0
        assert any(i["completed"] for i in p_data["guided_feedback"]["items_status"])

        # 4. Consulta endpoint live_feedback com tempo avançado para disparar hints proativos
        fb_res = client.get(f"/api/osce/sessions/{session_id}/live_feedback?elapsed_seconds=250")
        assert fb_res.status_code == 200
        fb_data = fb_res.get_json()
        assert fb_data["mode"] == "guided"
        assert len(fb_data["proactive_hints"]) >= 1, "Deveria ter alertas proativos do preceptor fantasma"


def test_osce_timeline_post_mortem_and_competency_radar(app, client):
    """Valida a geração da Linha do Tempo Beira-Leito e do Radar de Competências no espelho da prova."""
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        st = db.execute("SELECT id FROM osce_stations WHERE code = 'USP-RP-2024-CM-SCA'").fetchone()
        assert st is not None
        station_id = st["id"]

        # Inicia sessão
        st_res = client.post(
            "/api/osce/sessions/start",
            json={"station_id": station_id, "mode": "blind"}
        )
        assert st_res.status_code == 201
        session_id = st_res.get_json()["session_id"]

        # Ação 1: Vinais aos 45s (timely)
        client.post(
            f"/api/osce/sessions/{session_id}/action",
            json={"action_type": "vitals", "action_target": "vitals", "elapsed_seconds": 45}
        )

        # Ação 2: ECG aos 95s (timely Porta-ECG)
        client.post(
            f"/api/osce/sessions/{session_id}/action",
            json={"action_type": "lab_imaging", "action_target": "ecg", "elapsed_seconds": 95}
        )

        # Ação 3: Prescrição aos 220s
        client.post(
            f"/api/osce/sessions/{session_id}/prescribe",
            json={
                "prescription": [
                    {"drug_name": "AAS mastigável", "dose": "200", "unit": "mg", "route": "VO mastigado"},
                    {"drug_name": "Ticagrelor", "dose": "180", "unit": "mg", "route": "VO"}
                ],
                "elapsed_seconds": 220
            }
        )

        # Finaliza sessão
        finish_res = client.post(
            f"/api/osce/sessions/{session_id}/finish",
            json={"conduct_notes": "Paciente com SCA confirmado, prescrevo AAS e Ticagrelor e indico cate imediato."}
        )
        assert finish_res.status_code == 200
        data = finish_res.get_json()

        # Validações da Linha do Tempo Beira-Leito
        assert "timeline_post_mortem" in data
        timeline = data["timeline_post_mortem"]
        assert "events" in timeline
        assert "summary" in timeline
        assert len(timeline["events"]) >= 3
        assert timeline["summary"]["timely_count"] >= 2
        assert timeline["summary"]["door_to_ecg_seconds"] == 95

        # Validações do Radar de Competências
        assert "competency_radar" in data
        radar = data["competency_radar"]
        assert "dimensions" in radar
        assert len(radar["dimensions"]) == 6
        dim_keys = [d["key"] for d in radar["dimensions"]]
        assert "comunicacao_empatia" in dim_keys
        assert "raciocinio_clinico" in dim_keys
        assert "exame_fisico" in dim_keys
        assert "exames_complementares" in dim_keys
        assert "seguranca_farmacologica" in dim_keys
        assert "gestao_tempo" in dim_keys
        assert radar["overall_average"] > 0
        assert len(radar["strengths"]) >= 1

        # Valida que o endpoint GET /report recupera a mesma timeline e radar
        report_res = client.get(f"/api/osce/sessions/{session_id}/report")
        assert report_res.status_code == 200
        rep_data = report_res.get_json()
        assert "timeline_post_mortem" in rep_data
        assert "competency_radar" in rep_data
        assert len(rep_data["timeline_post_mortem"]["events"]) == len(timeline["events"])


def test_osce_generator_fmrp_usp(app, client):
    """Testa o Motor de Estações Inéditas Infinitas com padrão FMRP-USP e modo adaptativo."""
    with app.app_context():
        db = get_db()
        osce.seed_osce_stations(db)

        # 1. Geração com modo Adaptativo
        resp_adapt = client.post(
            "/api/osce/stations/generate",
            json={"adaptative": True, "difficulty": "hard"}
        )
        assert resp_adapt.status_code == 201
        data_adapt = resp_adapt.get_json()
        assert data_adapt["success"] is True
        assert data_adapt["institution"] == "USP-RP"
        assert data_adapt["code"].startswith("USP-RP-AI-")
        station_id_adapt = data_adapt["station_id"]
        assert station_id_adapt > 0

        # Verifica se a estação foi persistida corretamente no banco
        st_row = db.execute("SELECT * FROM osce_stations WHERE id = ?", (station_id_adapt,)).fetchone()
        assert st_row is not None
        assert "FMRP-USP" in st_row["scenario_door_markdown"] or "Ribeirão Preto" in st_row["scenario_door_markdown"]
        assert st_row["checklist_barema_json"] is not None

        # 2. Testa iniciar sessão real na estação inédita gerada pela IA
        start_res = client.post(
            "/api/osce/sessions/start",
            json={"station_id": station_id_adapt, "mode": "guided"}
        )
        assert start_res.status_code == 201
        sess_data = start_res.get_json()
        session_id = sess_data["session_id"]
        assert sess_data["institution"] == "USP-RP"

        # 3. Interage com a persona gerada dinamicamente
        interact_res = client.post(
            f"/api/osce/sessions/{session_id}/interact",
            json={"message": "Olá, sou o médico residente da USP Ribeirão Preto. Como o senhor está se sentindo?", "elapsed_seconds": 15}
        )
        assert interact_res.status_code == 200
        reply = interact_res.get_json()
        assert reply["sender"] == "paciente"
        assert len(reply["reply"]) > 5

        # 4. Geração direcionada por Área Clínica e Cirúrgica
        resp_cir = client.post(
            "/api/osce/stations/generate",
            json={"area": "Cirurgia Geral", "difficulty": "hard"}
        )
        assert resp_cir.status_code == 201
        data_cir = resp_cir.get_json()
        assert data_cir["area"] == "Cirurgia Geral"
        assert data_cir["code"].startswith("USP-RP-AI-")

        resp_ped = client.post(
            "/api/osce/stations/generate",
            json={"area": "Pediatria", "difficulty": "hard"}
        )
        assert resp_ped.status_code == 201
        data_ped = resp_ped.get_json()
        assert data_ped["area"] == "Pediatria"
        assert data_ped["code"].startswith("USP-RP-AI-")

