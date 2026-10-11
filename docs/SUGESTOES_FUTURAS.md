# 💡 MedQuest - Catálogo de Sugestões e Oportunidades Futuras

Este catálogo armazena ideias, melhorias arquiteturais e refinamentos mapeados durante auditorias e ciclos de desenvolvimento autônomo.

---

### Backend & Banco de Dados
- **Telemetria de latência para LibSQL / Turso Cloud**: Medir e registrar métricas de roundtrip em conexões remotas via `TursoConnection` em `app/backend/api/db.py`.
- **Padronização de respostas 404 e contrato JSON em api/questions.py**: Uniformizar endpoints `/attempt`, `/review` e `/favorite` com payloads estruturados e chaves semânticas consistentes (`error`, `message`, `question_id`).
- **Benchmark automatizado de carga**: Criar rotina de carga para testar endpoints de fila adaptativa e remediação (`/api/adaptive/queue`, `/api/questions/remediation`) sob concorrência.
- **Validação e fallback para payload FSRS legado em api/questions.py**: Implementar recuperação defensiva graciosa nas rotas `/attempt` e `/twin` caso um registro legado em `user_question_fsrs` contenha JSON malformado ou corrompido, evitando erro 500 no fluxo de estudo.

### Frontend & PWA
- **Prefetch inteligente de questões no modo offline**: Implementar rotina no Dexie para pre-carregar o próximo bloco de 10 questões baseado na trilha do usuário.
- **Suporte a navegação por teclado nos modais de curadoria**: Adicionar trap-focus acessível (`react-focus-lock` ou custom hook) para usuários que utilizam exclusivamente teclado.
- **Audit de contraste de cores nos badges de áreas médicas**: Revisar temas claro/escuro garantindo conformidade WCAG AAA (mínimo 7:1) em badges de subtemas clínicos.
- [Concluído] **Estratégia de Quota Recovery e Evicção no Dexie**: Em caso de `QuotaExceededError` durante `syncQuestions`, purga atômica de pacotes expirados de simulados (`simuladoPackages`) com retentativa transacional e testes unitários.
- **Purga Seletiva de Imagens Órfãs no Cache Storage (`medquest-image-cache`)**: Em cenários de esgotamento extremo de espaço onde a evicção do IndexedDB não seja suficiente, expurgar do Cache Storage imagens pertencentes a simulados removidos.
