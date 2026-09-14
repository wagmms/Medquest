from api.services.taxonomy import (
    find_area_for_subtema,
    get_areas,
    get_subtemas,
    get_taxonomy,
    is_valid_subtema,
    search_subtemas,
)


def test_get_taxonomy_and_areas():
    tax = get_taxonomy()
    assert len(tax) == 5
    areas = get_areas()
    assert len(areas) == 5
    assert "Cirurgia" in areas
    assert "Pediatria" in areas
    assert "Clínica Médica" in areas
    assert "Ginecologia e Obstetrícia" in areas
    assert "Medicina Preventiva" in areas


def test_get_subtemas_count():
    all_sub = get_subtemas()
    assert len(all_sub) == 170
    cir_sub = get_subtemas("Cirurgia")
    assert len(cir_sub) == 48
    ped_sub = get_subtemas("Pediatria")
    assert len(ped_sub) == 28


def test_is_valid_subtema_and_find_area():
    assert is_valid_subtema("Cirurgia", "Abdome Agudo Inflamatório (Apendicite e Diverticulite Aguda)")
    assert not is_valid_subtema("Pediatria", "Abdome Agudo Inflamatório (Apendicite e Diverticulite Aguda)")

    area = find_area_for_subtema("Reanimação Neonatal e Assistência em Sala de Parto")
    assert area == "Pediatria"


def test_search_subtemas():
    matches = search_subtemas("apendicite")
    assert any("Apendicite" in m for m in matches)
