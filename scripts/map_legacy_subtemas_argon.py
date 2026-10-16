#!/usr/bin/env python3
"""
Mapeamento Canônico de Subtemas Legados via Gemini 4 Argon.
Mapeia os 333 subtemas legados exatamente para os 170 macrotemas de taxonomy.json.
"""

import json
import os
import urllib.request
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "backend")
TAXONOMY_PATH = os.path.join(BACKEND_DIR, "data", "taxonomy.json")
UNMAPPED_PATH = os.path.join(BACKEND_DIR, "data", "unmapped_subtemas.json")
OUTPUT_PATH = os.path.join(BACKEND_DIR, "data", "legacy_subtemas_mapping.json")

def get_api_key():
    cfg_path = os.path.expanduser("~/.gemini/config/argon.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            return json.load(f)["apiKey"]
    raise RuntimeError("Chave GEMINI_API_KEY não encontrada em ~/.gemini/config/argon.json")

def call_argon(prompt: str) -> str:
    api_key = get_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]

def main():
    print("🚀 Carregando taxonomia oficial e subtemas legados...")
    with open(TAXONOMY_PATH) as f:
        tax = json.load(f)

    with open(UNMAPPED_PATH) as f:
        unmapped = json.load(f)

    # Agrupa legados por área
    legacy_by_area = {}
    canonical_by_area = {}

    for entry in tax:
        area = entry["area"]
        canonical_by_area[area] = [mt["theme"] for mt in entry["macroThemes"]]

    for item in unmapped:
        area = item["area"]
        legacy_by_area.setdefault(area, []).append(item["subtema"])

    final_mapping = {}

    for area in legacy_by_area:
        legacy_list = legacy_by_area[area]
        canonical_list = canonical_by_area.get(area, [])
        print(f"\n🩺 Mapeando {len(legacy_list)} subtemas de '{area}' com Gemini 4 Argon...")

        prompt = f"""Você é o Preceptor Chefe e Curador Médico de Residência Médica do MedQuest.
Temos uma lista de subtemas legados/específicos da área de {area} que precisam ser mapeados EXATAMENTE para um dos temas canônicos oficiais da plataforma.

LISTA DE TEMAS CANÔNICOS PERMITIDOS PARA {area}:
{json.dumps(canonical_list, ensure_ascii=False, indent=2)}

SUBTEMAS LEGADOS A MAPEAR:
{json.dumps(legacy_list, ensure_ascii=False, indent=2)}

DIRETRIZES MÉDICAS:
1. Para cada subtema legado, escolha o tema canônico mais adequado e focado para as provas de residência (USP, ENARE, UNICAMP).
2. O valor de destino DEVE ser uma string idêntica a um dos itens da LISTA DE TEMAS CANÔNICOS PERMITIDOS. Não crie novos temas.
3. Retorne um JSON no formato de dicionário:
{{
  "subtema_legado_1": "TEMA_CANONICO_EXATO",
  "subtema_legado_2": "TEMA_CANONICO_EXATO"
}}
"""
        response_text = call_argon(prompt)
        try:
            area_mapping = json.loads(response_text)
            # Validação estrita
            for k, v in area_mapping.items():
                if v not in canonical_list:
                    print(f"⚠️ Alerta: Tema de destino '{v}' para '{k}' não está na lista canônica! Procurando match aproximado...")
                    # fallback para melhor match
                    for c in canonical_list:
                        if c.lower() in v.lower() or v.lower() in c.lower():
                            area_mapping[k] = c
                            break
            final_mapping.update(area_mapping)
            print(f"✅ Área '{area}' mapeada: {len(area_mapping)} termos associados.")
        except Exception as e:
            print(f"❌ Erro ao parsear resposta da área {area}: {e}\nResposta: {response_text[:300]}")
            sys.exit(1)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_mapping, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Mapeamento concluído com sucesso!")
    print(f"📁 Salvo em: {OUTPUT_PATH} (Total de mapeamentos: {len(final_mapping)})")

if __name__ == "__main__":
    main()
