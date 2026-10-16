"""
Testes unitários e de integração para o Analisador Multimodal de Exames Médicos (Medical Vision).
"""

import base64
import io
import pytest
from PIL import Image

from api import create_app
from api.medical_vision import (
    extrair_alerta_sala_vermelha,
    otimizar_imagem_para_analise,
    analisar_exame_imagem,
    _gerar_laudo_fallback,
)


@pytest.fixture
def client():
    app = create_app(testing=True)
    with app.test_client() as c:
        yield c


def _criar_imagem_teste_bytes(largura: int = 200, altura: int = 200, cor: str = "red") -> bytes:
    """Gera bytes de imagem JPEG sintética para testes sem rede."""
    img = Image.new("RGB", (largura, altura), color=cor)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_otimizacao_imagem_redimensiona_proporcionalmente():
    bytes_grandes = _criar_imagem_teste_bytes(2000, 1000)
    otimizados, mime = otimizar_imagem_para_analise(bytes_grandes, max_dimensao=1200)

    assert mime == "image/jpeg"
    with Image.open(io.BytesIO(otimizados)) as img:
        assert max(img.size) <= 1200
        assert img.size[0] == 1200
        assert img.size[1] == 600


def test_extracao_alerta_sala_vermelha():
    laudo_critico = (
        "🚨 [ALERTA DE EMERGÊNCIA - SALA VERMELHA] IAM com supra de ST em parede anterior: Acionar hemodinâmica imediata.\n"
        "Passo 1: Ritmo sinusal com supradesnivelamento em V1-V4."
    )
    alerta = extrair_alerta_sala_vermelha(laudo_critico)
    assert alerta is not None
    assert "IAM com supra de ST" in alerta

    laudo_eletivo = (
        "## Avaliação Semiológica do ECG\n"
        "Ritmo sinusal regular, FC 72 bpm, eixo elétrico preservado."
    )
    assert extrair_alerta_sala_vermelha(laudo_eletivo) is None


def test_geracao_laudo_fallback_deterministico():
    laudo_ecg = _gerar_laudo_fallback("ecg", None, "erro_simulado")
    assert "FMRP-USP" in laudo_ecg
    assert "Passo 1" in laudo_ecg
    assert "🚨 [ALERTA DE EMERGÊNCIA - SALA VERMELHA]" in laudo_ecg

    laudo_rx = _gerar_laudo_fallback("rx_torax", None, "erro_simulado")
    assert "ABCDE" in laudo_rx
    assert "🚨 [ALERTA DE EMERGÊNCIA - SALA VERMELHA]" in laudo_rx


def test_analisar_exame_imagem_fluxo_integrado():
    bytes_img = _criar_imagem_teste_bytes()
    resultado = analisar_exame_imagem(bytes_img, modalidade="ecg")

    assert resultado["sucesso"] is True
    assert resultado["modalidade_solicitada"] == "ecg"
    assert len(resultado["laudo_semiologico"]) > 30



def test_api_route_analyze_image_missing_image(client):
    resp = client.post("/api/ai/analyze-image", json={})
    assert resp.status_code == 400
    dados = resp.get_json()
    assert dados["code"] == "MISSING_IMAGE"


def test_api_route_analyze_image_base64_ecg(client):
    bytes_img = _criar_imagem_teste_bytes(100, 100, "white")
    b64_str = base64.b64encode(bytes_img).decode("utf-8")

    payload = {
        "image_base64": b64_str,
        "modality": "ecg",
        "clinical_context": "Homem 58 anos com dor torácica retroesternal há 40 minutos",
    }
    resp = client.post("/api/ai/analyze-image", json=payload)
    assert resp.status_code == 200

    dados = resp.get_json()
    assert dados["sucesso"] is True
    assert "laudo_semiologico" in dados
    assert dados["tempo_processamento_ms"] > 0
    assert "alerta_sala_vermelha" in dados
    assert len(dados["laudo_semiologico"]) > 30


def test_api_route_analyze_image_multipart(client):
    bytes_img = _criar_imagem_teste_bytes(150, 150, "gray")
    data = {
        "image": (io.BytesIO(bytes_img), "rx_torax.jpg", "image/jpeg"),
        "modality": "rx_torax",
        "clinical_context": "Mulher 35 anos com dispneia e dor pleurítica à direita",
    }
    resp = client.post(
        "/api/ai/analyze-image",
        data=data,
        content_type="multipart/form-data"
    )
    assert resp.status_code == 200

    dados = resp.get_json()
    assert dados["sucesso"] is True
    assert "ABCDE" in dados["laudo_semiologico"] or "SALA VERMELHA" in dados["laudo_semiologico"] or "Radiografia" in dados["laudo_semiologico"] or "dispneia" in dados["laudo_semiologico"].lower()


def test_api_route_analyze_image_tc_torax_e_abdome(client):
    bytes_img = _criar_imagem_teste_bytes(120, 120, "black")
    b64_str = base64.b64encode(bytes_img).decode("utf-8")

    # Teste TC de Tórax
    payload_torax = {
        "image_base64": b64_str,
        "modality": "tc_torax",
        "clinical_context": "Suspeita de TEP com hipoxemia súbita e taquicardia",
    }
    resp_torax = client.post("/api/ai/analyze-image", json=payload_torax)
    assert resp_torax.status_code == 200
    dados_torax = resp_torax.get_json()
    assert dados_torax["sucesso"] is True
    assert dados_torax["modalidade_solicitada"] == "tc_torax"
    assert "TEP" in dados_torax["laudo_semiologico"] or "Tomografia" in dados_torax["laudo_semiologico"] or "Avaliação Semiológica" in dados_torax["laudo_semiologico"]

    # Teste TC de Abdome
    payload_abdome = {
        "image_base64": b64_str,
        "modality": "tc_abdome",
        "clinical_context": "Dor em fossa ilíaca direita com febre e Blumberg positivo",
    }
    resp_abdome = client.post("/api/ai/analyze-image", json=payload_abdome)
    assert resp_abdome.status_code == 200
    dados_abdome = resp_abdome.get_json()
    assert dados_abdome["sucesso"] is True
    assert dados_abdome["modalidade_solicitada"] == "tc_abdome"

