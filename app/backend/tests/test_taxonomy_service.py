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

    # Empty query should return all subtemas
    all_sub = search_subtemas("")
    assert len(all_sub) == 170


def test_find_area_for_nonexistent_subtema():
    assert find_area_for_subtema("Subtema Inexistente XYZ") is None


def test_load_raw_taxonomy_fallback_missing_files(monkeypatch):
    import api.services.taxonomy as taxonomy

    # Reset cache
    monkeypatch.setattr(taxonomy, "_TAXONOMY_CACHE", None)
    monkeypatch.setattr(taxonomy, "_SUBTEMA_TO_AREA", None)

    # Mock os.path.exists to return False for all paths
    monkeypatch.setattr("os.path.exists", lambda path: False)

    tax = taxonomy._load_raw_taxonomy()
    assert tax == {}
    assert taxonomy.get_areas() == []
    assert taxonomy.get_subtemas() == []


def test_load_raw_taxonomy_fallback_invalid_file(monkeypatch):
    import api.services.taxonomy as taxonomy

    # Reset cache
    monkeypatch.setattr(taxonomy, "_TAXONOMY_CACHE", None)
    monkeypatch.setattr(taxonomy, "_SUBTEMA_TO_AREA", None)

    # Mock os.path.exists to return True
    monkeypatch.setattr("os.path.exists", lambda path: True)

    # Mock builtins.open to raise Exception when reading
    def mock_open(*args, **kwargs):
        raise OSError("Permission denied or corrupt file")

    monkeypatch.setattr("builtins.open", mock_open)

    tax = taxonomy._load_raw_taxonomy()
    assert tax == {}
