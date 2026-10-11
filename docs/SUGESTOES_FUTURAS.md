# 💡 MedQuest - Catálogo de Sugestões e Oportunidades Futuras

Este catálogo armazena ideias, melhorias arquiteturais e refinamentos mapeados durante auditorias e ciclos de desenvolvimento autônomo.

---

### Backend & Banco de Dados
- **Telemetria de latência para LibSQL / Turso Cloud**: Medir e registrar métricas de roundtrip em conexões remotas via `TursoConnection` em `app/backend/api/db.py`.
- **Validação de existência prévia em toggle_favorite**: Validar existência de `question_id` antes da inserção em `favorites` em `app/backend/api/question_routes.py` para prevenir chaves órfãs.
- **Benchmark automatizado de carga**: Criar rotina de carga para testar endpoints de fila adaptativa e remediação (`/api/adaptive/queue`, `/api/questions/remediation`) sob concorrência.
- **Guardrail defensivo explícito em api/srs.py**: Adicionar clamp nativo em `review()` assegurando que qualquer data futura retornada nunca seja inferior a D+1 (>= 24h) mesmo sob drift temporal externo do servidor.

### Frontend & PWA
- **Prefetch inteligente de questões no modo offline**: Implementar rotina no Dexie para pre-carregar o próximo bloco de 10 questões baseado na trilha do usuário.
- **Suporte a navegação por teclado nos modais de curadoria**: Adicionar trap-focus acessível (`react-focus-lock` ou custom hook) para usuários que utilizam exclusivamente teclado.
- **Audit de contraste de cores nos badges de áreas médicas**: Revisar temas claro/escuro garantindo conformidade WCAG AAA (mínimo 7:1) em badges de subtemas clínicos.
