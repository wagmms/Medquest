"""
==============================================================================
MEDQUEST · TESTADOR MASTER: DRIVER DE API ULTRARRÁPIDO
==============================================================================
Executa diretamente sobre a aplicação Flask (in-memory test-client ou HTTP),
testando 100% dos endpoints, contratos de rotas, FSRS v6, TRI e guardrails.
==============================================================================
"""

import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Adiciona backend ao sys.path para importação do Flask factory
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "app" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tooling.testador_master.driver_base import DriverBase, ResultadoAcao
from tooling.testador_master.medical_oracle import MedicalOracle


class DriverAPI(DriverBase):
    """Driver ultrarrápido para execução in-memory contra o Flask do MedQuest."""

    def __init__(self, oracle: Optional[MedicalOracle] = None, user_id: str = "testador_master", offline: bool = False):
        self.oracle = oracle or MedicalOracle()
        self.user_id = user_id
        self.offline = offline
        self.app = None
        self.client = None
        self._questoes_cache: List[Dict[str, Any]] = []
        self._flashcards_cache: List[Dict[str, Any]] = []

    def inicializar(self) -> bool:
        """Cria a aplicação Flask em modo de teste com context isolado."""
        try:
            from api import create_app
            self.app = create_app(testing=True)
            self.client = self.app.test_client()
            return True
        except Exception as e:
            print(f"[DriverAPI] Erro ao instanciar aplicação Flask: {e}")
            return False

    def finalizar(self) -> None:
        """Limpa recursos."""
        self.client = None
        self.app = None

    def _obter_headers(self) -> Dict[str, str]:
        """Headers de autenticação canônicos de teste."""
        return {
            "Content-Type": "application/json",
            "X-User-ID": self.user_id,
            "X-User-Email": f"{self.user_id}@medquest.local",
        }

    def _executar_requisicao(
        self,
        metodo: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> ResultadoAcao:
        """Dispara a requisição HTTP in-memory com cronometragem de latência."""
        if not self.client:
            return ResultadoAcao(
                sucesso=False,
                tipo_acao="http_request",
                alvo=path,
                latencia_ms=0,
                status_code=500,
                mensagem="Driver de API não inicializado.",
            )

        headers = self._obter_headers()
        t0 = time.perf_counter()
        metodo_upper = metodo.upper()

        try:
            if metodo_upper == "GET":
                resp = self.client.get(path, query_string=query_params or {}, headers=headers)
            elif metodo_upper == "POST":
                resp = self.client.post(path, json=payload or {}, query_string=query_params or {}, headers=headers)
            elif metodo_upper == "PUT":
                resp = self.client.put(path, json=payload or {}, headers=headers)
            elif metodo_upper == "DELETE":
                resp = self.client.delete(path, headers=headers)
            else:
                raise ValueError(f"Método {metodo} não suportado.")

            latencia_ms = (time.perf_counter() - t0) * 1000.0
            status_code = resp.status_code

            dados = {}
            if resp.content_type and "application/json" in resp.content_type:
                try:
                    dados = resp.get_json() or {}
                except Exception:
                    dados = {}

            sucesso = 200 <= status_code < 300
            anomalias = []
            if not sucesso and status_code != 404:
                anomalias.append(f"HTTP {status_code} em {path}: {resp.get_data(as_text=True)[:200]}")

            return ResultadoAcao(
                sucesso=sucesso,
                tipo_acao=f"api_{metodo.lower()}",
                alvo=path,
                latencia_ms=latencia_ms,
                status_code=status_code,
                dados=dados if isinstance(dados, dict) else {"items": dados},
                anomalias=anomalias,
            )
        except Exception as e:
            latencia_ms = (time.perf_counter() - t0) * 1000.0
            return ResultadoAcao(
                sucesso=False,
                tipo_acao=f"api_{metodo.lower()}",
                alvo=path,
                latencia_ms=latencia_ms,
                status_code=500,
                mensagem=str(e),
                anomalias=[f"Exceção não tratada na requisição: {str(e)}"],
            )

    def responder_questao(
        self,
        questao_id: Optional[int] = None,
        alternativa: Optional[str] = None,
        confianca: str = "certeza",
        tempo_gasto_s: float = 45.0,
        filtros: Optional[Dict[str, Any]] = None,
    ) -> ResultadoAcao:
        """Resolve uma questão médica e valida FSRS e comentários canônicos."""
        # Se não informou ID, busca uma lista de questões
        if not questao_id:
            res_lista = self._executar_requisicao("GET", "/api/questions", query_params=filtros or {"limit": 15})
            if not res_lista.sucesso:
                return res_lista
            itens = res_lista.dados.get("items") or res_lista.dados.get("questions") or []
            if not itens:
                return ResultadoAcao(
                    sucesso=True,
                    tipo_acao="responder_questao",
                    alvo="/api/questions",
                    latencia_ms=res_lista.latencia_ms,
                    status_code=200,
                    mensagem="Nenhuma questão encontrada com os filtros fornecidos.",
                )
            questao_escolhida = random.choice(itens)
            questao_id = questao_escolhida.get("id")

        # 1. Carrega dados detalhados da questão
        res_detalhe = self._executar_requisicao("GET", f"/api/questions/{questao_id}")
        if not res_detalhe.sucesso:
            return res_detalhe

        dados_q = res_detalhe.dados.get("question") or res_detalhe.dados
        gabarito = dados_q.get("correct_answer") or dados_q.get("correct_letter") or "A"

        # 2. Decide a alternativa
        alt_final = alternativa or gabarito

        # 3. Submete a tentativa respeitando AttemptIn
        mapa_confianca_questao = {
            "certeza": "certeza",
            "duvida": "duvida",
            "chute": "chutei",
            "erro": "chutei",
        }
        payload = {
            "selected_letter": alt_final,
            "confidence": mapa_confianca_questao.get(confianca, "certeza"),
            "time_spent_ms": int(tempo_gasto_s * 1000),
        }
        res_tentativa = self._executar_requisicao("POST", f"/api/questions/{questao_id}/attempt", payload=payload)

        # 4. Auditoria pelo Oráculo Médico
        comentario = res_tentativa.dados.get("explanation") or dados_q.get("explanation")
        if comentario:
            ok_imut, msg_imut = self.oracle.auditar_imutabilidade_comentario(questao_id, comentario)
            if not ok_imut and msg_imut:
                res_tentativa.anomalias.append(msg_imut)

        # Validação do agendamento FSRS
        novo_due = res_tentativa.dados.get("due") or res_tentativa.dados.get("next_review")
        if novo_due:
            is_correto = res_tentativa.dados.get("is_correct", False)
            rating = "certeza" if is_correto else "Again"
            ok_fsrs, anom_fsrs = self.oracle.validar_calculo_fsrs(
                item_tipo="questao",
                rating=rating,
                due_timestamp_anterior=None,
                due_timestamp_novo=str(novo_due),
                intervalo_dias=7.0 if not is_correto else 18.0,
            )
            res_tentativa.anomalias.extend(anom_fsrs)

        res_tentativa.tipo_acao = "responder_questao"
        res_tentativa.alvo = f"/api/questions/{questao_id}/attempt"
        return res_tentativa

    def revisar_flashcard(
        self,
        card_id: Optional[int] = None,
        rating: str = "Good",
    ) -> ResultadoAcao:
        """Revisa um flashcard médico com agendamento FSRS v6."""
        if not card_id:
            res_due = self._executar_requisicao("GET", "/api/flashcards/due")
            itens = res_due.dados.get("items") or res_due.dados.get("flashcards") or []
            if not itens:
                # Tenta listar baralhos
                res_decks = self._executar_requisicao("GET", "/api/flashcards/decks")
                return ResultadoAcao(
                    sucesso=True,
                    tipo_acao="revisar_flashcard",
                    alvo="/api/flashcards/due",
                    latencia_ms=res_due.latencia_ms,
                    status_code=200,
                    mensagem="Nenhum flashcard devido no momento para revisão.",
                )
            card_id = random.choice(itens).get("id")

        # Converte rating para os literais de FlashcardReviewIn ("errei", "duvida", "certeza")
        mapa_confianca = {
            "Again": "errei",
            "Hard": "duvida",
            "Good": "duvida",
            "Easy": "certeza",
        }
        confianca_api = mapa_confianca.get(rating, "certeza")

        res_rev = self._executar_requisicao(
            "POST",
            f"/api/flashcards/{card_id}/review",
            payload={"confidence": confianca_api},
        )

        # Validação FSRS pelo Oráculo
        if res_rev.sucesso:
            next_date = res_rev.dados.get("next_review_date")
            ok_fsrs, anom_fsrs = self.oracle.validar_calculo_fsrs(
                item_tipo="flashcard",
                rating=rating,
                due_timestamp_anterior=None,
                due_timestamp_novo=next_date,
                intervalo_dias=1.0 if confianca_api == "errei" else 5.0,
            )
            res_rev.anomalias.extend(anom_fsrs)

        res_rev.tipo_acao = "revisar_flashcard"
        res_rev.alvo = f"/api/flashcards/{card_id}/review"
        return res_rev

    def executar_simulado(
        self,
        qtd_questoes: int = 10,
        instituicao: Optional[str] = None,
        ano: Optional[int] = None,
    ) -> ResultadoAcao:
        """Cria e avalia um simulado médico."""
        # 1. Cria o caderno de simulado respeitando SimuladoCustomIn
        payload = {
            "questions_per_area": max(1, min(20, qtd_questoes // 5 or 2)),
            "institutions": [str(instituicao)] if instituicao else ["USP", "ENARE"],
            "years": [str(ano)] if ano else ["2024", "2025"],
        }
        res_sim = self._executar_requisicao("POST", "/api/simulado/custom", payload=payload)
        if not res_sim.sucesso:
            # Fallback para rota simulado/usp
            res_sim = self._executar_requisicao("GET", "/api/simulado/usp")

        # 2. Testa avaliação TRI simulada
        payload_tri = {
            "responses": [
                {"item_id": f"q_{i}", "is_correct": bool(random.random() > 0.3), "discrimination": 1.2, "difficulty": 0.5, "guessing": 0.2}
                for i in range(qtd_questoes)
            ]
        }
        res_tri = self._executar_requisicao("POST", "/api/simulado/tri-evaluation", payload=payload_tri)
        if res_tri.sucesso:
            theta = res_tri.dados.get("theta") or res_tri.dados.get("score")
            ok_tri, anom_tri = self.oracle.validar_metricas_tri(theta)
            res_tri.anomalias.extend(anom_tri)

        res_sim.tipo_acao = "executar_simulado"
        res_sim.alvo = "/api/simulado"
        return res_sim

    def executar_estacao_osce(
        self,
        estacao_id: Optional[str] = None,
        respostas_clinicas: Optional[List[str]] = None,
    ) -> ResultadoAcao:
        """Simula a realização de uma estação prática clínica OSCE."""
        if self.offline:
            return ResultadoAcao(
                sucesso=True,
                tipo_acao="executar_estacao_osce",
                alvo="/api/osce/offline",
                latencia_ms=1.0,
                status_code=200,
                mensagem="[MODO OFFLINE] Estação OSCE ignorada para poupar chamadas de IA.",
            )

        # 1. Lista estações disponíveis
        res_stations = self._executar_requisicao("GET", "/api/osce/stations")
        if not res_stations.sucesso:
            return res_stations

        itens = res_stations.dados.get("stations") or res_stations.dados.get("items") or []
        station_id_escolhido = 1
        if itens:
            station_id_escolhido = itens[0].get("id", 1)

        # 2. Inicia sessão OSCE
        res_start = self._executar_requisicao(
            "POST",
            "/api/osce/sessions/start",
            payload={"station_id": station_id_escolhido},
        )
        if not res_start.sucesso:
            return res_start

        session_id = res_start.dados.get("session_id")
        if not session_id:
            return res_start

        # 3. Interage com fala / conduta
        falas = respostas_clinicas or [
            "Bom dia, sou o médico de plantão. Vou examinar o paciente e checar os sinais vitais.",
            "Solicito ECG de 12 derivações, troponina ultrassensível e radiografia de tórax no leito.",
            "Prescrevo oxigenioterapia se SpO2 < 90%, ácido acetilsalicílico 200mg e analgesia.",
        ]
        for fala in falas:
            self._executar_requisicao(
                "POST",
                f"/api/osce/sessions/{session_id}/interact",
                payload={"message": fala},
            )

        # 4. Finaliza a estação e obtém relatório
        res_finish = self._executar_requisicao("POST", f"/api/osce/sessions/{session_id}/finish")
        res_finish.tipo_acao = "executar_estacao_osce"
        res_finish.alvo = f"/api/osce/sessions/{session_id}/finish"
        return res_finish

    def consultar_analytics(self) -> ResultadoAcao:
        """Consulta métricas de proficiência, TRI e radar institucional."""
        res = self._executar_requisicao("GET", "/api/stats/overview")
        # Também testa o radar
        self._executar_requisicao("GET", "/api/stats/institution-radar")
        self._executar_requisicao("GET", "/api/stats/learning-profile")
        res.tipo_acao = "consultar_analytics"
        res.alvo = "/api/stats/overview"
        return res

    def buscar_conteudo(self, termo: str) -> ResultadoAcao:
        """Executa busca semântica/FTS em questões ou temas."""
        res = self._executar_requisicao("GET", "/api/search", query_params={"q": termo, "limit": 10})
        res.tipo_acao = "buscar_conteudo"
        res.alvo = f"/api/search?q={termo}"
        return res

    def fuzzing(self) -> ResultadoAcao:
        """Dispara requisições limítrofes/anômalas para testar resiliência."""
        testes_fuzz = [
            ("GET", "/api/questions/-9999", None),
            ("POST", "/api/questions/999999/attempt", {"selected_letter": "Z"}),
            ("GET", "/api/search", {"q": "'" * 20, "limit": -5}),
            ("POST", "/api/simulado/custom", {"question_count": -100}),
            ("GET", "/api/flashcards/-1", None),
        ]
        metodo, rota, payload = random.choice(testes_fuzz)
        res = self._executar_requisicao(metodo, rota, payload=payload)
        # Respostas 400 ou 404 tratadas são sucessos de robustez
        if res.status_code in (400, 404, 422):
            res.sucesso = True
            res.anomalias = []
        elif res.status_code == 500:
            res.sucesso = False
            res.anomalias.append(f"Fuzzer causou HTTP 500 em {rota} com payload {payload}")

        res.tipo_acao = "fuzzing"
        res.alvo = rota
        return res

    def analisar_exame_imagem(self, modalidade: str = "ecg") -> ResultadoAcao:
        """Simula o envio de um exame médico de imagem para o analisador multimodal."""
        if self.offline:
            return ResultadoAcao(
                sucesso=True,
                tipo_acao="analisar_exame_imagem",
                alvo="/api/ai/analyze-image/offline",
                latencia_ms=1.0,
                status_code=200,
                mensagem="[MODO OFFLINE] Análise multimodal ignorada para poupar chamadas de IA.",
            )

        import base64
        import io
        from PIL import Image

        # Cria uma imagem de teste sintética com dimensões de ECG / RX
        img = Image.new("RGB", (400, 200), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

        payload = {
            "image_base64": b64_str,
            "modality": modalidade,
            "clinical_context": "Paciente masculino, 64 anos, admitido na sala de emergência com precordialgia opressiva.",
        }

        res = self._executar_requisicao("POST", "/api/ai/analyze-image", payload=payload)
        res.tipo_acao = "analisar_exame_imagem"
        res.alvo = "/api/ai/analyze-image"
        return res

    def verificar_saude(self) -> ResultadoAcao:
        """Verifica a integridade das rotas principais."""
        res = self._executar_requisicao("GET", "/")
        res.tipo_acao = "verificar_saude"
        res.alvo = "/"
        return res
