"""
==============================================================================
MEDQUEST · TESTADOR MASTER: PERSONAS MÉDICAS
==============================================================================
Catálogo de perfis simulados para teste ostensivo de alta fidelidade:
- Internato Generalista (5 Grandes Áreas, aprendizado de base)
- R1 Residência Elite (USP/ENARE, simulados na íntegra, TRI)
- Revisor FSRS Metódico (Flashcards diários, repetição espaçada)
- Candidato OSCE Prático (Estações clínicas, checklists)
- Caótico Fuzzer (Concorrência, limites, payloads anômalos)
==============================================================================
"""

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PersonaMedica:
    """Representação de um médico ou estudante interagindo com o MedQuest."""
    id: str
    nome: str
    titulo: str
    icone: str
    descricao: str
    taxa_acerto_esperada: float
    pesos_acoes: Dict[str, float]
    temas_preferidos: List[str]
    instituicoes_alvo: List[str]
    ritmo_segundos: float = 1.5

    def escolher_acao(self) -> str:
        """Sorteia a próxima ação médica ponderada pelo perfil da persona."""
        acoes = list(self.pesos_acoes.keys())
        pesos = list(self.pesos_acoes.values())
        return random.choices(acoes, weights=pesos, k=1)[0]

    def gerar_pensamento_clinico(self, acao: str, contexto: Optional[Dict[str, Any]] = None) -> str:
        """Gera um balão de pensamento contextualizado com o momento clínico/estudo."""
        contexto = contexto or {}
        if acao == "responder_questao":
            pensamentos = [
                f"Analisando caso clínico... vamos avaliar as condutas de primeira linha.",
                f"Foco na anamnese e tempo de sintomas para diferenciar diagnósticos diferenciais.",
                f"Eliminando alternativas absurdas. Focando na melhor evidência médica.",
                f"Pegadinha clássica de edital! Vou checar a contraindicação antes de responder.",
            ]
            return random.choice(pensamentos)
        elif acao == "revisar_flashcard":
            pensamentos = [
                "Revisão ativa FSRS: tentando resgatar o critério diagnóstico da memória de longo prazo.",
                "Card de farmacologia clínica: dose, efeito adverso e mecanismo de ação.",
                "Algoritmo FSRS calibrado para D+1 no erro e retenção de 85%. Vamos testar a recuperação.",
            ]
            return random.choice(pensamentos)
        elif acao == "executar_simulado":
            pensamentos = [
                "Iniciando caderno de prova cronometrado: foco na gestão de tempo por questão.",
                "Simulando prova completa de Residência Médica para calibrar o escore TRI.",
                "100 questões estilo ENARE/USP: concentração total no ritmo de prova.",
            ]
            return random.choice(pensamentos)
        elif acao == "executar_estacao_osce":
            pensamentos = [
                "Estação OSCE iniciada: 'Bom dia, sou o médico assistente. O que o senhor está sentindo?'",
                "Solicitando monitorização, acesso venoso periférico calibroso e ECG de 12 derivações.",
                "Verificando checklist da banca: anamnese rápida, exame direcionado e conduta imediata.",
            ]
            return random.choice(pensamentos)
        elif acao == "consultar_analytics":
            pensamentos = [
                "Analisando gráfico de proficiência TRI (theta) e radar de cobertura das grandes áreas.",
                "Checando se meu percentil na USP e no SUS-SP está acima do corte da especialidade.",
            ]
            return random.choice(pensamentos)
        elif acao == "analisar_exame_imagem":
            pensamentos = [
                "Interpretando ECG em 12 derivações pelos 6 passos da FMRP-USP: checando supra de ST em parede anterior.",
                "Analisando radiografia de tórax no mnemônico ABCDE: avaliando seios costofrênicos e parênquima.",
                "Tomografia de crânio: buscando hemorragia intracraniana aguda, cisternas e desvio de linha média.",
                "Examinando lesão dermatológica na regra do ABCDE e identificando lesão elementar para conduta.",
            ]
            return random.choice(pensamentos)
        elif acao == "buscar_conteudo":
            pensamentos = [
                "Buscando questões sobre tromboembolismo pulmonar e escores de Wells e Geneva.",
                "Pesquisando atualizações sobre rastreamento de câncer colorretal e diretrizes do MS.",
            ]
            return random.choice(pensamentos)
        elif acao == "fuzzing":
            pensamentos = [
                "Disparando estresse de requisições simultâneas e alternância brusca de abas.",
                "Enviando payloads nos limites das rotas para verificar robustez e idempotência.",
            ]
            return random.choice(pensamentos)
        return "Examinando o sistema MedQuest..."


def obter_catalogo_personas(offline: bool = False) -> Dict[str, PersonaMedica]:
    """Retorna o catálogo completo de personas médicas."""
    catalogo = {
        "internato_generalista": PersonaMedica(
            id="internato_generalista",
            nome="Dra. Mariana Luz",
            titulo="Interna do 6º Ano (FMUSP)",
            icone="🩺",
            descricao="Foco nas 5 grandes áreas, dúvidas frequentes em condutas avançadas, estuda pelo rodízio.",
            taxa_acerto_esperada=0.68,
            pesos_acoes={
                "responder_questao": 0.45,
                "revisar_flashcard": 0.25,
                "buscar_conteudo": 0.15,
                "consultar_analytics": 0.10,
                "executar_estacao_osce": 0.05,
            },
            temas_preferidos=[
                "Clínica Médica",
                "Cirurgia Geral",
                "Pediatria",
                "Ginecologia e Obstetrícia",
                "Medicina Preventiva e Social",
            ],
            instituicoes_alvo=["USP", "UNIFESP", "UNICAMP"],
            ritmo_segundos=1.4,
        ),
        "r1_residencia_elite": PersonaMedica(
            id="r1_residencia_elite",
            nome="Dr. Gabriel Castro",
            titulo="Candidato R1 Focado em Top Editais",
            icone="🎯",
            descricao="Estudo de alto rendimento, simulados cronometrados, foco em TRI e editais concorridos.",
            taxa_acerto_esperada=0.86,
            pesos_acoes={
                "executar_simulado": 0.30,
                "responder_questao": 0.30,
                "analisar_exame_imagem": 0.15,
                "consultar_analytics": 0.15,
                "revisar_flashcard": 0.10,
            },
            temas_preferidos=[
                "Cardiologia de Emergência",
                "Trauma e ATLS",
                "Infectologia",
                "Nefrologia e DHE",
                "Obstetrícia de Alto Risco",
            ],
            instituicoes_alvo=["USP-SP", "ENARE", "SUS-SP", "UNICAMP", "SCMSP"],
            ritmo_segundos=1.0,
        ),
        "revisor_fsrs_metodico": PersonaMedica(
            id="revisor_fsrs_metodico",
            nome="Dra. Beatriz Mendes",
            titulo="Especialista em Repetição Espaçada",
            icone="🧠",
            descricao="Foco disciplinado em retenção de longo prazo com FSRS v6, zerando revisões pendentes.",
            taxa_acerto_esperada=0.79,
            pesos_acoes={
                "revisar_flashcard": 0.60,
                "responder_questao": 0.25,
                "consultar_analytics": 0.10,
                "buscar_conteudo": 0.05,
            },
            temas_preferidos=[
                "Farmacologia Clínica",
                "Critérios Diagnósticos",
                "Rastreamentos e Vacinação",
                "Marcadores Tumorais",
            ],
            instituicoes_alvo=["ENARE", "USP"],
            ritmo_segundos=1.2,
        ),
        "candidato_osce_pratico": PersonaMedica(
            id="candidato_osce_pratico",
            nome="Dr. Lucas Rezende",
            titulo="Treinamento para 2ª Fase Prática (OSCE)",
            icone="🏥",
            descricao="Focado em estações de habilidades médicas, atendimento ao paciente e checklist da banca.",
            taxa_acerto_esperada=0.75,
            pesos_acoes={
                "executar_estacao_osce": 0.40,
                "analisar_exame_imagem": 0.25,
                "responder_questao": 0.20,
                "revisar_flashcard": 0.10,
                "consultar_analytics": 0.05,
            },
            temas_preferidos=[
                "Suporte Avançado de Vida (ACLS)",
                "PALS e Emergências Pediátricas",
                "Comunicação de Más Notícias",
                "Exame Físico Neurológico",
            ],
            instituicoes_alvo=["USP", "UNIFESP", "EINSTEIN"],
            ritmo_segundos=1.6,
        ),
        "caotico_fuzzer": PersonaMedica(
            id="caotico_fuzzer",
            nome="Alex Chaos (Fuzzer)",
            titulo="Engenheiro Caótico de Robustez",
            icone="⚡",
            descricao="Submissões concorrentes, filtros extremos, IDs inexistentes e estresse de contratos de API.",
            taxa_acerto_esperada=0.50,
            pesos_acoes={
                "responder_questao": 0.30,
                "revisar_flashcard": 0.25,
                "fuzzing": 0.25,
                "executar_simulado": 0.10,
                "buscar_conteudo": 0.10,
            },
            temas_preferidos=["Todos", "FiltroInvalido", "SpecialChars_%$#"],
            instituicoes_alvo=["TODAS", "INVALIDA_999"],
            ritmo_segundos=0.3,
        ),
    }

    if offline:
        acoes_externas = {"executar_estacao_osce", "analisar_exame_imagem"}
        for p in catalogo.values():
            p.pesos_acoes = {k: v for k, v in p.pesos_acoes.items() if k not in acoes_externas}
            if not p.pesos_acoes:
                p.pesos_acoes = {"responder_questao": 0.6, "revisar_flashcard": 0.4}
            total = sum(p.pesos_acoes.values())
            if total > 0:
                p.pesos_acoes = {k: v / total for k, v in p.pesos_acoes.items()}

    return catalogo
