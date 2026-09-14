# Arquivos Legados e Históricos (Archive)

Este diretório armazena scripts pontuais, dados intermediários de scraping/extração e relatórios históricos de migrações e reclassificações passadas do MedQuest.

> **Aviso:** Nenhum arquivo nesta pasta deve ser executado em ambiente de produção. O runtime do MedQuest opera exclusivamente a partir dos pacotes em `app/backend/` e `app/frontend/`.

## Estrutura
- `scripts/`: Scripts efêmeros de inspeção, parse de HARs, contagem e scripts pontuais de migração de lotes (`parse_har_*.py`, `extract_clinica*.py`, `inspect_*.py`, etc.).
- `data/`: Lotes de questões intermediárias (`cir_*.json`, `cm_*.json`, `ped_*.json`, `go_*.json`, dumps e scratches).
- `reports/`: Relatórios de auditoria e reclassificações anteriores (`*.md`, `*_report.json`).
- `migrations/`: Scripts procedurais de migração histórica (`migrate_cirurgia.py`, `migrate_clinica.py`).
