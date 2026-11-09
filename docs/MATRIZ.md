# Matriz de requisitos, implementação e evidências

Situação de 05/11/2026. Resultado histórico de teste não aprova um commit novo. O SHA/check vigente deve ser conferido no PR e em HOMOLOGACAO.md. Esta matriz é incremental; não declara o escopo original completo.

| Requisito | Implementação / contrato | Verificação | Estado |
| --- | --- | --- | --- |
| FIN-01 — referência e saldo | balances.py, SALDOS.md | test_balances.py, integration_balances.py, browser_balances.cjs | Homologado 0.5 |
| FIN-02 — transferência/reversão | balances.py, migração 004 | Conservação, reversão, UUID/concorrência e FKs nos mesmos roteiros | Homologado 0.5 |
| FIN-03 — contas/cartões | lifecycle.py, CADASTROS.md, migração 005 | test_lifecycle.py, integration_lifecycle.py, browser_lifecycle.cjs | Homologado 0.6 |
| FIN-03 — metas | lifecycle.py, planning.py, migração 006 | test_goals_lifecycle.py, concorrência PostgreSQL, browser_goals.cjs | Homologado 0.7 |
| FIN-04 — estados anteriores | audit.py, AUDITORIA.md, migração 007 | test_audit.py, rollback/JSON PostgreSQL, consulta mobile/HTML | Homologado 0.8 |
| FIN-04 — correções agrupadas e conflitos | entries.py, operations.py, payment_corrections.py, CORRECOES.md e contratos 0.10/0.11 | test_corrections.py, test_entry_import_integrity.py, integrações e navegadores de correção | Compra manual homologada na 0.9; pagamentos homologados na 0.10; importados no mesmo contexto e versão de lançamentos homologados na 0.11; faturas/cenários pendentes |
| FIN-05 — contrato/idempotência | receipts.py, import_marks.py, contratos de saldo/correções/importação | Cancelamento, replay, concorrência e backfill legados | Recibos de compra manual/pagamento homologados na 0.9; marcas após exclusão homologadas na 0.11; documentos divergentes e contrato amplo pendentes |
| CSV/PDF | domain.py, pdf_import.py, parser isolado, PDF.md | test_finance.py, test_pdf.py, integration_pdf.py, browser_pdf.cjs | Formatos sintéticos declarados homologados; emissores/OCR/OFX pendentes |
| Planejamento conservador | planning.py, PLANEJAMENTO.md | test_planning.py, browser_planning.cjs | Base homologada; projeção e aportes vinculados pendentes |
| Separação por proprietário | Filtros ORM e FKs compostas | test_security.py, testes de domínio, integração de FKs | API/FKs testadas; RLS e privilégio mínimo pendentes |
| Login e segundo fator | OIDC/PKCE, Keycloak/TOTP, KEYCLOAK.md | test_oauth_transport.py, test_oidc_start.py, browser_oidc.cjs | Login local homologado; Google/recuperação/JWKS amplos pendentes |
| Sessão/CSRF/cotas | security.py, SEGURANCA.md | test_security.py, navegador de saldos/cadastros/metas | Base homologada; resposta atrasada protegida em 0.8 homologada |
| Histórico privado/expurgo | financial_audit, exportação/exclusão | test_audit.py: isolamento, cursor, expurgo e rollback | 0.8 homologado; retenção de produção e backups pendentes |
| HTML em conteúdo do histórico | history.js usa textContent | browser_goals.cjs: string de ataque não cria elemento | 0.8 homologado; XSS abrangente e segundo motor pendentes |
| Migração preservando dados | Runner/checksum e scripts 001–010 | integration_migrations.py: adoção, legado, repetição, rollback e checksum | 001–010 homologadas |
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

0.11 homologada: entradas versionadas, marcas de origem após exclusão, correção importada no mesmo contexto e cartões/demonstração no CI. Evidências em test_entry_import_integrity.py, integration_entry_import_integrity.py, browser_entry_import_integrity.cjs, browser_pdf.cjs, browser_cards.cjs e browser.cjs.

Evidência atual da 0.11: código `8124548`, [execução 42045260683](https://github.com/oYuriyan/walleturbo/actions/runs/42045260683), 133 testes em container e todas as etapas aprovadas. Inclui lotes invertidos sem deadlock, exclusão/reimportação, CSV/PDF compartilhados, revisão obsoleta, navegador mobile, cartões e demonstração/XSS. Três capturas inspecionadas visualmente; limites de layout/idioma nativo/acessibilidade e pendências continuam em HOMOLOGACAO.md/ROADMAP.md.

Contrato financeiro consolidado: DOMINIO_FINANCEIRO.md → tests/test_financial_contract.py. Duas variantes de três meses verificam valores independentes de resultado/caixa/saldo, parcelas com resto, estorno, reversão e correção de pagamento entre contas/meses, incluindo reenvios. Complementa FIN-04/05; não substitui REL-01 com login real nem encerra fases pendentes.

Vínculos CSV 0.17: import_review.py e LANCAMENTOS_E_IMPORTACAO.md → test_import_links.py, integration_entry_import_integrity.py e browser_entry_import_integrity.cjs. Isolamento, versão, reenvio, origem após exclusão, histórico/rollback, concorrência de destinos e NOWAIT PostgreSQL; escolha explícita mobile. IMP-03 permanece parcial conforme limites do contrato.

Desfazimento/remapeamento CSV 0.18: import_review.py e migração 013 → test_import_unlink.py (15 casos), integration_entry_import_integrity.py, integration_migrations.py e browser_entry_import_integrity.cjs. Verificam preservação financeira, revisões após desfazer/refazer, ocorrência independente, contexto/titular, destino corrigido/excluído, fatura conferida, rollback do histórico, upgrade das marcas, NOWAIT, disputa pelo desfazimento e jornada mobile. Não conclui IMP-03 para PDF, emissor/OFX ou colisões da identidade legada.

Conciliação PDF 0.19: pdf_import.py/import_review.py e PDF.md → test_pdf_links.py (14 casos), integration_pdf.py e browser_pdf.cjs. Verificam compra/estorno, campos revisados, índices originais em seleção parcial, token/sessão/titular, rejeição atômica, correção/exclusão do destino, rollback do histórico, desfazimento, ocorrência independente e proteção da identidade primária. PostgreSQL verifica disputas de associação/desfazimento (200/409), preservação financeira e recusa de envios antigos; mobile cobre consulta após edição, vínculo, motivo, desfazimento, releitura e nova associação. Não homologa emissores/OFX, OCR nem colisões legítimas.

OFX bancário 0.20: ofx.py/ofx_import.py e OFX.md → test_ofx.py (29 casos), fixtures/ofx/expected.json, integration_ofx.py e browser_ofx.cjs. Corpus SGML/XML fixa 100% das datas/valores/tipos/descrições e três identidades equivalentes, incluindo duas despesas iguais com FITIDs distintos. Recusas de sinal, tipo, data/fuso, correções, duplicidade de ID, múltiplas contas, entidades, profundidade/tamanho e contexto; assinatura, seleção e privacidade. PostgreSQL verifica concorrência/reordenação, exclusão/reenvio e NOWAIT; mobile verifica Windows-1252, troca de conta, vínculo/desfazimento e bloqueio da origem divergente. Não homologa bancos reais nem OFX de cartão.

OFX de cartão 0.21: ofx.py/ofx_card.py e OFX_CARTAO.md → test_ofx_card.py (18 casos), card-expected.json, integration_ofx_card.py e browser_ofx_card.cjs. Corpus distingue duas despesas iguais, crédito e pagamento; verifica máscara, confirmação de estorno, ausência de caixa/parcelas futuras, contexto, ciclo de fatura, assinatura, correção/exclusão e rollback da reserva com histórico. PostgreSQL disputa faturas diferentes e destino bloqueado; mobile verifica revisão desmarcada ao selecionar, pagamento não importável, vínculo/desfazimento e recusa em outro período. Não cobre realocação de origem, bancos reais ou crédito transportado.
