# Revisão 03 — Biblioteca pessoal por tema

Você fará uma segunda revisão crítica da tarefa anterior do Gemini no MedQuest. Releia o prompt de implementação correspondente e `docs/gemini/entregas/03.md`. Não presuma que o resumo da implementação é correto: inspecione o código e execute verificações independentes.

Preserve as alterações de outras tarefas. Não publique, não faça commits ou reset, não exponha segredos e não acesse o banco remoto. Use bancos e serviços temporários. Consulte AGENTS.md e documentação local aplicável. Revise escopo, contrato, isolamento de usuário, erros, regressões e testes, além de caminho feliz.

Corrija os problemas comprovados dentro do escopo, acrescente testes de regressão pertinentes e rode-os novamente. Não reescreva arquitetura por preferência. Se houver decisão de produto ambígua ou bloqueio real, descreva-o sem inventar requisitos. Não declare ausência de bugs como garantia.

Foco desta revisão:
Tente ler, editar e apagar a referência de outro usuário por ID. Teste `javascript:`, `data:`, URL relativa, host ausente e URL com credenciais, além de HTTPS válido e campos vazios. Confira limites e tipo da duração, inclusive true/false. Valide cancelamento de exclusão, envio repetido, erro de rede e manutenção dos dados digitados. Confirme que falhas não mostram sucesso e que títulos são renderizados como texto. Examine a migração em banco temporário com dados anteriores e verifique preservação da biblioteca no reset conforme a decisão documentada.

Entrega: resumo de até 15 linhas com achados por gravidade, correções, comandos e resultados realmente executados, limitações e pontos para auditoria pelo Codex. Salve também `docs/gemini/entregas/03-revisao.md`. A revisão deve ser executada separadamente da implementação; preferencialmente em uma nova conversa com acesso ao mesmo workspace. Não inicie o próximo prompt automaticamente.
