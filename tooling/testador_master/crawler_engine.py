"""
==============================================================================
MEDQUEST · TESTADOR MASTER: MOTOR DE GRAFO E COBERTURA (CRAWLER ENGINE)
==============================================================================
Mapeia rotas de API, telas e fluxos de navegação do MedQuest.
Rastreia nós visitados, calcula taxa de cobertura e guia as personas
para explorar funcionalidades ainda não tocadas.
==============================================================================
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class NodeGrafo:
    """Representa uma tela, aba ou endpoint da plataforma."""
    id: str
    nome: str
    tipo: str  # 'tela_frontend', 'rota_api', 'fluxo_negocio'
    visitas: int = 0
    ultima_visita: Optional[str] = None
    latencias_ms: List[float] = field(default_factory=list)
    falhas: int = 0


@dataclass
class ArestaGrafo:
    """Representa uma ação médica ou transição entre telas/endpoints."""
    origem: str
    destino: str
    acao: str
    execucoes: int = 0
    ultima_execucao: Optional[str] = None


class MedQuestGraph:
    """Grafo de navegação e cobertura do ecossistema MedQuest."""

    def __init__(self, caminho_persistente: Optional[str] = None):
        self.caminho_persistente = caminho_persistente
        self.nodes: Dict[str, NodeGrafo] = {}
        self.arestas: Dict[str, ArestaGrafo] = {}
        self._inicializar_mapa_padrao()

    def _inicializar_mapa_padrao(self):
        """Registra os recursos canônicos do MedQuest."""
        recursos_iniciais = [
            # Telas Frontend
            ("tela:/estudar", "Banco de Questões", "tela_frontend"),
            ("tela:/simulado", "Cockpit de Simulados", "tela_frontend"),
            ("tela:/revisao-ativa", "Flashcards FSRS", "tela_frontend"),
            ("tela:/osce", "Estações Práticas OSCE", "tela_frontend"),
            ("tela:/analise", "Dashboard TRI & Estatísticas", "tela_frontend"),
            ("tela:/planner", "Cronograma & Metas", "tela_frontend"),
            ("tela:/buscar", "Busca Semântica & FTS", "tela_frontend"),
            ("tela:/temas", "Navegação Taxonômica", "tela_frontend"),
            ("tela:/cobertura", "Radar de Editais & Cobertura", "tela_frontend"),
            # Rotas API Backend
            ("api:/api/questions", "Listar Questões & Filtros", "rota_api"),
            ("api:/api/questions/answer", "Submeter Resposta & FSRS", "rota_api"),
            ("api:/api/questions/simulado", "Geração de Caderno de Simulado", "rota_api"),
            ("api:/api/flashcards", "Listar Baralhos & Cards", "rota_api"),
            ("api:/api/flashcards/review", "Avaliar Card FSRS v6", "rota_api"),
            ("api:/api/osce/cases", "Casos Clínicos OSCE", "rota_api"),
            ("api:/api/osce/evaluate", "Avaliação de Rubrica OSCE", "rota_api"),
            ("api:/api/stats/overview", "Visão Geral de Desempenho", "rota_api"),
            ("api:/api/stats/tri", "Motor TRI & Percentis", "rota_api"),
            ("api:/api/stats/radar", "Radar Institucional", "rota_api"),
            ("api:/api/plan", "Plano de Estudos & Metas", "rota_api"),
            ("api:/api/themes", "Árvore de Especialidades Médicas", "rota_api"),
            ("api:/api/buscar", "Endpoint de Busca FTS", "rota_api"),
            ("api:/api/ai/analyze-image", "Analisador Multimodal de Imagens Médicas", "rota_api"),
        ]

        for rid, nome, tipo in recursos_iniciais:
            self.nodes[rid] = NodeGrafo(id=rid, nome=nome, tipo=tipo)

    @staticmethod
    def normalizar_node_id(node_id: str) -> str:
        """Normaliza identificadores dinâmicos (IDs numéricos, UUIDs e query strings) para rotas canônicas."""
        import re
        if not node_id:
            return node_id
        # Remove query strings: /api/search?q=... -> /api/search
        if "?" in node_id:
            node_id = node_id.split("?")[0]
        # Substitui UUIDs: /api/osce/sessions/630425c1-.../finish -> /api/osce/sessions/:uuid/finish
        node_id = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", ":uuid", node_id)
        # Substitui IDs numéricos: /api/questions/12230/attempt -> /api/questions/:id/attempt
        node_id = re.sub(r"/\d+(/|$)", r"/:id\1", node_id)
        return node_id

    def registrar_visita(
        self,
        node_id: str,
        sucesso: bool = True,
        latencia_ms: float = 0.0,
        tipo_padrao: str = "rota_api"
    ) -> None:
        """Registra visita e telemetria em um nó do grafo."""
        node_id = self.normalizar_node_id(node_id)
        agora = datetime.now(timezone.utc).isoformat()
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeGrafo(
                id=node_id,
                nome=node_id.replace("api:", "").replace("tela:", ""),
                tipo=tipo_padrao,
            )

        node = self.nodes[node_id]
        node.visitas += 1
        node.ultima_visita = agora
        if latencia_ms > 0:
            node.latencias_ms.append(latencia_ms)
            if len(node.latencias_ms) > 100:
                node.latencias_ms.pop(0)

        if not sucesso:
            node.falhas += 1

    def registrar_transicao(self, origem: str, destino: str, acao: str) -> None:
        """Registra uma aresta de transição entre recursos."""
        origem = self.normalizar_node_id(origem)
        destino = self.normalizar_node_id(destino)
        chave = f"{origem} -> {destino} ({acao})"
        agora = datetime.now(timezone.utc).isoformat()
        if chave not in self.arestas:
            self.arestas[chave] = ArestaGrafo(origem=origem, destino=destino, acao=acao)
        aresta = self.arestas[chave]
        aresta.execucoes += 1
        aresta.ultima_execucao = agora

    def calcular_cobertura(self) -> Dict[str, Any]:
        """Calcula métricas detalhadas de cobertura do ecossistema."""
        total_nodes = len(self.nodes)
        nodes_visitados = sum(1 for n in self.nodes.values() if n.visitas > 0)
        pct = (nodes_visitados / total_nodes * 100.0) if total_nodes > 0 else 0.0

        # Separação por tipo
        frontend_nodes = [n for n in self.nodes.values() if n.tipo == "tela_frontend"]
        api_nodes = [n for n in self.nodes.values() if n.tipo == "rota_api"]

        fe_visitados = sum(1 for n in frontend_nodes if n.visitas > 0)
        api_visitados = sum(1 for n in api_nodes if n.visitas > 0)

        return {
            "percentual_geral": round(pct, 1),
            "total_nodes": total_nodes,
            "nodes_visitados": nodes_visitados,
            "frontend_pct": round(fe_visitados / len(frontend_nodes) * 100.0, 1) if frontend_nodes else 0.0,
            "api_pct": round(api_visitados / len(api_nodes) * 100.0, 1) if api_nodes else 0.0,
            "total_transicoes": len(self.arestas),
        }

    def obter_nos_menos_explorados(self, limite: int = 5) -> List[NodeGrafo]:
        """Identifica os nós com menor frequência de teste para priorização."""
        ordenados = sorted(self.nodes.values(), key=lambda n: (n.visitas, n.falhas))
        return ordenados[:limite]

    def salvar_em_disco(self, caminho: Optional[str] = None) -> None:
        """Persiste o grafo atual em formato JSON."""
        target = caminho or self.caminho_persistente
        if not target:
            return
        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
            "cobertura": self.calcular_cobertura(),
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "arestas": {k: asdict(v) for k, v in self.arestas.items()},
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)

    def carregar_de_disco(self, caminho: Optional[str] = None) -> bool:
        """Carrega grafo previamente explorado."""
        target = caminho or self.caminho_persistente
        if not target:
            return False
        p = Path(target)
        if not p.exists():
            return False
        try:
            with open(p, "r", encoding="utf-8") as f:
                dados = json.load(f)
            for k, node_data in dados.get("nodes", {}).items():
                self.nodes[k] = NodeGrafo(**node_data)
            for k, aresta_data in dados.get("arestas", {}).items():
                self.arestas[k] = ArestaGrafo(**aresta_data)
            return True
        except Exception:
            return False
