# Matriz de requisitos, implementação e evidências

Situação de 05/11/2026. Resultado histórico de teste não aprova um commit novo. O SHA/check vigente deve ser conferido no PR e em HOMOLOGACAO.md. Esta matriz é incremental; não declara o escopo original completo.

| Requisito | Implementação / contrato | Verificação | Estado |
| --- | --- | --- | --- |
| FIN-01 — referência e saldo | balances.py, SALDOS.md | test_balances.py, integration_balances.py, browser_balances.cjs | Homologado 0.5 |
| FIN-02 — transferência/reversão | balances.py, migração 004 | Conservação, reversão, UUID/concorrência e FKs nos mesmos roteiros | Homologado 0.5 |
| FIN-03 — contas/cartões | lifecycle.py, CADASTROS.md, migração 005 | test_lifecycle.py, integration_lifecycle.py, browser_lifecycle.cjs | Homologado 0.6 |
| FIN-03 — metas | lifecycle.py, planning.py, migração 006 | test_goals_lifecycle.py, concorrência PostgreSQL, browser_goals.cjs | Homologado 0.7 |
| FIN-04 — estados anteriores | audit.py, AUDITORIA.md, migração 007 | test_audit.py, rollback/JSON PostgreSQL, consulta mobile/HTML | Homologado 0.8 |
| FIN-04 — correções agrupadas e conflitos | operations.py, CORRECOES.md, migração 008 | test_corrections.py, integração concorrente e browser_corrections.cjs | Compra manual homologada na 0.9; pagamentos homologados na 0.10; importados e versão ampla de lançamentos pendentes |
| FIN-05 — contrato/idempotência | receipts.py, CORRECOES.md, SALDOS.md | Cancelamento, replay, concorrência e backfill legados | Recibos de compra manual/pagamento homologados na 0.9; importações e contrato amplo pendentes |
| CSV/PDF | domain.py, pdf_import.py, parser isolado, PDF.md | test_finance.py, test_pdf.py, integration_pdf.py, browser_pdf.cjs | Formatos sintéticos declarados homologados; emissores/OCR/OFX pendentes |
| Planejamento conservador | planning.py, PLANEJAMENTO.md | test_planning.py, browser_planning.cjs | Base homologada; projeção e aportes vinculados pendentes |
| Separação por proprietário | Filtros ORM e FKs compostas | test_security.py, testes de domínio, integração de FKs | API/FKs testadas; RLS e privilégio mínimo pendentes |
| Login e segundo fator | OIDC/PKCE, Keycloak/TOTP, KEYCLOAK.md | test_oauth_transport.py, test_oidc_start.py, browser_oidc.cjs | Login local homologado; Google/recuperação/JWKS amplos pendentes |
| Sessão/CSRF/cotas | security.py, SEGURANCA.md | test_security.py, navegador de saldos/cadastros/metas | Base homologada; resposta atrasada protegida em 0.8 homologada |
| Histórico privado/expurgo | financial_audit, exportação/exclusão | test_audit.py: isolamento, cursor, expurgo e rollback | 0.8 homologado; retenção de produção e backups pendentes |
| HTML em conteúdo do histórico | history.js usa textContent | browser_goals.cjs: string de ataque não cria elemento | 0.8 homologado; XSS abrangente e segundo motor pendentes |
| Migração preservando dados | Runner/checksum e scripts 001–009 | integration_migrations.py: adoção, legado, repetição, rollback e checksum | 001–009 homologadas |
| Design e acessibilidade | Temas e formulários responsivos | Capturas mobile/desktop e overflow; inspeção visual de metas | Parcial; WCAG e revisão geral em UX-03/04 |
| Histórico do desenvolvimento | Commits pt-BR, PR rascunho e documentação | PR #1 e Actions | Atualizado por incremento; reorganizar futuros PRs em REL-09 |
| IA, perfil, desejos e ofertas | ROADMAP fases 6/7 | Ainda sem provedor/fontes reais homologados | Pendente |
| LGPD operacional e produção | PRIVACIDADE.md e fases 8/9 | Ainda sem aceite operacional/jurídico ou pentest | Pendente; publicação adiada |

Arquivos de teste ficam em `tests/`. A suíte SQLite/fakeredis valida regras isoladas; CI executa containers com PostgreSQL/Redis e Keycloak reais. O navegador usa sessões sintéticas somente nos roteiros financeiros; o roteiro OIDC usa login/TOTP real no provedor local. Não há bypass de autenticação disponibilizado pela aplicação para esses testes.

Próxima ordem de desenvolvimento preservada: concluir FIN-04/05, depois faturas/créditos/recorrências/projeção e aportes; ingestão ampliada e UX; confiabilidade local; IA/ofertas; identidade complementar e produção. Backup/restauração, RLS, scans, carga, pentest e LGPD são marcos obrigatórios antes de liberar uso público.

Evidência atual da 0.8: código `5b7b1b6`, [execução 41888034624](https://github.com/oYuriyan/walleturbo/actions/runs/41888034624), 109 testes em container e todas as etapas aprovadas. A publicação continua adiada; marcos A/B/C seguem conforme ROADMAP.md.

Evidência atual da 0.9: código `961b0e0`, [execução 41892139036](https://github.com/oYuriyan/walleturbo/actions/runs/41892139036), 116 testes em container e todas as etapas aprovadas, incluindo prévia/correção mobile, concorrência e proteção contra reenvio após exclusão de compra/pagamento. Pagamentos/importados e versão ampla continuam pendentes conforme as linhas FIN-04/05.

0.10 homologada: pagamento versionado com prévia de saldos/caixa, limite com demais pagamentos e remoção protegida (PAGAMENTOS.md). Verificações: test_payment_corrections.py, integration_payment_corrections.py, browser_payment_corrections.cjs e upgrade em integration_migrations.py.

Evidência atual da 0.10: código `39c0a67`, [execução 42033442245](https://github.com/oYuriyan/walleturbo/actions/runs/42033442245), 123 testes em container e todas as etapas aprovadas. Inclui concorrência de pagamentos/limite/remoção, saldos e jornada mobile; captura da prévia inspecionada visualmente.
