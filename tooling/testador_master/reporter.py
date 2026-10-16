"""
==============================================================================
MEDQUEST · TESTADOR MASTER: GERADOR DE RELATÓRIO E AUDITORIA (REPORTER)
==============================================================================
Gera e atualiza docs/RELATORIO_TESTADOR_MASTER.md e dados estruturados em JSON
com KPIs clínicos, cobertura de recursos e histórico de anomalias.
==============================================================================
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class MasterReporter:
    """Consolidador de dados e gerador de relatórios executivos em Markdown."""

    def __init__(self, output_md: str, output_json: str):
        self.output_md = Path(output_md)
        self.output_json = Path(output_json)
        self.historico_acoes: List[Dict[str, Any]] = []
        self.anomalias_detectadas: List[Dict[str, Any]] = []
        self.metricas_inicio: str = datetime.now(timezone.utc).isoformat()

    def registrar_acao(
        self,
        persona_id: str,
        resultado: Any,
        pensamento: str = ""
    ) -> None:
        """Registra uma ação concluída na memória do repórter."""
        registro = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "persona_id": persona_id,
            "tipo_acao": resultado.tipo_acao,
            "alvo": resultado.alvo,
            "sucesso": resultado.sucesso,
            "status_code": resultado.status_code,
            "latencia_ms": resultado.latencia_ms,
            "anomalias": resultado.anomalias,
            "pensamento": pensamento,
        }
        self.historico_acoes.append(registro)
        if resultado.anomalias:
            for anom in resultado.anomalias:
                self.anomalias_detectadas.append({
                    "timestamp": registro["timestamp"],
                    "persona_id": persona_id,
                    "alvo": resultado.alvo,
                    "acao": resultado.tipo_acao,
                    "descricao": anom,
                })

    def salvar_dados_json(self, cobertura: Dict[str, Any], oracle_stats: Dict[str, Any]) -> None:
        """Exporta o relatório consolidado em JSON com métricas acumuladas globais."""
        self.output_json.parent.mkdir(parents=True, exist_ok=True)
        total_acoes = len(self.historico_acoes)
        sucessos = sum(1 for a in self.historico_acoes if a.get("sucesso", True))
        taxa_sucesso = (sucessos / total_acoes * 100.0) if total_acoes > 0 else 100.0
        latencia_media = (
            sum(a.get("latencia_ms", 0.0) for a in self.historico_acoes) / total_acoes
            if total_acoes > 0
            else 0.0
        )
        dados = {
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "iniciado_em": self.metricas_inicio,
            "total_acoes": total_acoes,
            "total_sucessos": sucessos,
            "taxa_sucesso": round(taxa_sucesso, 1),
            "latencia_media_ms": round(latencia_media, 1),
            "cobertura": cobertura,
            "oracle_stats": oracle_stats,
            "total_anomalias": len(self.anomalias_detectadas),
            "anomalias": self.anomalias_detectadas,
            "historico": self.historico_acoes[-200:],  # Últimas 200 ações para manter o feed enxuto
        }
        with open(self.output_json, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)

    def gerar_relatorio_markdown(
        self,
        cobertura: Dict[str, Any],
        oracle_stats: Dict[str, Any],
        personas_catalogo: Dict[str, Any]
    ) -> None:
        """Gera documentação Markdown de alto impacto para revisão humana."""
        self.output_md.parent.mkdir(parents=True, exist_ok=True)

        total_acoes = len(self.historico_acoes)
        sucessos = sum(1 for a in self.historico_acoes if a["sucesso"])
        taxa_sucesso = (sucessos / total_acoes * 100.0) if total_acoes > 0 else 100.0
        latencia_media = (
            sum(a["latencia_ms"] for a in self.historico_acoes) / total_acoes
            if total_acoes > 0
            else 0.0
        )

        md = []
        md.append("# 🩺 MedQuest · Relatório do Testador Master (Auditoria Ostensiva)")
        md.append("")
        md.append(f"> **Gerado em**: `{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}`  ")
        md.append(f"> **Total de Ciclos/Ações**: `{total_acoes}` | **Taxa de Sucesso**: `{taxa_sucesso:.1f}%`  ")
        md.append(f"> **Latência Média**: `{latencia_media:.1f}ms`  ")
        md.append("")
        md.append("---")
        md.append("")

        # 1. Resumo de Cobertura
        md.append("## 1. Cobertura de Recursos e Telas")
        md.append("")
        md.append(f"- **Cobertura Geral**: `{cobertura.get('percentual_geral', 0)}%` ({cobertura.get('nodes_visitados', 0)}/{cobertura.get('total_nodes', 0)} recursos explorados)")
        md.append(f"- **Telas Frontend (Next.js)**: `{cobertura.get('frontend_pct', 0)}%`")
        md.append(f"- **Rotas de API (Flask)**: `{cobertura.get('api_pct', 0)}%`")
        md.append(f"- **Transições/Fluxos Testados**: `{cobertura.get('total_transicoes', 0)}`")
        md.append("")

        # 2. Oráculo Médico & Guardrails
        md.append("## 2. Oráculo de Guardrails & Regras de Negócio")
        md.append("")
        md.append("| Guardrail | Status | Ocorrências |")
        md.append("| :--- | :---: | :---: |")

        viol_imut = oracle_stats.get("violacoes_imutabilidade", 0)
        status_imut = "🟢 100% Protegido" if viol_imut == 0 else "🔴 VIOLAÇÃO DETECTADA"
        md.append(f"| **Imutabilidade de Comentários Médicos** | {status_imut} | `{viol_imut}` |")

        anom_fsrs = oracle_stats.get("anomalias_fsrs", 0)
        status_fsrs = "🟢 Calibrado (D+1+ / D+7)" if anom_fsrs == 0 else "🟡 Anomalias Observadas"
        md.append(f"| **Agendamento FSRS v6 (Retenção 85%)** | {status_fsrs} | `{anom_fsrs}` |")

        anom_tri = oracle_stats.get("anomalias_tri", 0)
        status_tri = "🟢 Cálculos Finitos e Válidos" if anom_tri == 0 else "🟡 Inconsistência TRI"
        md.append(f"| **Teoria de Resposta ao Item (TRI)** | {status_tri} | `{anom_tri}` |")
        md.append("")

        # 3. Personas Utilizadas
        md.append("## 3. Personas Médicas Simuladas")
        md.append("")
        md.append("| Persona | Título | Ações Executadas | Taxa Alvo |")
        md.append("| :--- | :--- | :---: | :---: |")
        for pid, persona in personas_catalogo.items():
            qtd_persona = sum(1 for a in self.historico_acoes if a["persona_id"] == pid)
            md.append(f"| {persona.icone} **{persona.nome}** | {persona.titulo} | `{qtd_persona}` | `{persona.taxa_acerto_esperada*100:.0f}%` |")
        md.append("")

        # 4. Anomalias e Pontos de Atenção
        md.append("## 4. Anomalias & Oportunidades Identificadas")
        md.append("")
        if not self.anomalias_detectadas:
            md.append("✨ **Nenhuma anomalia crítica foi encontrada.** Todos os fluxos, contratos de rotas e guardrails comportaram-se perfeitamente.")
        else:
            md.append("| Momento | Persona | Alvo / Rota | Descrição da Anomalia |")
            md.append("| :--- | :--- | :--- | :--- |")
            for anom in self.anomalias_detectadas[-15:]:
                md.append(f"| `{anom['timestamp'][11:19]}` | `{anom['persona_id']}` | `{anom['alvo']}` | {anom['descricao']} |")
        md.append("")
        md.append("---")
        md.append("*Relatório gerado automaticamente pelo MedQuest Master Tester.*")

        with open(self.output_md, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
