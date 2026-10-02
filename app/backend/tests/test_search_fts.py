"""Testes de integração e regressão para o motor de busca FTS5 e filtros clínicos."""

import pytest


def test_search_empty_returns_empty_list(client):
    res = client.get("/api/search")
    assert res.status_code == 200
    assert res.get_json() == []


def test_search_fts_clinical_term(client):
    res = client.get("/api/search?q=infarto")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    if len(data) > 0:
        first = data[0]
        assert "id" in first
        assert "stem_snippet" in first
        assert "area" in first
        assert "institution_code" in first


def test_search_with_area_filter(client):
    res = client.get("/api/search?q=infarto&area=Cl%C3%ADnica%20M%C3%A9dica")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    for item in data:
        assert item["area"] == "Clínica Médica"


def test_search_with_institution_filter(client):
    res = client.get("/api/search?q=diagnostico&institution=ENARE")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    for item in data:
        assert item["institution_code"] == "ENARE"


def test_search_structured_filter_only(client):
    res = client.get("/api/search?area=Cirurgia&limit=5")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data, list)
    assert len(data) <= 5
    for item in data:
        assert item["area"] == "Cirurgia"
