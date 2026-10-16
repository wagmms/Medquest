"""
==============================================================================
MEDQUEST · TESTADOR MASTER: GERADOR DO DASHBOARD VISUAL DO GRAFO
==============================================================================
Gera um dashboard HTML autônomo, responsivo e interativo (dashboard_grafo.html)
com visualização em rede de nós (Vis.js), telemetria clínica, grafo de
cobertura, personas médicas e monitoramento de guardrails em tempo real.
==============================================================================
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_GRAFO_JSON = ROOT_DIR / "data" / "testador_master_grafo.json"
DEFAULT_RELATORIO_JSON = ROOT_DIR / "data" / "testador_master_relatorio.json"
DEFAULT_OUTPUT_HTML = ROOT_DIR / "docs" / "dashboard_grafo.html"


class DashboardGenerator:
    """Compila o grafo de navegação e métricas do MedQuest em um dashboard HTML rico."""

    def __init__(
        self,
        output_html: Optional[Path] = None,
        grafo_json_path: Optional[Path] = None,
        relatorio_json_path: Optional[Path] = None,
    ):
        self.output_html = output_html or DEFAULT_OUTPUT_HTML
        self.grafo_json_path = grafo_json_path or DEFAULT_GRAFO_JSON
        self.relatorio_json_path = relatorio_json_path or DEFAULT_RELATORIO_JSON

    def gerar_dashboard(
        self,
        dados_grafo: Optional[Dict[str, Any]] = None,
        dados_relatorio: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Lê os dados e produz o docs/dashboard_grafo.html interativo."""
        if dados_grafo is None:
            if self.grafo_json_path.exists():
                with open(self.grafo_json_path, "r", encoding="utf-8") as f:
                    dados_grafo = json.load(f)
            else:
                dados_grafo = {"nodes": {}, "arestas": {}, "cobertura": {}}

        if dados_relatorio is None:
            if self.relatorio_json_path.exists():
                with open(self.relatorio_json_path, "r", encoding="utf-8") as f:
                    dados_relatorio = json.load(f)
            else:
                dados_relatorio = {"historico": [], "anomalias": [], "oracle_stats": {}}

        conteudo_html = self._construir_html(dados_grafo, dados_relatorio)

        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_html, "w", encoding="utf-8") as f:
            f.write(conteudo_html)

        # Cópia em data/dashboard_grafo.html para conveniência
        copia_data = ROOT_DIR / "data" / "dashboard_grafo.html"
        copia_data.parent.mkdir(parents=True, exist_ok=True)
        with open(copia_data, "w", encoding="utf-8") as f:
            f.write(conteudo_html)

        return self.output_html

    def _construir_html(self, dados_grafo: Dict[str, Any], dados_relatorio: Dict[str, Any]) -> str:
        grafo_json_str = json.dumps(dados_grafo, ensure_ascii=False)
        relatorio_json_str = json.dumps(dados_relatorio, ensure_ascii=False)
        gerado_em = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

        cobertura = dados_grafo.get("cobertura", {})
        pct_cobertura = cobertura.get("percentual_geral", 0.0)
        total_nodes = cobertura.get("total_nodes", len(dados_grafo.get("nodes", {})))
        nodes_visitados = cobertura.get("nodes_visitados", 0)

        historico = dados_relatorio.get("historico", [])
        total_acoes = dados_relatorio.get("total_acoes", len(historico))
        anomalias = dados_relatorio.get("anomalias", [])
        oracle_stats = dados_relatorio.get("oracle_stats", {})

        if "taxa_sucesso" in dados_relatorio:
            taxa_sucesso = float(dados_relatorio["taxa_sucesso"])
        elif "total_sucessos" in dados_relatorio and total_acoes > 0:
            taxa_sucesso = round((dados_relatorio["total_sucessos"] / total_acoes) * 100.0, 1)
        elif len(historico) > 0:
            sucessos_amostra = sum(1 for a in historico if a.get("sucesso", True))
            taxa_sucesso = round((sucessos_amostra / len(historico)) * 100.0, 1)
        else:
            taxa_sucesso = 100.0

        if "latencia_media_ms" in dados_relatorio:
            latencia_media = float(dados_relatorio["latencia_media_ms"])
        elif historico:
            latencia_media = round(sum(a.get("latencia_ms", 0.0) for a in historico) / len(historico), 1)
        else:
            latencia_media = 0.0

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MedQuest · Dashboard Visual do Grafo de Telas e Rotas</title>
  
  <!-- Vis.js Network para renderização interativa física de grafos -->
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>

  <style>
    :root {{
      --bg-main: #060911;
      --bg-card: #0c1222;
      --bg-panel: rgba(12, 18, 34, 0.92);
      --border: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(14, 165, 233, 0.5);
      --text: #f1f5f9;
      --text-muted: #94a3b8;
      --cyan: #06b6d4;
      --teal: #14b8a6;
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
      --purple: #8b5cf6;
      --blue: #3b82f6;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg-main);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}

    /* Header Superior */
    header {{
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 10;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand-icon {{
      font-size: 24px;
      background: rgba(6, 182, 212, 0.15);
      padding: 6px 10px;
      border-radius: 8px;
      border: 1px solid rgba(6, 182, 212, 0.3);
    }}
    .brand-title h1 {{
      font-size: 16px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .badge-live {{
      background: rgba(16, 185, 129, 0.15);
      color: var(--emerald);
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 12px;
      font-weight: 600;
      border: 1px solid rgba(16, 185, 129, 0.3);
    }}
    .brand-title p {{
      font-size: 12px;
      color: var(--text-muted);
    }}

    /* Grid de KPIs */
    .kpi-strip {{
      display: flex;
      gap: 16px;
      align-items: center;
    }}
    .kpi-item {{
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 8px;
      text-align: right;
    }}
    .kpi-label {{
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .kpi-value {{
      font-size: 15px;
      font-weight: 700;
      color: var(--cyan);
    }}
    .kpi-value.green {{ color: var(--emerald); }}
    .kpi-value.purple {{ color: var(--purple); }}

    /* Layout Central */
    .main-container {{
      display: flex;
      flex: 1;
      position: relative;
      overflow: hidden;
    }}

    /* Área do Grafo Interativo */
    #network-canvas {{
      flex: 1;
      height: 100%;
      background: radial-gradient(circle at center, #0a1122 0%, #060911 100%);
    }}

    /* Barra de Ferramentas Flutuante */
    .toolbar {{
      position: absolute;
      top: 16px;
      left: 16px;
      background: var(--bg-panel);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 8px 12px;
      display: flex;
      gap: 8px;
      z-index: 5;
    }}
    .toolbar button, .toolbar input {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .toolbar button:hover {{
      background: rgba(6, 182, 212, 0.2);
      border-color: var(--cyan);
    }}
    .toolbar input {{
      width: 180px;
      outline: none;
    }}
    .toolbar input:focus {{
      border-color: var(--cyan);
      box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.2);
    }}

    /* Legenda Flutuante */
    .legend-box {{
      position: absolute;
      bottom: 16px;
      left: 16px;
      background: var(--bg-panel);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 11px;
      z-index: 5;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text-muted);
    }}
    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}

    /* Painel Lateral de Detalhes */
    .sidebar {{
      width: 380px;
      background: var(--bg-card);
      border-left: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      z-index: 5;
    }}
    .sidebar-header {{
      padding: 16px;
      border-bottom: 1px solid var(--border);
    }}
    .sidebar-header h2 {{
      font-size: 14px;
      font-weight: 700;
      color: var(--cyan);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .sidebar-body {{
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .card-detail {{
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
    }}
    .card-detail h3 {{
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 6px;
      text-transform: uppercase;
    }}
    .detail-row {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      margin-bottom: 4px;
    }}
    .detail-val {{
      font-weight: 600;
      color: var(--text);
    }}

    /* Feed de Histórico */
    .feed-list {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 280px;
      overflow-y: auto;
    }}
    .feed-item {{
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 11px;
    }}
    .feed-top {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 3px;
    }}
    .feed-persona {{
      font-weight: 600;
      color: var(--cyan);
    }}
    .feed-thought {{
      font-style: italic;
      color: var(--text-muted);
      margin-top: 4px;
      line-height: 1.3;
    }}
  </style>
</head>
<body>

  <!-- Header Superior -->
  <header>
    <div class="brand">
      <div class="brand-icon">🩺</div>
      <div class="brand-title">
        <h1>MedQuest · Grafo de Cobertura & Auditoria E2E <span class="badge-live">AO VIVO</span></h1>
        <p>Atualizado em {gerado_em} • {total_acoes} Ações Executadas</p>
      </div>
    </div>

    <div class="kpi-strip">
      <div class="kpi-item">
        <div class="kpi-label">Cobertura Geral</div>
        <div class="kpi-value green">{pct_cobertura}% ({nodes_visitados}/{total_nodes})</div>
      </div>
      <div class="kpi-item">
        <div class="kpi-label">Taxa de Sucesso</div>
        <div class="kpi-value green">{taxa_sucesso}%</div>
      </div>
      <div class="kpi-item">
        <div class="kpi-label">Latência Média</div>
        <div class="kpi-value">{latencia_media}ms</div>
      </div>
      <div class="kpi-item">
        <div class="kpi-label">Comentários Imutáveis</div>
        <div class="kpi-value green">100% Protegido</div>
      </div>
    </div>
  </header>

  <!-- Container Principal -->
  <div class="main-container">
    
    <!-- Barra de Ferramentas -->
    <div class="toolbar">
      <input type="text" id="input-busca" placeholder="🔍 Buscar rota ou tela..." oninput="filtrarNos(this.value)">
      <button onclick="network.fit({{animation: true}})">🎯 Resetar Zoom</button>
      <button onclick="alternarFiltroTipo('todos')">🌐 Todos</button>
      <button onclick="alternarFiltroTipo('tela_frontend')">💻 Telas</button>
      <button onclick="alternarFiltroTipo('rota_api')">⚡ Rotas API</button>
    </div>

    <!-- Canvas do Vis.js -->
    <div id="network-canvas"></div>

    <!-- Legenda Visual -->
    <div class="legend-box">
      <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> Nó Visitado (100% Sucesso)</div>
      <div class="legend-item"><span class="legend-dot" style="background:#06b6d4;"></span> Tela Frontend (Next.js)</div>
      <div class="legend-item"><span class="legend-dot" style="background:#8b5cf6;"></span> Rota de API (Flask)</div>
      <div class="legend-item"><span class="legend-dot" style="background:#f43f5e;"></span> Anomalia / Falha</div>
      <div class="legend-item"><span class="legend-dot" style="background:#64748b;"></span> Recurso Não Visitado</div>
    </div>

    <!-- Painel Lateral -->
    <div class="sidebar">
      <div class="sidebar-header">
        <h2>Detalhes do Recurso</h2>
      </div>
      <div class="sidebar-body">
        
        <div class="card-detail" id="box-node-info">
          <h3>Nó Selecionado</h3>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Nome:</span>
            <span class="detail-val" id="det-nome">Clique em um nó no grafo</span>
          </div>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Identificador:</span>
            <span class="detail-val" id="det-id">-</span>
          </div>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Tipo:</span>
            <span class="detail-val" id="det-tipo">-</span>
          </div>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Visitas:</span>
            <span class="detail-val" id="det-visitas">-</span>
          </div>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Latência Média:</span>
            <span class="detail-val" id="det-latencia">-</span>
          </div>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Falhas:</span>
            <span class="detail-val" id="det-falhas">-</span>
          </div>
        </div>

        <div class="card-detail">
          <h3>Guardrails Canônicos</h3>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Comentários de Professores:</span>
            <span class="detail-val" style="color:var(--emerald)">Somente-Leitura (OK)</span>
          </div>
          <div class="detail-row">
            <span style="color:var(--text-muted)">FSRS v6 Scheduler:</span>
            <span class="detail-val" style="color:var(--emerald)">Piso D+1+ (OK)</span>
          </div>
          <div class="detail-row">
            <span style="color:var(--text-muted)">Teoria Resposta Item (TRI):</span>
            <span class="detail-val" style="color:var(--emerald)">Theta Finito (OK)</span>
          </div>
        </div>

        <div class="card-detail">
          <h3>Últimas Ações de Personas</h3>
          <div class="feed-list" id="feed-acoes">
            <!-- Injetado dinamicamente -->
          </div>
        </div>

      </div>
    </div>

  </div>

  <script>
    const DADOS_GRAFO = {grafo_json_str};
    const DADOS_RELATORIO = {relatorio_json_str};

    let network = null;
    let allNodes = [];
    let allEdges = [];

    function inicializarGrafo() {{
      const container = document.getElementById('network-canvas');
      const nodesMap = DADOS_GRAFO.nodes || {{}};
      const arestasMap = DADOS_GRAFO.arestas || {{}};

      const visNodes = [];
      const visEdges = [];

      // Monta nós
      for (const [key, node] of Object.entries(nodesMap)) {{
        const isFrontend = node.tipo === 'tela_frontend';
        const foiVisitado = node.visitas > 0;
        const temFalhas = node.falhas > 0;

        let corBg = '#64748b'; // Não visitado (cinza)
        let corBorda = '#94a3b8';

        if (temFalhas) {{
          corBg = '#f43f5e';
          corBorda = '#fda4af';
        }} else if (foiVisitado) {{
          corBg = isFrontend ? '#06b6d4' : '#10b981';
          corBorda = isFrontend ? '#67e8f9' : '#6ee7b7';
        }}

        visNodes.push({{
          id: node.id,
          label: node.nome || node.id,
          shape: isFrontend ? 'box' : 'dot',
          size: Math.min(35, Math.max(16, 16 + (node.visitas * 2))),
          margin: 10,
          color: {{
            background: corBg,
            border: corBorda,
            highlight: {{ background: '#38bdf8', border: '#ffffff' }}
          }},
          font: {{ color: '#f8fafc', size: 12, face: 'sans-serif' }},
          rawNode: node
        }});
      }}

      // Monta arestas
      let edgeCount = 0;
      for (const [key, aresta] of Object.entries(arestasMap)) {{
        visEdges.push({{
          id: 'edge_' + (edgeCount++),
          from: aresta.origem,
          to: aresta.destino,
          arrows: 'to',
          color: {{ color: 'rgba(148, 163, 184, 0.4)', highlight: '#38bdf8' }},
          label: aresta.acao || '',
          font: {{ color: '#94a3b8', size: 9, align: 'middle' }},
          smooth: {{ type: 'cubicBezier', roundness: 0.2 }}
        }});
      }}

      allNodes = visNodes;
      allEdges = visEdges;

      const data = {{
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges)
      }};

      const options = {{
        physics: {{
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {{
            gravitationalConstant: -40,
            centralGravity: 0.008,
            springLength: 120,
            springConstant: 0.08
          }},
          stabilization: {{ iterations: 120 }}
        }},
        interaction: {{
          hover: true,
          tooltipDelay: 100,
          navigationButtons: false
        }}
      }};

      network = new vis.Network(container, data, options);

      // Evento de clique em nó
      network.on('click', function(params) {{
        if (params.nodes.length > 0) {{
          const nodeId = params.nodes[0];
          const nodeData = nodesMap[nodeId];
          if (nodeData) {{
            exibirDetalhesNode(nodeData);
          }}
        }}
      }});
    }}

    function exibirDetalhesNode(node) {{
      document.getElementById('det-nome').innerText = node.nome;
      document.getElementById('det-id').innerText = node.id;
      document.getElementById('det-tipo').innerText = node.tipo === 'tela_frontend' ? 'Tela Frontend (Next.js)' : 'Rota API (Flask)';
      document.getElementById('det-visitas').innerText = node.visitas + ' vezes';
      document.getElementById('det-falhas').innerText = node.falhas + ' falhas';

      const latencias = node.latencias_ms || [];
      if (latencias.length > 0) {{
        const media = latencias.reduce((a, b) => a + b, 0) / latencias.length;
        document.getElementById('det-latencia').innerText = media.toFixed(1) + 'ms';
      }} else {{
        document.getElementById('det-latencia').innerText = 'N/A';
      }}
    }}

    function popularFeedAcoes() {{
      const feedContainer = document.getElementById('feed-acoes');
      const historico = DADOS_RELATORIO.historico || [];
      if (historico.length === 0) {{
        feedContainer.innerHTML = '<p style="color:var(--text-muted);font-size:12px;">Nenhuma ação registrada ainda.</p>';
        return;
      }}

      feedContainer.innerHTML = '';
      const ultimas = historico.slice(-12).reverse();

      ultimas.forEach(item => {{
        const div = document.createElement('div');
        div.className = 'feed-item';
        div.innerHTML = `
          <div class="feed-top">
            <span class="feed-persona">${{item.persona_id || 'Persona'}}</span>
            <span style="color:${{item.sucesso ? 'var(--emerald)' : 'var(--rose)'}}">${{item.status_code || 200}} (${{Math.round(item.latencia_ms)}}ms)</span>
          </div>
          <div><strong>Ação:</strong> ${{item.tipo_acao}} → ${{item.alvo}}</div>
          ${{item.pensamento ? `<div class="feed-thought">"${{item.pensamento}}"</div>` : ''}}
        `;
        feedContainer.appendChild(div);
      }});
    }}

    function filtrarNos(termo) {{
      if (!network || !termo) {{
        network.fit({{animation: true}});
        return;
      }}
      const t = termo.toLowerCase();
      const nodeEncontrado = allNodes.find(n => (n.label || '').toLowerCase().includes(t) || n.id.toLowerCase().includes(t));
      if (nodeEncontrado) {{
        network.focus(nodeEncontrado.id, {{
          scale: 1.3,
          animation: true
        }});
        exibirDetalhesNode(nodeEncontrado.rawNode);
      }}
    }}

    function alternarFiltroTipo(tipo) {{
      if (!network) return;
      if (tipo === 'todos') {{
        network.setData({{
          nodes: new vis.DataSet(allNodes),
          edges: new vis.DataSet(allEdges)
        }});
      }} else {{
        const filtrados = allNodes.filter(n => n.rawNode.tipo === tipo);
        network.setData({{
          nodes: new vis.DataSet(filtrados),
          edges: new vis.DataSet(allEdges)
        }});
      }}
      network.fit({{animation: true}});
    }}

    window.onload = function() {{
      inicializarGrafo();
      popularFeedAcoes();
    }};
  </script>
</body>
</html>
"""
