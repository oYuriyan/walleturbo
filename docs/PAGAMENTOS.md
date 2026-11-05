# Correção de registros de pagamento — 0.10

## Uso e alcance

Em **Contas e cartões**, escolha **Corrigir pagamento** num registro existente. Ajuste conta, data e valor, escolha a data de consulta dos saldos e informe o motivo. **Conferir pagamento** mostra a prévia; **Confirmar ajuste do registro** aplica a correção. Editar o formulário invalida a prévia. Em conflito, use **Recarregar pagamento** e confira novamente.

A fatura, o cartão e o ID do pagamento são mantidos. A correção não executa transferência, pagamento ou devolução no banco. Não altera compras/parcelas nem despesas de consumo. A data do pagamento muda sua participação no caixa do mês e nos saldos por data; o valor muda quanto está pago e quanto falta na fatura. Para outra fatura, remova o registro incorreto explicitamente e registre um novo pagamento com novo identificador.

A fatura precisa estar conferida. O valor corrigido deve ser positivo e não pode superar o total menos os demais pagamentos. Conferência e soma são revalidadas sob lock, inclusive quando outro pagamento da mesma fatura é corrigido em paralelo. Manter a conta original arquivada permite corrigir seu registro existente; mudar para outra conta exige destino ativo. Cartão arquivado não impede corrigir um pagamento existente.

## Prévia dos saldos e do caixa

A prévia não grava pagamento, recibo de envio ou histórico. Para cada conta afetada, apresenta saldo antes/depois **na data de consulta**. Respeita a referência de saldo vigente e sua data inicial: registros anteriores à referência ficam no histórico e não entram no cálculo; pagamentos posteriores à consulta também não entram. Sem referência aplicável, mostra saldo desconhecido, sem inventar zero. A prévia também apresenta pago/restante da fatura e mudanças no caixa dos meses envolvidos.

Exemplo sintético: referências de R$ 100,00 na conta Principal e R$ 200,00 na Reserva no início de novembro; fatura de R$ 150,00, com pagamentos de R$ 60,00 e R$ 30,00 na Principal em novembro. Corrigir o primeiro pagamento para R$ 40,00 na Reserva em dezembro resulta, na consulta até o fim de dezembro, em R$ 70,00 na Principal e R$ 160,00 na Reserva. A fatura fica com R$ 70,00 pagos e R$ 80,00 restantes. O consumo de novembro continua R$ 150,00; a variação do caixa registrado muda em +R$ 60,00 em novembro e −R$ 40,00 em dezembro.

A prévia é uma simulação dos registros naquele instante, sem reserva de saldo ou consulta bancária. Outras operações/referências podem mudar depois dela; confirmação revalida a versão do pagamento e o limite da fatura. O formulário deve ser revisado novamente após conflito. Saldos calculados não autorizam automaticamente aportes ou compras.

## Contrato da API

- `GET /api/statement-payments/{id}`: registro atual com `version` e resumo da fatura.
- `POST /api/statement-payments/{id}/preview`: `request_id` (UUID novo de correção), `expected_version`, `account_id`, `date`, `amount_cents`, `as_of` e `reason`.
- `PUT /api/statement-payments/{id}`: confirma o mesmo corpo, mantendo fatura, ID e UUID da criação.
- `DELETE /api/statement-payments/{id}?expected_version=N`: remove somente a versão revisada do registro.

**Mudança de contrato na 0.10:** a remoção agora exige `expected_version`. Clientes antigos sem o parâmetro recebem 422 e precisam atualizar. Versão desatualizada recebe 409; não é apagada uma correção feita por outra sessão. Repetir a remoção de um registro cujo recibo já está cancelado pode retornar 204 sem novos eventos. IDs alheios retornam 404; sessão/origem/CSRF e cotas permanecem obrigatórios.

A versão monotônica começa em 1 e aumenta em alterações efetivas, inclusive mudança e retorno aos mesmos valores. Cada correção exige motivo. O recibo usa escopo `payment_edit`; o UUID/hash originais da criação continuam preservados. Reenvio idêntico da criação ou correção retorna o estado atual sem reaplicar valores antigos, desde que os cadastros necessários continuem existentes. Reuso do UUID de correção com outros dados recebe 409. Falha reverte a alteração e o recibo; a mesma tentativa pode ser corrigida e reenviada se não foi aceita.

Após remoção, uma correção não recria o pagamento. O recibo original cancelado continua bloqueando reenvio da criação, conforme CORRECOES.md. Conta de origem antiga removida pode causar 404 no reenvio da criação antes da consulta do recibo; isso também impede recriação.

## Integridade, histórico e privacidade

A ordem dos locks é recibo de correção → cartão/fatura → pagamento → contas ordenadas por ID. Os escritores existentes continuam bloqueando cartão/fatura antes das contas. A correção conserva o ID e o vínculo à fatura e é gravada com o histórico na mesma transação. Falha no histórico impede a mudança financeira. Motivo, conta, data, valor e versão anteriores/posteriores integram o histórico privado e a exportação.

A consulta visual do histórico usa os nomes atuais dos cadastros para os vínculos a contas; o JSON exportado preserva os IDs, inclusive se um cadastro já não existir. Renomeações seguem a política de CADASTROS.md. Os motivos não devem conter informações sensíveis desnecessárias. Dados e recibos integram o expurgo financeiro integral; retenção de produção/backups e encerramento da identidade continuam pendentes nas fases operacionais/LGPD.

Migração 009 adiciona versão e motivo aos pagamentos legados sem alterar valor, conta, data, ID ou UUID. Não cria alterações financeiras fictícias. Aplicação e clientes de remoção devem ser atualizados com o schema.

## Validação e pendências

`test_payment_corrections.py` cobre prévia sem escrita, saldo desconhecido, fronteira da referência, datas futuras, caixa por mês, limite com outros pagamentos, versões/retorno ao estado anterior, remoção obsoleta, reenvios, arquivamento, isolamento, expurgo e rollback em falha do histórico. `integration_payment_corrections.py` verifica concorrência em PostgreSQL, inclusive dois pagamentos distintos disputando limite e remoção versus edição. `browser_payment_corrections.cjs` verifica a jornada mobile, prévia, conflito/recarga, remoção obsoleta e limpeza de sessão. O upgrade preserva pagamento legado no roteiro de migrações.

Esta entrega não conclui FIN-04/05: versão ampla de lançamentos diretos, correção integral de importados, importações após exclusão e idempotência entre formatos permanecem pendentes. Regras de crédito negativo, projeção/recorrências e aportes continuam nas fases seguintes. Homologação completa depende do CI registrado em HOMOLOGACAO.md.

**Homologação técnica aprovada:** [CI 42033442245](https://github.com/oYuriyan/walleturbo/actions/runs/42033442245), código `39c0a67`, com 123 testes em container, PostgreSQL/Redis, upgrade e roteiro mobile. Captura da prévia inspecionada visualmente. A aprovação cobre os cenários declarados e mantém as pendências acima.
