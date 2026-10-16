"""
==============================================================================
MEDQUEST · TESTADOR MASTER: GERADOR DE REPRODUÇÃO ISOLADA (AUTO-REPRO)
==============================================================================
Gera scripts de teste pytest isolados em tests/repros/ sempre que uma falha,
anomalia ou quebra de contrato de API for detectada durante a execução.
==============================================================================
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class ReproGenerator:
    """Gerador automático de suítes de reprodução minimalistas."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def gerar_repro_api(
        self,
        acao: str,
        endpoint: str,
        metodo: str,
        payload: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, Any]],
        status_code: Optional[int],
        resposta_erro: Any,
        anomalias: list,
    ) -> Path:
        """Gera um arquivo test_repro_*.py pronto para execução via pytest."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_seguro = re.sub(r"[^a-zA-Z0-9_]", "_", f"{acao}_{endpoint}").strip("_")[:40]
        arquivo_alvo = self.output_dir / f"test_repro_{timestamp}_{nome_seguro}.py"

        payload_json = json.dumps(payload or {}, indent=4, ensure_ascii=False)
        headers_json = json.dumps(headers or {}, indent=4, ensure_ascii=False)
        anomalias_formatadas = "\n".join(f"# - {a}" for a in anomalias)

        conteudo = f'''"""
TESTE DE REPRODUÇÃO AUTOMÁTICA GERADO PELO TESTADOR MASTER
Data: {datetime.now().isoformat()}
Ação: {acao}
Endpoint: {endpoint}
Status Observado: {status_code}

Anomalias Identificadas:
{anomalias_formatadas}
"""

import pytest
from api import create_app


@pytest.fixture
def client():
    app = create_app(testing=True)
    with app.test_client() as c:
        yield c


def test_repro_{nome_seguro}(client):
    endpoint = "{endpoint}"
    payload = {payload_json}
    headers = {headers_json}

    # Dispara a requisição que manifestou a anomalia
    metodo = "{metodo.upper()}"
    if metodo == "POST":
        resp = client.post(endpoint, json=payload, headers=headers)
    elif metodo == "PUT":
        resp = client.put(endpoint, json=payload, headers=headers)
    elif metodo == "DELETE":
        resp = client.delete(endpoint, headers=headers)
    else:
        resp = client.get(endpoint, headers=headers)

    # Asserções de conformidade
    assert resp.status_code in (200, 201), f"Esperado sucesso, recebido {{resp.status_code}}: {{resp.get_data(as_text=True)}}"
'''
        with open(arquivo_alvo, "w", encoding="utf-8") as f:
            f.write(conteudo)

        return arquivo_alvo
