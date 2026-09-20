# Revisão 05 — Testes de navegação e falhas da jornada

Você fará uma segunda revisão crítica da tarefa anterior do Gemini no MedQuest. Releia o prompt de implementação correspondente e `docs/gemini/entregas/05.md`. Não presuma que o resumo da implementação é correto: inspecione o código e execute verificações independentes.

Preserve as alterações de outras tarefas. Não publique, não faça commits ou reset, não exponha segredos e não acesse o banco remoto. Use bancos e serviços temporários. Consulte AGENTS.md e documentação local aplicável. Revise escopo, contrato, isolamento de usuário, erros, regressões e testes, além de caminho feliz.

Corrija os problemas comprovados dentro do escopo, acrescente testes de regressão pertinentes e rode-os novamente. Não reescreva arquitetura por preferência. Se houver decisão de produto ambígua ou bloqueio real, descreva-o sem inventar requisitos. Não declare ausência de bugs como garantia.

Foco desta revisão:
Verifique que os testes realmente atravessam as telas e interações, e não apenas repetem funções auxiliares. Testes de persistência devem recarregar e reconsultar dados; mocks que sempre devolvem sucesso não provam gravação. Simule falhas reais nas respostas e confira ausência de falso estado concluído. Procure sleeps fixos, testes ignorados e dependência de horário/ordem. Confirme que nenhuma alteração de teste libera autenticação ou dados em produção. Execute a suíte nova e as regressões afetadas e relate falhas separando ambiente de produto.

Entrega: resumo de até 15 linhas com achados por gravidade, correções, comandos e resultados realmente executados, limitações e pontos para auditoria pelo Codex. Salve também `docs/gemini/entregas/05-revisao.md`. A revisão deve ser executada separadamente da implementação; preferencialmente em uma nova conversa com acesso ao mesmo workspace. Não inicie o próximo prompt automaticamente.
