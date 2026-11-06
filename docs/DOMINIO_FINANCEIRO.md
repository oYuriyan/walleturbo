# Contrato financeiro consolidado

Descreve o comportamento existente até a 0.14. Não representa contabilidade fiscal ou saldo consultado em banco. Valores são inteiros em centavos de BRL, sem conversão cambial. Datas financeiras são datas civis informadas, sem conversão automática de fuso. O mês da primeira fatura é explícito: a data da compra não determina automaticamente o fechamento do emissor.

## Grandezas e sinais

| Grandeza | Regra | Não inclui |
| --- | --- | --- |
| Receita mensal | Receitas diretas na data do lançamento | Saldo inicial, transferência própria, estorno de cartão |
| Despesa mensal | Despesas diretas + parcelas na fatura do mês − estornos nessa fatura | Pagamentos de fatura, transferências, reserva declarada de meta |
| Resultado mensal | Receita − despesa | Saldo acumulado de meses anteriores |
| Variação de caixa mensal | Receitas diretas − despesas diretas − pagamentos registrados no mês | Compra/estorno de cartão sem efeito bancário |
| Saldo calculado da conta | Referência inicial + movimentos vinculados desde a referência até a consulta | Registros sem conta e anteriores à referência |
| Restante da fatura | Total das parcelas menos estornos e pagamentos vinculados | Crédito automático de outra fatura |

No dashboard, `balance_cents` significa resultado mensal e `cash_balance_cents` significa variação de caixa. No planejamento, os equivalentes são `result_cents` e `cash_change_cents`. Em `/api/balances`, `balance_cents` por conta significa saldo calculado. Consumidores da API devem respeitar o contexto dos nomes legados.

Compras e estornos recebem valor positivo e tipo explícito; o sinal é aplicado no cálculo. Parcelamento conserva o valor total: R$ 100,01 em três vezes resulta em R$ 33,34, R$ 33,34 e R$ 33,33. Restos ficam nas primeiras parcelas. Linha importada de fatura representa cobrança daquele mês, sem gerar parcelas futuras automaticamente.

Transferência própria conserva a soma dos saldos e altera cada conta. Reversão tem data própria e preserva o movimento original. Corrigir/remover registro local de pagamento não executa devolução bancária. Estorno de cartão deve ser registrado na fatura em que o emissor o creditou, sem criar receita direta para ajustar o caixa.

## Exemplo verificável em três meses

No início de novembro, A tem R$ 100,00 e B R$ 5,00. Em novembro: receita de R$ 500,00 e despesa de R$ 12,34 em A; compra de R$ 100,01 em três faturas a partir de novembro; estorno de R$ 3,34 na primeira fatura; pagamento parcial de R$ 20,00 por A; transferência de R$ 50,00 de A para B. A transferência é revertida em dezembro. Sem outros movimentos:

| Mês | Despesa | Resultado | Variação de caixa | Saldo A | Saldo B |
| --- | ---: | ---: | ---: | ---: | ---: |
| Novembro | R$ 42,34 | R$ 457,66 | R$ 467,66 | R$ 517,66 | R$ 55,00 |
| Dezembro | R$ 33,34 | −R$ 33,34 | R$ 0,00 | R$ 567,66 | R$ 5,00 |
| Janeiro | R$ 33,33 | −R$ 33,33 | R$ 0,00 | R$ 567,66 | R$ 5,00 |

A primeira fatura totaliza R$ 30,00, com R$ 10,00 restantes. As demais continuam pendentes; ausência de pagamento não apaga despesa. Soma final dos saldos = R$ 105,00 iniciais + R$ 467,66 de caixa registrado = R$ 572,66.

Se o comprovante demonstrar pagamento de R$ 20,00 em dezembro pela conta B, a correção altera novembro para caixa de R$ 487,66 e saldo A de R$ 537,66; dezembro passa a caixa de −R$ 20,00, saldo A de R$ 587,66 e B de −R$ 15,00. Resultado, parcelas e restante da primeira fatura permanecem iguais. A soma continua R$ 572,66. Saldo negativo é admitido e não autoriza operação bancária. Relatórios passados refletem correções atuais; não são snapshots contábeis imutáveis.

`tests/test_financial_contract.py` verifica ambas as variantes via API contra valores fixos independentes, comparando dashboard, planejamento e saldos. Repete compra, pagamento, transferência, reversão e correção para verificar ausência de duplicação. Usa dados sintéticos e sessão de teste; não substitui login real de REL-01 nem concorrência PostgreSQL.

## Correções, versões e idempotência

Prévia não grava. Correções aceitas preservam histórico privado e são atômicas; conflitos exigem recarga. Compras que atingem fatura conferida não são editadas silenciosamente. Conferência exige total e revisão atuais; reabertura é impedida enquanto houver pagamentos. Planejamento confirmado exige revisão dos registros lidos, inclusive mudanças sem alteração de totais. Alterações posteriores podem invalidá-lo na próxima consulta.

UUIDs protegem reenvios conforme cada operação; conteúdo divergente com o mesmo identificador é conflito. Recibos de compras/pagamentos e marcas de importação sobrevivem à exclusão individual. Expurgo financeiro remove essas proteções com os dados; não há idempotência eterna após expurgo. Contratos específicos: [CORRECOES.md](CORRECOES.md), [PAGAMENTOS.md](PAGAMENTOS.md), [LANCAMENTOS_E_IMPORTACAO.md](LANCAMENTOS_E_IMPORTACAO.md) e [SALDOS.md](SALDOS.md).

## Legado, referências e limites

Esta consolidação não modifica schema ou valores. Migrações 001–012 continuam obrigatórias, verificadas por checksum. Lançamentos legados sem conta não recebem vínculo presumido. Conta sem referência tem saldo desconhecido. A igualdade entre saldo inicial mais caixa acumulado e saldo final só vale para o conjunto integralmente vinculado e dentro das referências utilizadas. Referência corrigida altera consultas históricas; revisões permanecem exportáveis.

Planejamento é simulação conservadora atual, não disponibilidade bancária: não somar automaticamente saldos à capacidade de aporte. Metas têm reserva declarada independente das contas. Créditos/faturas negativas, limites/encargos, recorrências, projeções e aportes vinculados permanecem na fase 2. Identidade entre documentos divergentes segue em IMP-02/03. RLS, restauração, volume e jornada real completa seguem na fase 5. Esta documentação não conclui esses itens nem libera produção.
