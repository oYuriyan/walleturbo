# Correções de compras e proteção de reenvios — 0.9

## Correção integral

Em **Contas e cartões**, numa fatura aberta, use **Corrigir compra** em uma compra manual. O formulário carrega a operação inteira, inclusive parcelas de outros meses. Informe descrição, data, valor total, quantidade de parcelas, primeira fatura, tipo, categoria/revisão e motivo. **Conferir alterações** mostra os totais das faturas antes/depois; a prévia não grava parcelas, faturas, recibos de envio ou histórico. Alterar o formulário invalida a prévia. **Confirmar correção** aplica os valores conferidos em uma transação.

O cartão original é mantido e deve estar ativo. Todas as faturas de origem e destino precisam estar abertas, mesmo quando uma parcela será removida do mês. Se alguma estiver conferida, a correção inteira é recusada; pagamentos existentes impedem reabrir a fatura conforme a política atual. Revise/remova registros incorretos de pagamento antes de reabrir, sem desfazer transações bancárias reais. Não há alteração automática de fatura paga.

O valor total é redistribuído em centavos, com o resto nas primeiras parcelas. Sobreviventes mantêm seus IDs; parcelas excedentes são removidas e novas recebem IDs próprios. Categoria e revisão informadas aplicam-se a todas as parcelas. O motivo fica em `correction_reason` e no histórico. Novas faturas são criadas somente na confirmação, se necessárias. Faturas antigas vazias permanecem preservadas. Estorno exige uma única parcela. Não há cálculo de juros ou movimentação bancária.

Linhas importadas por CSV/PDF continuam com revisão de categoria e exclusão conforme regras existentes; a correção integral delas permanece pendente para não invalidar silenciosamente sua deduplicação. Demonstração não simula essa nova operação. Edição direta de pagamento, troca de cartão, crédito entre faturas e versão ampla de lançamentos/pagamentos continuam no roadmap.

## API e concorrência

- `GET /api/card-operations/{uuid}`: operação atual, parcelas e revisão opaca.
- `POST /api/card-operations/{uuid}/preview`: corpo de compra mais UUID novo de envio, `expected_revision` e `reason`; retorna os totais por mês sem escrita.
- `PUT /api/card-operations/{uuid}`: confirma o mesmo corpo; revalida revisão e faturas dentro da transação.

A revisão incorpora o estado das parcelas e sua versão monotônica. Uma revisão de categoria também a invalida, inclusive quando a categoria muda e depois volta ao valor anterior. Versão desatualizada recebe 409; **Recarregar compra** descarta o formulário e busca a operação atual para nova conferência. A prévia não reserva valores nem impede alterações por outra sessão. Chamadas diretas de API devem oferecer ao usuário a mesma revisão antes da confirmação.

Um UUID de correção aceito retorna o estado atual da operação no reenvio idêntico, sem reaplicar valores antigos. Reuso do UUID com conteúdo/compra diferente recebe 409. Após excluir a operação, correções não a recriam. Identificadores de terceiros retornam 404; mutações exigem origem/CSRF e cotas existentes. A API de revisão por parcela recarrega o vínculo à fatura depois de adquirir os locks para respeitar uma correção concorrente que mova a parcela.

Escritores com UUID bloqueiam recibo antes do cartão; em seguida faturas e conta de pagamento conforme necessário. Correções preservam o histórico na mesma conexão/transação. Falha em qualquer parcela/histórico reverte também recibos e faturas criadas nessa tentativa. Concorrência real é verificada em PostgreSQL; SQLite isolado não prova locks.

## Recibos de envio e exclusões

`request_receipts` guarda proprietário, escopo (`purchase`, `payment`, `purchase_edit`), UUID, hash de conteúdo e referência ao registro, além de cancelamento. O hash não é exposto na exportação. Não armazena faturas brutas, descrições ou credenciais.

Exclusão de compra manual e remoção de pagamento preservam seu UUID como cancelado. Reenvio posterior é recusado (409 quando o cadastro associado ainda existe), em vez de recriar o registro. Nova operação exige novo UUID. Exclusão repetida de um registro cujo recibo já está cancelado pode retornar 204 sem gerar novo evento financeiro. Uma tentativa malsucedida não consome o UUID: recibo e operação são revertidos juntos.

Reenvio da criação de uma compra corrigida retorna suas parcelas atuais; não restaura os valores originais. O hash de criação continua correspondendo ao envio original. Recibos de correção permanecem separados. A proteção cobre compras manuais e pagamentos com UUID, incluindo cadastros existentes na migração. CSV/PDF após exclusão, lançamentos manuais sem UUID e idempotência entre formatos ainda dependem de FIN-05/IMP-02. O histórico não substitui esses controles.

## Migração, retenção e privacidade

Migração 008 adiciona versão/motivo às parcelas e cria recibos a partir das compras manuais e pagamentos existentes. UUIDs de registros já excluídos são reservados quando há evento correspondente no histórico introduzido na 0.8. Para esses cancelamentos sem hash original, a migração reserva o UUID com hash marcador; ele nunca é aceito como envio novo. Registros ativos têm precedência sobre eventos antigos. Não é possível recuperar exclusões anteriores ao histórico ou não registradas nele.

Recibos permanecem durante a manutenção dos dados financeiros do titular, integram a exportação e são removidos pela exclusão integral de privacidade. Exclusão isolada não os remove. Retenção de produção/backups, RLS, privilégios mínimos e cotas de armazenamento continuam pendentes nas fases operacionais. A migração preserva valores/IDs; não remove volumes. O crescimento e a exportação integral precisam da revisão REL-04/08.

## Verificação

`test_corrections.py`: prévia sem escrita, centavos/IDs, redução/aumento de parcelas, versão obsoleta/retorno ao estado anterior, bloqueio de fatura de origem/destino conferida, isolamento, importados, arquivamento, UUID cancelado, expurgo e rollback parcial. `integration_cards.py`: correções concorrentes, exclusão versus reenvio, pagamentos removidos e UUID entre cartões. `integration_migrations.py`: dados legados, versões, recibos e cancelamentos auditados. `browser_corrections.cjs`: prévia mobile, confirmação, conflito/recarga, reenvio cancelado e limpeza na expiração. Aceite completo depende do CI do código correspondente, registrado em HOMOLOGACAO.md.
