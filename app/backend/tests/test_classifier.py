import pytest
from api.services.classifier import (
    CirurgiaClassifier,
    PediatriaClassifier,
    classify,
    get_classifier,
    load_canonical_taxonomy,
)


@pytest.fixture(scope="module")
def canonical_tax():
    return load_canonical_taxonomy()


def test_taxonomy_loads_170_canonical_themes(canonical_tax):
    """Verifica que a taxonomia canônica oficial dos 170 temas é carregada com precisão."""
    assert canonical_tax is not None
    assert set(canonical_tax.keys()) == {
        "Cirurgia",
        "Clínica Médica",
        "Ginecologia e Obstetrícia",
        "Pediatria",
        "Medicina Preventiva",
    }
    total_themes = sum(len(themes) for themes in canonical_tax.values())
    assert total_themes == 170, f"Esperado 170 temas, obtido {total_themes}"


def test_cirurgia_fournier_and_wounds(canonical_tax):
    q = {
        "stem": "Paciente com dor perineal intensa, crepitação e necrose de partes moles em região escrotal com extensão perianal.",
        "topic": "Fournier",
        "explanation": "Diagnóstico de gangrena de Fournier / fasceíte necrosante.",
    }
    res = classify(q, target_area="Cirurgia")
    assert res.target_area == "Cirurgia"
    assert res.target_subtema == "Cicatrização, Tratamento de Feridas, Enxertos e Retalhos"
    assert res.target_subtema in canonical_tax["Cirurgia"]


def test_cirurgia_pediatric_burns_vs_adult(canonical_tax):
    q_ped = {
        "stem": "Lactente de 1 ano de idade sofreu queimadura por escaldadura com água fervente no tronco.",
        "explanation": "Reposição volêmica pelo Parkland pediátrico.",
    }
    res_ped = classify(q_ped, target_area="Cirurgia")
    assert res_ped.target_subtema == "Particularidades das Queimaduras na Faixa Etária Pediátrica"
    assert res_ped.target_subtema in canonical_tax["Cirurgia"]

    q_adult = {
        "stem": "Homem de 35 anos vítima de explosão apresenta queimaduras de 2º e 3º graus em 40% da superfície corporal queimada (SCQ).",
        "explanation": "Ressuscitação volêmica pela fórmula de Parkland.",
    }
    res_adult = classify(q_adult, target_area="Cirurgia")
    assert res_adult.target_subtema == "Atendimento ao Paciente Queimado e Reposição Volêmica"
    assert res_adult.target_subtema in canonical_tax["Cirurgia"]


def test_cirurgia_appendicitis_and_diverticulitis(canonical_tax):
    q = {
        "stem": "Paciente com dor em fossa ilíaca direita, sinal de Blumberg positivo e leucocitose.",
        "explanation": "Quadro clássico de apendicite aguda (abdome agudo inflamatório).",
    }
    res = classify(q, target_area="Cirurgia")
    assert res.target_subtema == "Abdome Agudo Inflamatório (Apendicite e Diverticulite Aguda)"
    assert res.target_subtema in canonical_tax["Cirurgia"]


def test_pediatria_multidisciplinary_deviation_to_cirurgia(canonical_tax):
    # Tumor de Wilms -> Cirurgia Uro-Oncologia
    q_wilms = {
        "stem": "Criança de 3 anos levada à consulta por massa abdominal no flanco esquerdo assintomática.",
        "explanation": "Nefroblastoma / Tumor de Wilms.",
    }
    res_wilms = classify(q_wilms, target_area="Pediatria")
    assert res_wilms.target_area == "Cirurgia"
    assert res_wilms.target_subtema == "Uro-Oncologia: Câncer de Próstata, Rim, Bexiga e Testículo"
    assert res_wilms.target_subtema in canonical_tax["Cirurgia"]

    # Ortopedia Pediátrica (Ortolani/Barlow) -> Cirurgia
    q_ddh = {
        "stem": "Recém-nascido no alojamento conjunto apresenta manobra de Ortolani positiva à direita.",
        "explanation": "Displasia do desenvolvimento do quadril.",
    }
    res_ddh = classify(q_ddh, target_area="Pediatria")
    assert res_ddh.target_area == "Cirurgia"
    assert res_ddh.target_subtema == "Ortopedia Pediátrica: Displasia do Quadril, Pé Torto e Epifisiólise"
    assert res_ddh.target_subtema in canonical_tax["Cirurgia"]


def test_pediatria_multidisciplinary_deviation_to_clinica(canonical_tax):
    # Acidentes por animais peçonhentos -> Clínica Médica
    q_tox = {
        "stem": "Menino de 6 anos picado por escorpião amarelo (Tityus serrulatus) apresentando sudorese e salivação.",
        "explanation": "Acidente escorpiônico moderado.",
    }
    res_tox = classify(q_tox, target_area="Pediatria")
    assert res_tox.target_area == "Clínica Médica"
    assert res_tox.target_subtema == "Toxicologia Clínica e Acidentes por Animais Peçonhentos"
    assert res_tox.target_subtema in canonical_tax["Clínica Médica"]

    # DM1 / Cetoacidose -> Clínica Médica
    q_dka = {
        "stem": "Escolar de 8 anos com poliúria, polidipsia e perda ponderal, evoluindo com respiração de Kussmaul e cetonúria.",
        "explanation": "Cetoacidose diabética inaugural em DM1.",
    }
    res_dka = classify(q_dka, target_area="Pediatria")
    assert res_dka.target_area == "Clínica Médica"
    assert res_dka.target_subtema == "Diabetes Mellitus: Metas Glicêmicas, Complicações e Tratamento"
    assert res_dka.target_subtema in canonical_tax["Clínica Médica"]


def test_pediatria_canonical_themes(canonical_tax):
    # Reanimação Neonatal
    q_resusc = {
        "stem": "RN a termo, apneico após nascimento e passos iniciais na sala de parto. Frequência cardíaca = 80 bpm.",
        "explanation": "Indicação de ventilação com pressão positiva (VPP) em sala de parto.",
    }
    res_resusc = classify(q_resusc, target_area="Pediatria")
    assert res_resusc.target_area == "Pediatria"
    assert res_resusc.target_subtema == "Reanimação Neonatal e Assistência em Sala de Parto"
    assert res_resusc.target_subtema in canonical_tax["Pediatria"]

    # Vacinas PNI
    q_vac = {
        "stem": "Lactente de 2 meses é levado ao posto de saúde para atualização do calendário vacinal.",
        "explanation": "Administração de Pentavalente, VIP, Pneumo 10 e Rotavírus.",
    }
    res_vac = classify(q_vac, target_area="Pediatria")
    assert res_vac.target_area == "Pediatria"
    assert res_vac.target_subtema == "Calendário Vacinal do PNI e Imunizações Especiais"
    assert res_vac.target_subtema in canonical_tax["Pediatria"]


def test_classifier_registry_caching():
    c1 = get_classifier("Cirurgia")
    c2 = get_classifier("cirurgia")
    assert c1 is c2
    assert isinstance(c1, CirurgiaClassifier)

    p1 = get_classifier("Pediatria")
    p2 = get_classifier("pediatria")
    assert p1 is p2
    assert isinstance(p1, PediatriaClassifier)
