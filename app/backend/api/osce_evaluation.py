"""Motores determinísticos de auditoria clínica, red flags, cronologia e radar OSCE."""
from __future__ import annotations

import unicodedata
from typing import Any, Optional


def _normalize_text(text: str) -> str:
    """Normaliza texto removendo acentos e espaços extras para matching tolerante a grafia."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


_NEGATION_PREFIXES = (
    "nao ", "nunca ", "jamais ", "sem ", "evitar ", "evito ",
    "contraindicad", "proibid", "nao faco ", "nao prescrevo ", "nao administrar "
)


def _has_affirmative_mention(spoken_norm: str, prescribed_norm: str, terms: list[str]) -> bool:
    """Retorna True se algum termo foi prescrito na prancheta ou mencionado sem negação explícita."""
    if any(t in prescribed_norm for t in terms):
        return True
    for term in terms:
        start = 0
        while True:
            idx = spoken_norm.find(term, start)
            if idx == -1:
                break
            window_start = max(0, idx - 45)
            prefix = spoken_norm[window_start:idx]
            if not any(neg in prefix for neg in _NEGATION_PREFIXES):
                return True
            start = idx + len(term)
    return False


def evaluate_critical_safety_violations(
    critical_errors: list[str],
    evidence_text: str,
    actions: list[dict[str, Any]],
    station_meta: dict[str, Any]
) -> list[str]:
    """
    Motor de Auditoria de Segurança Clínica Beira-Leito (ClinicalSafetyGuard).
    Cruza contraindicações formais das bancas com falas, prescrições e procedimentos do candidato.
    """
    norm_evidence = _normalize_text(evidence_text)
    prescriptions: list[dict[str, Any]] = []

    for a in actions:
        if a.get("action_type") == "prescription":
            prescriptions.extend(a.get("prescription_items", []))

    all_prescribed_drugs = " ".join([
        _normalize_text(f"{p.get('drug_name', '')} {p.get('dose', '')} {p.get('route', '')} {p.get('notes', '')}")
        for p in prescriptions
    ])
    full_corpus = f"{norm_evidence} {all_prescribed_drugs}"

    station_subtema = _normalize_text(station_meta.get("subtema", ""))
    detected_violations: list[str] = []

    for err in critical_errors:
        err_norm = _normalize_text(err)
        flagged = False

        if "bicarbonato" in err_norm:
            if _has_affirmative_mention(norm_evidence, all_prescribed_drugs, ["bicarbonato", "nahco3", "bicarb"]):
                flagged = True

        elif "potassio" in err_norm and "insulina" in err_norm:
            has_insulin = _has_affirmative_mention(norm_evidence, all_prescribed_drugs, ["insulina", "bic de insulina", "insulina regular"])
            checked_k = any(term in full_corpus for term in ["potassio", "k+", "gasometria", "eletrolitos", "kcl"])
            if has_insulin and not checked_k:
                flagged = True

        elif "suspender" in err_norm and "insulina" in err_norm:
            if _has_affirmative_mention(norm_evidence, all_prescribed_drugs, ["suspender insulina", "desligo a insulina", "parar a insulina"]):
                flagged = True

        elif "trombolitico" in err_norm or "fibrinolitico" in err_norm:
            if _has_affirmative_mention(norm_evidence, all_prescribed_drugs, ["trombolise", "alteplase", "tenecteplase", "estreptoquinase", "metalyse", "actilyse"]):
                flagged = True

        elif "nitrato" in err_norm:
            has_nitrate = any(term in full_corpus for term in ["nitrato", "isordil", "mononitrato", "dinitrato", "tridil", "nitroglicerina"])
            checked_contra = any(term in full_corpus for term in ["sildenafila", "viagra", "tadalafila", "erecao", "ventriculo direito", "vd"])
            if has_nitrate and not checked_contra:
                flagged = True

        elif "oxigenioterapia" in err_norm:
            if any(term in full_corpus for term in ["cateter de o2", "oxigenio a", "o2 a", "mascara de o2", "o2 2l", "o2 3l"]):
                flagged = True

        elif "aguardar" in err_norm and ("troponina" in err_norm or "marcador" in err_norm or "enzima" in err_norm):
            if any(term in full_corpus for term in ["aguardar troponina", "esperar a troponina", "aguardo o resultado da troponina", "esperar enzimas"]):
                flagged = True

        elif "tomografia" in err_norm and ("instavel" in err_norm or "fast" in err_norm):
            has_tc = any(a.get("action_target") == "tc" or "tomografia" in full_corpus for a in actions)
            if has_tc:
                flagged = True

        elif "endoscopia" in err_norm or "eda" in err_norm:
            if any(term in full_corpus for term in ["eda", "endoscopia", "endoscopia digestiva"]):
                flagged = True

        elif ("radiografia" in err_norm or "tomografia" in err_norm) and "pneumotorax" in station_subtema:
            rx_done = any(a.get("action_type") == "lab_imaging" and a.get("action_target") in ["rx", "raio_x", "tc"] for a in actions)
            decompression_done = any(a.get("action_type") == "procedure" and "puncture" in str(a.get("procedure_type", "")) for a in actions)
            if rx_done and not decompression_done:
                flagged = True

        elif "cortico" in err_norm and "bronquiolite" in station_subtema:
            if any(term in full_corpus for term in ["prednisolona", "prednisona", "dexametasona", "hidrocortisona", "corticoide"]):
                flagged = True
        elif "antibiotico" in err_norm and "bronquiolite" in station_subtema:
            if any(term in full_corpus for term in ["amoxicilina", "azitromicina", "ceftriaxona", "claritromicina", "ampicilina"]):
                flagged = True

        elif "adrenalina" in err_norm and "anafilaxia" in station_subtema:
            if any(term in full_corpus for term in ["adrenalina sc", "subcutanea", "adrenalina subcutanea"]):
                flagged = True

        elif ("anti-inflamatorio" in err_norm or "aas" in err_norm) and "dengue" in station_subtema:
            if any(term in full_corpus for term in ["aas", "aspirina", "ibuprofeno", "cetoprofeno", "nimesulida", "diclofenaco"]):
                flagged = True

        elif ("diazepam" in err_norm or "fenitoina" in err_norm) and "preeclampsia" in station_subtema:
            if any(term in full_corpus for term in ["diazepam", "fenitoina", "hidantal"]):
                flagged = True

        elif "insulina" in err_norm and "glicose" in err_norm and "hipercalemia" in station_subtema:
            has_insulin = _has_affirmative_mention(norm_evidence, all_prescribed_drugs, ["insulina"])
            has_glucose = any(
                term in full_corpus
                for term in ["glicose", "glicosado", "glicoinsulina", "sg 50", "sg50", "sg 10", "sg10", "dextrose"]
            )
            if has_insulin and not has_glucose:
                flagged = True

        elif "espironolactona" in err_norm or "poupador" in err_norm:
            if "espironolactona" in full_corpus:
                flagged = True

        elif "succinilcolina" in err_norm:
            if "succinilcolina" in full_corpus:
                flagged = True

        elif "tocolitico" in err_norm:
            if any(term in full_corpus for term in ["tocolise", "atosibana", "salbutamol", "terbutalina", "nifedipino para tocolise"]):
                flagged = True

        elif "amiodarona" in err_norm and "taquicardia" in station_subtema:
            if any(term in full_corpus for term in ["amiodarona venosa", "amiodarona 300"]):
                flagged = True

        elif "dopamina" in err_norm and "sepse" in station_subtema:
            if "dopamina" in full_corpus:
                flagged = True

        elif "alta" in err_norm and ("hipoxemia" in err_norm or "observacao" in err_norm):
            if any(phrase in full_corpus for phrase in ["dar alta", "libero para casa", "alta hospitalar", "alta para casa"]):
                flagged = True

        if flagged and err not in detected_violations:
            detected_violations.append(err)

    return detected_violations


def generate_timeline_post_mortem(
    station_meta: dict[str, Any],
    transcript: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    evaluated_items: list[dict[str, Any]],
    elapsed_seconds: int
) -> dict[str, Any]:
    """
    Reconstitui a cronologia beira-leito da estação segundo a segundo:
    - Identifica marcos da anamnese, sinais vitais, ECG, labs, manequim e prescrição
    - Detecta atrasos operacionais (porta-ECG, porta-ação inicial)
    - Detecta períodos de hesitação/inércia (> 65s sem ação)
    - Sinaliza quebras críticas de segurança clínica
    """
    events = []

    inst_name = station_meta.get("institution", "Banca Oficial")
    st_title = station_meta.get("title", "Estação Clínica")
    events.append({
        "time_seconds": 0,
        "time_formatted": "00:00",
        "event_type": "start",
        "title": "Entrada na Sala de Exame",
        "description": f"Candidato entra no consultório da banca ({inst_name} • {st_title}).",
        "status": "neutral",
        "feedback": "Início da contagem regressiva oficial. Boa prática: cumprimentar paciente e se identificar.",
        "score_impact": "Início da Prova"
    })

    candidate_action_times = [0]

    for act in actions:
        sec = int(act.get("elapsed_seconds", 0))
        act_type = act.get("action_type")
        act_target = act.get("action_target", "")
        payload = act.get("payload", {})
        candidate_action_times.append(sec)

        m = sec // 60
        s = sec % 60
        tf = f"{m:02d}:{s:02d}"

        if act_type == "vitals":
            status = "timely" if sec <= 90 else ("neutral" if sec <= 180 else "delayed")
            feedback = (
                "Monitorização de sinais vitais realizada com rapidez cirúrgica."
                if status == "timely" else
                "Sinais vitais checados adequadamente."
                if status == "neutral" else
                "Atenção ao tempo: em emergência, sinais vitais devem ser checados nos primeiros 90 segundos."
            )
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "vitals",
                "title": "Aferição de Sinais Vitais & Monitor",
                "description": "Sinais vitais checados no monitor: PA, FC, FR, SatO2 e temperatura.",
                "status": status,
                "feedback": feedback,
                "score_impact": "+ Pontos Vitais"
            })

        elif act_type == "physical_exam":
            status = "timely" if sec <= 180 else "neutral"
            target_label = act_target.replace("_", " ").capitalize()
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "physical_exam",
                "title": f"Exame Físico: {target_label}",
                "description": f"Palpação e ausculta direcionada ao segmento {target_label}.",
                "status": status,
                "feedback": f"Segmento {target_label} examinado com busca ativa de achados do barema.",
                "score_impact": "+1.0 pt"
            })

        elif act_type == "lab_imaging":
            target_norm = act_target.lower()
            is_ecg = any(k in target_norm for k in ["ecg", "eletro", "eletrocardiograma"])
            is_fast = any(k in target_norm for k in ["fast", "efast", "ultrassom"])

            if is_ecg:
                status = "timely" if sec <= 120 else ("neutral" if sec <= 240 else "delayed")
                feedback = (
                    "Meta Porta-ECG de excelência: solicitado em menos de 2 minutos de prova."
                    if status == "timely" else
                    "ECG solicitado em tempo aceitável para a queixa apresentada."
                    if status == "neutral" else
                    "Atraso Porta-ECG: dor torácica/isquemia exige solicitação imediata (< 2-3 min)."
                )
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "lab_imaging",
                    "title": "Solicitação de ECG 12 Derivações",
                    "description": "Eletrocardiograma de 12 derivações entregue pela banca.",
                    "status": status,
                    "feedback": feedback,
                    "score_impact": "Porta-ECG"
                })
            elif is_fast:
                status = "timely" if sec <= 180 else "neutral"
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "procedure",
                    "title": "Ultrassom E-FAST Beira-Leito",
                    "description": "Rastreamento ultrassonográfico de líquido livre em janelas torácicas e abdominais.",
                    "status": status,
                    "feedback": "Protocolo ATLS: busca precoce de hemoperitônio ou hemo/pneumotórax.",
                    "score_impact": "+2.0 pts"
                })
            else:
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "lab_imaging",
                    "title": f"Exame Complementar: {act_target.upper()}",
                    "description": f"Solicitado exame {act_target.upper()} e interpretado laudo.",
                    "status": "neutral",
                    "feedback": "Exame complementar solicitado e analisado junto à banca examinadora.",
                    "score_impact": "+0.5 a 1.0 pt"
                })

        elif act_type == "prescription":
            drugs_summary = payload.get("text", act_target)
            status = "timely" if sec <= 360 else "delayed"
            feedback = (
                "Prescrição administrada oportunamente antes da fase final da estação."
                if status == "timely" else
                "Prescrição realizada tardiamente no final da prova. Priorize estabilização precoce."
            )
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "prescription",
                "title": "Prescrição Farmacológica na Prancheta",
                "description": f"Administração assinada na prancheta de emergência: {drugs_summary[:120]}...",
                "status": status,
                "feedback": feedback,
                "score_impact": "Conduta Terapêutica"
            })

        elif act_type == "procedure":
            proc_title = payload.get("title", act_target)
            events.append({
                "time_seconds": sec,
                "time_formatted": tf,
                "event_type": "procedure",
                "title": f"Procedimento: {proc_title}",
                "description": "Execução de procedimento beira-leito no manequim interativo.",
                "status": "timely",
                "feedback": "Procedimento invasivo executado com indicação e técnica corretas.",
                "score_impact": "+2.0 pts"
            })

    for item in transcript:
        if item.get("sender") == "candidato":
            sec = int(item.get("elapsed_seconds", 0))
            candidate_action_times.append(sec)
            msg = item.get("message", "")
            msg_lower = msg.lower()

            m = sec // 60
            s = sec % 60
            tf = f"{m:02d}:{s:02d}"

            if any(w in msg_lower for w in ["minha conduta", "prescrevo", "indico cirurgia", "encaminho", "passo o caso"]):
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "conduct",
                    "title": "Verbalização da Conduta Definitiva",
                    "description": msg[:140] + ("..." if len(msg) > 140 else ""),
                    "status": "timely" if sec >= 240 else "neutral",
                    "feedback": "Conduta e encaminhamento verbalizados claramente para o examinador.",
                    "score_impact": "+1.5 pts"
                })
            elif len(msg) > 15 and not any(e["time_seconds"] == sec and e["event_type"] == "anamnese" for e in events):
                events.append({
                    "time_seconds": sec,
                    "time_formatted": tf,
                    "event_type": "anamnese",
                    "title": "Interação Clínica com o Paciente",
                    "description": f'"{msg[:110]}..."',
                    "status": "timely" if sec <= 180 else "neutral",
                    "feedback": "Investigação sintomática, acolhimento e escuta atenta do paciente.",
                    "score_impact": "+ Diálogo"
                })

    candidate_action_times.sort()
    unique_times = sorted(list(set(candidate_action_times)))
    for i in range(len(unique_times) - 1):
        t1 = unique_times[i]
        t2 = unique_times[i + 1]
        gap = t2 - t1
        if gap >= 70:
            gap_mid = t1 + (gap // 2)
            m = gap_mid // 60
            s = gap_mid % 60
            events.append({
                "time_seconds": gap_mid,
                "time_formatted": f"{m:02d}:{s:02d}",
                "event_type": "hesitacao",
                "title": f"Período de Hesitação ({gap}s sem ação)",
                "description": f"Intervalo de {gap} segundos sem perguntas ou intervenções ativas do candidato.",
                "status": "delayed",
                "feedback": f"Atenção ao ritmo: {gap} segundos sem conduta. Na 2ª fase presencial, cada minuto ocioso consome tempo crucial de barema.",
                "score_impact": "Ritmo Comprometido"
            })

    st_title_lower = station_meta.get("title", "").lower()
    st_subtema_lower = station_meta.get("subtema", "").lower()
    all_targets = [str(a.get("action_target", "")).lower() for a in actions]
    all_types = [str(a.get("action_type", "")).lower() for a in actions]

    if "vitals" not in all_types:
        events.append({
            "time_seconds": elapsed_seconds or 480,
            "time_formatted": f"{(elapsed_seconds or 480)//60:02d}:{(elapsed_seconds or 480)%60:02d}",
            "event_type": "omissao",
            "title": "Omissão Crítica: Sinais Vitais Não Checados",
            "description": "Candidato não solicitou monitorização ou sinais vitais durante toda a estação.",
            "status": "critical_gap",
            "feedback": "Falta de segurança: todo atendimento beira-leito deve iniciar com a checagem dos sinais vitais.",
            "score_impact": "Perda Grave de Barema"
        })

    if ("sca" in st_title_lower or "coronariana" in st_subtema_lower or "taquicardia" in st_title_lower) and not any("ecg" in t for t in all_targets):
        events.append({
            "time_seconds": elapsed_seconds or 480,
            "time_formatted": f"{(elapsed_seconds or 480)//60:02d}:{(elapsed_seconds or 480)%60:02d}",
            "event_type": "omissao",
            "title": "Omissão Crítica: Eletrocardiograma Não Solicitado",
            "description": "Em queixa de dor torácica/isquemia, o ECG de 12 derivações é item obrigatório do barema.",
            "status": "critical_gap",
            "feedback": "Erro eliminatório: tempo porta-ECG não atingido porque o exame não foi solicitado.",
            "score_impact": "Eliminatório / -2.0 pts"
        })

    events.sort(key=lambda x: x["time_seconds"])

    timely_count = sum(1 for e in events if e.get("status") == "timely")
    delayed_count = sum(1 for e in events if e.get("status") == "delayed")
    critical_count = sum(1 for e in events if e.get("status") == "critical_gap")

    first_action_sec = unique_times[1] if len(unique_times) > 1 else elapsed_seconds
    ecg_sec = next((e["time_seconds"] for e in events if "ecg" in e["title"].lower()), None)

    if critical_count > 0 or delayed_count >= 3:
        pace_label = "Hesitante / Atrasos Críticos"
    elif timely_count >= 4 and delayed_count <= 1:
        pace_label = "Ritmo Cirúrgico / Ágil"
    else:
        pace_label = "Equilibrado / Médio"

    return {
        "events": events,
        "summary": {
            "total_events": len(events),
            "timely_count": timely_count,
            "delayed_count": delayed_count,
            "critical_gaps_count": critical_count,
            "door_to_first_action_seconds": first_action_sec,
            "door_to_ecg_seconds": ecg_sec,
            "pace_label": pace_label
        }
    }


def generate_competency_radar(
    station_meta: dict[str, Any],
    evaluated_items: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    elapsed_seconds: int,
    critical_warnings: Optional[list[str]] = None
) -> dict[str, Any]:
    """
    Calcula o Radar de Competências Médicas em 6 dimensões fundamentais de prova prática:
    1. Comunicação & Empatia
    2. Raciocínio Clínico & Anamnese
    3. Exame Físico & Habilidades Práticas
    4. Indicação & Interpretação de Exames Complementares
    5. Tomada de Decisão & Segurança Farmacológica
    6. Gestão do Tempo Beira-Leito
    """
    category_scores = {
        "comunicacao_empatia": {"earned": 0.0, "max": 0.0, "items": []},
        "raciocinio_clinico": {"earned": 0.0, "max": 0.0, "items": []},
        "exame_fisico": {"earned": 0.0, "max": 0.0, "items": []},
        "exames_complementares": {"earned": 0.0, "max": 0.0, "items": []},
        "seguranca_farmacologica": {"earned": 0.0, "max": 0.0, "items": []},
        "gestao_tempo": {"earned": 0.0, "max": 0.0, "items": []}
    }

    for it in evaluated_items:
        cat = it.get("category", "").lower()
        earned = float(it.get("score_earned", 0.0))
        weight = float(it.get("weight", 1.0))

        if "comunicacao" in cat or "empatia" in cat or "relacao" in cat:
            key = "comunicacao_empatia"
        elif "anamnese" in cat or "diagnostico" in cat or "raciocinio" in cat:
            key = "raciocinio_clinico"
        elif "fisico" in cat or "manobra" in cat or "procedimento" in cat:
            key = "exame_fisico"
        elif "lab" in cat or "imagem" in cat or "complementar" in cat or ("exame" in cat and "fisico" not in cat):
            key = "exames_complementares"
        elif "farmaco" in cat or "prescricao" in cat or "tratamento" in cat or "conduta" in cat:
            key = "seguranca_farmacologica"
        else:
            key = "raciocinio_clinico"

        category_scores[key]["earned"] += earned
        category_scores[key]["max"] += weight
        category_scores[key]["items"].append(it)

    time_score_max = 2.0
    time_score_earned = 2.0
    if elapsed_seconds > 450:
        time_score_earned -= 0.5
    action_times = sorted([int(a.get("elapsed_seconds", 0)) for a in actions if a.get("elapsed_seconds")])
    for i in range(len(action_times) - 1):
        if action_times[i+1] - action_times[i] >= 75:
            time_score_earned -= 0.5
            break
    time_score_earned = max(0.5, time_score_earned)
    category_scores["gestao_tempo"]["earned"] = time_score_earned
    category_scores["gestao_tempo"]["max"] = time_score_max

    dim_configs = [
        ("comunicacao_empatia", "Comunicação & Empatia", "Relação médico-paciente, acolhimento e clareza de linguagem."),
        ("raciocinio_clinico", "Raciocínio & Anamnese", "Investigação sintomática, fatores de risco e hipótese diagnóstica."),
        ("exame_fisico", "Exame Físico & Habilidades", "Ausculta, palpação, monitorização e procedimentos beira-leito."),
        ("exames_complementares", "Exames Complementares", "Indicação criteriosa de ECG, imagem, gasometria e laboratoriais."),
        ("seguranca_farmacologica", "Segurança Farmacológica", "Doses corretas, vias seguras, contraindicações e drogas prioritárias."),
        ("gestao_tempo", "Gestão do Tempo", "Ritmo, dinamismo e tomada de decisão antes dos avisos da banca.")
    ]

    dimensions = []
    total_pct = 0.0

    for key, name, desc in dim_configs:
        earned = category_scores[key]["earned"]
        c_max = category_scores[key]["max"]
        if c_max == 0:
            c_max = 1.0
            earned = 0.8

        pct = round(min(100.0, max(0.0, (earned / c_max) * 100)), 1)
        if key == "seguranca_farmacologica" and critical_warnings:
            penal_pct = max(15.0, pct - (len(critical_warnings) * 35.0))
            pct = round(penal_pct, 1)
        total_pct += pct

        if pct >= 80.0:
            level = "Excelente"
            feedback = "Domínio seguro nesta competência. Execução precisa segundo o gabarito oficial."
        elif pct >= 60.0:
            level = "Satisfatório"
            feedback = "Bom desempenho, com oportunidades de refinamento e maior agilidade."
        else:
            level = "Necessita Atenção"
            feedback = "Ponto de atenção na prova prática. Revise os passos capitais no FSRS."

        dimensions.append({
            "key": key,
            "name": name,
            "score_earned": round(earned, 1),
            "score_max": round(c_max, 1),
            "percentage": pct,
            "level": level,
            "description": desc,
            "feedback": feedback
        })

    overall_avg = round(total_pct / len(dimensions), 1)

    sorted_dims = sorted(dimensions, key=lambda d: d["percentage"], reverse=True)
    strengths = [d["name"] for d in sorted_dims[:2] if d["percentage"] >= 65]
    if not strengths:
        strengths = [sorted_dims[0]["name"]]
    weaknesses = [d["name"] for d in sorted_dims[-2:] if d["percentage"] < 75]

    return {
        "overall_average": overall_avg,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "dimensions": dimensions
    }


def evaluate_osce_red_flags(
    actions: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    station_meta: dict[str, Any],
    checklist_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Motor Determinístico de Detecção de Erros Críticos Eliminatórios (Red Flags Engine).
    Identifica iatrogenias anatômicas, quebra de sequência do ATLS e prescrições de risco letal.
    """
    red_flags: list[dict[str, Any]] = []
    proc_actions = [a for a in actions if a.get("action_type") == "procedure"]
    exam_actions = [a for a in actions if a.get("action_type") in ("exam", "vitals", "labs", "imaging")]

    for p in proc_actions:
        site = str(p.get("anatomical_site", "")).lower()
        proc = str(p.get("procedure_type", "")).lower()
        elapsed = p.get("elapsed_seconds", 0)

        if "inferior_border" in site or ("iatrogenic" in site and ("thoracocentesis" in proc or "relief" in proc or "r2" in site)):
            red_flags.append({
                "code": "RF_ANAT_NEUROVASC",
                "title": "Lesão Iatrogênica do Feixe Vásculo-Nervoso Intercostal",
                "description": "Punção realizada rente à BORDA INFERIOR da costela superior. Risco iminente de hemotórax maciço por laceração de artéria e veia intercostais.",
                "timestamp_sec": elapsed,
                "score_deduction": 2.5,
                "caps_station_at": 4.0,
                "clinical_consequence": "Hemotórax iatrogênico agudo decorrente de sítio cirúrgico incorreto."
            })

        if "thyroid_gland" in site or ("iatrogenic" in site and ("crico" in proc or "cricothyroidotomy" in site or "thyroid" in site)):
            red_flags.append({
                "code": "RF_ANAT_THYROID",
                "title": "Erro Anatômico Crítico em Via Aérea Cirúrgica",
                "description": "Incisão cirúrgica realizada sobre o istmo da glândula tireoide em vez da membrana cricotireoidea.",
                "timestamp_sec": elapsed,
                "score_deduction": 3.0,
                "caps_station_at": 3.0,
                "clinical_consequence": "Hemorragia cervical maciça com inundação traqueal e impossibilidade de oxigenação."
            })

    for a in actions:
        if a.get("action_type") == "cardioversion" or (a.get("action_type") == "procedure" and "cardioversion" in str(a.get("procedure_type", "")).lower()):
            if a.get("sync") is False or "desincronizado" in str(a.get("findings", "")).lower():
                red_flags.append({
                    "code": "RF_ELEC_UNSYNC_VT",
                    "title": "Choque Desincronizado em Taquiarritmia com Pulso",
                    "description": "Disparo elétrico não-sincronizado aplicado em paciente com pulso presente (Fenômeno R-sobre-T).",
                    "timestamp_sec": a.get("elapsed_seconds", 0),
                    "score_deduction": 3.0,
                    "caps_station_at": 3.0,
                    "clinical_consequence": "Indução iatrogênica de Fibrilação Ventricular e Parada Cardiorrespiratória."
                })

    station_code = str(station_meta.get("code", "")).upper()
    is_trauma = any(k in station_code for k in ("FAST", "TRAUMA", "PNEUMO")) or "trauma" in str(station_meta.get("title", "")).lower()
    if is_trauma:
        imaging_requests = [a for a in exam_actions if any(term in str(a.get("action_target", "")).lower() for term in ("tc", "tomografia", "raio", "rx"))]
        has_decompression = any("thoracocentesis" in str(p.get("procedure_type", "")).lower() or "chest_tube" in str(p.get("procedure_type", "")).lower() for p in proc_actions)
        if imaging_requests and not has_decompression and "PNEUMO" in station_code:
            first_img_time = imaging_requests[0].get("elapsed_seconds", 0)
            red_flags.append({
                "code": "RF_ABCDE_VIOLATION",
                "title": "Atropelo da Sequência do ATLS (Quebra do ABCDE)",
                "description": "Solicitou exames de imagem secundários antes de realizar a descompressão de emergência em tórax hipertensivo.",
                "timestamp_sec": first_img_time,
                "score_deduction": 2.0,
                "caps_station_at": 4.5,
                "clinical_consequence": "Atraso crítico na reversão de choque obstrutivo com evolução para PCR em AESP."
            })

    candidate_all_text = " ".join([str(t.get("message", "")).lower() for t in transcript if t.get("sender") == "candidato"])
    subtema_lower = str(station_meta.get("subtema", "")).lower()
    if any(drug in candidate_all_text for drug in ("betabloqueador", "metoprolol", "propranolol", "atenolol")):
        if any(term in subtema_lower for term in ("sca", "infarto", "choque", "cocaína")):
            red_flags.append({
                "code": "RF_PHARM_CONTRA",
                "title": "Prescrição Farmacológica de Alto Risco",
                "description": "Prescrição de betabloqueador em vigência de choque cardiogênico ou sinais de congestão pulmonar aguda.",
                "timestamp_sec": 0,
                "score_deduction": 2.0,
                "caps_station_at": 4.5,
                "clinical_consequence": "Depressão miocárdica aguda e agravamento de choque cardiogênico."
            })

    return red_flags


def compute_competency_radar_5d(
    station_meta: dict[str, Any],
    evaluated_items: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    elapsed_seconds: int,
    red_flags: list[dict[str, Any]]
) -> dict[str, Any]:
    """Computa o Radar Psicométrico em 5 Dimensões Médicas Fundamentais (0 a 100)."""
    diag_items = [it for it in evaluated_items if any(k in str(it.get("category", "")).lower() for k in ("anamnese", "diagnostico", "raciocinio"))]
    diag_pct = (sum(it.get("score_earned", 0.0) for it in diag_items) / max(1.0, sum(it.get("weight", 1.0) for it in diag_items))) * 100 if diag_items else 75.0

    cand_dialogue_count = len([t for t in transcript if t.get("sender") == "candidato" and t.get("target") != "EXAMINER"])
    comm_pct = min(100.0, max(40.0, cand_dialogue_count * 14.0 + 30.0))

    proc_items = [it for it in evaluated_items if any(k in str(it.get("category", "")).lower() for k in ("fisico", "procedimento", "manobra", "ausculta"))]
    proc_pct = (sum(it.get("score_earned", 0.0) for it in proc_items) / max(1.0, sum(it.get("weight", 1.0) for it in proc_items))) * 100 if proc_items else 70.0

    safety_pct = 100.0
    for _ in red_flags:
        safety_pct -= 25.0
    safety_pct = max(10.0, min(100.0, safety_pct))

    first_action_time = min([int(a.get("elapsed_seconds", 0)) for a in actions if a.get("elapsed_seconds")], default=150)
    time_pct = 95.0 if first_action_time <= 90 else (75.0 if first_action_time <= 150 else 50.0)

    return {
        "clinical_reasoning": round(diag_pct, 1),
        "communication_empathy": round(comm_pct, 1),
        "surgical_semiotics": round(proc_pct, 1),
        "patient_safety": round(safety_pct, 1),
        "sus_time_efficiency": round(time_pct, 1)
    }


def build_chief_preceptor_review(
    station_meta: dict[str, Any],
    evaluated_items: list[dict[str, Any]],
    red_flags: list[dict[str, Any]],
    final_score: float
) -> dict[str, Any]:
    """Sintetiza parecer executivo de alto rendimento no padrão de preceptor de residência médica."""
    subtema = str(station_meta.get("subtema", "")).upper()
    title = str(station_meta.get("title", ""))
    inst = str(station_meta.get("institution", "USP-RP"))

    full_items = [it.get("title") for it in evaluated_items if it.get("status") == "cumprido_total"]
    what_went_well = full_items[:3] if full_items else ["Atendimento iniciado dentro do tempo limite oficial."]

    critical_corrections = [rf.get("description") for rf in red_flags]
    if not critical_corrections:
        unfulfilled = [it.get("title") for it in evaluated_items if it.get("status") == "nao_cumprido"]
        critical_corrections = unfulfilled[:3] if unfulfilled else ["Manter ritmo de prova e verbalização clara das condutas."]

    if "PNEUMO" in subtema or "PNEUMOTÓRAX" in title.upper():
        canonical = (
            "1. Reconhecimento clínico imediato de Pneumotórax Hipertensivo (hipotensão, turgência jugular, MV abolido e timpanismo unilateral).\n"
            "2. Proibido solicitar Raio-X ou TC de tórax: o diagnóstico é puramente clínico!\n"
            "3. Descompressão imediata por toracocentese de alívio com Jelco 14G na borda superior da costela no 2º EIC LHC ou 5º EIC LAA.\n"
            "4. Monitorização contínua com oxigênio suplementar em máscara não-reinalante.\n"
            "5. Solicitação imediata à enfermagem da bandeja de toracostomia tubular com dreno 28-32 Fr em selo d'água."
        )
    elif "SCA" in subtema or "CORONARIANA" in title.upper():
        canonical = (
            "1. ECG de 12 derivações realizado e laudado em menos de 10 minutos (meta ATLS/AHA).\n"
            "2. Monitorização multiparamétrica, acesso venoso calibroso e oxigênio se SpO2 < 90%.\n"
            "3. Terapia anti-isquêmica e antiplaquetária dupla imediata: AAS 200-300 mg mastigado + Ticagrelor 180 mg ou Clopidogrel 300-600 mg.\n"
            "4. Nitrato sublingual se dor refratária (contraindicado em infarto de VD ou uso de sildenafila nas últimas 24h).\n"
            "5. Acionamento do laboratório de hemodinâmica para angioplastia primária com tempo porta-balão < 90 minutos."
        )
    elif "TV" in subtema or "TAQUICARDIA" in title.upper():
        canonical = (
            "1. Avaliação rápida de estabilidade hemodinâmica (Dor torácica anginosa, Dispneia/congestão, Hipotensão, Rebaixamento do sensório).\n"
            "2. Em paciente instável: Cardioversão Elétrica SINCRONIZADA imediata (100 J bifásico) com sedação rápida (Fentanil + Midazolam ou Etomidato).\n"
            "3. Garantir confirmação da marcação das ondas R (SYNC ativo) antes do disparo elétrico.\n"
            "4. Reavaliação imediata de ritmo e pulso pós-choque."
        )
    elif "HPP" in subtema or "HEMORRAGIA" in title.upper():
        canonical = (
            "1. Mapeamento da etiologia pelos 4 T's (Tônus 70%, Trauma, Tecido, Trombina).\n"
            "2. Massagem uterina bimanual imediata (Manobra de Hamilton) associada a ocitocina IV em infusão contínua.\n"
            "3. Acessos calibrosos 14-16G, coleta de tipagem sanguínea com prova cruzada e prova do coágulo beira-leito.\n"
            "4. Ácido tranexâmico 1g IV infundido nos primeiros 10 minutos de sangramento ativo."
        )
    else:
        canonical = (
            f"Atendimento padrão {inst}: Abordagem sistemática, anamnese direcionada, exame físico segmentar, "
            f"solicitação criteriosa de exames laboratoriais/imagem e prescrição de conduta padrão com doses e vias explícitas."
        )

    summary = (
        f"Desempenho oficial de {final_score:.1f}/10.0 na estação de {title} ({inst}). "
        + ("Excelente maturidade clínica, execução ágil dos passos capitais e segurança no manejo de emergência."
           if final_score >= 8.5 else
           "Atendimento consistente, mas com lacunas técnicas ou hesitações de conduta que limitaram a pontuação final."
           if final_score >= 7.0 else
           "Pontuação abaixo da nota de corte da banca examinadora. Identificadas falhas metodológicas ou violações de segurança que exigem remediação.")
    )

    return {
        "executive_summary": summary,
        "what_went_well": what_went_well,
        "critical_corrections": critical_corrections,
        "gold_standard_canonical_conduct": canonical
    }


def build_medquest_remediation(
    station_meta: dict[str, Any],
    weaknesses: list[str]
) -> dict[str, Any]:
    """Gera prescrição de estudo focado para remediação no MedQuest."""
    area = str(station_meta.get("area", "Clínica Médica"))
    subtema = str(station_meta.get("subtema", "Emergências"))

    return {
        "recommended_flashcard_decks": [
            f"5º Ano - {area} ({subtema})",
            "R1 USP/UNICAMP - Protocolos de Emergência Beira-Leito"
        ],
        "recommended_qbank_filters": [
            {"specialty": area, "subtopic": subtema, "difficulty": "Médio / Difícil"}
        ],
        "suggested_retry_station_id": str(station_meta.get("id", ""))
    }
