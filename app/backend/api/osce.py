"""Motor de Simulação de Prova Prática (OSCE) e 2ª Fase de Residência Médica.

Gerencia o catálogo de estações das bancas oficiais que realizam prova prática
(UNICAMP, UNIFESP, Einstein, Revalida INEP, SCMSP, USP-RP), o ciclo de vida
das sessões de beira-leito, a atuação do paciente virtual e do examinador,
e a auditoria oficial do barema de correção com geração de flashcards de choque.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .db import db_transaction, get_db
from .universal_pool import generate_content_with_fallback

logger = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """Normaliza texto removendo acentos e espaços extras para matching tolerante a grafia."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

CANONICAL_STATIONS: list[dict[str, Any]] = [
    {
        "code": "USP-RP-2024-CM-CAD",
        "title": "Cetoacidose Diabética no HC-UE Ribeirão Preto",
        "area": "Clínica Médica",
        "subtema": "Diabetes Mellitus e Emergências Endócrinas",
        "institution": "USP-RP",
        "year": 2024,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: SALA VERMELHA / UNIDADE DE EMERGÊNCIA (HC-UE FMRP-USP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico de plantão na Sala Vermelha da Unidade de Emergência do Hospital das Clínicas da FMRP-USP (Ribeirão Preto).\n\n"
            "**Cenário**:\n"
            "- Paciente: Lucas Silveira, 19 anos, estudante, portador de Diabetes Mellitus tipo 1.\n"
            "- Queixa: Vômitos intensos, dor abdominal difusa e sonolência progressiva iniciados há 2 dias após suspender a insulina por conta própria.\n\n"
            "**Sua Tarefa**:\n"
            "1. Realize a avaliação clínica inicial e identifique a complicação aguda do diabetes.\n"
            "2. Solicite e interprete os exames laboratoriais e a gasometria arterial.\n"
            "3. Prescreva o plano de hidratação venosa e o manejo hidroeletrolítico (Potássio).\n"
            "4. Prescreva a insulinoterapia em bomba e estabeleça os critérios de vigilância.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Lucas Silveira",
            "age": 19,
            "gender": "masculino",
            "chief_complaint": "Tô... com muita sede... a boca tá colando... a barriga dói demais...",
            "past_medical_history": "DM1 diagnosticado há 5 anos. Usa insulina Glargina e Lispro, mas suspendeu há 2 dias porque estava enjoado e achou que a glicemia ia cair.",
            "allergies": "Nenhuma alergia relatada."
        },
        "physical_exam": {
            "vitals": {
                "pa": "90x60 mmHg",
                "fc": "128 bpm",
                "fr": "32 irpm (Respiração de Kussmaul)",
                "sato2": "97% em ar ambiente",
                "temp": "36.2 °C",
                "hgt": "HI (> 500 mg/dL)"
            },
            "findings": {
                "geral": "Torporoso, abertura ocular ao chamado verbal, hálito cetônico marcante (odor de maçã podre), desidratação grave 3+/4+ com mucosas secas e olhos encovados.",
                "respiratorio": "Hiperpneia profunda e rápida com incursões toracoabdominais amplas (respiração ácida de Kussmaul), murmúrio vesicular simétrico sem ruídos adventícios.",
                "cardiovascular": "Taquicardia sinusal rítmica, bulhas normofonéticas, pulsos periféricos finos, tempo de enchimento capilar de 3 segundos.",
                "abdome": "Abdome difusamente doloroso à palpação profunda porém flácido, sem visceromegalias ou sinais de irritação peritoneal (dor decorrente da cetose e acidose)."
            }
        },
        "lab_imaging": {
            "gasometria_eletrólitos": {
                "title": "Gasometria Arterial e Eletrólitos Séricos",
                "available": True,
                "result_text": "pH 7.12, pCO2 24 mmHg, HCO3 9 mEq/L, BE -16 mEq/L. Na: 132 mEq/L, K: 4.2 mEq/L, Cl: 99 mEq/L. Ânion Gap calculado: 24 mEq/L (Acidose Metabólica Grave com Ânion Gap Elevado). Cetonúria: 4+."
            },
            "funcao_renal": {
                "title": "Função Renal e Glicemia Sérica",
                "available": True,
                "result_text": "Glicemia sérica: 580 mg/dL. Ureia: 64 mg/dL. Creatinina: 1.4 mg/dL. Lactato: 1.8 mmol/L."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Avaliação Inicial do Nível de Consciência e Respiração de Kussmaul",
                "description": "Identifica o torpor, a taquipneia profunda de Kussmaul e o hálito cetônico característicos da cetoacidose.",
                "weight": 1.0,
                "category": "exame_fisico",
                "keywords": ["kussmaul", "hálito cetônico", "torpor", "desidratação", "taquipneia"]
            },
            {
                "id": "item_2",
                "title": "Diagnóstico Correto de Cetoacidose Diabética (CAD) Grave",
                "description": "Verbaliza o diagnóstico de CAD grave com base na tríade: hiperglicemia > 200 + acidose metabólica (pH < 7.3, HCO3 < 15) + cetonemia/cetonúria com ânion gap elevado.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["cetoacidose diabética", "cad", "ânion gap", "acidose metabólica"]
            },
            {
                "id": "item_3",
                "title": "Prescrição Imediata de Hidratação Venosa Rápida (Soro Fisiológico 0,9%)",
                "description": "Prescreve infusão rápida de Soro Fisiológico 0,9% (1000 a 1500 ml na primeira hora - 15 a 20 ml/kg) para expansão volêmica.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["soro fisiológico", "sf 0,9%", "1000 ml", "1 litro", "expansão", "primeira hora"]
            },
            {
                "id": "item_4",
                "title": "Manejo Obrigatório do Potássio Sérico ANTES/DURANTE a Insulina",
                "description": "Avalia o K+ sérico (4.2 mEq/L) e prescreve reposição de 20-30 mEq de KCl por litro de soro, sabendo que a insulina desloca o potássio para o meio intracelular.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["potássio", "kcl", "cloreto de potássio", "20 meq", "repor potássio"]
            },
            {
                "id": "item_5",
                "title": "Insulinoterapia Venosa Contínua com Insulina Regular",
                "description": "Prescreve Insulina Regular em bomba de infusão contínua (0,1 U/kg/h ou bólus de 0,1 U/kg seguido de 0,1 U/kg/h) com meta de queda glicêmica de 50 a 70 mg/dL/h.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["insulina regular", "bomba de infusão", "bic", "0,1 u/kg", "queda glicêmica"]
            },
            {
                "id": "item_6",
                "title": "Introdução de Soro Glicosado a 5% ao Atingir Glicemia 200-250 mg/dL",
                "description": "Verbaliza a regra de ouro da USP-RP: associar SG 5% quando a glicemia atingir 200-250 mg/dL mantendo a insulina para fechar o ânion gap sem hipoglicemia.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["soro glicosado", "sg 5%", "200", "250", "fechar ânion gap"]
            }
        ],
        "critical_errors": [
            "Iniciar insulina venosa plena com potássio sérico desconhecido ou < 3.3 mEq/L (risco de arritmia ventricular fatal por hipocalemia)",
            "Prescrever Bicarbonato de Sódio de rotina para pH de 7.12 (contraindicado na CAD para pH > 6.9 pela ADA e protocolo FMRP-USP)",
            "Suspender a infusão de insulina assim que a glicemia baixar de 250 mg/dL (o critério de resolução é o fechamento do ânion gap e HCO3 > 18)"
        ]
    },
    {
        "code": "USP-RP-2024-CM-SCA",
        "title": "SCA sem Supra / Angina Instável de Alto Risco no HC-UE",
        "area": "Clínica Médica",
        "subtema": "Síndromes Coronarianas Agudas",
        "institution": "USP-RP",
        "year": 2024,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: UNIDADE CORONARIANA / CARDIOLOGIA (HC-UE FMRP-USP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico plantonista da Cardiologia da Unidade de Emergência da FMRP-USP (Ribeirão Preto).\n\n"
            "**Cenário**:\n"
            "- Paciente: Dona Neusa, 64 anos, aposentada, hipertensa e diabética de longa data.\n"
            "- Queixa: Episódios de dor em aperto no peito no último mês aos esforços, que hoje iniciou em repouso há 2 horas com náuseas e sudorese.\n\n"
            "**Sua Tarefa**:\n"
            "1. Realize a anamnese e exame cardiovascular direcionados.\n"
            "2. Solicite e interprete o ECG de 12 derivações e biomarcadores.\n"
            "3. Estratifique o risco isquêmico através de escore validado (GRACE / TIMI).\n"
            "4. Estabeleça a conduta antitrombótica, anti-isquêmica e o momento da estratificação invasiva.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Neusa Maria",
            "age": 64,
            "gender": "feminino",
            "chief_complaint": "Doutor, sinto um aperto no meio do peito que queima e vai pro pescoço. Já vinha sentindo quando varria o quintal, mas hoje deu sentado no sofá e não passa.",
            "past_medical_history": "HAS há 15 anos em uso de Losartana e Anlodipino. DM2 há 10 anos em uso de Metformina. Nega tabagismo.",
            "allergies": "Nenhuma alergia."
        },
        "physical_exam": {
            "vitals": {
                "pa": "135x85 mmHg",
                "fc": "78 bpm",
                "fr": "18 irpm",
                "sato2": "96% em ar ambiente",
                "temp": "36.5 °C"
            },
            "findings": {
                "geral": "Lúcida, ansiosa, sudorética, corada, eupneica em repouso.",
                "cardiovascular": "Ritmo cardíaco regular em 2 tempos, presença de B4 à ausculta no foco mitral (sobrecarga/disfunção diastólica), ausência de sopros ou atrito pericárdico.",
                "respiratorio": "Murmúrio vesicular limpo bilateralmente, sem estertores (Killip I)."
            }
        },
        "lab_imaging": {
            "ecg": {
                "title": "Eletrocardiograma de 12 Derivações",
                "available": True,
                "result_text": "Ritmo sinusal regular, FC 78 bpm. Presença de infradesnivelamento horizontal do segmento ST de 1,5 mm nas derivações V4, V5 e V6, associado a inversão de onda T assimétrica. Ausência de supradesnivelamento de ST.",
                "image_url": "/images/osce/ecg_infra_st.png"
            },
            "troponina": {
                "title": "Troponina Ultrassensível e Escore GRACE",
                "available": True,
                "result_text": "Troponina I: 0.28 ng/mL (limite de corte: 0.04 ng/mL - curva em ascensão). Escore GRACE calculado: 146 pontos (> 140 = Alto Risco de Eventos Isquêmicos Maiores)."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Identificação de Angina de Repouso e Crescendo",
                "description": "Caracteriza a dor como Síndrome Coronariana Aguda sem Supradesnivelamento de ST (SAMSST) com padrão de angina em repouso prolongada (> 20 min).",
                "weight": 1.5,
                "category": "anamnese",
                "keywords": ["samsst", "sem supra", "angina de repouso", "angina instável", "infarto sem supra"]
            },
            {
                "id": "item_2",
                "title": "Interpretação Precisa do Eletrocardiograma",
                "description": "Identifica o infradesnivelamento do segmento ST em parede lateral (V4-V6) e inversão de onda T.",
                "weight": 1.5,
                "category": "exames_complementares",
                "keywords": ["infradesnivelamento", "infra de st", "onda t", "isquemia"]
            },
            {
                "id": "item_3",
                "title": "Estratificação de Alto Risco (Escore GRACE / TIMI)",
                "description": "Reconhece o alto risco isquêmico pelo escore GRACE > 140, alterações dinâmicas de ST e troponina positiva.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["grace", "timi", "alto risco", "estratificação"]
            },
            {
                "id": "item_4",
                "title": "Dupla Antiagregação Plaquetária Imediata",
                "description": "Prescreve AAS mastigável (200-300 mg) associado a Inibidor de P2Y12 (Ticagrelor 180 mg ou Clopidogrel 300-600 mg).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["aas", "ticagrelor", "clopidogrel", "dupla antiagregação"]
            },
            {
                "id": "item_5",
                "title": "Anticoagulação Plena com Enoxaparina",
                "description": "Prescreve Enoxaparina 1 mg/kg por via subcutânea de 12 em 12 horas (ajustando para função renal).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["enoxaparina", "clexane", "anticoagulação", "1 mg/kg"]
            },
            {
                "id": "item_6",
                "title": "Terapia Anti-isquêmica Otimizada e Estatina de Alta Potência",
                "description": "Prescreve Nitrato sublingual se dor torácica ativa, Betabloqueador oral precoce e Atorvastatina 80 mg.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["nitrato", "betabloqueador", "atorvastatina", "isordil"]
            },
            {
                "id": "item_7",
                "title": "Indicação de Estratégia Invasiva Precoce (CATE em até 24 Horas)",
                "description": "Indica cineangiocoronariografia (cateterismo) precoce em até 24 horas decorrente do escore GRACE > 140 e troponina positiva.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["cateterismo", "cate", "24 horas", "estratégia invasiva precoce"]
            }
        ],
        "critical_errors": [
            "Indicar trombolítico (fibrinolítico) em Síndrome Coronariana Aguda SEM supradesnivelamento de ST (contraindicação formal absoluta)",
            "Não indicar estratégia invasiva precoce em paciente classificado como alto risco pelo escore GRACE"
        ]
    },
    {
        "code": "USP-RP-2023-CG-FAST",
        "title": "Politrauma com Choque Hemorrágico e E-FAST Positivo",
        "area": "Cirurgia Geral",
        "subtema": "Trauma e ATLS",
        "institution": "USP-RP",
        "year": 2023,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: SALA VERMELHA DE TRAUMA (HC-UE FMRP-USP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o cirurgião geral plantonista da Sala Vermelha de Trauma da Unidade de Emergência da FMRP-USP.\n\n"
            "**Cenário**:\n"
            "- Paciente: Carlos Eduardo, 32 anos, vítima de colisão auto x caminhão na Rodovia Anhanguera há 25 minutos.\n"
            "- Admitido pelo SAMU em prancha rígida e colar cervical, pálido, taquicárdico e hipotenso.\n\n"
            "**Sua Tarefa**:\n"
            "1. Conduza a avaliação primária do ATLS na ordem estrita ABCDE.\n"
            "2. Solicite e interprete o E-FAST beira-leito imediato na sala vermelha.\n"
            "3. Prescreva as medidas de ressuscitação hemostática e protocolo de transfusão maciça.\n"
            "4. Defina a conduta cirúrgica imediata e o destino seguro do paciente.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Carlos Eduardo (Trauma)",
            "age": 32,
            "gender": "masculino",
            "chief_complaint": "Minha barriga... tá doendo muito do lado esquerdo... tô com frio...",
            "past_medical_history": "Previamente hígido."
        },
        "physical_exam": {
            "vitals": {
                "pa": "80x50 mmHg",
                "fc": "134 bpm",
                "fr": "26 irpm",
                "sato2": "95% em máscara de O2 com colar cervical",
                "temp": "35.8 °C (hipotermia)"
            },
            "findings": {
                "atls_a": "Via aérea pérvia, falando com voz pastosa, colar cervical bem posicionado e alinhado.",
                "atls_b": "Tórax estável à palpação, murmúrio vesicular universalmente audível e simétrico, sem sinais de pneumotórax ou hemotórax.",
                "atls_c": "Choque Hemorrágico Grau III: palidez cutânea 3+/4+, sudorese fria, pulsos radiais filiformes. Abdome distendido com equimose importante no hipocôndrio e flanco esquerdos (sinal do cinto de segurança), dor intensa à palpação profunda com descompressão duvidosa.",
                "atls_d": "Glasgow 14 (confuso), pupilas isocóricas e fotorreagentes.",
                "atls_e": "Pelve estável, sem sangramento em meato uretral, aquecimento do paciente com mantas térmicas."
            }
        },
        "lab_imaging": {
            "e_fast": {
                "title": "E-FAST Beira-Leito (Sala Vermelha)",
                "available": True,
                "result_text": "Janela pericárdica: sem derrame. Espaço hepatorrenal (Morison): lâmina fina de líquido livre. Espaço esplenorrenal (recesso de Koller): presença de grande quantidade de líquido livre anecoico circundando o baço com laceração esplênica visível. Pelve: líquido livre em fundo de saco retrovesical. FAST POSITIVO."
            },
            "gaso_lactato": {
                "title": "Gasometria e Lactato da Admissão",
                "available": True,
                "result_text": "pH 7.24, BE -9 mEq/L, Lactato: 4.2 mmol/L. Hemoglobina inicial: 8.2 g/dL."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Sistematização do ATLS (Ordem ABCDE Rigorosa)",
                "description": "Verifica via aérea e coluna cervical (A), respiração e ausculta pulmonar (B) e foca na circulação e controle de sangramento (C).",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["atls", "abcde", "colar cervical", "respiração", "circulação"]
            },
            {
                "id": "item_2",
                "title": "Diagnóstico de Choque Hemorrágico Classe III",
                "description": "Reconhece os sinais de choque descompensado (PA 80x50, FC 134, hipotermia, acidose e lactato elevado).",
                "weight": 1.0,
                "category": "diagnostico",
                "keywords": ["choque hemorrágico", "classe 3", "classe iii", "choque hipovolêmico"]
            },
            {
                "id": "item_3",
                "title": "Solicitação Imediata de E-FAST na Sala Vermelha",
                "description": "Solicita E-FAST beira-leito sem retirar o paciente da sala de reanimação.",
                "weight": 1.5,
                "category": "exames_complementares",
                "keywords": ["fast", "e-fast", "ultrassom", "ultrassonografia beira-leito"]
            },
            {
                "id": "item_4",
                "title": "Interpretação do FAST: Hemoperitônio Maciço / Trauma Esplênico",
                "description": "Identifica líquido livre no espaço esplenorrenal e na pelve caracterizando hemoperitônio agudo no paciente chocado.",
                "weight": 1.0,
                "category": "diagnostico",
                "keywords": ["hemoperitônio", "líquido livre", "esplenorrenal", "baço", "trauma esplênico"]
            },
            {
                "id": "item_5",
                "title": "Protocolo de Transfusão Maciça Balanceada (1:1:1)",
                "description": "Aciona protocolo de transfusão maciça com proporção 1:1:1 (Concentrado de Hemácias, Plasma Fresco Congelado e Plaquetas) e restringe infusão excessiva de cristaloides.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["transfusão maciça", "1:1:1", "concentrado de hemácias", "plasma", "plaquetas"]
            },
            {
                "id": "item_6",
                "title": "Prescrição Imediata de Ácido Tranexâmico em < 3 Horas",
                "description": "Prescreve Ácido Tranexâmico 1g IV em bólus de 10 min seguido de 1g em 8 horas conforme protocolo CRASH-2 / ATLS.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["ácido tranexâmico", "transamin", "1g", "antifibrinolítico"]
            },
            {
                "id": "item_7",
                "title": "NÃO Solicitar Tomografia e Indicar Laparotomia Exploradora Imediata",
                "description": "Verbaliza enfaticamente: Paciente instável hemodinamicamente com FAST positivo NÃO pode ir à Tomografia! Encaminha imediatamente para Laparotomia Exploradora no Centro Cirúrgico.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["não fazer tc", "não levar para tomografia", "laparotomia", "centro cirúrgico", "cirurgia imediata"]
            }
        ],
        "critical_errors": [
            "Encaminhar paciente politraumatizado instável hemodinamicamente (PA 80x50) com FAST positivo para Tomografia Computadorizada (erro gravíssimo com óbito na sala de exame)",
            "Realizar ressuscitação agressiva com mais de 2 litros de cristaloide levando a coagulopatia dilucional e hipotermia grave"
        ]
    },
    {
        "code": "USP-RP-2024-PED-BVA",
        "title": "Bronquiolite Viral Aguda no HC-Criança FMRP-USP",
        "area": "Pediatria",
        "subtema": "Doenças Respiratórias Pediátricas",
        "institution": "USP-RP",
        "year": 2024,
        "difficulty": "medium",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: PRONTO-SOCORRO PEDIÁTRICO (HC-CRIANÇA FMRP-USP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico pediatra plantonista do HC-Criança da FMRP-USP (Ribeirão Preto).\n\n"
            "**Cenário**:\n"
            "- Paciente: Matheus, 4 meses (peso: 6.2 kg), acompanhado pela mãe.\n"
            "- Queixa: O bebê começou com coriza e febre baixa há 3 dias. Há 24 horas começou a tossir, ficar ofegante e cansadinho para mamar no peito.\n\n"
            "**Sua Tarefa**:\n"
            "1. Realize a anamnese e exame físico respiratório pediátrico.\n"
            "2. Estabeleça o diagnóstico com base na melhor evidência clínica.\n"
            "3. Prescreva o manejo terapêutico de suporte indicado pela Sociedade Brasileira de Pediatria e FMRP-USP.\n"
            "4. Decida a necessidade de exames complementares e local de internação/observação.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Mãe do Matheus (Dona Priscila)",
            "age": 28,
            "gender": "feminino",
            "chief_complaint": "Doutor, ele tá com o peitinho afundando quando respira e não consegue mamar sem cansar. Começou com um resfriadinho faz 3 dias e piorou muito hoje.",
            "past_medical_history": "Nascido a termo de parto normal, sem intercorrências neonatais. Em aleitamento materno exclusivo. Vacinas em dia.",
            "siblings": "Irmãozinho de 4 anos frequenta creche e estava gripado na semana passada."
        },
        "physical_exam": {
            "vitals": {
                "fc": "148 bpm",
                "fr": "62 irpm (Taquipneia)",
                "sato2": "88% em ar ambiente",
                "temp": "37.5 °C",
                "peso": "6.2 kg"
            },
            "findings": {
                "geral": "Lactente reativo, irritado durante o exame, afebril no momento, hidratado.",
                "respiratorio": "Presença de batimento de asa de nariz leve, tiragem subcostal e intercostal moderadas. Ausculta pulmonar com tempo expiratório prolongado, sibilos expiratórios bilaterais e estertores subcrepitantes difusos em ambas as bases.",
                "cardiovascular": "Ritmo cardíaco regular em 2 tempos, sem sopros, pulsos cheios.",
                "orofaringe_otoscopia": "Presença de secreção hialina abundante em fossas nasais, membranas timpânicas íntegras e translúcidas."
            }
        },
        "lab_imaging": {},
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Acolhimento da Mãe e Investigação de Fatores de Risco",
                "description": "Acolhe a mãe, confirma idade (4 meses), primeiro episódio de sibilância, ausência de prematuridade e contato com irmão resfriado.",
                "weight": 1.0,
                "category": "anamnese",
                "keywords": ["primeiro episódio", "idade", "prematuro", "amamentação", "creche"]
            },
            {
                "id": "item_2",
                "title": "Avaliação dos Sinais de Desconforto Respiratório e Hipoxemia",
                "description": "Verifica taquipneia (FR 62), tiragem subcostal, batimento de asa nasal e hipoxemia em ar ambiente (SatO2 88%).",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["tiragem", "taquipneia", "batimento de asa", "hipoxemia", "sat 88"]
            },
            {
                "id": "item_3",
                "title": "Diagnóstico Correto de Bronquiolite Viral Aguda (BVA)",
                "description": "Fecha o diagnóstico eminentemente clínico de BVA típica (provável VSR) em lactente jovem sem necessidade de radiografia de tórax de rotina.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["bronquiolite viral aguda", "bva", "vsr", "diagnóstico clínico"]
            },
            {
                "id": "item_4",
                "title": "Prescrição Imediata de Oxigenioterapia sob Cânula Nasal",
                "description": "Prescreve oxigênio suplementar em cânula nasal umidificada (0.5 a 1.0 L/min) com meta de manter SatO2 >= 90 a 92%.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["oxigênio", "cânula nasal", "cateter nasal", "meta 90%", "meta 92%"]
            },
            {
                "id": "item_5",
                "title": "Prescrição de Lavagem Nasal com Soro Fisiológico 0,9%",
                "description": "Prescreve desobstrução e lavagem nasal com Soro Fisiológico abundante antes das mamadas e sob demanda.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["lavagem nasal", "soro fisiológico", "desobstrução", "nariz"]
            },
            {
                "id": "item_6",
                "title": "Orientações Nutricionais e Fracionamento de Mamadas",
                "description": "Orienta manutenção do aleitamento materno com mamadas mais frequentes e volumes menores para evitar broncoaspiração.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["aleitamento", "leite materno", "fracionar mamadas", "hidratação"]
            },
            {
                "id": "item_7",
                "title": "NÃO Prescrever Corticoides, Broncodilatadores de Rotina ou Antibióticos",
                "description": "Adota a postura clássica da FMRP-USP de medicina baseada em evidências: contraindica corticoides (orais ou inalatórios), broncodilatadores e antibióticos na BVA típica.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["não prescrever corticoide", "não usar salbutamol", "sem antibiótico", "evidência"]
            }
        ],
        "critical_errors": [
            "Prescrever Corticosteroide sistêmico (Prednisolona/Dexametasona) para bronquiolite viral aguda típica (prática sem benefício e desaprovada pela FMRP-USP)",
            "Prescrever Antibióticos para lactente com quadro viral típico e sem foco bacteriano",
            "Dar alta para lactente de 4 meses com hipoxemia (SatO2 88%) e tiragem moderada"
        ]
    },
    {
        "code": "USP-RP-2023-GO-HPP",
        "title": "Hemorragia Pós-Parto por Atonia Uterina (Protocolo Mater)",
        "area": "Ginecologia e Obstetrícia",
        "subtema": "Hemorragias da Gestação e Puerpério",
        "institution": "USP-RP",
        "year": 2023,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: CENTRO OBSTÉTRICO / SALA DE PARTO (MATER FMRP-USP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico obstetra plantonista da Sala de Parto do Hospital Mater da FMRP-USP (Ribeirão Preto).\n\n"
            "**Cenário**:\n"
            "- Paciente: Ana Paula, 26 anos, secundigesta, submetida a parto vaginal há 30 minutos de concepto com peso de 4.150g.\n"
            "- A puérpera apresenta sangramento vaginal abundante contínuo com saída de coágulos volumosos.\n\n"
            "**Sua Tarefa**:\n"
            "1. Reconheça a Hemorragia Pós-Parto (HPP) e investigue a causa pelos '4 Ts'.\n"
            "2. Execute a manobra física imediata de controle do sangramento.\n"
            "3. Prescreva as medicações uterotônicas de 1ª e 2ª linhas com doses corretas.\n"
            "4. Indique as medidas mecânicas e cirúrgicas caso ocorra refratariedade.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Ana Paula (Puérpera)",
            "age": 26,
            "gender": "feminino",
            "chief_complaint": "Doutor, tô sentindo um calor descendo no meio das pernas... a cama tá encharcada de sangue... minha vista tá escurecendo...",
            "obstetric_history": "G2P2 (dois partos vaginais). Recém-nascido macrossômico (4.150g). Dequitação placentária completa ocorrida há 25 minutos."
        },
        "physical_exam": {
            "vitals": {
                "pa": "85x50 mmHg",
                "fc": "122 bpm",
                "fr": "22 irpm",
                "sato2": "97%"
            },
            "findings": {
                "geral": "Pálida 2+/4+, sudorética, taquicárdica, sonolenta.",
                "exame_abdominal": "Útero hipotônico, flácido, amolecido à palpação, localizado a cerca de 4 cm acima da cicatriz umbilical ('útero ensacado').",
                "exame_especular": "Exame com valvas afasta lacerações de trajeto (colo uterino e paredes vaginais íntegros, sem hematomas). Sangramento ativo volumoso exteriorizando-se pelo orifício cervical externo."
            }
        },
        "lab_imaging": {},
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Acionamento Imediato de Ajuda e Código Vermelho Obstétrico",
                "description": "Pede ajuda imediata da equipe de enfermagem e anestesia, solicita 2 acessos venosos calibrosos (jelco 14 ou 16) e monitorização contínua.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["código vermelho", "chamar ajuda", "equipe", "acesso calibroso", "dois acessos"]
            },
            {
                "id": "item_2",
                "title": "Diagnóstico Etiológico Baseado nos 4 Ts (Atonia Uterina)",
                "description": "Investiga os 4 Ts (Tônus, Trauma, Tecido, Trombina) e identifica a Atonia Uterina (tônus) como a causa do sangramento.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["4 ts", "atonia uterina", "tônus", "útero hipotônico", "útero amolecido"]
            },
            {
                "id": "item_3",
                "title": "Realização da Massagem Uterina Bimanual (Manobra de Hamilton)",
                "description": "Executa imediatamente a compressão bimanual do útero (uma mão com punho cerrado na vagina e a outra comprimindo o fundo uterino pelo abdome).",
                "weight": 2.0,
                "category": "exame_fisico",
                "keywords": ["hamilton", "massagem bimanual", "compressão bimanual", "massagem uterina"]
            },
            {
                "id": "item_4",
                "title": "Prescrição Imediata de Ocitocina IV (1ª Linha)",
                "description": "Prescreve Ocitocina IV imediata (5 UI em bólus lento ou 20 a 40 UI diluídas em 500 ml de SF 0,9% em infusão contínua rápida).",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["ocitocina", "uterotônico", "primeira linha", "bólus lento"]
            },
            {
                "id": "item_5",
                "title": "Prescrição de Ácido Tranexâmico em até 3 Horas",
                "description": "Prescreve Ácido Tranexâmico 1g IV em bólus de 10 minutos para reduzir mortalidade materna por sangramento obstétrico (WOMAN Trial).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["ácido tranexâmico", "transamin", "1g", "antifibrinolítico"]
            },
            {
                "id": "item_6",
                "title": "Uterotônicos de 2ª Linha e Sondagem Vesical de Alívio",
                "description": "Prescreve Misoprostol 800 mcg retal/sublingual (ou Metilergometrina 0.2 mg IM se não hipertensa) e realiza cateterismo vesical para esvaziar a bexiga.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["misoprostol", "metilergometrina", "ergotrate", "sondagem vesical", "bexiga"]
            },
            {
                "id": "item_7",
                "title": "Medidas Mecânicas e Cirúrgicas se Refratariedade (Balão de Bakri / B-Lynch)",
                "description": "Indica passagem de Balão de Tamponamento Intrauterino (Bakri) e preparo para laparotomia com sutura hemostática de B-Lynch ou histerectomia se falha.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["balão de bakri", "tamponamento", "b-lynch", "histerectomia", "centro cirúrgico"]
            }
        ],
        "critical_errors": [
            "Não realizar massagem bimanual (Hamilton) em vigência de atonia uterina com sangramento maciço",
            "Atrasar o início de uterotônicos venosos e ácido tranexâmico enquanto a paciente se mantém hipotensa"
        ]
    },
    {
        "code": "USP-RP-2024-PREV-MCCP",
        "title": "Consulta Centrada na Pessoa no CSE Sumarezinho FMRP-USP",
        "area": "Medicina Preventiva",
        "subtema": "Medicina de Família e Comunidade",
        "institution": "USP-RP",
        "year": 2024,
        "difficulty": "medium",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: ATENÇÃO PRIMÁRIA / CSE SUMAREZINHO (FMRP-USP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico residente de Medicina de Família e Comunidade do Centro de Saúde Escola Sumarezinho da FMRP-USP (Ribeirão Preto).\n\n"
            "**Cenário**:\n"
            "- Paciente: Dona Luzia, 52 anos, dona de casa, comparece à consulta com queixas inespecíficas de dor de cabeça, queimação no estômago e desânimo há 3 meses.\n"
            "- Já realizou diversos exames em prontos-atendimentos que vieram estritamente normais.\n\n"
            "**Sua Tarefa**:\n"
            "1. Conduza a consulta aplicando o Método Clínico Centrado na Pessoa (MCCP).\n"
            "2. Explore a experiência subjetiva da doença e os estressores psicossociais.\n"
            "3. Desenhe e utilize a ferramenta de abordagem familiar adequada (Genograma).\n"
            "4. Estabeleça um plano de cuidados conjunto com foco em prevenção quaternária.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Luzia Aparecida",
            "age": 52,
            "gender": "feminino",
            "chief_complaint": "Doutor, venho porque não aguento mais essa dor de cabeça e essa pontada no estômago. No pronto-socorro me deram remédio na veia e disseram que não é nada, mas eu sinto que tem algo ruim em mim.",
            "hidden_context": "O marido sofreu um AVC isquêmico há 4 meses e ficou acamado, usando fralda, sob cuidados exclusivos dela. O filho caçula de 22 anos perdeu o emprego e voltou a morar com ela, bebendo muito. Ela não dorme, não tem tempo para si e morre de medo de ter um AVC ou infarto e deixar o marido desamparado.",
            "expectations": "Gostaria de ser ouvida e entender o que está acontecendo com seu corpo sem ser dispensada com uma receita rápida."
        },
        "physical_exam": {
            "vitals": {
                "pa": "125x80 mmHg",
                "fc": "74 bpm",
                "fr": "16 irpm",
                "temp": "36.4 °C"
            },
            "findings": {
                "geral": "Fácies de cansaço extremo, postura encurvada, choro fácil durante a conversa, sem déficits neurológicos ou alterações orgânicas ao exame físico."
            }
        },
        "lab_imaging": {},
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Acolhimento Empático e Escuta Ativa sem Julgamentos",
                "description": "Recebe Dona Luzia com acolhimento, faz perguntas abertas e demonstra genuíno interesse por sua história de vida.",
                "weight": 1.5,
                "category": "relacao_medico_paciente",
                "keywords": ["acolhimento", "escuta ativa", "o que mais", "como tem sido", "estou aqui para ouvir"]
            },
            {
                "id": "item_2",
                "title": "Aplicação do MCCP: Explorando a Experiência da Doença (SIFE)",
                "description": "Explora Sentimentos (medo de adoecer), Ideias (o que acha que tem), Função (como afeta seu dia) e Expectativas (o que espera da consulta).",
                "weight": 2.0,
                "category": "anamnese",
                "keywords": ["mccp", "sentimentos", "ideias", "função", "expectativas", "o que a senhora acha"]
            },
            {
                "id": "item_3",
                "title": "Abordagem Familiar: Construção e Investigação do Genograma",
                "description": "Pergunta sobre a dinâmica familiar e identifica a sobrecarga de cuidadora do marido sequelado e o filho com etilismo.",
                "weight": 2.0,
                "category": "anamnese",
                "keywords": ["genograma", "família", "marido", "avc", "cuidadora", "filho", "sobrecarga"]
            },
            {
                "id": "item_4",
                "title": "Validação do Sofrimento e Explicação da Somatização",
                "description": "Valida que as dores que ela sente são reais e explica com sensibilidade como o estresse contínuo e a sobrecarga física/emocional repercutem no corpo.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["sua dor é real", "somatização", "sobrecarga de cuidados", "corpo e mente", "estresse"]
            },
            {
                "id": "item_5",
                "title": "Prevenção Quaternária: Não Solicitar Exames Desnecessários",
                "description": "Evita iatrogenia e cascata diagnóstica (não pede endoscopia ou tomografia desnecessárias, pois os exames recentes já descartaram doença orgânica).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["prevenção quaternária", "evitar exames", "não precisa de tomografia", "não precisa de endoscopia"]
            },
            {
                "id": "item_6",
                "title": "Pactuação de Projeto Terapêutico Singular (PTS) e Apoio Domiciliar",
                "description": "Aciona o Programa de Atenção Domiciliar (PAD) para o marido acamado, encaminha para apoio psicológico/grupo de cuidadores no CSE Sumarezinho e agenda retorno breve com a mesma equipe.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["pad", "melhor em casa", "atenção domiciliar", "retorno", "equipe multiprofissional", "cuidadores"]
            }
        ],
        "critical_errors": [
            "Desmerecer a queixa da paciente dizendo que 'é tudo psicológico' ou que 'ela não tem nada'",
            "Solicitar bateria excessiva de exames complementares invasivos reforçando a fixação somática (falha em prevenção quaternária)",
            "Prescrever polifarmácia sedativa (benzodiazepínicos) sem abordar a causa familiar da sobrecarga"
        ]
    },
    {
        "code": "UNICAMP-2024-CM-SCA",
        "title": "Infarto com Supra de ST (SCA Anterior Extensa)",
        "area": "Clínica Médica",
        "subtema": "Síndromes Coronarianas Agudas",
        "institution": "UNICAMP",
        "year": 2024,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: SALA VERMELHA / EMERGÊNCIA ADULTA\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico plantonista da Emergência do HC-UNICAMP.\n\n"
            "**Cenário**:\n"
            "- Paciente: Antônio Carlos, 58 anos, pedreiro.\n"
            "- Queixa: Dor precordial opressiva de forte intensidade iniciada há 45 minutos.\n\n"
            "**Sua Tarefa**:\n"
            "1. Realize a anamnese direcionada e exame físico pertinente.\n"
            "2. Solicite e interprete os exames complementares imediatos.\n"
            "3. Defina o diagnóstico sindrômico e topográfico.\n"
            "4. Estabeleça a conduta terapêutica imediata, prescrição de emergência e rota de reperfusão.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Antônio Carlos",
            "age": 58,
            "gender": "masculino",
            "chief_complaint": "Doutor, parece que tem um elefante pisando no meu peito! Começou faz uns 45 minutos enquanto eu tava trabalhando.",
            "pain_characteristics": "Dor em aperto, peso e queimação retroesternal, intensidade 9/10, irradiando para o braço esquerdo e mandíbula.",
            "associated_symptoms": "Tô suando frio, nauseado e com falta de ar.",
            "past_medical_history": "Fumo há 30 anos (1 maço por dia). Minha pressão às vezes dava alta, mas nunca tomei remédio contínuo.",
            "allergies": "Não tenho nenhuma alergia conhecida.",
            "sildenafil_use": "Não usei remédio pra ereção, doutor."
        },
        "physical_exam": {
            "vitals": {
                "pa": "140x90 mmHg",
                "fc": "92 bpm",
                "fr": "20 irpm",
                "sato2": "96% em ar ambiente",
                "temp": "36.4 °C",
                "hgt": "126 mg/dL"
            },
            "findings": {
                "geral": "Paciente em decúbito elevado, sudorético, fácies de dor, ansioso, acianótico, anictérico.",
                "cardiovascular": "Ritmo cardíaco regular em 2 tempos, bulhas normais, sem sopros audíveis ou B3/B4. Pulsos periféricos simétricos e cheios.",
                "respiratorio": "Murmúrio vesicular universalmente audível, sem ruídos adventícios (Killip I).",
                "abdome": "Abdome plano, flácido, indolor à palpação, sem visceromegalias.",
                "membros": "Membros sem edemas ou sinais de trombose venosa profunda."
            },
            "auscultation_audio": {
                "cardiac": "bulhas_normais",
                "pulmonary": "murmurio_limpo"
            }
        },
        "lab_imaging": {
            "ecg": {
                "title": "Eletrocardiograma de 12 derivações",
                "available": True,
                "result_text": "Ritmo sinusal regular, FC 92 bpm, eixo normal. Supradesnivelamento do segmento ST de 4 mm nas derivações V1 a V4 (parede anterior extensa), sem alterações em derivações direitas (V3R/V4R) ou posteriores.",
                "image_url": "/images/osce/ecg_supra_anterior.png"
            },
            "rx_torax": {
                "title": "Radiografia de Tórax no Leito",
                "available": True,
                "result_text": "Área cardíaca normal, parênquima pulmonar sem consolidações ou sinais de congestão vascular, cúpulas diafragmáticas livres."
            },
            "troponina": {
                "title": "Marcadores de Necrose Miocárdica (Troponina I)",
                "available": True,
                "result_text": "Amostra enviada ao laboratório (resultado em 45 minutos). Nota da banca: Em IAM com supra de ST, a terapia de reperfusão NÃO deve aguardar o resultado de biomarcadores."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Apresentação e Relação Médico-Paciente",
                "description": "Cumprimenta o paciente, se apresenta pelo nome e demonstra empatia com o sofrimento.",
                "weight": 0.5,
                "category": "relacao_medico_paciente",
                "keywords": ["olá", "bom dia", "boa tarde", "me chamo", "sou o médico", "vou cuidar de você"]
            },
            {
                "id": "item_2",
                "title": "Caracterização Completa da Dor Precordial",
                "description": "Investiga início, irradiação (braço/mandíbula), intensidade (0-10) e sintomas associados (sudorese, náuseas).",
                "weight": 1.0,
                "category": "anamnese",
                "keywords": ["quando começou", "irradia", "braço", "mandíbula", "pescoço", "falta de ar", "sudorese", "náusea"]
            },
            {
                "id": "item_3",
                "title": "Fatores de Risco Cardiovasculares e Medicamentos",
                "description": "Pergunta sobre tabagismo, hipertensão, diabetes, histórico familiar e uso de inibidores de fosfodiesterase (sildenafila).",
                "weight": 0.5,
                "category": "anamnese",
                "keywords": ["fuma", "tabagismo", "pressão alta", "diabetes", "remédio", "sildenafila", "viagra"]
            },
            {
                "id": "item_4",
                "title": "Medidas Iniciais de Emergência",
                "description": "Solicita monitorização cardíaca contínua, oximetria de pulso e 2 acessos venosos periféricos calibrosos.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["monitor", "monitorização", "oximetria", "acesso venoso", "acesso periférico"]
            },
            {
                "id": "item_5",
                "title": "Solicitação Imediata de ECG em < 10 Minutos",
                "description": "Solicita ECG de 12 derivações em até 10 minutos da admissão hospitalar (meta porta-eletro).",
                "weight": 1.5,
                "category": "exames_complementares",
                "keywords": ["ecg", "eletrocardiograma", "12 derivações", "porta-eletro"]
            },
            {
                "id": "item_6",
                "title": "Interpretação e Diagnóstico Correto de IAM com Supra",
                "description": "Identifica supradesnivelamento de ST em parede anterior (V1-V4) e verbaliza o diagnóstico sindrômico/topográfico.",
                "weight": 1.0,
                "category": "diagnostico",
                "keywords": ["supra", "supradesnivelamento", "st", "anterior", "iam", "infarto"]
            },
            {
                "id": "item_7",
                "title": "Dupla Antiagregação Plaquetária Imediata",
                "description": "Prescreve AAS (200-300 mg mastigável) + Inibidor de P2Y12 (Ticagrelor 180 mg ou Clopidogrel 300-600 mg).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["aas", "aspirina", "ticagrelor", "clopidogrel", "mastigar", "dose de ataque"]
            },
            {
                "id": "item_8",
                "title": "Anticoagulação Plena e Estratificação",
                "description": "Prescreve Enoxaparina (ou Heparina Não Fracionada) e estratifica Killip I (sem necessidade de O2 suplementar rotineiro).",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["enoxaparina", "heparina", "anticoagulação", "clexane"]
            },
            {
                "id": "item_9",
                "title": "Indicação Rápida de Reperfusão Coronariana (Angioplastia Primária)",
                "description": "Aciona o laboratório de hemodinâmica para angioplastia primária em tempo porta-balão < 90 min (ou trombólise se porta-balão > 120 min).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["angioplastia", "cateterismo", "hemodinâmica", "porta-balão", "reperfusão"]
            },
            {
                "id": "item_10",
                "title": "Comunicação Clara do Plano ao Paciente",
                "description": "Explica o diagnóstico de infarto e a necessidade de desobstruir a artéria de forma calma e humanizada.",
                "weight": 0.5,
                "category": "relacao_medico_paciente",
                "keywords": ["infarto", "artéria", "coração", "desobstruir", "cateterismo", "procedimento"]
            }
        ],
        "critical_errors": [
            "Aguardar resultado de troponina para decidir conduta de reperfusão em IAM com supra de ST",
            "Prescrever nitrato para paciente sem checar uso prévio de sildenafila ou na suspeita de infarto de ventrículo direito",
            "Prescrever oxigenioterapia de rotina para paciente com SatO2 de 96% em ar ambiente"
        ]
    },
    {
        "code": "UNICAMP-2023-CG-PERF",
        "title": "Abdome Agudo Perfurativo (Úlcera Péptica)",
        "area": "Cirurgia Geral",
        "subtema": "Abdome Agudo",
        "institution": "UNICAMP",
        "year": 2023,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: PRONTO-SOCORRO DE CIRURGIA GERAL\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico plantonista da Cirurgia Geral do HC-UNICAMP.\n\n"
            "**Cenário**:\n"
            "- Paciente: Márcia Regina, 42 anos, balconista.\n"
            "- Queixa: Dor súbita e excruciante no estômago há 2 horas que se espalhou por toda a barriga.\n\n"
            "**Sua Tarefa**:\n"
            "1. Realize anamnese direcionada e exame físico abdominal completo.\n"
            "2. Solicite e interprete os exames de imagem pertinentes.\n"
            "3. Estabeleça o diagnóstico sindrômico e etiológico provável.\n"
            "4. Indique as medidas de suporte imediato e a conduta cirúrgica definitiva.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Márcia Regina",
            "age": 42,
            "gender": "feminino",
            "chief_complaint": "Doutor, foi de repente! Uma dor insuportável no estômago, parecia uma facada! Agora a barriga inteira tá dura e dói até pra respirar.",
            "pain_characteristics": "Dor súbita em pontada/facada, intensidade 10/10, iniciada no epigástrio e difusa por todo o abdome.",
            "associated_symptoms": "Náuseas intensas, sudorese, febre não aferida.",
            "past_medical_history": "Uso crônico de Diclofenaco e Ibuprofeno para dores na coluna há 6 meses por conta própria.",
            "allergies": "Nenhuma alergia relatada."
        },
        "physical_exam": {
            "vitals": {
                "pa": "100x60 mmHg",
                "fc": "118 bpm",
                "fr": "24 irpm",
                "sato2": "97% em ar ambiente",
                "temp": "37.8 °C",
                "hgt": "110 mg/dL"
            },
            "findings": {
                "geral": "Posição antálgica imóvel no leito, fácies de sofrimento agudo, sudorese fria, taquicárdica e taquipneica.",
                "cardiovascular": "Taquicardia sinusal, sem sopros audíveis.",
                "respiratorio": "Respiração superficial e rápida, movimentos respiratórios limitados pela dor abdominal.",
                "abdome": "Abdome tenso, com defesa involuntária difusa ('abdome em tábua'). Descompressão brusca difusamente positiva (sinal de Blumberg generalizado). Perda da macicez hepática à percussão (Sinal de Jobert presente). Ruídos hidroaéreos abolidos.",
                "toque_retal": "Sem massas palpáveis, fundo de saco de Douglas doloroso."
            },
            "auscultation_audio": {
                "cardiac": "taquicardia_sinusal",
                "pulmonary": "murmurio_limpo"
            }
        },
        "lab_imaging": {
            "rx_torax": {
                "title": "Radiografia de Tórax em PA (em cúpulas)",
                "available": True,
                "result_text": "Presença de ar livre subdiafragmático bilateral evidente sob as cúpulas (pneumoperitônio maciço), sem derrame pleural.",
                "image_url": "/images/osce/rx_pneumoperitonio.png"
            },
            "hemograma": {
                "title": "Hemograma e Bioquímica",
                "available": True,
                "result_text": "Leucócitos: 16.800/mm³ com 10% de bastões. PCR: 145 mg/L. Creatinina: 1,1 mg/dL. Lactato: 2,2 mmol/L."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Apresentação e Relação Médico-Paciente",
                "description": "Apresenta-se à paciente com respeito e tranquilidade em momento de dor aguda intensa.",
                "weight": 0.5,
                "category": "relacao_medico_paciente",
                "keywords": ["olá", "me chamo", "sou médico", "estamos cuidando"]
            },
            {
                "id": "item_2",
                "title": "História de Uso Crônico de AINEs e Sintomas Pépticos",
                "description": "Investiga dor em facada súbita e pergunta ativamente sobre uso de anti-inflamatórios e histórico de queimação prévia.",
                "weight": 1.0,
                "category": "anamnese",
                "keywords": ["anti-inflamatório", "remédio para dor", "ibuprofeno", "diclofenaco", "úlcera", "queimação"]
            },
            {
                "id": "item_3",
                "title": "Exame Físico Abdominal Metódico",
                "description": "Verifica inspeção, palpação com defesa involuntária (abdome em tábua), descompressão brusca e percussão hepática (Jobert).",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["abdome em tábua", "defesa", "blumberg", "jobert", "macicez hepática", "descompressão"]
            },
            {
                "id": "item_4",
                "title": "Solicitação Correta de Radiografia em Cúpulas Diafragmáticas",
                "description": "Solicita radiografia de tórax em cúpulas diafragmáticas em pé (ou decúbito com raios horizontais / Hjelm-Laurell se imóvel).",
                "weight": 1.5,
                "category": "exames_complementares",
                "keywords": ["rx", "radiografia", "cúpulas", "tórax em pé", "laurell"]
            },
            {
                "id": "item_5",
                "title": "Identificação e Verbalização de Pneumoperitônio",
                "description": "Reconhece o ar subdiafragmático no RX e fecha o diagnóstico de abdome agudo perfurativo por úlcera péptica.",
                "weight": 1.0,
                "category": "diagnostico",
                "keywords": ["pneumoperitônio", "ar livre", "perfurativo", "úlcera perfurada"]
            },
            {
                "id": "item_6",
                "title": "Medidas Imediatas de Suporte Clínico",
                "description": "Prescreve jejum absoluto imediato, sonda nasogástrica (SNG) aberta e hidratação venosa rápida com cristaloide.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["jejum", "sonda nasogástrica", "sng", "hidratação", "soro", "cristaloide", "ringer"]
            },
            {
                "id": "item_7",
                "title": "Antibioticoterapia de Amplo Espectro e Analgesia",
                "description": "Prescreve antibioticoterapia cobrindo gram-negativos e anaeróbios (ex: Ceftriaxona + Metronidazol ou Pip-Tazo) e analgesia venosa.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["antibiótico", "ceftriaxona", "metronidazol", "piperacilina", "analgesia"]
            },
            {
                "id": "item_8",
                "title": "Indicação Cirúrgica de Urgência",
                "description": "Indica laparotomia ou laparoscopia exploradora imediata para fechamento da perfuração e lavagem da cavidade peritoneal.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["cirurgia", "laparotomia", "laparoscopia", "centro cirúrgico", "urgência"]
            },
            {
                "id": "item_9",
                "title": "Explicação e Termo de Consentimento à Paciente",
                "description": "Comunica a necessidade de cirurgia de urgência de forma clara à paciente e solicita reserva de concentrado e vaga de UTI.",
                "weight": 0.5,
                "category": "relacao_medico_paciente",
                "keywords": ["cirurgia", "operar", "consentimento", "explicar", "família"]
            }
        ],
        "critical_errors": [
            "Não indicar cirurgia imediata em presença de pneumoperitônio e peritonite difusa",
            "Solicitar endoscopia digestiva alta (EDA) na suspeita aguda de víscera oca perfurada (contraindicação formal absoluta)"
        ]
    },
    {
        "code": "UNICAMP-2024-PED-ANAF",
        "title": "Anafilaxia Grave em Lactente",
        "area": "Pediatria",
        "subtema": "Emergências Pediátricas",
        "institution": "UNICAMP",
        "year": 2024,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: EMERGÊNCIA PEDIÁTRICA\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico de plantão na Sala de Urgência Pediátrica do Hospital de Clínicas da UNICAMP.\n\n"
            "**Cenário**:\n"
            "- Paciente: Lucas, 3 anos (peso estimado: 15 kg), trazido nos braços da mãe aos prantos.\n"
            "- Queixa: O menino comeu pasta de amendoim há 20 minutos e começou a vomitar, empolar o corpo inteiro e ficar roxo para respirar.\n\n"
            "**Sua Tarefa**:\n"
            "1. Execute a avaliação rápida da criança pela abordagem ABCDE.\n"
            "2. Reconheça a gravidade e estabeleça o diagnóstico sindrômico.\n"
            "3. Prescreva a medicação de primeira linha salvadora de vida com dose e via corretas.\n"
            "4. Estabeleça as condutas secundárias e orientação à mãe.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Mãe do Lucas (Dona Carla)",
            "age": 29,
            "gender": "feminino",
            "chief_complaint": "Doutor, salva meu filho! Ele comeu um biscoito com amendoim na pracinha e começou a vomitar e tossir com um barulho estranho no pescoço! O rostinho dele tá todo inchado!",
            "lucas_signs": "Choro fraco e rouco, estridor inspiratório audível, placas de urticária pruriginosas avermelhadas confluentes em tronco e face.",
            "past_medical_history": "Lucas não tem doenças prévias conhecidas. Nunca tinha comido amendoim antes.",
            "allergies": "Nenhuma alergia alimentar previamente documentada."
        },
        "physical_exam": {
            "vitals": {
                "pa": "78x45 mmHg",
                "fc": "165 bpm",
                "fr": "48 irpm",
                "sato2": "89% em ar ambiente",
                "temp": "36.8 °C",
                "peso": "15 kg"
            },
            "findings": {
                "via_aerea": "Edema de lábios e pálpebras, rouquidão intensa e estridor inspiratório marcante.",
                "respiratorio": "Tiragem intercostal e de fúrcula moderada a grave. Ausculta pulmonar com sibilos inspiratórios e expiratórios difusos.",
                "cardiovascular": "Taquicardia acentuada, pulsos radiais finos, tempo de enchimento capilar de 4 segundos.",
                "pele": "Placas eritematosas, elevadas e pruriginosas (urticária) disseminadas por todo o corpo e angioedema facial."
            },
            "auscultation_audio": {
                "cardiac": "taquicardia_sinusal",
                "pulmonary": "estridor_e_sibilos"
            }
        },
        "lab_imaging": {},
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Acolhimento da Mãe e Avaliação Rápida ABCDE",
                "description": "Acolhe a mãe em desespero e inicia imediatamente a avaliação sistemática do triângulo pediátrico e ABCDE.",
                "weight": 1.0,
                "category": "anamnese",
                "keywords": ["calma", "vamos ajudar", "abcde", "via aérea", "respiração", "circulação"]
            },
            {
                "id": "item_2",
                "title": "Identificação Imediata de Anafilaxia Grave",
                "description": "Reconhece o envolvimento multissistêmico agudo (pele + via aérea/respiratório + hemodinâmico) como anafilaxia grave.",
                "weight": 1.0,
                "category": "diagnostico",
                "keywords": ["anafilaxia", "choque anafilático", "estridor", "insuficiência respiratória"]
            },
            {
                "id": "item_3",
                "title": "Prescrição Imediata de Adrenalina IM (1ª Linha)",
                "description": "Prescreve Adrenalina 1:1000 sem diluição na dose de 0,01 mg/kg (0,15 ml para 15 kg) por via Intramuscular (IM) na face anterolateral da coxa.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["adrenalina", "epinefrina", "intramuscular", "im", "coxa", "0,15", "vasto lateral"]
            },
            {
                "id": "item_4",
                "title": "Oxigenioterapia de Alto Fluxo e Posicionamento",
                "description": "Aplica oxigênio sob máscara com reservatório a 10-15 L/min e mantém a criança deitada com membros inferiores elevados.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["oxigênio", "máscara", "reservatório", "deitar", "elevar pernas"]
            },
            {
                "id": "item_5",
                "title": "Acesso Venoso e Ressuscitação Volêmica",
                "description": "Obtém acesso venoso (ou intraósseo se falha) e prescreve expansão rápida com Soro Fisiológico a 20 ml/kg em bólus.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["acesso venoso", "intraósseo", "soro fisiológico", "20 ml/kg", "expansão"]
            },
            {
                "id": "item_6",
                "title": "Medicamentos Coadjuvantes de 2ª Linha",
                "description": "Prescreve corticoide sistêmico (Metilprednisolona/Hidrocortisona) e anti-histamínico IV, ressaltando que são coadjuvantes pós-adrenalina.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["corticoide", "hidrocortisona", "anti-histamínico", "difenidramina", "segunda linha"]
            },
            {
                "id": "item_7",
                "title": "Orientação de Observação e Prescrição de Autoinjetor",
                "description": "Informa a necessidade de monitorização por pelo menos 6-12 horas pelo risco de reação bifásica e orienta caneta autoinjetora de adrenalina.",
                "weight": 1.5,
                "category": "relacao_medico_paciente",
                "keywords": ["reação bifásica", "observação", "autoinjetor", "caneta", "alergista"]
            }
        ],
        "critical_errors": [
            "Prescrever corticoide ou anti-histamínico antes ou em substituição à adrenalina intramuscular",
            "Administrar adrenalina por via subcutânea (SC) ou tentar infusão intravenosa pura sem parada cardíaca"
        ]
    },
    {
        "code": "UNIFESP-2024-GO-PREECL",
        "title": "Pré-Eclâmpsia Grave & Iminência de Eclâmpsia",
        "area": "Ginecologia e Obstetrícia",
        "subtema": "Hipertensão na Gestação",
        "institution": "UNIFESP",
        "year": 2024,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: PRONTO-SOCORRO OBSTÉTRICO\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico plantonista da Maternidade do Hospital São Paulo (UNIFESP).\n\n"
            "**Cenário**:\n"
            "- Paciente: Fernanda de Sousa, 27 anos, primigesta com 34 semanas de gestação.\n"
            "- Queixa: Cefaleia frontal latejante intensa que não melhorou com dipirona, dor na boca do estômago e visão embaçada com pontinhos brilhantes.\n\n"
            "**Sua Tarefa**:\n"
            "1. Realize a anamnese e o exame clínico-obstétrico imediato.\n"
            "2. Reconheça a síndrome hipertensiva e os sinais de gravidade / iminência.\n"
            "3. Prescreva o esquema de profilaxia de convulsões (sulfatação de magnésio) com doses de ataque e manutenção.\n"
            "4. Indique o manejo pressórico e os parâmetros de vigilância clínica.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Fernanda de Sousa",
            "age": 27,
            "gender": "feminino",
            "chief_complaint": "Doutor, minha cabeça tá explodindo! Começou ontem à noite e agora tô enxergando uns pontinhos piscando na minha frente e com uma queimação forte no estômago.",
            "associated_symptoms": "Dor epigástrica em barra, náuseas, inchaço rápido nas mãos e rosto.",
            "gestational_age": "34 semanas confirmadas por ultrassom de primeiro trimestre.",
            "past_history": "Pré-natal habitual sem queixas até a semana passada. Nenhuma doença crônica prévia.",
            "allergies": "Nenhuma alergia."
        },
        "physical_exam": {
            "vitals": {
                "pa": "175x115 mmHg",
                "fc": "88 bpm",
                "fr": "18 irpm",
                "sato2": "98%",
                "temp": "36.6 °C"
            },
            "findings": {
                "neurologico": "Consciente, orientada, queixando-se de escotomas visuais cintilantes. Reflexo patelar hiperativo (clônus esgotável de 3 batimentos).",
                "obstetrico": "Altura uterina: 32 cm. Batimentos Cardiofetais (BCF): 142 bpm regulares. Tônus uterino normal, ausência de dinâmica de trabalho de parto.",
                "especular_toque": "Colo grosso, posterior e fechado, sem perdas líquidas ou sangramento vaginal.",
                "edema": "Edema em membros inferiores 3+/4+ e edema facial visível."
            },
            "auscultation_audio": {
                "cardiac": "bulhas_normais",
                "bcf": "bcf_normal_140"
            }
        },
        "lab_imaging": {
            "laboratorio_urgencia": {
                "title": "Painel Laboratorial de Pré-Eclâmpsia",
                "available": True,
                "result_text": "Plaquetas: 135.000/mm³. TGO: 68 U/L, TGP: 72 U/L. Creatinina: 1,0 mg/dL. Ácido úrico: 6,8 mg/dL. Fita urinária: Proteinúria 3+."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Acolhimento e Aferição Adequada da Pressão Arterial",
                "description": "Acolhe a gestante, confirma a PA em decúbito lateral esquerdo ou sentada com manguito adequado.",
                "weight": 0.5,
                "category": "relacao_medico_paciente",
                "keywords": ["acolhimento", "pressão arterial", "pa", "decúbito lateral"]
            },
            {
                "id": "item_2",
                "title": "Identificação dos Sinais Premonitórios de Eclâmpsia",
                "description": "Identifica a tríade de cefaleia refratária + escotomas visuais + epigastralgia em barra associada à hiperreflexia.",
                "weight": 1.5,
                "category": "anamnese",
                "keywords": ["cefaleia", "escotomas", "epigastralgia", "iminência de eclâmpsia", "hiperreflexia"]
            },
            {
                "id": "item_3",
                "title": "Avaliação da Vitalidade Fetal e Exame Obstétrico",
                "description": "Realiza ausculta do BCF (142 bpm) e palpação obstétrica para avaliar tônus e contrações uterinas.",
                "weight": 1.0,
                "category": "exame_fisico",
                "keywords": ["bcf", "batimentos fetais", "altura uterina", "tônus"]
            },
            {
                "id": "item_4",
                "title": "Prescrição Imediata do Esquema de Sulfato de Magnésio",
                "description": "Prescreve Sulfato de Magnésio pelo esquema Zuspan (ataque 4g IV em 15-20 min + manutenção 1-2g/h em BIC contínua) ou Pritchard.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["sulfato de magnésio", "zuspan", "ataque 4g", "manutenção", "anticonvulsivante"]
            },
            {
                "id": "item_5",
                "title": "Prescrição de Anti-Hipertensivo de Ação Rápida",
                "description": "Prescreve Hidralazina IV (5 mg a cada 20 min) ou Nifedipino oral para PAD >= 110 mmHg, com meta de PAD entre 90 e 100 mmHg.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["hidralazina", "nifedipino", "anti-hipertensivo", "pressão"]
            },
            {
                "id": "item_6",
                "title": "Vigilância de Intoxicação por Magnésio e Antídoto Beira-Leito",
                "description": "Orienta monitorização de reflexo patelar, diurese horária (>25 ml/h) e FR (>16 irpm), deixando Gluconato de Cálcio 10% beira-leito.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["gluconato de cálcio", "reflexo patelar", "diurese", "frequência respiratória", "intoxicação"]
            },
            {
                "id": "item_7",
                "title": "Planejamento e Corticoterapia para Maturidade Pulmonar",
                "description": "Prescreve corticoterapia para maturação pulmonar fetal (Betametasona 12 mg IM) por se tratar de gestação de 34 semanas.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["betametasona", "corticoide", "maturação pulmonar", "parto"]
            },
            {
                "id": "item_8",
                "title": "Comunicação Empática do Risco e Internação em UTI/UCO",
                "description": "Informa a paciente e família sobre a necessidade de internação em unidade de terapia intensiva / cuidados obstétricos.",
                "weight": 0.5,
                "category": "relacao_medico_paciente",
                "keywords": ["internação", "uti", "segurança", "bebê", "explicar"]
            }
        ],
        "critical_errors": [
            "Não prescrever sulfato de magnésio em paciente com iminência de eclâmpsia",
            "Prescrever Diazepam ou Fenitoína para profilaxia de convulsões em pré-eclâmpsia (sulfato de magnésio é a droga de escolha exclusiva)",
            "Reduzir abruptamente a PA sistólica para valores < 120 mmHg com risco de sofrimento fetal agudo"
        ]
    },
    {
        "code": "UNIFESP-2023-PREV-SPIKES",
        "title": "Comunicação de Más Notícias (Protocolo SPIKES)",
        "area": "Medicina Preventiva",
        "subtema": "Relação Médico-Paciente e Ética",
        "institution": "UNIFESP",
        "year": 2023,
        "difficulty": "medium",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: CONSULTÓRIO DA ATENÇÃO PRIMÁRIA / UBS\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico de família da UBS Vila Mariana (UNIFESP).\n\n"
            "**Cenário**:\n"
            "- Paciente: Seu Valdir de Oliveira, 54 anos, caminhoneiro aposentado, desacompanhado.\n"
            "- Motivo da consulta: Retorna para conferir o laudo da biópsia gástrica realizada na semana anterior por queixa de perda ponderal e dor de estômago.\n"
            "- Resultado do laudo no prontuário: 'Adenocarcinoma gástrico tubular invasivo moderadamente diferenciado'.\n\n"
            "**Sua Tarefa**:\n"
            "1. Conduza a consulta utilizando as etapas do Protocolo SPIKES.\n"
            "2. Transmita o resultado do laudo de forma ética, clara e sem jargões herméticos.\n"
            "3. Acolha as manifestações emocionais do paciente.\n"
            "4. Estabeleça os próximos passos da linha de cuidado oncológico compartilhado.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Valdir de Oliveira",
            "age": 54,
            "gender": "masculino",
            "chief_complaint": "Doutor, vim pegar o resultado daquele exame que fiz da garganta pro estômago. Tomara que seja só uma gastrite boba, né?",
            "perception": "Acho que não deve ser nada demais, doutor... Só que perdi uns 6 quilos no último mês e a comida às vezes entala.",
            "emotional_state": "Inicialmente tenta demonstrar tranquilidade, mas fica muito angustiado e emudece quando ouve a palavra tumor/câncer, com olhos marejados.",
            "social_history": "Mora com a esposa e uma filha de 18 anos. É muito ligado à família."
        },
        "physical_exam": {
            "vitals": {
                "pa": "130x85 mmHg",
                "fc": "76 bpm",
                "fr": "16 irpm",
                "temp": "36.5 °C"
            },
            "findings": {
                "geral": "Paciente lúcido, corado, emagrecido, aparentando ansiedade contida.",
                "exame_fisico": "Sem linfonodomegalias palpáveis em fossas supraclaviculares (ausência de nódulo de Virchow) ou periumbilicais (sem nódulo da Irmã Maria José)."
            }
        },
        "lab_imaging": {
            "biopsia": {
                "title": "Laudo Anatomopatológico de Biópsia Gástrica",
                "available": True,
                "result_text": "Fragmentos de mucosa gástrica exibindo Adenocarcinoma Tubular Invasivo, moderadamente diferenciado. Pesquisa de Helicobacter pylori positiva."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "S - Setting (Preparação do Ambiente e Conexão Inicial)",
                "description": "Garante ambiente privativo, senta-se próximo, faz contato visual, desliga distrações e pergunta se o paciente gostaria da presença de acompanhante.",
                "weight": 1.5,
                "category": "relacao_medico_paciente",
                "keywords": ["privacidade", "acompanhante", "esposa", "confortável", "sentar"]
            },
            {
                "id": "item_2",
                "title": "P - Perception (Exploração da Percepção do Paciente)",
                "description": "Pergunta o que o paciente já sabe sobre o quadro, o que ele entende sobre a investigação e como tem se sentido.",
                "weight": 1.5,
                "category": "anamnese",
                "keywords": ["o que o senhor sabe", "o que imagina", "percepção", "o que disseram"]
            },
            {
                "id": "item_3",
                "title": "I - Invitation (Convite e Consentimento para Informações)",
                "description": "Pergunta até onde o paciente gostaria de saber os detalhes do resultado e como prefere receber a notícia.",
                "weight": 1.5,
                "category": "relacao_medico_paciente",
                "keywords": ["gostaria de saber", "detalhes", "como prefere", "informações"]
            },
            {
                "id": "item_4",
                "title": "K - Knowledge (Aviso Prévio e Transmissão em Linguagem Clara)",
                "description": "Utiliza frase de aviso prévio ('Infelizmente não trago boas notícias...'), comunica o tumor em termos acessíveis e faz pausas reflexivas.",
                "weight": 2.0,
                "category": "diagnostico",
                "keywords": ["aviso prévio", "infelizmente", "más notícias", "tumor", "câncer", "linguagem simples"]
            },
            {
                "id": "item_5",
                "title": "E - Empathy (Acolhimento Empático e Validação de Sentimentos)",
                "description": "Respeita o silêncio, oferece suporte humano, valida as emoções ('Compreendo o seu medo, é natural se sentir assim').",
                "weight": 2.0,
                "category": "relacao_medico_paciente",
                "keywords": ["compreendo", "estamos juntos", "é natural sentir medo", "silêncio", "acolher", "apoio"]
            },
            {
                "id": "item_6",
                "title": "S - Strategy (Pactuação de Estratégia e Continuidade)",
                "description": "Apresenta o plano de estadiamento e encaminhamento para a equipe de oncologia/cirurgia com garantia de não abandono.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["encaminhamento", "oncologia", "estadiamento", "não vamos te abandonar", "próxima consulta"]
            }
        ],
        "critical_errors": [
            "Dar a notícia de câncer de forma fria, abrupta ou em pé sem aviso prévio",
            "Usar jargões incompreensíveis ('adenocarcinoma invasivo moderadamente diferenciado') sem traduzir ao paciente",
            "Dizer 'não há nada a fazer' ou transferir o paciente abandonando o vínculo da atenção primária"
        ]
    },
    {
        "code": "UNIFESP-2024-CM-TV",
        "title": "Taquicardia Ventricular Monomórfica Instável",
        "area": "Clínica Médica",
        "subtema": "Arritmias Cardíacas",
        "institution": "UNIFESP",
        "year": 2024,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: SALA DE EMERGÊNCIA / CARDIOLOGIA\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico plantonista da Emergência do Hospital São Paulo (UNIFESP).\n\n"
            "**Cenário**:\n"
            "- Paciente: Dona Sebastiana, 62 anos, com palpitações cardíacas súbitas, sensação de desmaio iminente e mal-estar.\n\n"
            "**Sua Tarefa**:\n"
            "1. Avalie rapidamente os sinais de estabilidade hemodinâmica.\n"
            "2. Solicite e interprete o traçado eletrocardiográfico/monitorização.\n"
            "3. Execute a conduta terapêutica de urgência padronizada pelo ACLS.\n"
            "4. Indique as medidas de segurança e analgesia/sedação pré-procedimento.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Sebastiana dos Santos",
            "age": 62,
            "gender": "feminino",
            "chief_complaint": "Ai doutor... meu coração tá pulando fora do peito... a vista tá escurecendo... vou apagar...",
            "past_history": "Infartou há 4 anos, tem insuficiência cardíaca crônica."
        },
        "physical_exam": {
            "vitals": {
                "pa": "75x45 mmHg",
                "fc": "180 bpm",
                "fr": "26 irpm",
                "sato2": "91% em ar ambiente"
            },
            "findings": {
                "geral": "Sonolenta, má perfusão periférica, tempo de enchimento capilar de 4 segundos, sudorese profusa e pele fria.",
                "cardiovascular": "Ritmo cardíaco taquicárdico com pulsos centrais presentes porém finos e filiformes.",
                "respiratorio": "Estertores crepitantes em terço inferior de ambos os hemitórax."
            }
        },
        "lab_imaging": {
            "ecg": {
                "title": "Monitor Cardíaco e ECG de Ritmo",
                "available": True,
                "result_text": "Taquicardia de QRS largo regular (> 120 ms) com frequência de 180 bpm, concordância positiva precordial e dissociação atrioventricular (Taquicardia Ventricular Monomórfica Sustentada).",
                "image_url": "/images/osce/ecg_tv_monomorfica.png"
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Reconhecimento dos 4 Sinais de Instabilidade do ACLS",
                "description": "Identifica a hipotensão arterial severa (PA 75x45), alteração do nível de consciência e congestão pulmonar.",
                "weight": 2.0,
                "category": "diagnostico",
                "keywords": ["hipotensão", "instabilidade", "choque", "congestão", "rebaixamento"]
            },
            {
                "id": "item_2",
                "title": "Solicitação do Cardioversor / Desfibrilador Manual",
                "description": "Pede imediatamente o carrinho de parada com desfibrilador manual e pás adesivas no tórax.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["desfibrilador", "cardioversor", "carrinho de parada", "pás"]
            },
            {
                "id": "item_3",
                "title": "Modo SINCRONIZADO Obrigatório",
                "description": "Ativa o botão de SINCRONIZAÇÃO no monitor para evitar o fenômeno R sobre T e fibrilação ventricular iatrogênica.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["sincronizar", "sincronizado", "sincronização", "onda r"]
            },
            {
                "id": "item_4",
                "title": "Sedação e Analgesia Rápida",
                "description": "Prescreve sedação rápida com Etomidato ou Midazolam + Fentanil antes do choque elétrico na paciente consciente.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["sedação", "etomidato", "midazolam", "fentanil", "analgesia"]
            },
            {
                "id": "item_5",
                "title": "Aplicação da Cardioversão Elétrica com Carga Correta",
                "description": "Aplica o choque elétrico sincronizado de 100 Joules (bifásico) com segurança da equipe ('afasta todos').",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["100 joules", "choque", "afasta", "cardioversão elétrica", "segurança"]
            }
        ],
        "critical_errors": [
            "Tentar administrar Amiodarona venosa em paciente com taquicardia ventricular instável em choque (conduta que atrasa a cardioversão salvadora)",
            "Chocar sem acionar o botão de SINCRONIZAÇÃO (risco de induzir Fibrilação Ventricular por R sobre T)"
        ]
    },
    {
        "code": "EINSTEIN-2024-CM-SEPSE",
        "title": "Choque Séptico & Protocolo Sepse 1 Hora",
        "area": "Clínica Médica",
        "subtema": "Infectologia e Terapia Intensiva",
        "institution": "Einstein",
        "year": 2024,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: CENTRO DE TERAPIA INTENSIVA / PRONTO ATENDIMENTO\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico de plantão no Pronto Atendimento do Hospital Israelita Albert Einstein.\n\n"
            "**Cenário**:\n"
            "- Paciente: Seu Geraldo, 74 anos, acamado por sequela de AVC prévio, trazido por cuidadores com febre, tosse produtiva e sonolência há 2 dias.\n\n"
            "**Sua Tarefa**:\n"
            "1. Reconheça a gravidade e o choque séptico.\n"
            "2. Execute integralmente o Bundle de 1 Hora da Sepse.\n"
            "3. Indique as metas hemodinâmicas e destino do paciente.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Geraldo Ferreira (Cuidadores)",
            "age": 74,
            "gender": "masculino",
            "chief_complaint": "Ele tá muito quente desde ontem e quase não acorda hoje, tossindo uma secreção amarelada grossa.",
            "past_history": "Hipertensão, DM2, AVC isquêmico há 3 anos."
        },
        "physical_exam": {
            "vitals": {
                "pa": "80x48 mmHg (PAM 58 mmHg)",
                "fc": "124 bpm",
                "fr": "28 irpm",
                "sato2": "90% em ar ambiente",
                "temp": "38.9 °C"
            },
            "findings": {
                "geral": "Sonolento, respondendo apenas a estímulos dolorosos, tempo de enchimento capilar de 4 segundos, livedo reticular em membros inferiores.",
                "respiratorio": "Murmúrio diminuído em base direita com estertores crepitantes abundantes no terço médio e inferior.",
                "cardiovascular": "Taquicardia sinusal, sem sopros audíveis."
            }
        },
        "lab_imaging": {
            "gasometria_lactato": {
                "title": "Gasometria Arterial e Lactato Sérico",
                "available": True,
                "result_text": "pH 7.28, pCO2 30, HCO3 16, BE -8, Lactato arterial 3.8 mmol/L (hiperlactatemia acentuada por hipoperfusão)."
            }
        },
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Reconhecimento Imediato de Sepse com Hipoperfusão Tecidual",
                "description": "Verifica PAM < 65 mmHg e lactato > 2 mmol/L caracterizando choque séptico de foco pulmonar.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["sepse", "choque séptico", "hipoperfusão", "lactato"]
            },
            {
                "id": "item_2",
                "title": "Coleta Imediata de Lactato e Hemoculturas",
                "description": "Solicita lactato sérico e coleta de 2 pares de hemoculturas e cultura de escarro/urina ANTES do antibiótico.",
                "weight": 2.0,
                "category": "exames_complementares",
                "keywords": ["hemocultura", "cultura", "lactato", "antes do antibiótico"]
            },
            {
                "id": "item_3",
                "title": "Antibioticoterapia de Amplo Espectro em < 1 Hora",
                "description": "Prescreve antibiótico venoso cobrindo patógenos nosocomiais/comunitários graves (ex: Pip-Tazo ou Cefepime) em até 60 minutos.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["antibiótico", "piperacilina", "cefepime", "amplo espectro", "primeira hora"]
            },
            {
                "id": "item_4",
                "title": "Ressuscitação Volêmica com Cristaloide (30 ml/kg)",
                "description": "Inicia infusão intravenosa rápida de 30 ml/kg de Ringer Lactato ou Soro Fisiológico nas primeiras 3 horas.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["30 ml/kg", "cristaloide", "ringer lactato", "volume", "expansão"]
            },
            {
                "id": "item_5",
                "title": "Vasopressor Precoce (Noradrenalina)",
                "description": "Indica início precoce de Noradrenalina se PAM permanecer < 65 mmHg durante ou após a expansão com meta de PAM >= 65 mmHg.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["noradrenalina", "vasopressor", "pam 65", "uti"]
            }
        ],
        "critical_errors": [
            "Atrasar o antibiótico por mais de 1 hora em paciente com choque séptico",
            "Prescrever dopamina como vasopressor de primeira linha (Noradrenalina é padrão-ouro absoluto)"
        ]
    },
    {
        "code": "EINSTEIN-2023-CG-PNEUMO",
        "title": "Trauma Torácico: Pneumotórax Hipertensivo",
        "area": "Cirurgia Geral",
        "subtema": "Trauma e ATLS",
        "institution": "Einstein",
        "year": 2023,
        "difficulty": "hard",
        "duration_seconds": 480,
        "scenario_door_markdown": (
            "### ESTAÇÃO: SALA DE TRAUMA / EMERGÊNCIA CIRÚRGICA\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico de plantão na Sala de Trauma do Hospital Israelita Albert Einstein.\n\n"
            "**Cenário**:\n"
            "- Paciente: Rafael, 28 anos, vítima de colisão moto x poste há 20 minutos, pranchado e com colar cervical.\n\n"
            "**Sua Tarefa**:\n"
            "1. Conduza a avaliação primária do ATLS.\n"
            "2. Identifique a lesão com risco iminente de morte.\n"
            "3. Execute o procedimento cirúrgico/descompressivo salvador de vida imediato.\n\n"
            "*Tempo de prova: 8 minutos.*"
        ),
        "patient_persona": {
            "name": "Rafael (Trauma)",
            "age": 28,
            "gender": "masculino",
            "chief_complaint": "Tô... sufocando... peito vai explodir...",
            "past_history": "Previamente hígido."
        },
        "physical_exam": {
            "vitals": {
                "pa": "70x40 mmHg",
                "fc": "138 bpm",
                "fr": "34 irpm",
                "sato2": "84% com colar cervical e máscara"
            },
            "findings": {
                "atls_a": "Via aérea pérvia, coluna cervical imobilizada.",
                "atls_b": "Dispneia extrema, cianose, desvio de traqueia visível para o lado esquerdo, turgência jugular patológica bilateral. Hemitórax direito hiperinsuflado, com hipertimpanismo à percussão e murmúrio vesicular completamente abolido à direita.",
                "atls_c": "Choque obstrutivo com pulsos periféricos impalpáveis e taquicardia extrema."
            }
        },
        "lab_imaging": {},
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Avaliação Primária Sistemática (ABCDE do ATLS)",
                "description": "Verifica via aérea com controle da coluna cervical (A) e avança para a respiração e ventilação (B).",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["atls", "abcde", "colar cervical", "via aérea"]
            },
            {
                "id": "item_2",
                "title": "Diagnóstico Clínico Imediato de Pneumotórax Hipertensivo",
                "description": "Reconhece a tétrade: murmúrio abolido + hipertimpanismo + desvio de traqueia + turgência jugular com choque obstrutivo.",
                "weight": 2.5,
                "category": "diagnostico",
                "keywords": ["pneumotórax hipertensivo", "choque obstrutivo", "desvio de traqueia", "turgência"]
            },
            {
                "id": "item_3",
                "title": "NÃO Solicitar Radiografia / NÃO Atrasar a Conduta",
                "description": "Verbaliza enfaticamente que o diagnóstico é 100% clínico e que solicitar RX de tórax levaria o paciente à parada cardíaca.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["não pedir rx", "diagnóstico clínico", "sem atraso"]
            },
            {
                "id": "item_4",
                "title": "Descompressão Torácica Imediata com Agulha (Toracocentese)",
                "description": "Realiza punção de alívio imediata com cateter agulhado calibroso (jelco 14/16) no 2º EIC na linha hemiclavicular ou 4º/5º EIC anterior à axilar média.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["punção", "agulha", "toracocentese", "alívio", "2º espaço", "5º espaço"]
            },
            {
                "id": "item_5",
                "title": "Drenagem Torácica Tubular em Selo d'Água Definitiva",
                "description": "Executa a drenagem de tórax fechada em selo d'água no 5º EIC entre as linhas axilar anterior e média.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["drenagem de tórax", "selo d'água", "dreno", "5º espaço"]
            }
        ],
        "critical_errors": [
            "Solicitar radiografia de tórax ou tomografia antes de descomprimir o pneumotórax hipertensivo (falta gravíssima com óbito imediato)",
            "Aguardar intubação orotraqueal antes de descomprimir o tórax (a ventilação com pressão positiva piora o pneumotórax e acelera a PCR)"
        ]
    },
    {
        "code": "REVALIDA-2024-PED-DESID",
        "title": "Desidratação Grave por Gastroenterite Aguda (Plano C)",
        "area": "Pediatria",
        "subtema": "Gastroenterologia Pediátrica",
        "institution": "Revalida INEP",
        "year": 2024,
        "difficulty": "medium",
        "duration_seconds": 600,
        "scenario_door_markdown": (
            "### ESTAÇÃO: ATENDIMENTO PEDIÁTRICO DE EMERGÊNCIA (REVALIDA INEP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico que atende na Sala de Emergência Pediátrica.\n\n"
            "**Cenário**:\n"
            "- Paciente: Lactente Cauã, 11 meses (peso: 10 kg), trazido pela mãe com história de diarreia líquida há 3 dias (mais de 10 evacuações hoje) e vômitos frequentes.\n\n"
            "**Sua Tarefa**:\n"
            "1. Classifique o estado de hidratação segundo as normas do Ministério da Saúde.\n"
            "2. Prescreva o plano de hidratação adequado com volumes, tempos e soluções.\n"
            "3. Forneça as orientações complementares de alimentação e suplementação.\n\n"
            "*Tempo de prova: 10 minutos.*"
        ),
        "patient_persona": {
            "name": "Mãe do Cauã",
            "age": 24,
            "gender": "feminino",
            "chief_complaint": "Doutor, ele tá molinho, não quer mamar e a fralda tá seca desde de manhã cedo.",
            "past_history": "Nascido a termo, calendário vacinal em dia."
        },
        "physical_exam": {
            "vitals": {
                "pa": "65x40 mmHg",
                "fc": "162 bpm",
                "fr": "44 irpm",
                "sato2": "97%"
            },
            "findings": {
                "geral": "Letárgico, olhos muito fundos, sem lágrimas no choro, boca e língua extremamente secas.",
                "pele": "Sinal da prega cutânea desaparece muito lentamente (> 2 segundos).",
                "perfusao": "Pulsos radiais débeis, extremidades frias, tempo de enchimento capilar de 4 segundos."
            }
        },
        "lab_imaging": {},
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Avaliação dos Sinais Clínicos de Desidratação",
                "description": "Verifica estado geral (letargia), olhos fundos, lágrimas ausentes, boca seca e sinal da prega cutânea > 2s.",
                "weight": 2.0,
                "category": "exame_fisico",
                "keywords": ["letargia", "olhos fundos", "lágrimas", "sinal da prega", "boca seca"]
            },
            {
                "id": "item_2",
                "title": "Classificação Correta: Desidratação Grave (Plano C)",
                "description": "Classifica a criança no Grupo C (Desidratação Grave com sinais de choque hipovolêmico inicial).",
                "weight": 2.0,
                "category": "diagnostico",
                "keywords": ["desidratação grave", "plano c", "choque hipovolêmico"]
            },
            {
                "id": "item_3",
                "title": "Prescrição Correta do Volume da Fase Rápida (100 ml/kg)",
                "description": "Prescreve hidratação venosa imediata: 30 ml/kg em 30 minutos + 70 ml/kg em 2h30 (criança < 1 ano) com SF 0,9% ou Ringer Lactato.",
                "weight": 3.0,
                "category": "conduta_tratamento",
                "keywords": ["100 ml/kg", "30 ml/kg", "70 ml/kg", "soro fisiológico", "ringer lactato", "fase rápida"]
            },
            {
                "id": "item_4",
                "title": "Conduta Alimentar e Continuidade do Aleitamento",
                "description": "Orienta suspensão de líquidos orais apenas durante a infusão rápida inicial, com retorno precoce do aleitamento materno assim que hidratado.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["aleitamento materno", "leite materno", "alimentação"]
            },
            {
                "id": "item_5",
                "title": "Prescrição de Suplementação com Zinco",
                "description": "Prescreve suplementação com Sulfato de Zinco (20 mg/dia para >= 6 meses) por 10 a 14 dias para reduzir a duração e recorrência da diarreia.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["zinco", "20 mg", "14 dias", "sulfato de zinco"]
            }
        ],
        "critical_errors": [
            "Tentar manter apenas Terapia de Reidratação Oral (Plano A ou B) em lactente letárgico com choque hipovolêmico e desidratação grave",
            "Prescrever antimicrobianos de rotina para diarreia aquosa aguda sem sangue nas fezes"
        ]
    },
    {
        "code": "REVALIDA-2023-GO-PEP",
        "title": "Acolhimento e Profilaxias em Violência Sexual",
        "area": "Ginecologia e Obstetrícia",
        "subtema": "Ginecologia Geral e Emergências",
        "institution": "Revalida INEP",
        "year": 2023,
        "difficulty": "medium",
        "duration_seconds": 600,
        "scenario_door_markdown": (
            "### ESTAÇÃO: ATENDIMENTO EM VIOLÊNCIA SEXUAL (REVALIDA INEP)\n\n"
            "**Candidato(a)**:\n"
            "Você é o médico de plantão no Serviço de Referência de Emergência Ginecológica.\n\n"
            "**Cenário**:\n"
            "- Paciente: Juliana, 21 anos, estudante universitária, vítima de violência sexual há 18 horas por agressor desconhecido.\n\n"
            "**Sua Tarefa**:\n"
            "1. Realize o acolhimento humanizado, ético e empático em ambiente privativo.\n"
            "2. Esclareça os direitos da paciente sem exigência de boletim de ocorrência.\n"
            "3. Prescreva as profilaxias medicamentosas pós-exposição (viral, não-viral e gravidez).\n"
            "4. Indique o seguimento multiprofissional.\n\n"
            "*Tempo de prova: 10 minutos.*"
        ),
        "patient_persona": {
            "name": "Juliana",
            "age": 21,
            "gender": "feminino",
            "chief_complaint": "Eu estava voltando da faculdade ontem à noite... um homem me arrastou pro terreno baldio... estou com medo de pegar doenças ou engravidar...",
            "past_history": "Nega uso de método contraceptivo habitual. Não tem certeza se tomou vacina de hepatite B."
        },
        "physical_exam": {
            "vitals": {
                "pa": "120x80 mmHg",
                "fc": "84 bpm",
                "sato2": "99%"
            },
            "findings": {
                "geral": "Muito abalada emocionalmente, chorosa, com escoriações leves em punhos e joelhos.",
                "ginecologico": "Hiperemia vulvar sem lacerações com sangramento ativo (exame genital realizado apenas com consentimento prévio da paciente)."
            }
        },
        "lab_imaging": {},
        "checklist_barema": [
            {
                "id": "item_1",
                "title": "Acolhimento Humanizado e Consentimento Livre",
                "description": "Garante sigilo, acolhimento sem julgamentos e esclarece que o atendimento em saúde independe de boletim de ocorrência ou perícia policial.",
                "weight": 2.0,
                "category": "relacao_medico_paciente",
                "keywords": ["sigilo", "acolhimento", "não precisa de bo", "boletim de ocorrência", "consentimento"]
            },
            {
                "id": "item_2",
                "title": "Anticoncepção de Emergência Precoce",
                "description": "Prescreve Levonorgestrel 1,5 mg dose única por via oral para prevenção de gravidez (tempo decorrido < 72 horas).",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["levonorgestrel", "1,5 mg", "anticoncepção de emergência", "pílula do dia seguinte"]
            },
            {
                "id": "item_3",
                "title": "Profilaxia Pós-Exposição para HIV (PEP)",
                "description": "Prescreve PEP com Tenofovir (TDF) + Lamivudina (3TC) + Dolutegravir (DTG) por 28 dias iniciado em até 72 horas.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["pep", "hiv", "tenofovir", "lamivudina", "dolutegravir", "28 dias"]
            },
            {
                "id": "item_4",
                "title": "Profilaxia de Infecções Sexualmente Transmissíveis Não Virais",
                "description": "Prescreve Ceftriaxona 500 mg IM (gonococo) + Azitromicina 1g VO (clamídia) + Metronidazol 2g VO (tricomoníase).",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["ceftriaxona", "azitromicina", "metronidazol", "gonococo", "clamídia", "ist"]
            },
            {
                "id": "item_5",
                "title": "Profilaxia para Hepatite B e Suporte Multiprofissional",
                "description": "Indica vacina contra Hepatite B + Imunoglobulina Humana Anti-Hepatite B (IGHB) se não vacinada e encaminha para apoio psicológico.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["hepatite b", "vacina", "imunoglobulina", "ighb", "psicologia", "assistência social"]
            }
        ],
        "critical_errors": [
            "Exigir boletim de ocorrência policial como condição para realizar o atendimento médico de urgência",
            "Não prescrever a profilaxia de HIV (PEP) dentro da janela de 72 horas após estupro"
        ]
    }
]


def seed_osce_stations(db) -> int:
    """Insere ou atualiza o catálogo canônico de estações de prova prática."""
    inserted = 0
    with db_transaction(db, immediate=True):
        for st in CANONICAL_STATIONS:
            existing = db.execute("SELECT id FROM osce_stations WHERE code = ?", (st["code"],)).fetchone()
            door_md = st["scenario_door_markdown"]
            persona_json = json.dumps(st["patient_persona"], ensure_ascii=False)
            exam_json = json.dumps(st["physical_exam"], ensure_ascii=False)
            lab_json = json.dumps(st.get("lab_imaging", {}), ensure_ascii=False)
            barema_json = json.dumps({
                "items": st["checklist_barema"],
                "critical_errors": st.get("critical_errors", [])
            }, ensure_ascii=False)

            if existing:
                db.execute("""
                    UPDATE osce_stations
                    SET title = ?, area = ?, subtema = ?, institution = ?, year = ?,
                        difficulty = ?, duration_seconds = ?, scenario_door_markdown = ?,
                        patient_persona_json = ?, physical_exam_json = ?,
                        lab_imaging_json = ?, checklist_barema_json = ?
                    WHERE code = ?
                """, (
                    st["title"], st["area"], st["subtema"], st["institution"], st["year"],
                    st["difficulty"], st["duration_seconds"], door_md,
                    persona_json, exam_json, lab_json, barema_json,
                    st["code"]
                ))
            else:
                db.execute("""
                    INSERT INTO osce_stations (
                        code, title, area, subtema, institution, year,
                        difficulty, duration_seconds, scenario_door_markdown,
                        patient_persona_json, physical_exam_json,
                        lab_imaging_json, checklist_barema_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    st["code"], st["title"], st["area"], st["subtema"], st["institution"], st["year"],
                    st["difficulty"], st["duration_seconds"], door_md,
                    persona_json, exam_json, lab_json, barema_json
                ))
                inserted += 1
    return inserted


def list_osce_stations(
    db,
    user_id: Optional[str] = None,
    area: Optional[str] = None,
    institution: Optional[str] = None,
    difficulty: Optional[str] = None
) -> list[dict[str, Any]]:
    """Lista as estações práticas disponíveis com histórico de tentativas do usuário."""
    query = """
        SELECT s.id, s.code, s.title, s.area, s.subtema, s.institution, s.year,
               s.difficulty, s.duration_seconds, s.scenario_door_markdown,
               (
                   SELECT MAX(sess.final_score)
                   FROM osce_sessions sess
                   WHERE sess.station_id = s.id AND sess.user_id = ? AND sess.status = 'completed'
               ) as best_score,
               (
                   SELECT COUNT(*)
                   FROM osce_sessions sess
                   WHERE sess.station_id = s.id AND sess.user_id = ? AND sess.status = 'completed'
               ) as completed_attempts
        FROM osce_stations s
        WHERE 1=1
    """
    params: list[Any] = [user_id or "", user_id or ""]

    if area and area != "Todas as Áreas":
        query += " AND s.area = ?"
        params.append(area)
    if institution and institution not in ("Todas as Bancas", "TODAS"):
        query += " AND s.institution = ?"
        params.append(institution)
    if difficulty:
        query += " AND s.difficulty = ?"
        params.append(difficulty)

    query += " ORDER BY s.institution, s.area, s.id"
    rows = db.execute(query, tuple(params)).fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "code": r["code"],
            "title": r["title"],
            "area": r["area"],
            "subtema": r["subtema"],
            "institution": r["institution"],
            "year": r["year"],
            "difficulty": r["difficulty"],
            "duration_seconds": r["duration_seconds"],
            "scenario_door_markdown": r["scenario_door_markdown"],
            "best_score": round(float(r["best_score"]), 1) if r["best_score"] is not None else None,
            "completed_attempts": int(r["completed_attempts"] or 0),
        })
    return result


def get_osce_station(db, station_id: int, include_barema: bool = False) -> Optional[dict[str, Any]]:
    """Carrega detalhes de uma estação, mantendo o barema oculto durante a prova."""
    row = db.execute("""
        SELECT id, code, title, area, subtema, institution, year,
               difficulty, duration_seconds, scenario_door_markdown,
               patient_persona_json, physical_exam_json, lab_imaging_json,
               checklist_barema_json
        FROM osce_stations
        WHERE id = ?
    """, (station_id,)).fetchone()
    if not row:
        return None

    physical_exam = json.loads(row["physical_exam_json"] or "{}")
    lab_imaging = json.loads(row["lab_imaging_json"] or "{}")
    patient_persona = json.loads(row["patient_persona_json"] or "{}")

    station = {
        "id": row["id"],
        "code": row["code"],
        "title": row["title"],
        "area": row["area"],
        "subtema": row["subtema"],
        "institution": row["institution"],
        "year": row["year"],
        "difficulty": row["difficulty"],
        "duration_seconds": row["duration_seconds"],
        "scenario_door_markdown": row["scenario_door_markdown"],
        "patient_persona": {
            "name": patient_persona.get("name"),
            "age": patient_persona.get("age"),
            "gender": patient_persona.get("gender"),
            "chief_complaint": patient_persona.get("chief_complaint"),
        },
        "physical_exam_categories": list(physical_exam.get("findings", {}).keys()),
        "vitals_available": bool(physical_exam.get("vitals")),
        "lab_imaging_catalog": [
            {"key": k, "title": v.get("title", k)}
            for k, v in lab_imaging.items()
        ]
    }

    if include_barema:
        barema = json.loads(row["checklist_barema_json"] or "{}")
        station["checklist_barema"] = barema.get("items", [])
        station["critical_errors"] = barema.get("critical_errors", [])
        station["patient_persona_full"] = patient_persona
        station["physical_exam_full"] = physical_exam
        station["lab_imaging_full"] = lab_imaging

    return station


# =========================================================================
# VETOR 5: MOTOR DE ESTAÇÕES INÉDITAS INFINITAS (IA DA FMRP-USP)
# =========================================================================

FMRP_USP_TEMPLATES: list[dict[str, Any]] = [
    {
        "area": "Clínica Médica",
        "subtema": "Hipercalemia Grave e Eletrocardiograma",
        "title_template": "Hipercalemia Grave com Alteração Eletrocardiográfica no HC-UE",
        "hospital_unit": "SALA VERMELHA / UNIDADE DE EMERGÊNCIA (HC-UE FMRP-USP)",
        "patient_names": ["Sebastião Ferreira", "Antônio Carlos dos Santos", "Benedito Prado"],
        "age_range": (52, 68),
        "gender": "masculino",
        "chief_complaint": "Doutor, tô com as pernas pesadas parecendo chumbo... minhas mãos estão formigando e meu peito tá batendo esquisito...",
        "history": "Portador de DRC estágio 4/5 não dialítica e ICC. Fez uso inadvertido de Cetoprofeno para dor lombar e ingeriu carambola nos últimos dias.",
        "vitals": {
            "pa": "150x90 mmHg",
            "fc": "46 bpm (bradicardia sinusal importante)",
            "fr": "20 irpm",
            "sato2": "96% em ar ambiente",
            "temp": "36.4 °C"
        },
        "findings": {
            "geral": "Lúcido, orientado, hipocorado 1+/4+, afebril, eupnéico em repouso. Fraqueza muscular simétrica proximal em MMII (grau 3/5).",
            "cardiovascular": "Bradicardia rítmica a 46 bpm, bulhas normofonéticas sem sopros, pulsos radiais cheios porém lentos.",
            "neurologico": "Parestesias periorais e em pontas dos dedos das mãos e pés, hiporreflexia patelar bilateral sem déficit focal."
        },
        "lab_imaging": {
            "ecg": {
                "title": "Eletrocardiograma de 12 Derivações de Emergência",
                "available": True,
                "result_text": "Bradicardia sinusal a 46 bpm. Ondas T apiculadas, simétricas e de base estreita ('em tenda') difusas, achatamento da onda P e alargamento de QRS (130 ms). Alto risco iminente de assistolia ou fibrilação ventricular.",
                "image_url": "/images/osce/ecg_hipercalemia.png"
            },
            "eletrolitos_gaso": {
                "title": "Gasometria Venosa e Eletrólitos Séricos Urgentes",
                "available": True,
                "result_text": "Potássio (K+): 7.9 mEq/L (Normal: 3.5 a 5.0). Sódio: 136 mEq/L. Cálcio Iônico: 1.15 mmol/L. pH: 7.28, HCO3: 16 mEq/L, Ureia: 142 mg/dL, Creatinina: 4.8 mg/dL."
            }
        },
        "barema_items": [
            {
                "id": "item_1",
                "title": "Reconhecimento Imediato de Hipercalemia Grave com Instabilidade Eletrocardiográfica",
                "description": "Correlaciona a clínica de fraqueza/parestesia com as ondas T em tenda e bradicardia do ECG, verbalizando emergência cardiológica.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["hipercalemia", "hiperpotassemia", "onda t em tenda", "onda t apiculada", "emergência"]
            },
            {
                "id": "item_2",
                "title": "Estabilização de Membrana com Gluconato de Cálcio 10% IV (1ª Medida Obrigatória)",
                "description": "Prescreve Gluconato de Cálcio 10% 1 ampola (10 ml) IV lento em 3 a 5 minutos com monitorização cardíaca contínua.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["gluconato de cálcio", "estabilização de membrana", "10%", "1 ampola", "iv lento"]
            },
            {
                "id": "item_3",
                "title": "Prescrição de Solução Polarizante (Glicoinsulina) para Shift Intracelular",
                "description": "Prescreve Insulina Regular 10 UI associada a Glicose 50% (50g = 100ml) IV em 30 minutos para forçar entrada de potássio nas células.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["glicoinsulina", "insulina regular", "glicose 50%", "solução polarizante", "shift"]
            },
            {
                "id": "item_4",
                "title": "Medidas Adjuvantes de Shift: Nebulização com Beta-2 Agonista e Bicarbonato",
                "description": "Prescreve nebulização com Salbutamol/Fenoterol em altas doses (10-20 gotas) e/ou Bicarbonato de Sódio 8,4% se acidose metabólica.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["salbutamol", "fenoterol", "nebulização", "beta-2", "bicarbonato"]
            },
            {
                "id": "item_5",
                "title": "Medidas de Esfoliação / Eliminação: Resinas de Troca e Diurético de Alça",
                "description": "Prescreve Furosemida IV se paciente não anúrico e resina de troca (Poliestirenossulfonato de cálcio / Sorcal 30g VO).",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["furosemida", "sorcal", "resina de troca", "eliminação"]
            },
            {
                "id": "item_6",
                "title": "Indicação e Contato Imediato com a Nefrologia para Hemodiálise de Urgência",
                "description": "Aciona a equipe de Nefrologia do HC-UE para passagem de cateter de hemodiálise (Shilley) e sessão dialítica de emergência.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["hemodiálise", "nefrologia", "urgência dialítica", "cateter de diálise"]
            }
        ],
        "critical_errors": [
            "Administrar Insulina Regular pura sem glicose simultânea (risco de hipoglicemia grave)",
            "Esquecer a administração de Gluconato de Cálcio em paciente com alterações eletrocardiográficas",
            "Prescrever diurético poupador de potássio (Espironolactona)"
        ]
    },
    {
        "area": "Clínica Médica",
        "subtema": "Intoxicação Exógena e Síndrome Colinérgica",
        "title_template": "Intoxicação por Organofosforados na Região de Ribeirão Preto",
        "hospital_unit": "SALA DE URGÊNCIA / UNIDADE DE EMERGÊNCIA (HC-UE FMRP-USP)",
        "patient_names": ["Valdir Aparecido", "José Donizete", "Marcos Roberto"],
        "age_range": (38, 55),
        "gender": "masculino",
        "chief_complaint": "Tô afogando... na minha própria baba... minha vista tá escura... não consigo puxar o ar...",
        "history": "Trabalhador rural da lavoura de cana/laranja da região metropolitana de Ribeirão Preto. Deu entrada trazido por colegas após pulverizar inseticida sem equipamento de proteção.",
        "vitals": {
            "pa": "100x65 mmHg",
            "fc": "50 bpm (bradicardia)",
            "fr": "34 irpm com esforço respiratório",
            "sato2": "87% em ar ambiente",
            "temp": "35.8 °C"
        },
        "findings": {
            "geral": "Agitado, sudorético difuso, salivação abundante escorrendo pela comissura labial, lacrimejamento e fasciculações musculares visíveis em tronco e face.",
            "respiratorio": "Roncos e estertores crepitantes difusos em ambos os hemitórax ('pulmão encharcado' por broncorreia maciça), sibilos expiratórios.",
            "ocular": "Miose bilateral puntiforme acentuada não reativa.",
            "gastrointestinal": "Ruídos hidroaéreos hiperativos, diarreia e náuseas."
        },
        "lab_imaging": {
            "gasometria_arterial": {
                "title": "Gasometria Arterial sob Máscara de O2",
                "available": True,
                "result_text": "pH 7.24, pO2 58 mmHg, pCO2 49 mmHg, HCO3 20 mEq/L, SatO2 88%. Insuficiência respiratória mista por broncorreia maciça e broncoespasmo colinérgico."
            }
        },
        "barema_items": [
            {
                "id": "item_1",
                "title": "Proteção Individual da Equipe e Descontaminação Rápida do Paciente",
                "description": "Exige uso de luvas, máscara e avental impermeável; retira imediatamente roupas contaminadas do trabalhador e lava a pele com água e sabão.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["epi", "descontaminação", "retirar roupas", "lavagem", "paramentação"]
            },
            {
                "id": "item_2",
                "title": "Diagnóstico Clínico da Síndrome Colinérgica Aguda por Inibidores da Acetilcolinesterase",
                "description": "Reconhece a tríade clássica muscarínica: miose puntiforme, broncorreia com estertores difusos e sialorreia associada a fasciculações nicotínicas.",
                "weight": 2.0,
                "category": "diagnostico",
                "keywords": ["síndrome colinérgica", "organofosforado", "carbamato", "miose", "broncorreia"]
            },
            {
                "id": "item_3",
                "title": "Prescrição Imediata de Atropina IV em Doses Dobradas (Atropinização)",
                "description": "Prescreve Atropina 1 a 2 mg IV a cada 3 a 5 minutos, dobrando a dose progressivamente até atingir os critérios de atropinização (secar secreções pulmonares).",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["atropina", "atropinização", "1 mg", "2 mg", "secar secreção", "iv"]
            },
            {
                "id": "item_4",
                "title": "Manejo Ventilatório: Oxigenoterapia e Aspiração das Vias Aéreas",
                "description": "Instala oxigênio em máscara com reservatório a 10-15 L/min e realiza aspiração frequente de secreções orotraqueais.",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["oxigênio", "máscara com reservatório", "aspiração", "vias aéreas"]
            },
            {
                "id": "item_5",
                "title": "Prescrição de Oximas (Pralidoxima) como Reativador da Acetilcolinesterase",
                "description": "Prescreve Pralidoxima (Contrathion) 1 a 2g IV em infusão de 30 minutos para reverter os efeitos nicotínicos (fraqueza e fasciculações).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["pralidoxima", "contrathion", "oxima", "reativador"]
            },
            {
                "id": "item_6",
                "title": "Encaminhamento e Vaga de UTI com Monitorização Contínua",
                "description": "Solicita leito intensivo no HC-UE com vigilância de recidiva colinérgica e síndrome intermediária.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["uti", "leito de uti", "síndrome intermediária", "vigilância"]
            }
        ],
        "critical_errors": [
            "Suspender ou atrasar a Atropina por medo de taquicardia (a meta da atropinização é a resolução da broncorreia, não a frequência cardíaca)",
            "Prescrever Succinilcolina para intubação orotraqueal (metabolizada pela colinesterase, causando bloqueio neuromuscular irreversível)"
        ]
    },
    {
        "area": "Cirurgia Geral",
        "subtema": "Abdome Agudo Obstrutivo",
        "title_template": "Volvo de Sigmoide em Paciente Chagásico no HC-UE",
        "hospital_unit": "SALA DE EMERGÊNCIA CIRÚRGICA (HC-UE FMRP-USP)",
        "patient_names": ["Benedito de Paula", "Geraldo Magela", "Sebastião Vicente"],
        "age_range": (64, 78),
        "gender": "masculino",
        "chief_complaint": "Doutor, minha barriga tá inchando que nem um tambor... faz 4 dias que não sai nem um pingo de ar nem fezes...",
        "history": "Natural de Minas Gerais, residente na região de Ribeirão Preto. Portador de Megaesôfago e Megacólon Chagásico de longa data.",
        "vitals": {
            "pa": "115x75 mmHg",
            "fc": "98 bpm",
            "fr": "22 irpm",
            "sato2": "96%",
            "temp": "36.8 °C"
        },
        "findings": {
            "geral": "Fácies de desconforto, desidratado 2+/4+, lúcido e afebril.",
            "abdome": "Abdome acentuadamente distendido, assimétrico com abaulamento oblíquo em flanco esquerdo e fossa ilíaca, timpanismo metálico difuso à percussão, ruídos hidroaéreos com timbre de luta metálica. Sem sinais francos de peritonite (abdome indolor à descompressão brusca).",
            "toque_retal": "Ampola retal vazia, sem fezes, sem massas palpáveis ou sangue na luva."
        },
        "lab_imaging": {
            "rx_abdome": {
                "title": "Radiografia Simples de Abdome (Rotina de Abdome Agudo)",
                "available": True,
                "result_text": "Alça colônica maciçamente dilatada em forma de 'U' invertido com as pontas voltadas para a pelve ('sinal do grão de café' ou 'sinal da câmara de ar dupla'). Ausência de pneumoperitônio.",
                "image_url": "/images/osce/rx_volvo_sigmoide.png"
            }
        },
        "barema_items": [
            {
                "id": "item_1",
                "title": "Suspeita Diagnóstica de Volvo de Sigmoide em Contexto de Doença de Chagas",
                "description": "Correlaciona a parada de fezes e flatos com a história chagásica e distensão assimétrica, verbalizando hipótese de volvo de sigmoide.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["volvo", "sigmoide", "chagas", "megacólon", "obstrução intestinal"]
            },
            {
                "id": "item_2",
                "title": "Realização Obrigatória do Toque Retal",
                "description": "Executa o exame proctológico identificando a ampola retal vazia e descartando fecaloma ou neoplasia baixa.",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["toque retal", "ampola vazia", "fecaloma", "proctológico"]
            },
            {
                "id": "item_3",
                "title": "Medidas de Suporte Inicial: Jejum, Sonda Nasogástrica e Hidratação Venosa",
                "description": "Prescreve jejum absoluto, passagem de Sonda Nasogástrica aberta para descompressão e expansão com Ringer Lactato ou SF 0,9%.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["jejum", "sonda nasogástrica", "sng", "hidratação venosa", "cristaloide"]
            },
            {
                "id": "item_4",
                "title": "Solicitação e Interpretação Precisa da Radiografia de Abdome",
                "description": "Reconhece o clássico 'sinal do grão de café' ou 'U invertido' característico do volvo de sigmoide na radiografia simples.",
                "weight": 2.0,
                "category": "exames_complementares",
                "keywords": ["rx", "grão de café", "u invertido", "radiografia simples"]
            },
            {
                "id": "item_5",
                "title": "Indicação da Descompressão Endoscópica (Colonoscopia / Sigmoidoscopia Rígida)",
                "description": "Indica descompressão endoscópica inicial como medida de 1ª linha devido à ausência de sinais de peritonite ou necrose.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["descompressão endoscópica", "colonoscopia", "sigmoidoscopia", "desobstrução"]
            },
            {
                "id": "item_6",
                "title": "Planejamento da Cirurgia Eletiva Posterior (Sigmoidectomia a Duhamel / Haddad)",
                "description": "Orienta a necessidade de cirurgia definitiva programada durante a mesma internação para prevenir recidiva do volvo.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["cirurgia definitiva", "sigmoidectomia", "duhamel", "recidiva"]
            }
        ],
        "critical_errors": [
            "Prescrever laxativos, óleo mineral ou procinéticos para o paciente com abdome agudo obstrutivo",
            "Tentar descompressão endoscópica se houver sinais francos de peritonite (dor à descompressão brusca ou febre)"
        ]
    },
    {
        "area": "Pediatria",
        "subtema": "Emergências Neurológicas Pediátricas",
        "title_template": "Estado de Mal Epiléptico Febril no HC-Criança Ribeirão Preto",
        "hospital_unit": "SALA DE EMERGÊNCIA PEDIÁTRICA (HC-CRIANÇA FMRP-USP)",
        "patient_names": ["Enzo Gabriel", "Mateus Henrique", "Arthur Miguel"],
        "age_range": (2, 3),
        "gender": "masculino",
        "chief_complaint": "Doutor, acode meu filho! Ele tá tremendo tudo sem parar faz mais de 10 minutos e tá queimando em brasa!",
        "history": "Lactente de 2 anos, sem histórico prévio de epilepsia. Quadro de febre alta há 24h por infecção de vias aéreas, iniciou crise convulsiva tônico-clônica generalizada contínua há 12 minutos.",
        "vitals": {
            "pa": "95x60 mmHg",
            "fc": "155 bpm",
            "fr": "36 irpm",
            "sato2": "89% em ar ambiente",
            "temp": "39.4 °C",
            "hgt": "108 mg/dL"
        },
        "findings": {
            "geral": "Crise convulsiva tônico-clônica generalizada ativa durante a avaliação, sialorreia espumosa, cianose perioral discreta, hipertermia ao toque.",
            "respiratorio": "Roncos de transmissão por secreções em orofaringe, tiragem intercostal discreta.",
            "neurologico": "Movimentos clônicos síncronos dos 4 membros, desvio do olhar para cima, sem abertura ocular ao chamado."
        },
        "lab_imaging": {},
        "barema_items": [
            {
                "id": "item_1",
                "title": "Medidas Imediatas de Suporte Básico à Vida (Posicionamento e Vias Aéreas)",
                "description": "Posiciona a criança em decúbito lateral, protege contra traumas, não insere objetos na boca e aspira vias aéreas.",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["decúbito lateral", "proteger", "vias aéreas", "não colocar objeto", "aspirar"]
            },
            {
                "id": "item_2",
                "title": "Oxigenioterapia sob Máscara de O2 e Checagem da Glicemia Capilar (HGT)",
                "description": "Oferta O2 sob máscara com reservatório e afere HGT imediato para excluir hipoglicemia como causa da crise.",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["oxigênio", "máscara", "hgt", "glicemia capilar", "hipoglicemia"]
            },
            {
                "id": "item_3",
                "title": "Prescrição de Benzodiazepínico de 1ª Linha com Dose Pediátrica Correta",
                "description": "Prescreve Diazepam 0,2 a 0,3 mg/kg IV lento (ou Midazolam 0,2 mg/kg IM/nasal/retal) para cessar a crise.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["diazepam", "midazolam", "0.2 mg/kg", "0.3 mg/kg", "benzodiazepínico"]
            },
            {
                "id": "item_4",
                "title": "Reavaliação e Repetição do Benzodiazepínico após 5 Minutos se Persistência",
                "description": "Cronometra o tempo e prescreve segunda dose do benzodiazepínico caso a crise não cesse em 5 minutos.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["repetir", "5 minutos", "segunda dose"]
            },
            {
                "id": "item_5",
                "title": "Prescrição de Fenitoína IV (2ª Linha) para Estado de Mal Epiléptico",
                "description": "Prescreve Fenitoína 20 mg/kg IV diluída em SF 0,9% em infusão lenta de 20 minutos com monitorização eletrocardiográfica.",
                "weight": 2.0,
                "category": "conduta_tratamento",
                "keywords": ["fenitoína", "20 mg/kg", "segunda linha", "infusão lenta"]
            },
            {
                "id": "item_6",
                "title": "Manejo Térmico e Investigação Etiológica do Foco Infeccioso",
                "description": "Prescreve antitérmico (Dipirona 15 mg/kg) e inicia exame físico direcionado aos focos comuns (otoscopia, oroscopia e sinais meníngeos).",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["dipirona", "antitérmico", "otoscopia", "oroscopia", "foco"]
            }
        ],
        "critical_errors": [
            "Colocar abaixador de língua ou dedos na boca da criança durante a crise convulsiva",
            "Fazer infusão rápida em bólus de fenitoína (alto risco de bradiarritmia e PCR)",
            "Não checar a glicemia capilar na convulsão pediátrica"
        ]
    },
    {
        "area": "Ginecologia e Obstetrícia",
        "subtema": "Hemorragia da 2ª Metade da Gestação",
        "title_template": "Descolamento Prematuro de Placenta (DPP) no Hospital Mater",
        "hospital_unit": "CENTRO OBSTÉTRICO / SALA DE PARTO (HOSPITAL MATER FMRP-USP)",
        "patient_names": ["Camila Rodrigues", "Priscila Nogueira", "Patrícia Barbosa"],
        "age_range": (28, 36),
        "gender": "feminino",
        "chief_complaint": "Doutor, minha barriga tá dura que nem pedra... uma dor insuportável que não passa... e tá saindo um sangue escuro...",
        "history": "Gestante de 34 semanas, secundigesta, hipertensa crônica em uso irregular de Metildopa. Deu entrada com dor súbita e sangramento genital escuro moderado há 1 hora.",
        "vitals": {
            "pa": "165x105 mmHg",
            "fc": "112 bpm",
            "fr": "24 irpm",
            "sato2": "97%",
            "bcf": "104 bpm (bradicardia fetal sustentada)"
        },
        "findings": {
            "geral": "Ansiosa, fácies de intensa dor, sudorética, taquicárdica.",
            "exame_obstetrico": "Hipertonia uterina mantida ('útero de madeira / lehn'), fundo uterino 34 cm doloroso difusamente, contrações espásticas contínuas sem período de relaxamento.",
            "exame_especular": "Sangramento genital moderado a volumoso de cor vermelho-escura com coágulos saindo pelo colo uterino."
        },
        "lab_imaging": {},
        "barema_items": [
            {
                "id": "item_1",
                "title": "Diagnóstico Clínico Imediato de Descolamento Prematuro de Placenta (DPP)",
                "description": "Reconhece o quadro cardinal: dor abdominal súbita intensa, hipertonia uterina contínua, sangramento escuro e bradicardia fetal.",
                "weight": 2.0,
                "category": "diagnostico",
                "keywords": ["dpp", "descolamento prematuro de placenta", "útero de madeira", "hipertonia"]
            },
            {
                "id": "item_2",
                "title": "Posicionamento em DLE, Oxigênio e Dois Acessos Venosos Calibrosos",
                "description": "Instala a gestante em Decúbito Lateral Esquerdo para descompressão da veia cava, oferta O2 e punciona 2 acessos venosos calibrosos (Jelco 14/16).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["decúbito lateral esquerdo", "dle", "oxigênio", "acesso calibroso", "veia cava"]
            },
            {
                "id": "item_3",
                "title": "Amniotomia Precoce (Rotura Artificial das Membranas Ovulares)",
                "description": "Indica e realiza amniotomia imediata para reduzir a pressão intrauterina, diminuir o extravasamento hemático e descompressão vascular.",
                "weight": 1.5,
                "category": "exame_fisico",
                "keywords": ["amniotomia", "romper bolsa", "rompimento de membranas", "descompressão"]
            },
            {
                "id": "item_4",
                "title": "Indicação Imediata de Parto pela Via Mais Rápida (Cesariana de Emergência)",
                "description": "Diante do sofrimento fetal agudo (BCF 104 bpm) e colo fechado, aciona a equipe cirúrgica e anestésica para cesariana imediata.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["cesariana de emergência", "cesárea", "parto imediato", "sofrimento fetal"]
            },
            {
                "id": "item_5",
                "title": "Prevenção da Atonia Uterina e Útero de Couvelaire",
                "description": "Prescreve Ocitocina IV imediata e Ácido Tranexâmico, alertando sobre o risco elevado de apoplexia uteroplacentária (útero de Couvelaire).",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["ocitocina", "útero de couvelaire", "ácido tranexâmico", "hemorragia pós-parto"]
            },
            {
                "id": "item_6",
                "title": "Solicitação de Tipagem, Coagulograma e Reserva de Hemoderivados",
                "description": "Pede tipagem ABO/Rh, tempo de coagulação e reserva de concentrado de hemácias pelo risco iminente de coagulopatia de consumo (CIVD).",
                "weight": 1.0,
                "category": "exames_complementares",
                "keywords": ["tipagem sanguínea", "coagulograma", "reserva de sangue", "civd"]
            }
        ],
        "critical_errors": [
            "Prescrever tocolíticos para tentar inibir as contrações no DPP (contraindicação absoluta)",
            "Atrasar o encaminhamento para cesariana para aguardar resultado de exames laboratoriais ou ultrassom"
        ]
    },
    {
        "area": "Medicina Preventiva",
        "subtema": "Arboviroses e Vigilância em Saúde",
        "title_template": "Dengue com Sinais de Alarme no CSE Sumarezinho Ribeirão Preto",
        "hospital_unit": "CENTRO DE SAÚDE ESCOLA SUMAREZINHO (CSE FMRP-USP)",
        "patient_names": ["Lucas Henrique", "Felipe Augusto", "Guilherme Santos"],
        "age_range": (21, 32),
        "gender": "masculino",
        "chief_complaint": "Doutor, a febre passou ontem, mas hoje minha barriga começou a doer demais, tô vomitando sem parar e quando levanto minha vista escurece...",
        "history": "Morador do bairro Ipiranga em Ribeirão Preto. 5º dia de doença, com história de febre alta, mialgia e cefaleia retro-orbitária. Hoje apresentou defervescência com início de dor abdominal e tontura.",
        "vitals": {
            "pa": "Sentado: 110x70 mmHg | Em pé: 85x55 mmHg (Hipotensão postural)",
            "fc": "104 bpm",
            "fr": "20 irpm",
            "sato2": "98%",
            "temp": "36.2 °C (defervescência)"
        },
        "findings": {
            "geral": "Letárgico, desidratado 2+/4+, extremidades frias, tempo de enchimento capilar de 2.5 segundos.",
            "abdome": "Dor intensa à palpação profunda de hipocôndrio direito com fígado palpável a 3 cm do RCD (hepatomegalia dolorosa), sem irritação peritoneal.",
            "pele": "Exantema maculopapular discreto em tronco, prova do laço positiva com 24 petéquias no quadrado de 2,5 cm."
        },
        "lab_imaging": {
            "hemograma_urgente": {
                "title": "Hemograma Completo com Hematócrito de Urgência",
                "available": True,
                "result_text": "Hematócrito (Ht): 52% (Concentrado - aumento > 20% do basal). Hemoglobina: 16.8 g/dL. Leucócitos: 2.800/mm³ com linfocitose atípica. Plaquetas: 48.000/mm³ (Trombocitopenia moderada a grave)."
            }
        },
        "barema_items": [
            {
                "id": "item_1",
                "title": "Reconhecimento da Fase Crítica da Dengue na Defervescência",
                "description": "Identifica que o término da febre (5º dia) marca a janela de maior risco de extravasamento plasmático e choque da dengue.",
                "weight": 1.5,
                "category": "diagnostico",
                "keywords": ["fase crítica", "defervescência", "extravasamento plasmático", "choque"]
            },
            {
                "id": "item_2",
                "title": "Classificação Precisa de Risco como Dengue Grupo C (Sinais de Alarme)",
                "description": "Classifica o caso no Grupo C do Ministério da Saúde pela presença de dor abdominal contínua, vômitos persistentes e hipotensão postural.",
                "weight": 2.0,
                "category": "diagnostico",
                "keywords": ["grupo c", "sinais de alarme", "classificação de risco", "dor abdominal"]
            },
            {
                "id": "item_3",
                "title": "Prescrição Imediata de Hidratação Venosa Rápida (10 ml/kg na 1ª Hora)",
                "description": "Prescreve hidratação venosa imediata no CSE com Soro Fisiológico 0,9% ou Ringer Lactato na dose de 10 ml/kg/h em sala de observação.",
                "weight": 2.5,
                "category": "conduta_tratamento",
                "keywords": ["hidratação venosa", "10 ml/kg", "sf 0,9%", "ringer lactato", "primeira hora"]
            },
            {
                "id": "item_4",
                "title": "Solicitação de Hemograma Urgente e Vigilância do Hematócrito",
                "description": "Solicita hemograma completo imediato com ênfase na hemoconcentração (Ht > 50%) e contagem plaquetária.",
                "weight": 1.5,
                "category": "exames_complementares",
                "keywords": ["hemograma", "hematócrito", "hemoconcentração", "plaquetas"]
            },
            {
                "id": "item_5",
                "title": "Contraindicação Expressa de Anti-inflamatórios Não Esteroidais (AINEs) e AAS",
                "description": "Registra na conduta a contraindicação absoluta de AINEs (Ibuprofeno, Cetoprofeno, Diclofenaco) e AAS pelo risco de sangramento.",
                "weight": 1.5,
                "category": "conduta_tratamento",
                "keywords": ["contraindicar aine", "não usar aine", "sem aas", "ibuprofeno", "sangramento"]
            },
            {
                "id": "item_6",
                "title": "Notificação Compulsória Imediata no SINAN e Ações de Vigilância Epidemiológica",
                "description": "Preenche ficha de Notificação Compulsória de Dengue para a Vigilância Epidemiológica de Ribeirão Preto.",
                "weight": 1.0,
                "category": "conduta_tratamento",
                "keywords": ["notificação compulsória", "sinan", "vigilância epidemiológica", "notificar"]
            }
        ],
        "critical_errors": [
            "Liberar o paciente para casa com hidratação oral sem internação em leito de observação (falta gravíssima)",
            "Prescrever anti-inflamatório (Ibuprofeno, Nimesulida, Cetoprofeno) ou AAS para paciente com dengue"
        ]
    }
]


def generate_osce_station(
    db,
    user_id: str,
    area: Optional[str] = None,
    subtema: Optional[str] = None,
    difficulty: str = "hard",
    adaptative: bool = False
) -> dict[str, Any]:
    """
    Motor de Geração de Estações Inéditas Infinitas com o padrão da FMRP-USP (Ribeirão Preto).
    - Se adaptative=True ou area=='adaptativo': analisa o histórico do aluno (erros teóricos em attempts ou notas baixas em osce_sessions)
      para priorizar a fraqueza clínica real.
    - Constrói cenários de alta complexidade médica nos ambientes reais do complexo FMRP-USP
      (HC-UE, HC-Criança, Mater, CSE Sumarezinho, UCO).
    - Persiste a estação na tabela osce_stations com código USP-RP-AI-<hash>.
    - Retorna os dados completos da estação criada pronta para execução na Arena OSCE.
    """
    import random
    target_area = area
    target_subtema = subtema

    # 1. Raciocínio Adaptativo: Localiza fraquezas reais do aluno
    if adaptative or not target_area or target_area.lower() in ["adaptativo", "fraquezas", "auto"]:
        # Tenta identificar histórico recente de reprovação em OSCE
        try:
            low_osce = db.execute("""
                SELECT st.area, st.subtema, AVG(s.final_score) as avg_score
                FROM osce_sessions s
                JOIN osce_stations st ON s.station_id = st.id
                WHERE s.user_id = ? AND s.status = 'completed'
                GROUP BY st.area, st.subtema
                HAVING avg_score < 7.0
                ORDER BY avg_score ASC
                LIMIT 1
            """, (user_id,)).fetchone()
            if low_osce:
                target_area = low_osce["area"]
                target_subtema = low_osce["subtema"]
        except Exception:
            pass

        # Se não achou no OSCE, verifica erros na 1ª fase (questões de prova teórica)
        if not target_area or target_area.lower() in ["adaptativo", "fraquezas", "auto"]:
            try:
                worst_topic = db.execute("""
                    SELECT q.area, q.subtema, COUNT(*) as err_count
                    FROM attempts a
                    JOIN questions q ON a.question_id = q.id
                    WHERE a.is_correct = 0 AND (a.user_id = ? OR a.user_id = 1)
                    GROUP BY q.area, q.subtema
                    ORDER BY err_count DESC
                    LIMIT 1
                """, (user_id,)).fetchone()
                if worst_topic:
                    target_area = worst_topic["area"]
                    target_subtema = worst_topic["subtema"]
            except Exception:
                pass

        # Fallback de seleção aleatória entre as grandes áreas
        if not target_area or target_area.lower() in ["adaptativo", "fraquezas", "auto"]:
            areas_catalog = ["Clínica Médica", "Cirurgia Geral", "Pediatria", "Ginecologia e Obstetrícia", "Medicina Preventiva"]
            target_area = random.choice(areas_catalog)

    # 2. Filtra modelos disponíveis da FMRP-USP
    matched_templates = [
        t for t in FMRP_USP_TEMPLATES
        if _normalize_text(t["area"]) == _normalize_text(target_area)
    ]
    if target_subtema:
        sub_norm = _normalize_text(target_subtema)
        specific_templates = [t for t in matched_templates if sub_norm in _normalize_text(t["subtema"])]
        if specific_templates:
            matched_templates = specific_templates

    if not matched_templates:
        matched_templates = FMRP_USP_TEMPLATES

    chosen_template = random.choice(matched_templates)

    # 3. Parametrização Dinâmica do Caso (Variações Inéditas de Paciente)
    patient_name = random.choice(chosen_template["patient_names"])
    patient_age = random.randint(chosen_template["age_range"][0], chosen_template["age_range"][1])
    unique_hash = uuid.uuid4().hex[:8].upper()
    station_code = f"USP-RP-AI-{unique_hash}"

    # Monta cartaz na porta da estação
    door_md = (
        f"### ESTAÇÃO: {chosen_template['hospital_unit']}\n\n"
        f"**Candidato(a)**:\n"
        f"Você é o médico de plantão no complexo hospitalar da Faculdade de Medicina de Ribeirão Preto (FMRP-USP).\n\n"
        f"**Cenário de Atendimento**:\n"
        f"- Paciente: {patient_name}, {patient_age} anos, {chosen_template['gender']}.\n"
        f"- Queixa de Admissão: \"{chosen_template['chief_complaint']}\"\n\n"
        f"**Sua Tarefa Obrigatória**:\n"
        f"1. Conduza o atendimento beira-leito imediato, realize a anamnese direcionada e acolha o paciente.\n"
        f"2. Solicite e interprete o exame físico segmentar e os exames complementares disponíveis.\n"
        f"3. Estabeleça o diagnóstico diferencial ou etiológico principal.\n"
        f"4. Prescreva o plano terapêutico inicial e verbalize a conduta de encerramento da estação.\n\n"
        f"*Tempo de prova: 8 minutos (Cronômetro Oficial FMRP-USP/FAEPA).*"
    )

    persona_payload = {
        "name": patient_name,
        "age": patient_age,
        "gender": chosen_template["gender"],
        "chief_complaint": chosen_template["chief_complaint"],
        "past_medical_history": chosen_template["history"],
        "allergies": "Nenhuma alergia conhecida."
    }

    physical_payload = {
        "vitals": chosen_template["vitals"],
        "findings": chosen_template["findings"]
    }

    labs_payload = chosen_template.get("lab_imaging", {})
    barema_payload = {
        "items": chosen_template["barema_items"],
        "critical_errors": chosen_template.get("critical_errors", [])
    }

    # 4. Salva a nova estação inédita no banco
    with db_transaction(db, immediate=True):
        cursor = db.execute("""
            INSERT INTO osce_stations (
                code, title, area, subtema, institution, year,
                difficulty, duration_seconds, scenario_door_markdown,
                patient_persona_json, physical_exam_json,
                lab_imaging_json, checklist_barema_json
            ) VALUES (?, ?, ?, ?, 'USP-RP', 2026, ?, 480, ?, ?, ?, ?, ?)
        """, (
            station_code,
            chosen_template["title_template"],
            chosen_template["area"],
            chosen_template["subtema"],
            difficulty,
            door_md,
            json.dumps(persona_payload, ensure_ascii=False),
            json.dumps(physical_payload, ensure_ascii=False),
            json.dumps(labs_payload, ensure_ascii=False),
            json.dumps(barema_payload, ensure_ascii=False)
        ))
        new_station_id = cursor.lastrowid

    return {
        "success": True,
        "station_id": new_station_id,
        "code": station_code,
        "title": chosen_template["title_template"],
        "area": chosen_template["area"],
        "subtema": chosen_template["subtema"],
        "institution": "USP-RP",
        "difficulty": difficulty,
        "message": f"Estação inédita FMRP-USP sintetizada com sucesso para {chosen_template['area']} ({chosen_template['subtema']})."
    }


def evaluate_live_barema_progress(
    checklist_items: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """Avalia o progresso em tempo real do barema para o Modo Treino com Preceptor Fantasma."""
    candidate_texts = [
        t.get("message", "").lower() for t in transcript if t.get("sender") == "candidato"
    ]
    actions_texts = [
        f"{a.get('action_type', '')} {a.get('action_target', '')} {a.get('findings', '')}".lower() for a in actions
    ]
    for a in actions:
        if a.get("action_type") == "prescription":
            for p in a.get("prescription_items", []):
                actions_texts.append(f"{p.get('drug_name', '')} {p.get('dose', '')} {p.get('unit', '')} {p.get('route', '')} {p.get('notes', '')}".lower())

    all_evidence = " ".join(candidate_texts + actions_texts)
    norm_evidence = _normalize_text(all_evidence)

    items_status = []
    total_earned = 0.0
    total_weight = 0.0

    for item in checklist_items:
        weight = float(item.get("weight", 1.0))
        total_weight += weight
        keywords = item.get("keywords", [])
        matches = [kw for kw in keywords if _normalize_text(kw) in norm_evidence]
        match_ratio = len(matches) / max(1, len(keywords))

        is_completed = match_ratio >= 0.4 or len(matches) >= 2
        is_partial = not is_completed and (match_ratio > 0.15 or len(matches) == 1)

        score_earned = weight if is_completed else (round(weight * 0.5, 2) if is_partial else 0.0)
        total_earned += score_earned

        items_status.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "category": item.get("category"),
            "weight": weight,
            "score_earned": score_earned,
            "completed": is_completed or is_partial,
            "status": "cumprido_total" if is_completed else ("cumprido_parcial" if is_partial else "nao_cumprido"),
            "matched_keywords": matches[:3]
        })

    # Dicas e Alertas Proativos do Preceptor Fantasma baseados no tempo e itens pendentes
    proactive_hints = []
    uncompleted_categories = set(i["category"] for i in items_status if not i["completed"])

    if elapsed_seconds >= 180 and "exame_fisico" in uncompleted_categories:
        proactive_hints.append("⚠️ Preceptor Fantasma: Já se passaram 3 minutos! Não se esqueça de checar os sinais vitais e o exame físico segmentar.")
    if elapsed_seconds >= 240 and "exames_complementares" in uncompleted_categories:
        proactive_hints.append("⚠️ Preceptor Fantasma: Metade da estação decorrida! Lembre-se de solicitar o exame complementar essencial (ECG, Labs ou Imagem).")
    if elapsed_seconds >= 300 and ("conduta_tratamento" in uncompleted_categories or "tratamento" in uncompleted_categories):
        proactive_hints.append("🚨 Preceptor Fantasma: Faltam 3 minutos! Inicie a prescrição de urgência na prancheta ou verbalize as medidas terapêuticas imediatas.")

    normalized_score = round(min(10.0, (total_earned / max(1.0, total_weight)) * 10.0), 1)

    return {
        "mode": "guided",
        "current_score": normalized_score,
        "max_score": 10.0,
        "raw_earned": round(total_earned, 2),
        "raw_weight": round(total_weight, 2),
        "percentage": round((total_earned / max(1.0, total_weight)) * 100),
        "items_status": items_status,
        "proactive_hints": proactive_hints
    }


def get_session_mode(actions: list[dict[str, Any]]) -> str:
    """Extrai o modo da sessão (blind ou guided) a partir do histórico de ações."""
    for a in actions:
        if a.get("action_type") == "session_init" and a.get("mode"):
            return str(a.get("mode"))
    return "blind"


def start_osce_session(
    db,
    station_id: int,
    user_id: str,
    circuit_session_id: Optional[str] = None,
    mode: str = "blind"
) -> dict[str, Any]:
    """Inicia uma sessão cronometrada de prova prática no Modo Prova Cega ou Treino Guiado."""
    station = db.execute("SELECT id, code, title, institution, duration_seconds, scenario_door_markdown, checklist_barema_json FROM osce_stations WHERE id = ?", (station_id,)).fetchone()
    if not station:
        raise ValueError(f"Estação {station_id} não encontrada.")

    session_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    session_mode = "guided" if mode == "guided" else "blind"

    initial_transcript = [
        {
            "sender": "examinador",
            "message": "Candidato(a), você pode entrar na sala de exame. O tempo de prova começou.",
            "timestamp": now_iso
        }
    ]

    initial_actions = [
        {
            "action_type": "session_init",
            "mode": session_mode,
            "timestamp": now_iso
        }
    ]

    with db_transaction(db, immediate=True):
        db.execute("""
            INSERT INTO osce_sessions (
                id, station_id, user_id, circuit_session_id,
                status, start_time, elapsed_seconds,
                transcript_json, actions_taken_json
            ) VALUES (?, ?, ?, ?, 'in_progress', ?, 0, ?, ?)
        """, (
            session_id, station_id, user_id, circuit_session_id,
            now_iso, json.dumps(initial_transcript, ensure_ascii=False),
            json.dumps(initial_actions, ensure_ascii=False)
        ))

    barema_raw = json.loads(station["checklist_barema_json"] or "{}")
    checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])

    guided_feedback = None
    if session_mode == "guided":
        guided_feedback = evaluate_live_barema_progress(checklist_items, initial_transcript, initial_actions, 0)

    return {
        "session_id": session_id,
        "station_id": station_id,
        "code": station["code"],
        "title": station["title"],
        "institution": station["institution"],
        "duration_seconds": station["duration_seconds"],
        "start_time": now_iso,
        "transcript": initial_transcript,
        "mode": session_mode,
        "guided_feedback": guided_feedback
    }


def get_osce_live_feedback(db, session_id: str, user_id: str, elapsed_seconds: int = 0) -> dict[str, Any]:
    """Retorna o progresso em tempo real do barema para o Modo Treino com Preceptor Fantasma."""
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
    checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])

    mode = get_session_mode(actions)
    feedback = evaluate_live_barema_progress(checklist_items, transcript, actions, elapsed_seconds)
    feedback["mode"] = mode
    return feedback


def interact_osce_session(
    db,
    session_id: str,
    user_id: str,
    message: str,
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """Processa fala/pergunta do aluno ao paciente virtual ou ao examinador."""
    sess = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.status, s.transcript_json, s.actions_taken_json,
               st.title, st.area, st.subtema, st.patient_persona_json, st.scenario_door_markdown,
               st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError(f"Sessão {session_id} não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão já finalizada.", "status": sess["status"]}

    transcript = json.loads(sess["transcript_json"] or "[]")
    persona = json.loads(sess["patient_persona_json"] or "{}")

    now_iso = datetime.now(timezone.utc).isoformat()
    clean_msg = message.strip()

    # Adiciona a mensagem do aluno ao transcript
    transcript.append({
        "sender": "candidato",
        "message": clean_msg,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds
    })

    # Decisão de resposta via Ator Virtual com inteligência e fallback médico
    system_prompt = (
        f"Você é o paciente simulado em uma prova prática presencial de residência médica (OSCE).\n"
        f"NOME: {persona.get('name', 'Paciente')}, IDADE: {persona.get('age', 'Adulto')}, GÊNERO: {persona.get('gender', '')}.\n"
        f"QUEIXA PRINCIPAL: {persona.get('chief_complaint')}\n"
        f"HISTÓRICO OCULTO: {json.dumps(persona, ensure_ascii=False)}\n\n"
        f"REGRAS DE ATUAÇÃO RIGOROSAS:\n"
        f"1. Fale como um paciente LEIGO com dor/desconforto. NUNCA use jargões médicos como 'retroesternal', 'eclâmpsia', 'pneumoperitônio'.\n"
        f"2. NUNCA revele o diagnóstico de graça. Só conte detalhes específicos se o médico perguntar expressamente.\n"
        f"3. Responda em no máximo 2 a 3 frases curtas e realistas para manter a dinâmica ágil de prova.\n"
        f"4. Se o médico se apresentar ou demonstrar empatia, responda de forma receptiva.\n"
    )

    history_str = "\n".join([
        f"{t['sender'].upper()}: {t['message']}"
        for t in transcript[-6:]
    ])

    user_prompt = f"Diálogo recente na sala de exame:\n{history_str}\n\nResponda como o paciente {persona.get('name')}:"

    reply_text = ""
    try:
        resp = generate_content_with_fallback(
            prompt=user_prompt,
            system_instruction=system_prompt,
            timeout=12,
            temperature=0.3
        )
        reply_text = resp.get("text", "").strip()
    except Exception as e:
        logger.warning(f"OSCE LLM fallback ativado: {e}")

    if not reply_text:
        # Fallback determinístico contextual de alta fidelidade
        msg_lower = clean_msg.lower()
        if any(w in msg_lower for w in ["dor", "onde dói", "sente", "queima", "aperta"]):
            reply_text = persona.get("pain_characteristics") or persona.get("chief_complaint", "Dói muito aqui no peito, doutor.")
        elif any(w in msg_lower for w in ["quando", "começou", "tempo", "horas", "minutos"]):
            reply_text = f"Começou de repente faz pouco tempo, doutor. {persona.get('chief_complaint', '')}"
        elif any(w in msg_lower for w in ["fuma", "cigarro", "bebe", "álcool", "remédio", "pressão", "diabete", "histórico"]):
            reply_text = persona.get("past_medical_history") or persona.get("past_history", "Não tomo nenhum remédio doutor.")
        elif any(w in msg_lower for w in ["falta de ar", "suor", "suando", "enjoo", "náusea", "vomit"]):
            reply_text = persona.get("associated_symptoms", "Tô sentindo uma náusea forte e um suor frio.")
        elif any(w in msg_lower for w in ["viagra", "sildenafila", "ereção"]):
            reply_text = persona.get("sildenafil_use", "Não tomei nada disso não, doutor.")
        elif any(w in msg_lower for w in ["olá", "bom dia", "boa tarde", "nome", "sou o médico", "vamos cuidar"]):
            reply_text = f"Doutor, por favor me ajuda, tá doendo demais! {persona.get('chief_complaint', '')}"
        else:
            reply_text = "Entendi, doutor. O que o senhor vai fazer pra me ajudar?"

    transcript.append({
        "sender": "paciente",
        "message": reply_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed_seconds
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (json.dumps(transcript, ensure_ascii=False), elapsed_seconds, session_id))

    res_payload: dict[str, Any] = {
        "reply": reply_text,
        "sender": "paciente",
        "elapsed_seconds": elapsed_seconds,
        "transcript_count": len(transcript)
    }

    actions = json.loads(sess["actions_taken_json"] or "[]")
    if get_session_mode(actions) == "guided":
        barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
        checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_payload["guided_feedback"] = evaluate_live_barema_progress(checklist_items, transcript, actions, elapsed_seconds)

    return res_payload


def execute_osce_action(
    db,
    session_id: str,
    user_id: str,
    action_type: str,
    action_target: str,
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Executa uma ação clínica beira-leito:
    - action_type = 'physical_exam': inspeciona segmento ou ausculta com estetoscópio virtual.
    - action_type = 'vitals': solicita sinais vitais imediatos.
    - action_type = 'lab_imaging': solicita exame complementar (ECG, RX, TC, labs).
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.physical_exam_json, st.lab_imaging_json, st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão finalizada."}

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    exam = json.loads(sess["physical_exam_json"] or "{}")
    labs = json.loads(sess["lab_imaging_json"] or "{}")

    now_iso = datetime.now(timezone.utc).isoformat()
    target_clean = action_target.strip().lower()

    action_record = {
        "action_type": action_type,
        "action_target": action_target,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": now_iso
    }

    examiner_message = ""
    result_payload: dict[str, Any] = {}

    if action_type == "vitals":
        vitals = exam.get("vitals", {})
        examiner_message = (
            f"Sinais Vitais: PA {vitals.get('pa', '120x80')}, FC {vitals.get('fc', '80 bpm')}, "
            f"FR {vitals.get('fr', '16 irpm')}, SatO2 {vitals.get('sato2', '98%')}, "
            f"Temp {vitals.get('temp', '36.5 °C')}"
        )
        if "hgt" in vitals:
            examiner_message += f", Glicemia {vitals.get('hgt')}"
        result_payload = {"vitals": vitals}

    elif action_type == "physical_exam":
        findings = exam.get("findings", {})
        norm_target = _normalize_text(action_target)
        finding_text = None
        for k, v in findings.items():
            norm_k = _normalize_text(k)
            if norm_target in norm_k or norm_k in norm_target:
                finding_text = v
                break

        if not finding_text:
            finding_text = "Sem anormalidades detectáveis nesta área."

        audio_key = exam.get("auscultation_audio", {}).get(target_clean)
        examiner_message = f"Exame Físico ({action_target}): {finding_text}"
        result_payload = {
            "finding": finding_text,
            "target": action_target,
            "audio_key": audio_key
        }

    elif action_type == "lab_imaging":
        lab_item = None
        norm_target = _normalize_text(action_target)
        for k, v in labs.items():
            norm_k = _normalize_text(k)
            norm_title = _normalize_text(v.get("title", ""))
            if norm_target in norm_k or norm_k in norm_target or norm_target in norm_title or norm_title in norm_target:
                lab_item = v
                break

        if lab_item and lab_item.get("available", True):
            examiner_message = f"Examinador entrega: {lab_item.get('title', action_target)}. Resultado: {lab_item.get('result_text')}"
            result_payload = {
                "title": lab_item.get("title", action_target),
                "result_text": lab_item.get("result_text"),
                "image_url": lab_item.get("image_url")
            }
        else:
            examiner_message = f"Examinador informa: O exame '{action_target}' não está disponível de imediato ou não foi fornecido pela banca nesta estação."
            result_payload = {"available": False, "title": action_target}

    # Registra ação e intervenção do examinador
    actions.append(action_record)
    transcript.append({
        "sender": "examinador",
        "message": examiner_message,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds,
        "action_payload": result_payload
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET actions_taken_json = ?, transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (
            json.dumps(actions, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            elapsed_seconds,
            session_id
        ))

    res_payload: dict[str, Any] = {
        "action_type": action_type,
        "target": action_target,
        "examiner_message": examiner_message,
        "payload": result_payload,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(actions) == "guided":
        barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
        checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_payload["guided_feedback"] = evaluate_live_barema_progress(checklist_items, transcript, actions, elapsed_seconds)

    return res_payload


def dispatch_osce_speech(
    db,
    session_id: str,
    user_id: str,
    message: str,
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Dispatcher de voz Hands-Free de alta performance para a sala prática do OSCE.
    Analisa a fala natural do candidato e classifica/executa em tempo real:
    1. Comandos ao Examinador (sinais vitais, exames complementares, exame físico, conduta verbalizada).
    2. Diálogo com o Paciente Simulado (anamnese, perguntas clínicas, acolhimento).
    3. Fila de áudio falado (spoken_queue) para execução de áudio encadeado.
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.status, s.actions_taken_json, s.transcript_json,
               st.title, st.area, st.subtema, st.patient_persona_json, st.physical_exam_json, st.lab_imaging_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError(f"Sessão {session_id} não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão já finalizada.", "status": sess["status"]}

    clean_msg = message.strip()
    norm_msg = _normalize_text(clean_msg)
    if not clean_msg:
        return {"error": "Mensagem vazia."}

    exam = json.loads(sess["physical_exam_json"] or "{}")
    labs = json.loads(sess["lab_imaging_json"] or "{}")
    persona = json.loads(sess["patient_persona_json"] or "{}")

    actions_executed = []
    spoken_queue = []
    is_conduct_verbalized = False

    # 1. Detecta Conduta Verbalizada
    conduct_triggers = [
        "minha conduta", "prescrevo", "prescrever", "iniciar tratamento", "vou iniciar",
        "encaminho para", "solicito vaga", "indico cirurgia", "indico laparotomia",
        "passo o caso", "diagnostico e conduta", "administro"
    ]
    if any(trigger in norm_msg for trigger in conduct_triggers):
        is_conduct_verbalized = True

    # 2. Detecta Solicitação de Sinais Vitais
    vitals_triggers = [
        "sinais vitais", "vitais completos", "dados vitais", "aferir pa", "pressao arterial",
        "frequencia cardiaca", "saturacao de o2", "temperatura axilar", "hgt", "glicemia capilar"
    ]
    if any(trigger in norm_msg for trigger in vitals_triggers):
        act_res = execute_osce_action(db, session_id, user_id, "vitals", "vitals", elapsed_seconds)
        actions_executed.append(act_res)
        spoken_queue.append({
            "speaker": "examinador",
            "text": act_res["examiner_message"]
        })

    # 3. Detecta Solicitação de Exames Complementares (Labs e Imagens)
    for k, v in labs.items():
        norm_k = _normalize_text(k)
        norm_title = _normalize_text(v.get("title", ""))
        triggers = [norm_k, norm_title]

        if "ecg" in norm_k or "eletro" in norm_k or "eletrocardiograma" in norm_title:
            triggers.extend(["ecg", "eletro", "eletrocardiograma", "tracado"])
        if "gasometria" in norm_k or "gaso" in norm_title:
            triggers.extend(["gasometria", "gaso", "eletrolitos", "potassio", "sodio", "gaso arterial"])
        if "rx" in norm_k or "raio" in norm_k or "radiografia" in norm_title:
            triggers.extend(["raio x", "rx", "radiografia", "rx torax", "rx de torax"])
        if "tomografia" in norm_k or "tc" in norm_title:
            triggers.extend(["tomografia", "tc", "tc de torax", "tc de abdome", "angiotomografia"])
        if "fast" in norm_k or "ultrassom" in norm_title or "efast" in norm_k:
            triggers.extend(["fast", "e-fast", "efast", "ultrassom", "ultrasonografia", "ultrassonografia beira leito"])
        if "troponina" in norm_k or "enzimas" in norm_title:
            triggers.extend(["troponina", "enzimas cardiacas", "curva de troponina"])
        if "hemograma" in norm_k or "leucocitos" in norm_title:
            triggers.extend(["hemograma", "leucograma", "plaquetas"])

        if any(trig in norm_msg for trig in triggers):
            if not any(a.get("target") == k for a in actions_executed):
                act_res = execute_osce_action(db, session_id, user_id, "lab_imaging", k, elapsed_seconds)
                actions_executed.append(act_res)
                spoken_queue.append({
                    "speaker": "examinador",
                    "text": act_res["examiner_message"]
                })

    # 4. Detecta Exame Físico / Ausculta
    findings = exam.get("findings", {})
    for segment, desc in findings.items():
        norm_seg = _normalize_text(segment)
        seg_triggers = [norm_seg]
        if norm_seg == "cardiovascular":
            seg_triggers.extend(["ausculta cardiaca", "coracao", "bulhas", "sopros"])
        elif norm_seg == "respiratorio":
            seg_triggers.extend(["ausculta pulmonar", "pulmao", "murmurio", "respiracao", "estertores", "sibilos"])
        elif norm_seg == "abdome":
            seg_triggers.extend(["palpacao do abdome", "palpar abdome", "exame do abdome", "descompressao", "blumberg", "ruidos hidroaereos"])
        elif norm_seg == "geral":
            seg_triggers.extend(["exame geral", "estado geral", "aspecto geral", "hidratacao", "mucosas"])

        if any(trig in norm_msg for trig in seg_triggers):
            if not any(a.get("target") == segment for a in actions_executed):
                act_res = execute_osce_action(db, session_id, user_id, "physical_exam", segment, elapsed_seconds)
                actions_executed.append(act_res)
                spoken_queue.append({
                    "speaker": "examinador",
                    "text": act_res["examiner_message"]
                })

    # 5. Se houver conduta verbalizada, adiciona confirmação do examinador
    if is_conduct_verbalized:
        examiner_confirm = "Examinador registra: Conduta verbalizada pelo candidato anotada no barema."
        spoken_queue.append({
            "speaker": "examinador",
            "text": examiner_confirm
        })

    # 6. Avalia se a fala também contém interação com o Paciente
    patient_dialogue_triggers = [
        "dona", "senhor", "senhora", "voce", "vc", "como vai", "ola", "bom dia", "boa tarde",
        "boa noite", "onde doi", "qual e a dor", "quando comecou", "falta de ar", "remedio",
        "toma algum", "alergia", "fuma", "bebe", "antecedentes", "familia", "febre", "vomito",
        "vomitou", "sente", "o que aconteceu", "me conta", "calma", "estou aqui", "vamos cuidar"
    ]
    is_patient_dialogue = (
        len(actions_executed) == 0 and not is_conduct_verbalized
    ) or any(trig in norm_msg for trig in patient_dialogue_triggers)

    patient_reply_text = ""
    if is_patient_dialogue:
        interact_res = interact_osce_session(db, session_id, user_id, clean_msg, elapsed_seconds)
        patient_reply_text = interact_res.get("reply", "")
        if patient_reply_text:
            spoken_queue.append({
                "speaker": "paciente",
                "text": patient_reply_text
            })

    # Recupera o transcript e ações atualizados
    updated_sess = db.execute("""
        SELECT s.transcript_json, s.actions_taken_json, st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()
    current_transcript = json.loads(updated_sess["transcript_json"] or "[]")
    current_actions = json.loads(updated_sess["actions_taken_json"] or "[]")

    res_dispatch: dict[str, Any] = {
        "transcription": clean_msg,
        "actions_executed": actions_executed,
        "is_patient_dialogue": is_patient_dialogue,
        "patient_reply": patient_reply_text,
        "spoken_queue": spoken_queue,
        "transcript": current_transcript,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(current_actions) == "guided":
        barema_raw = json.loads(updated_sess["checklist_barema_json"] or "{}")
        checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_dispatch["guided_feedback"] = evaluate_live_barema_progress(checklist_items, current_transcript, current_actions, elapsed_seconds)

    return res_dispatch


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

    # 1. Evento de Abertura
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

    # 2. Processa Ações Clínicas Estruturadas
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

    # 3. Adiciona Marcos de Anamnese e Diálogo a partir do Transcript
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

    # 4. Detecção de Períodos de Hesitação / Inércia (gaps >= 70s)
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

    # 5. Omissões Críticas Específicas
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
    elapsed_seconds: int
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

    # Competência 6: Gestão de Tempo
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
            earned = 0.8  # Fallback padrão quando o barema da estação não foca exclusivamente nessa categoria

        pct = round(min(100.0, max(0.0, (earned / c_max) * 100)), 1)
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


def finish_osce_session(
    db,
    session_id: str,
    user_id: str,
    conduct_notes: Optional[str] = None
) -> dict[str, Any]:
    """
    Finaliza a estação de prova prática e executa a auditoria completa do Barema Oficial:
    - Calcula nota ponderada de 0.0 a 10.0
    - Avalia cada item do checklist com citações de evidência
    - Constrói a Linha do Tempo Beira-Leito ("Timeline Post-Mortem") com marcos e atrasos
    - Computa o Radar de Competências Médicas em 6 dimensões
    - Detecta faltas eliminatórias graves
    - Sintetiza parecer clínico do Preceptor Sênior
    - Gera Flashcards de Choque no formato FSRS e Criador de Cards
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.start_time, s.elapsed_seconds,
               s.transcript_json, s.actions_taken_json,
               st.title, st.area, st.subtema, st.institution, st.year,
               st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")

    transcript = json.loads(sess["transcript_json"] or "[]")
    actions = json.loads(sess["actions_taken_json"] or "[]")
    barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
    checklist_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
    critical_errors = barema_raw.get("critical_errors", []) if isinstance(barema_raw, dict) else []

    if conduct_notes:
        transcript.append({
            "sender": "candidato",
            "message": f"Conduta e Prescrição Verbalizada: {conduct_notes.strip()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": sess["elapsed_seconds"]
        })

    # Reúne todo o texto produzido pelo aluno e ações realizadas
    candidate_texts = [
        t["message"].lower() for t in transcript if t.get("sender") == "candidato"
    ]
    actions_texts = [
        f"{a.get('action_type')} {a.get('action_target')}".lower() for a in actions
    ]
    all_evidence_corpus = " ".join(candidate_texts + actions_texts)
    norm_evidence_corpus = _normalize_text(all_evidence_corpus)

    total_score = 0.0
    max_score = 0.0
    evaluated_items = []
    shock_cards = []

    for item in checklist_items:
        weight = float(item.get("weight", 1.0))
        max_score += weight
        keywords = item.get("keywords", [])

        matches = [kw for kw in keywords if _normalize_text(kw) in norm_evidence_corpus]
        match_ratio = len(matches) / max(1, len(keywords))

        if match_ratio >= 0.4 or len(matches) >= 2:
            earned = weight
            status = "cumprido_total"
            evidence = f"Identificado na conduta do candidato: termos [{', '.join(matches[:4])}]."
        elif match_ratio > 0.15 or len(matches) == 1:
            earned = round(weight * 0.5, 2)
            status = "cumprido_parcial"
            evidence = f"Cumprimento parcial identificado com o termo [{matches[0]}]."
        else:
            earned = 0.0
            status = "nao_cumprido"
            evidence = "Critério não contemplado nas falas ou ações do candidato durante o tempo de prova."

        total_score += earned
        evaluated_items.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "category": item.get("category"),
            "weight": weight,
            "score_earned": earned,
            "status": status,
            "evidence": evidence
        })

        if status != "cumprido_total":
            shock_cards.append({
                "station_code": sess["subtema"],
                "front": f"🚨 [OSCE {sess['institution']} - {sess['area']}]\nQual é a conduta obrigatória segundo o barema oficial para:\n👉 **{item.get('title')}**?",
                "back": f"💡 **Critério de Avaliação da Banca**:\n{item.get('description', '')}\n\n⚠️ **Palavras-chave de aprovação**: {', '.join(item.get('keywords', []))}",
                "category": item.get("category"),
                "weight": weight
            })

    final_score_normalized = round(min(10.0, (total_score / max(1.0, max_score)) * 10.0), 1)

    critical_warnings = []
    for err in critical_errors:
        err_lower = err.lower()
        if "oxigenioterapia" in err_lower and "o2" in all_evidence_corpus and "cateter" in all_evidence_corpus:
            critical_warnings.append(err)
        elif "aguardar" in err_lower and "troponina" in all_evidence_corpus:
            critical_warnings.append(err)
        elif "eda" in err_lower and "endoscopia" in all_evidence_corpus:
            critical_warnings.append(err)

    # Computa Timeline Post-Mortem e Radar de Competências
    timeline_data = generate_timeline_post_mortem(
        station_meta=dict(sess),
        transcript=transcript,
        actions=actions,
        evaluated_items=evaluated_items,
        elapsed_seconds=sess["elapsed_seconds"]
    )

    radar_data = generate_competency_radar(
        station_meta=dict(sess),
        evaluated_items=evaluated_items,
        actions=actions,
        transcript=transcript,
        elapsed_seconds=sess["elapsed_seconds"]
    )

    preceptor_feedback = {
        "final_score": final_score_normalized,
        "max_score": 10.0,
        "approved": final_score_normalized >= 7.0,
        "station_title": sess["title"],
        "institution": sess["institution"],
        "summary": (
            f"Desempenho de {final_score_normalized}/10.0 na estação de {sess['title']} ({sess['institution']}). "
            + ("Excelente domínio técnico beira-leito, com atendimento estruturado e cumprimento dos pontos capitais da banca."
               if final_score_normalized >= 8.5 else
               "Atendimento satisfatório, porém com perda de pontos em passos operacionais e justificativa de conduta."
               if final_score_normalized >= 6.0 else
               "Atenção crítica: falhas fundamentais no barema que causariam eliminação ou pontuação insuficiente na 2ª fase presencial.")
        ),
        "critical_warnings": critical_warnings,
        "shock_cards_count": len(shock_cards),
        "timeline_post_mortem": timeline_data,
        "competency_radar": radar_data
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET status = 'completed',
                end_time = ?,
                final_score = ?,
                checklist_evaluation_json = ?,
                preceptor_feedback_json = ?,
                transcript_json = ?
            WHERE id = ?
        """, (
            now_iso,
            final_score_normalized,
            json.dumps({"items": evaluated_items, "critical_warnings": critical_warnings}, ensure_ascii=False),
            json.dumps(preceptor_feedback, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            session_id
        ))

    return {
        "session_id": session_id,
        "final_score": final_score_normalized,
        "status": "completed",
        "evaluated_items": evaluated_items,
        "preceptor_feedback": preceptor_feedback,
        "shock_cards": shock_cards,
        "elapsed_seconds": sess["elapsed_seconds"],
        "timeline_post_mortem": timeline_data,
        "competency_radar": radar_data
    }


def get_osce_session_report(db, session_id: str, user_id: str) -> Optional[dict[str, Any]]:
    """Recupera o espelho oficial de prova e relatório detalhado pós-sessão com Timeline e Radar."""
    row = db.execute("""
        SELECT s.id, s.station_id, s.user_id, s.status, s.start_time, s.end_time,
               s.elapsed_seconds, s.final_score, s.transcript_json, s.actions_taken_json,
               s.checklist_evaluation_json, s.preceptor_feedback_json,
               st.code, st.title, st.area, st.subtema, st.institution, st.year,
               st.duration_seconds, st.scenario_door_markdown
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not row:
        return None

    evaluation = json.loads(row["checklist_evaluation_json"] or "{}")
    feedback = json.loads(row["preceptor_feedback_json"] or "{}")
    transcript = json.loads(row["transcript_json"] or "[]")
    actions = json.loads(row["actions_taken_json"] or "[]")

    timeline_data = feedback.get("timeline_post_mortem")
    radar_data = feedback.get("competency_radar")

    if not timeline_data or not radar_data:
        timeline_data = generate_timeline_post_mortem(
            station_meta=dict(row),
            transcript=transcript,
            actions=actions,
            evaluated_items=evaluation.get("items", []),
            elapsed_seconds=row["elapsed_seconds"]
        )
        radar_data = generate_competency_radar(
            station_meta=dict(row),
            evaluated_items=evaluation.get("items", []),
            actions=actions,
            transcript=transcript,
            elapsed_seconds=row["elapsed_seconds"]
        )

    return {
        "session_id": row["id"],
        "station_id": row["station_id"],
        "code": row["code"],
        "title": row["title"],
        "area": row["area"],
        "subtema": row["subtema"],
        "institution": row["institution"],
        "year": row["year"],
        "status": row["status"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "elapsed_seconds": row["elapsed_seconds"],
        "duration_seconds": row["duration_seconds"],
        "final_score": row["final_score"],
        "scenario_door_markdown": row["scenario_door_markdown"],
        "checklist_evaluation": evaluation.get("items", []),
        "critical_warnings": evaluation.get("critical_warnings", []),
        "preceptor_feedback": feedback,
        "transcript": transcript,
        "timeline_post_mortem": timeline_data,
        "competency_radar": radar_data
    }


def export_osce_flashcards(db, session_id: str, user_id: str) -> dict[str, Any]:
    """Exporta os Flashcards de Choque do barema diretamente para a tabela de flashcards do MedQuest."""
    report = get_osce_session_report(db, session_id, user_id)
    if not report:
        raise ValueError("Sessão não encontrada.")

    evaluated_items = report.get("checklist_evaluation", [])
    station_subtema = report.get("subtema", "OSCE Prático")
    station_area = report.get("area", "Clínica Médica")

    exported_count = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    with db_transaction(db, immediate=True):
        for item in evaluated_items:
            if item.get("status") != "cumprido_total":
                front = (
                    f"🚨 [OSCE {report.get('institution')} - {station_area}]\n"
                    f"Qual a conduta e critérios da banca para:\n"
                    f"👉 **{item.get('title')}**?"
                )
                back = (
                    f"💡 **Critério de Avaliação do Barema**:\n{item.get('evidence', '')}\n\n"
                    f"📌 **Subtema**: {station_subtema} ({report.get('code')})"
                )
                db.execute("""
                    INSERT INTO flashcards (
                        user_id, question_id, front, back,
                        created_at, next_review_date, source_context,
                        deck_name, tags, source_type, is_ai_generated
                    ) VALUES (
                        ?, NULL, ?, ?,
                        ?, ?, ?,
                        ?, ?, 'osce_barema', 1
                    )
                """, (
                    user_id, front, back,
                    now_iso, now_iso, f"{station_area} > {station_subtema}",
                    f"OSCE {report.get('institution')}", f"osce,2a_fase,{report.get('code')}"
                ))
                exported_count += 1

    return {
        "success": True,
        "cards_created": exported_count,
        "exported_count": exported_count,
        "message": f"{exported_count} flashcards de choque adicionados à sua revisão ativa FSRS."
    }


# =========================================================================
# VETOR 2: CATÁLOGOS E MOTORES DE PRESCRIÇÃO E MANEQUIM INTERATIVO
# =========================================================================

EMERGENCY_DRUGS_CATALOG: list[dict[str, Any]] = [
    {
        "id": "adrenalina",
        "name": "Adrenalina (Epinefrina 1:1000 - 1 mg/ml)",
        "category": "Ressuscitação & Aminas",
        "default_dose": "0.5",
        "default_unit": "mg",
        "routes": ["IM (vasto lateral da coxa)", "EV em bólus (PCR)", "SC", "Nebulização"],
        "indications": "Anafilaxia grave (0,01 mg/kg até 0,5mg IM), PCR (1mg EV a cada 3-5min), Laringite/Estridor",
        "hints": "Na anafilaxia, via IM no vasto lateral é prioritária. Nunca fazer EV puro se o paciente não estiver em PCR."
    },
    {
        "id": "noradrenalina",
        "name": "Noradrenalina (Hemitartarato 2 mg/ml - ampola 4ml/8mg)",
        "category": "Ressuscitação & Aminas",
        "default_dose": "0.1",
        "default_unit": "mcg/kg/min",
        "routes": ["EV em BIC contínua"],
        "indications": "Choque séptico refratário a volume, choque distributivo, hipotensão grave",
        "hints": "Diluição padrão: 4 ampolas (16mg) + 234 ml SG 5% (64 mcg/ml). Titular para PAM >= 65 mmHg."
    },
    {
        "id": "atropina",
        "name": "Atropina (Sulfato 0,5 mg/ml)",
        "category": "Ressuscitação & Aminas",
        "default_dose": "1.0",
        "default_unit": "mg",
        "routes": ["EV em bólus"],
        "indications": "Bradiarritmias sintomáticas e instáveis (1mg a cada 3-5min até máx 3mg)",
        "hints": "Dose mínima de 0,5-1mg para evitar efeito bradicardizante paradoxal inicial."
    },
    {
        "id": "amiodarona",
        "name": "Amiodarona (Cloridrato 50 mg/ml - ampola 3ml/150mg)",
        "category": "Antiarrítmicos & Cardiovasculares",
        "default_dose": "300",
        "default_unit": "mg",
        "routes": ["EV em bólus rápido (PCR)", "EV em infusão rápida (150mg em 10min se estável)", "EV em BIC contínua"],
        "indications": "PCR em FV/TV sem pulso refratária (300mg no 3º choque); Taquicardias ventriculares",
        "hints": "Diluir sempre em Soro Glicosado 5% para prevenir flebite e precipitação."
    },
    {
        "id": "aas",
        "name": "AAS (Ácido Acetilsalicílico) comprimido mastigável 100mg",
        "category": "Antiarrítmicos & Cardiovasculares",
        "default_dose": "200",
        "default_unit": "mg",
        "routes": ["VO mastigado", "VO deglutido"],
        "indications": "Síndrome Coronariana Aguda (SCA com e sem supra), AVC isquêmico agudo",
        "hints": "Dose inicial mastigada de 160 a 325 mg (preferencialmente 200 a 300 mg) para absorção bucal imediata."
    },
    {
        "id": "ticagrelor",
        "name": "Ticagrelor comprimido 90mg",
        "category": "Antiarrítmicos & Cardiovasculares",
        "default_dose": "180",
        "default_unit": "mg",
        "routes": ["VO"],
        "indications": "SCA com ou sem supra de ST (dupla antiagregação plaquetária em dose de ataque)",
        "hints": "Dose de ataque: 2 comprimidos (180 mg). Preferido em relação ao clopidogrel na diretriz SBC/ESC."
    },
    {
        "id": "clopidogrel",
        "name": "Clopidogrel comprimido 75mg",
        "category": "Antiarrítmicos & Cardiovasculares",
        "default_dose": "300",
        "default_unit": "mg",
        "routes": ["VO"],
        "indications": "SCA (se ticagrelor indisponível, contraindicado ou idoso > 75 anos trombolisado)",
        "hints": "Dose de 300mg (angioplastia ou conservador) ou 600mg (angioplastia primária planejada imediata)."
    },
    {
        "id": "enoxaparina",
        "name": "Enoxaparina sódica seringa preenchida 40mg/60mg/80mg",
        "category": "Antiarrítmicos & Cardiovasculares",
        "default_dose": "1",
        "default_unit": "mg/kg",
        "routes": ["SC de 12/12h", "EV em bólus de 30mg (ataque se SCA com supra < 75 anos)"],
        "indications": "Anticoagulação plena em SCA, TEP agudo, TVP",
        "hints": "Dose plena: 1 mg/kg SC a cada 12 horas. Ajustar para 1 mg/kg 1x/dia se ClCr < 30 ml/min."
    },
    {
        "id": "nitroglicerina",
        "name": "Nitroglicerina (Tridil) ampola 50mg/10ml",
        "category": "Antiarrítmicos & Cardiovasculares",
        "default_dose": "5",
        "default_unit": "mcg/min",
        "routes": ["EV em BIC contínua"],
        "indications": "Dor isquêmica refratária na SCA, edema agudo de pulmão hipertensivo, crise hipertensiva",
        "hints": "Contraindicado se PA sistólica < 90 mmHg, infarto de ventrículo direito ou uso de sildenafila nas últimas 24h."
    },
    {
        "id": "sf09",
        "name": "Soro Fisiológico 0,9% (Cloreto de Sódio) bolsa 500ml / 1000ml",
        "category": "Soluções & Expansão Volêmica",
        "default_dose": "1000",
        "default_unit": "ml",
        "routes": ["EV em infusão rápida", "EV contínuo"],
        "indications": "Expansão volêmica inicial em choque hipovolêmico, desidratação, cetoacidose diabética (1000-1500 ml na 1ª hora)",
        "hints": "Na CAD grave, correr 15 a 20 ml/kg (cerca de 1000 a 1500 ml) na primeira hora."
    },
    {
        "id": "ringers_lactate",
        "name": "Ringer Lactato bolsa 500ml / 1000ml",
        "category": "Soluções & Expansão Volêmica",
        "default_dose": "1000",
        "default_unit": "ml",
        "routes": ["EV em infusão rápida"],
        "indications": "Ressuscitação balanceada no trauma (ATLS 10ª ed: 1000ml restritivo), sepse, grandes queimados",
        "hints": "Menor risco de acidose hiperclorêmica do que o soro fisiológico em grandes volumes."
    },
    {
        "id": "sg5",
        "name": "Soro Glicosado 5% bolsa 500ml",
        "category": "Soluções & Expansão Volêmica",
        "default_dose": "500",
        "default_unit": "ml",
        "routes": ["EV contínuo"],
        "indications": "Associação na CAD quando glicemia atingir 200-250 mg/dL para fechar ânion gap sem hipoglicemia",
        "hints": "Regra áurea do HC-FMRP: nunca suspender a insulina ao atingir 250 mg/dL, abrir o SG 5% junto!"
    },
    {
        "id": "glicose50",
        "name": "Glicose Hipertônica a 50% (ampola 10ml ou 20ml)",
        "category": "Soluções & Expansão Volêmica",
        "default_dose": "40",
        "default_unit": "ml",
        "routes": ["EV em bólus"],
        "indications": "Hipoglicemia sintomática grave (HGT < 70 mg/dL com rebaixamento de nível de consciência)",
        "hints": "40 a 50 ml de Glicose 50% EV rápido. Reavaliar HGT em 15 minutos."
    },
    {
        "id": "kcl",
        "name": "Cloreto de Potássio (KCl 19,1% - ampola 10ml com 25 mEq)",
        "category": "Soluções & Expansão Volêmica",
        "default_dose": "20",
        "default_unit": "mEq",
        "routes": ["EV diluído em solução (NUNCA em bólus puro!)"],
        "indications": "Reposição de potássio na Cetoacidose Diabética (20-30 mEq/L de soro para manter K+ entre 4 e 5)",
        "hints": "AVISO CRÍTICO: KCl puro em bólus é letal por assistolia. Sempre diluir em soro!"
    },
    {
        "id": "gluconato_calcio",
        "name": "Gluconato de Cálcio 10% ampola 10ml",
        "category": "Soluções & Expansão Volêmica",
        "default_dose": "1",
        "default_unit": "ampola",
        "routes": ["EV lento em 3 a 5 minutos"],
        "indications": "Estabilização miocárdica na Hipercalemia grave com alterações de ECG; antídoto do sulfato de magnésio",
        "hints": "Não reduz o potássio sérico por si só, apenas protege o miocárdio contra arritmias ventriculares."
    },
    {
        "id": "insulina_regular",
        "name": "Insulina Regular Humana frasco 100 UI/ml",
        "category": "Endócrino & Metabólico",
        "default_dose": "0.1",
        "default_unit": "U/kg/h",
        "routes": ["EV em BIC contínua", "EV em bólus de 0,1 U/kg"],
        "indications": "Cetoacidose Diabética, Estado Hiperglicêmico Hiperosmolar, Hipercalemia grave",
        "hints": "Diluição clássica: 100 UI em 100 ml de SF 0,9% (1 UI/ml). Checar K+ sérico antes de abrir a infusão!"
    },
    {
        "id": "tranexamico",
        "name": "Ácido Tranexâmico (Transamin) ampola 50mg/ml - 5ml (250mg) / ampola 500mg",
        "category": "Hemostasia & Trauma",
        "default_dose": "1",
        "default_unit": "g",
        "routes": ["EV em bólus de 10 min"],
        "indications": "Politrauma grave com choque hemorrágico (CRASH-2: em < 3h 1g EV em 10 min seguido de 1g em 8h); Hemorragia pós-parto (WOMAN Trial)",
        "hints": "Reduz mortalidade no choque hemorrágico e na atonia uterina. Deve ser feito precocemente (< 3 horas)."
    },
    {
        "id": "ocitocina",
        "name": "Ocitocina ampola 5 UI / ampola 10 UI",
        "category": "Ginecologia & Obstetrícia",
        "default_dose": "10",
        "default_unit": "UI",
        "routes": ["EV em infusão lenta / bólus lento", "EV diluída em BIC (20-40 UI em 500ml SF)", "IM"],
        "indications": "Prevenção e tratamento de primeira linha de Hemorragia Pós-Parto por Atonia Uterina",
        "hints": "Primeira droga de escolha para atonia uterina. Bólus IV excessivamente rápido pode causar hipotensão transitória."
    },
    {
        "id": "misoprostol",
        "name": "Misoprostol comprimido 200 mcg",
        "category": "Ginecologia & Obstetrícia",
        "default_dose": "800",
        "default_unit": "mcg",
        "routes": ["Via retal", "Via sublingual", "Via oral"],
        "indications": "Tratamento de 2ª linha para atonia uterina na Hemorragia Pós-Parto",
        "hints": "Dose de 800 mcg via retal ou sublingual se a hemorragia persistir após ocitocina e ácido tranexâmico."
    },
    {
        "id": "sulfato_magnesio",
        "name": "Sulfato de Magnésio 50% (ampola 10ml com 5g) / 10%",
        "category": "Ginecologia & Obstetrícia",
        "default_dose": "4",
        "default_unit": "g",
        "routes": ["EV em 15-20 min (ataque)", "EV em BIC a 1-2g/h (manutenção - Esquema Zuspan)"],
        "indications": "Prevenção e tratamento de Eclâmpsia em gestantes com Pré-Eclâmpsia grave; Torsades de Pointes",
        "hints": "Regra Zuspan: Ataque 4g EV em 20 min + Manutenção 1 a 2 g/h em BIC contínua. Monitorar reflexo patelar, FR e diurese."
    },
    {
        "id": "hidralazina",
        "name": "Hidralazina (Cloridrato) ampola 20mg/ml",
        "category": "Ginecologia & Obstetrícia",
        "default_dose": "5",
        "default_unit": "mg",
        "routes": ["EV lento a cada 20 min"],
        "indications": "Crise hipertensiva na gestação (PAS >= 160 ou PAD >= 110 mmHg em Pré-eclâmpsia grave)",
        "hints": "Dose inicial de 5mg EV lento. Repetir 5-10mg a cada 20 min se necessário (meta: PAS 140-150 e PAD 90-100 mmHg)."
    },
    {
        "id": "salbutamol",
        "name": "Salbutamol (Aerolin spray 100 mcg/dose ou gotas)",
        "category": "Pneumologia & Alergia",
        "default_dose": "4",
        "default_unit": "puffs",
        "routes": ["Inalatória com espaçador", "Nebulização"],
        "indications": "Crise de asma aguda, exacerbação de DPOC, broncoespasmo",
        "hints": "4 a 8 jatos com espaçador a cada 20 minutos na primeira hora de crise asmática."
    },
    {
        "id": "hidrocortisona",
        "name": "Hidrocortisona pó para solução injetável 100mg / 500mg",
        "category": "Pneumologia & Alergia",
        "default_dose": "200",
        "default_unit": "mg",
        "routes": ["EV em bólus"],
        "indications": "Anafilaxia (segunda linha para prevenir fase tardia), Crise asmática grave, Insuficiência adrenal",
        "hints": "Lembre-se: em anafilaxia, corticoides e anti-histamínicos NÃO substituem a Adrenalina IM prioritária!"
    },
    {
        "id": "midazolam",
        "name": "Midazolam ampola 5mg/ml ou 1mg/ml",
        "category": "Sedação & Analgesia",
        "default_dose": "5",
        "default_unit": "mg",
        "routes": ["EV lento", "IM", "Intranasal"],
        "indications": "Estado de Mal Epiléptico (ataque inicial), Sedação consciente para cardioversão de urgência, IOT",
        "hints": "Antídoto de reversão imediata: Flumazenil."
    },
    {
        "id": "fentanil",
        "name": "Fentanil (Citrato 50 mcg/ml - ampola 2ml/100mcg)",
        "category": "Sedação & Analgesia",
        "default_dose": "100",
        "default_unit": "mcg",
        "routes": ["EV lento"],
        "indications": "Analgesia potente no trauma, analgesia na intubação em sequência rápida (1-3 mcg/kg)",
        "hints": "Antídoto de reversão: Naloxona."
    },
    {
        "id": "ceftriaxona",
        "name": "Ceftriaxona pó para solução injetável 1g / 2g",
        "category": "Antimicrobianos",
        "default_dose": "2",
        "default_unit": "g",
        "routes": ["EV em infusão de 30 min", "IM"],
        "indications": "Bundle de 1 hora da Sepse/Choque séptico; Meningite bacteriana; Profilaxia pós-violência sexual",
        "hints": "Na sepse com choque, administrar na 1ª hora após coleta dos pares de hemoculturas."
    }
]

PROCEDURES_CATALOG: list[dict[str, Any]] = [
    {
        "id": "morrison_efast",
        "type": "efast",
        "name": "Janela Hepatorrenal (Espaço de Morrison)",
        "site": "morrison",
        "body_region": "Hipocôndrio Direito (Linha Axilar Média)",
        "description": "Transdutor posicionado no 8º a 11º EIC direito para avaliar líquido livre entre o fígado e o rim direito."
    },
    {
        "id": "splenorenal_efast",
        "type": "efast",
        "name": "Janela Esplenorrenal (Recesso de Koller)",
        "site": "splenorenal",
        "body_region": "Hipocôndrio Esquerdo (Linha Axilar Posterior)",
        "description": "Transdutor posicionado no 6º a 9º EIC esquerdo para avaliar trauma esplênico e hemoperitônio."
    },
    {
        "id": "pelvic_efast",
        "type": "efast",
        "name": "Janela Pélvica / Suprapúbica",
        "site": "pelvic",
        "body_region": "Hipogástrio (Suprapúbico)",
        "description": "Transdutor posicionado acima da sínfise púbica para avaliar líquido livre no fundo de saco peritoneal."
    },
    {
        "id": "pericardial_efast",
        "type": "efast",
        "name": "Janela Subxifoide / Pericárdica",
        "site": "pericardial",
        "body_region": "Epigástrio / Subxifoide",
        "description": "Transdutor sob o apêndice xifoide apontando para o ombro esquerdo para descartar tamponamento cardíaco."
    },
    {
        "id": "pleural_right_efast",
        "type": "efast",
        "name": "E-FAST Pulmonar Direito (Lung Sliding)",
        "site": "pleural_right",
        "body_region": "2º/3º EIC Direito Linha Hemiclavicular",
        "description": "Avaliação do deslizamento pleural anterior com ultrassom para descartar pneumotórax traumático."
    },
    {
        "id": "pleural_left_efast",
        "type": "efast",
        "name": "E-FAST Pulmonar Esquerdo (Lung Sliding)",
        "site": "pleural_left",
        "body_region": "2º/3º EIC Esquerdo Linha Hemiclavicular",
        "description": "Avaliação do deslizamento pleural anterior à esquerda com ultrassom para detecção de pneumotórax."
    },
    {
        "id": "thoracocentesis_relief",
        "type": "puncture",
        "name": "Toracocentese de Alívio com Agulha",
        "site": "thoracocentesis",
        "body_region": "2º EIC Linha Hemiclavicular ou 4º/5º EIC Linha Axilar Anterior",
        "description": "Punção com abocath calibroso na borda superior da costela para descompressão de pneumotórax hipertensivo."
    },
    {
        "id": "chest_tube_drainage",
        "type": "drainage",
        "name": "Drenagem Torácica Fechada em Selo D'água",
        "site": "chest_tube",
        "body_region": "5º EIC Linha Axilar Média (Triângulo de Segurança)",
        "description": "Toracostomia com dreno tubular 28-36 Fr em selo d'água após alívio inicial de pneumotórax ou hemotórax."
    },
    {
        "id": "hamilton_maneuver",
        "type": "maneuver",
        "name": "Compressão Uterina Bimanual (Manobra de Hamilton)",
        "site": "hamilton",
        "body_region": "Pelve e Hipogástrio",
        "description": "Mão intravaginal fechada em punho contra parede anterior do útero e mão externa comprimindo fundo uterino."
    },
    {
        "id": "synchronized_cardioversion",
        "type": "cardioversion",
        "name": "Cardioversão Elétrica Sincronizada",
        "site": "cardioversion",
        "body_region": "Tórax Infraclavicular Direito e Ápice Cardíaco",
        "description": "Aplicação de pás com gel condutor, sincronização no monitor e disparo de choque para taquicardia instável."
    },
    {
        "id": "vascular_access_central",
        "type": "vascular",
        "name": "Acesso Venoso Central (Subclávia ou Jugular Interna)",
        "site": "central_vein",
        "body_region": "Região Cervical / Infraclavicular",
        "description": "Punção venosa profunda guiada por marcos anatômicos ou ultrassom beira-leito pela técnica de Seldinger."
    },
    {
        "id": "intraosseous_access",
        "type": "vascular",
        "name": "Punção Intraóssea (Tíbia Proximal)",
        "site": "intraosseous",
        "body_region": "Tíbia Proximal (2 cm abaixo da tuberosidade tibial)",
        "description": "Acesso vascular de resgate de emergência rápida no choque pediátrico ou adulto com colapso venoso periférico."
    }
]


def get_emergency_drugs_catalog() -> list[dict[str, Any]]:
    """Retorna o catálogo completo de medicamentos da sala de emergência do OSCE."""
    return EMERGENCY_DRUGS_CATALOG


def get_procedures_catalog() -> list[dict[str, Any]]:
    """Retorna o catálogo de procedimentos beira-leito e janelas E-FAST para o manequim 2D."""
    return PROCEDURES_CATALOG


def prescribe_osce_drugs(
    db,
    session_id: str,
    user_id: str,
    prescription_items: list[dict[str, Any]],
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Processa a assinatura de uma prescrição médica estruturada na Sala Vermelha / Emergência:
    - Analisa os fármacos e doses prescritos contra o checklist e regras clínicas da estação.
    - Notifica a intervenção da equipe de enfermagem da banca.
    - Enfileira fala do examinador para TTS imediato.
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.code, st.title, st.checklist_barema_json, st.scenario_door_markdown
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão finalizada."}

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
    barema_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
    now_iso = datetime.now(timezone.utc).isoformat()

    if not prescription_items:
        return {"error": "Nenhum medicamento informado na prescrição."}

    # Monta a descrição legível e busca correspondências no barema
    drug_summaries: list[str] = []
    matched_checklist_titles: list[str] = []

    for item in prescription_items:
        name = item.get("drug_name", "Medicamento").strip()
        dose = item.get("dose", "").strip()
        unit = item.get("unit", "").strip()
        route = item.get("route", "").strip()
        notes = item.get("notes", "").strip()

        desc_parts = [name]
        if dose:
            desc_parts.append(f"{dose} {unit}".strip())
        if route:
            desc_parts.append(f"via {route}")
        if notes:
            desc_parts.append(f"({notes})")

        drug_summaries.append(" ".join(desc_parts))

        # Checa pertinência com os itens de tratamento do barema da estação
        norm_item = _normalize_text(f"{name} {dose} {unit} {route} {notes}")
        for crit in barema_items:
            if isinstance(crit, dict) and crit.get("category") in ("conduta_tratamento", "tratamento", "conduta"):
                for kw in crit.get("keywords", []):
                    if _normalize_text(kw) in norm_item:
                        if crit.get("title") not in matched_checklist_titles:
                            matched_checklist_titles.append(crit.get("title", ""))

    prescription_text = "; ".join(drug_summaries)
    examiner_message = (
        f"Prescrição da Sala de Emergência recebida pela equipe de enfermagem: {prescription_text}. "
        "Fármacos checados e administrados conforme prescrito. Sinais vitais em monitorização contínua."
    )

    action_record = {
        "action_type": "prescription",
        "action_target": "emergency_prescription",
        "prescription_items": prescription_items,
        "matched_criteria": matched_checklist_titles,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": now_iso
    }

    spoken_queue: list[dict[str, str]] = [
        {"speaker": "examinador", "text": f"Prescrição recebida e administrada pela enfermagem beira-leito: {prescription_text}."}
    ]

    actions.append(action_record)
    transcript.append({
        "sender": "examinador",
        "message": examiner_message,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds,
        "action_payload": {
            "type": "prescription",
            "items": prescription_items,
            "matched_criteria": matched_checklist_titles
        }
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET actions_taken_json = ?, transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (
            json.dumps(actions, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            elapsed_seconds,
            session_id
        ))

    res_presc: dict[str, Any] = {
        "success": True,
        "prescription_text": prescription_text,
        "examiner_message": examiner_message,
        "matched_criteria": matched_checklist_titles,
        "spoken_queue": spoken_queue,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(actions) == "guided":
        res_presc["guided_feedback"] = evaluate_live_barema_progress(barema_items, transcript, actions, elapsed_seconds)

    return res_presc


def perform_osce_procedure(
    db,
    session_id: str,
    user_id: str,
    procedure_type: str,
    anatomical_site: str,
    elapsed_seconds: int = 0
) -> dict[str, Any]:
    """
    Executa um procedimento invasivo ou varredura ultrassonográfica (E-FAST) no manequim 2D beira-leito.
    """
    sess = db.execute("""
        SELECT s.id, s.station_id, s.status, s.actions_taken_json, s.transcript_json,
               st.code, st.title, st.physical_exam_json, st.lab_imaging_json, st.checklist_barema_json
        FROM osce_sessions s
        JOIN osce_stations st ON s.station_id = st.id
        WHERE s.id = ?
    """, (session_id,)).fetchone()

    if not sess:
        raise ValueError("Sessão não encontrada.")
    if sess["status"] != "in_progress":
        return {"error": "Sessão finalizada."}

    actions = json.loads(sess["actions_taken_json"] or "[]")
    transcript = json.loads(sess["transcript_json"] or "[]")
    station_code = sess["code"]
    labs = json.loads(sess["lab_imaging_json"] or "{}")
    now_iso = datetime.now(timezone.utc).isoformat()

    site_clean = anatomical_site.strip().lower()
    proc_type_clean = procedure_type.strip().lower()

    examiner_message = ""
    findings_desc = ""
    is_positive_finding = False
    image_url: Optional[str] = None

    # 1. VARREDURA ULTRASSONOGRÁFICA E-FAST (POCUS)
    if proc_type_clean == "efast" or site_clean in ("morrison", "splenorenal", "pelvic", "pericardial", "pleural_right", "pleural_left"):
        is_trauma_fast = "FAST" in station_code or "trauma" in sess["title"].lower() or "politrauma" in sess["title"].lower()

        if site_clean == "morrison":
            if is_trauma_fast:
                findings_desc = (
                    "Janela Hepatorrenal (Morrison): Presença de lâmina fina de líquido livre anecoico "
                    "no recesso entre o lobo hepático direito e o córtex renal anterior. Espaço de Morrison POSITIVO para líquido livre."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Hepatorrenal (Morrison): Interface hepatorrenal nítida sem acúmulo de líquido anecoico."
        elif site_clean == "splenorenal":
            if is_trauma_fast:
                findings_desc = (
                    "Janela Esplenorrenal (Recesso de Koller): Presença de volumosa quantidade de líquido livre anecoico "
                    "circundando o polo inferior e hilo do baço, com irregularidade cortical compatível com laceração esplênica ativa. FAST POSITIVO."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Esplenorrenal: Recesso de Koller sem coleções ou líquido livre visível."
        elif site_clean == "pelvic":
            if is_trauma_fast:
                findings_desc = (
                    "Janela Pélvica / Suprapúbica: Presença de líquido livre anecoico acumulado no fundo de saco peritoneal posterior. FAST POSITIVO."
                )
                is_positive_finding = True
            else:
                findings_desc = "Janela Pélvica: Bexiga fisiologicamente preenchida, sem líquido livre em escavação pélvica."
        elif site_clean == "pericardial":
            findings_desc = (
                "Janela Subxifoide / Pericárdica: Espaço pericárdico virtual preservado, sem lâmina anecoica ou "
                "sinais de tamponamento cardíaco. Contratilidade ventricular preservada."
            )
        elif site_clean in ("pleural_right", "pleural_left"):
            is_right = "right" in site_clean
            findings_desc = (
                f"E-FAST Pleuropulmonar {'Direito' if is_right else 'Esquerdo'}: Deslizamento pleural ('lung sliding') presente, "
                "com linhas A fisiológicas e sinal da praia no Modo M. Ausência de pneumotórax neste hemitórax."
            )
        else:
            findings_desc = f"Varredura ultrassonográfica no sítio {anatomical_site}: Estruturas anatômicas avaliadas sem coleções agudas adicionais."

        examiner_message = f"Examinador entrega imagem do E-FAST: {findings_desc}"

    # 2. TORACOCENTESE DE ALÍVIO COM AGULHA
    elif proc_type_clean in ("puncture", "thoracocentesis") or "thoracocentesis" in site_clean:
        is_pneumo = "PNEUMO" in station_code or "pneumotórax" in sess["title"].lower()
        if is_pneumo:
            findings_desc = (
                "Descompressão torácica imediata com agulha no 2º EIC na linha hemiclavicular! "
                "Ocorre escape audível e vigoroso de ar sob alta pressão! O murmúrio vesicular retorna parcialmente, "
                "a turgência jugular atenua e a SatO2 eleva-se rapidamente para 93%."
            )
            is_positive_finding = True
        else:
            findings_desc = "Punção realizada com agulha no espaço intercostal. Não houve saída de ar sob pressão ou sangue."
        examiner_message = f"Procedimento de Toracocentese de Alívio executado: {findings_desc}"

    # 3. DRENAGEM TORÁCICA TUBULAR EM SELO D'ÁGUA
    elif proc_type_clean in ("drainage", "chest_tube") or "chest_tube" in site_clean:
        findings_desc = (
            "Dreno torácico tubular 32 Fr introduzido no 5º EIC na linha axilar média (triângulo de segurança) "
            "e conectado a selo d'água. Dreno posicionado com sucesso, fixado com ponto em bailarina. "
            "Observa-se oscilação adequada da coluna d'água e drenagem de pequena quantidade de secreção serossanguinolenta."
        )
        examiner_message = f"Drenagem Torácica Fechada: {findings_desc}"
        is_positive_finding = True

    # 4. MANOBRA DE HAMILTON (COMPRESSÃO BIMANUAL UTERINA)
    elif proc_type_clean in ("maneuver", "hamilton") or "hamilton" in site_clean:
        is_hpp = "HPP" in station_code or "hemorragia" in sess["title"].lower() or "atonia" in sess["title"].lower()
        if is_hpp:
            findings_desc = (
                "Manobra de compressão bimanual de Hamilton iniciada imediatamente: punho cerrado no fundo de saco anterior "
                "da vagina contra a parede anterior uterina e mão abdominal tracionando o fundo para frente. "
                "O útero contrai parcialmente sob a compressão com redução do sangramento vaginal em jato."
            )
            is_positive_finding = True
        else:
            findings_desc = "Manobra executada conforme a técnica obstétrica padrão."
        examiner_message = f"Manobra Obstétrica Beira-Leito: {findings_desc}"

    # 5. CARDIOVERSÃO ELÉTRICA SINCRONIZADA
    elif proc_type_clean in ("cardioversion",) or "cardioversion" in site_clean:
        is_tv = "TV" in station_code or "taquicardia" in sess["title"].lower()
        if is_tv:
            findings_desc = (
                "Pás de desfibrilador posicionadas com gel (infraclavicular direita e ápice cardíaco). "
                "Modo sincronizado ATIVADO, flag nas ondas R confirmado. Sedação rápida administrada. "
                "A equipe afasta-se e o choque de 100 Joules é disparado! O monitor acusa reversão imediata para Ritmo Sinusal, "
                "FC 84 bpm, pulsos amplos e PA normalizada em 115x75 mmHg!"
            )
            is_positive_finding = True
        else:
            findings_desc = "Cardioversão sincronizada realizada com choque disparado na onda R."
        examiner_message = f"Cardioversão Elétrica Sincronizada: {findings_desc}"

    # 6. ACESSO VENOSO PROFUNDO / INTRAÓSSEO
    elif proc_type_clean in ("vascular", "intraosseous") or "intraosseous" in site_clean or "central_vein" in site_clean:
        if "intraosseous" in site_clean or proc_type_clean == "intraosseous":
            findings_desc = (
                "Punção intraóssea realizada na tíbia proximal (2 cm abaixo e medial à tuberosidade tibial). "
                "Aspiração de medula óssea positiva e infusão livre de soro sem extravasamento. Via de emergência garantida."
            )
        else:
            findings_desc = (
                "Acesso venoso central obtido por punção de veia subclávia direita sob técnica de Seldinger. "
                "Refluxo venoso escuro livre e infusão em fluxo rápido confirmada."
            )
        examiner_message = f"Acesso Vascular de Urgência: {findings_desc}"
        is_positive_finding = True

    # OUTROS PROCEDIMENTOS
    else:
        findings_desc = f"Procedimento ({procedure_type} no sítio {anatomical_site}) realizado com sucesso pela técnica asséptica beira-leito."
        examiner_message = f"Procedimento Beira-Leito Realizado: {findings_desc}"

    action_record = {
        "action_type": "procedure",
        "procedure_type": procedure_type,
        "anatomical_site": anatomical_site,
        "findings": findings_desc,
        "is_positive": is_positive_finding,
        "elapsed_seconds": elapsed_seconds,
        "timestamp": now_iso
    }

    spoken_queue: list[dict[str, str]] = [
        {"speaker": "examinador", "text": examiner_message}
    ]

    actions.append(action_record)
    transcript.append({
        "sender": "examinador",
        "message": examiner_message,
        "timestamp": now_iso,
        "elapsed_seconds": elapsed_seconds,
        "action_payload": {
            "type": "procedure",
            "procedure_type": procedure_type,
            "anatomical_site": anatomical_site,
            "findings": findings_desc,
            "image_url": image_url
        }
    })

    with db_transaction(db, immediate=True):
        db.execute("""
            UPDATE osce_sessions
            SET actions_taken_json = ?, transcript_json = ?, elapsed_seconds = ?
            WHERE id = ?
        """, (
            json.dumps(actions, ensure_ascii=False),
            json.dumps(transcript, ensure_ascii=False),
            elapsed_seconds,
            session_id
        ))

    res_proc: dict[str, Any] = {
        "success": True,
        "procedure_type": procedure_type,
        "anatomical_site": anatomical_site,
        "findings": findings_desc,
        "examiner_message": examiner_message,
        "spoken_queue": spoken_queue,
        "elapsed_seconds": elapsed_seconds
    }

    if get_session_mode(actions) == "guided":
        barema_raw = json.loads(sess["checklist_barema_json"] or "{}")
        c_items = barema_raw.get("items", []) if isinstance(barema_raw, dict) else (barema_raw if isinstance(barema_raw, list) else [])
        res_proc["guided_feedback"] = evaluate_live_barema_progress(c_items, transcript, actions, elapsed_seconds)

    return res_proc


