# Contas, cartões e faturas — versão 0.2

## Conceitos financeiros

**Resultado do mês** = receitas diretas − despesas diretas − compras/parcelas de cartão com vencimento no mês + estornos creditados nessas faturas.

**Movimentação líquida de caixa** = receitas diretas − despesas diretas − pagamentos de fatura efetivamente registrados no mês. É a variação registrada, não um saldo bancário consultado: não inclui saldo inicial nem integração com o banco.

Exemplo: uma compra de R$ 100,01 em três vezes gera R$ 33,34, R$ 33,34 e R$ 33,33. Registrar um pagamento de R$ 20,00 na primeira fatura mantém a despesa daquele mês em R$ 33,34, reduz o caixa em R$ 20,00 e deixa R$ 13,34 a pagar. Se o pagamento ocorrer no mês seguinte, só o caixa do mês seguinte muda.

## Utilização

1. Em **Contas e cartões**, cadastre um apelido para a conta e um apelido/dia de vencimento para o cartão. Não são coletados número completo, CVV ou credenciais bancárias.
2. Use **Compra ou estorno**. Informe o **valor total da compra**, quantidade de parcelas e mês da primeira fatura conforme o emissor. A distribuição preserva os centavos, acrescentando o resto às primeiras parcelas. Limite de 36 parcelas.
3. Troque o período para consultar as próximas faturas. Para dias 29–31 em meses mais curtos, o vencimento é ajustado ao último dia. Não há ajuste por feriados/dias úteis.
4. Alternativamente, abra uma fatura vazia e importe um CSV nela. Cada linha corresponde a um lançamento **já cobrado naquela fatura**, sem gerar novas parcelas automaticamente. CSV de fatura aceita apenas `despesa`; registre estornos separadamente para evitar interpretar receitas como créditos indevidos.
5. Revise as categorias. Use **Conferir total** e digite o valor informado pelo emissor. A fatura só é fechada se não houver revisões pendentes e os valores coincidirem exatamente. Encargos podem ser registrados como despesa antes da conferência.
6. Use **Registrar pagamento** para registrar o que já foi pago no banco. Pagamentos parciais são aceitos até o valor restante. O sistema não executa transferências nem quita o cartão junto ao banco.
7. Para corrigir um pagamento, use **Estornar registro**. Isso remove o registro local, sem desfazer uma operação bancária. Uma fatura com pagamentos não pode ser reaberta; primeiro remova os registros incorretos, depois reabra e ajuste.

A exclusão de uma compra remove todas as suas parcelas atomicamente. Se alguma fatura estiver conferida, a exclusão é recusada. Estornos financeiros são lançamentos explícitos, distintos da correção de um registro. Estornos creditados após uma fatura paga devem ser lançados na fatura em que o emissor os creditou.

## Integridade e concorrência

- Compras/pagamentos exigem UUID de solicitação. Reenvio idêntico enquanto o registro existir retorna o registro anterior; reuso com conteúdo diferente retorna 409. Não é um registro permanente de idempotência: após exclusão, o mesmo identificador pode ser reutilizado. Clientes devem sempre gerar identificadores novos para novas operações.
- Escritores bloqueiam o cartão e a fatura na mesma ordem no PostgreSQL. Isso serializa fechamento, edição e pagamentos; duas solicitações não conseguem pagar mais que o saldo restante.
- Chaves estrangeiras compostas com `owner` impedem associar conta/cartão/fatura de outra pessoa também no banco.
- Importação é atômica. A deduplicação de cartão considera proprietário, fatura e ocorrência da linha; a de movimentações diretas pode ser vinculada a uma conta. Arquivos distintos com compras realmente diferentes, mas com dados idênticos na mesma fatura, ainda podem colidir; revisar com o emissor.
- Exportação e exclusão financeira incluem contas, cartões, faturas, parcelas e pagamentos. O histórico 0.1 permanece como lançamento direto, sem conversão automática para cartão, para não inventar associações.

## Limites explícitos

A conferência compara totais digitados; não autentica um documento do banco. Existe leitura assistida limitada de PDF textual (ver PDF.md). Não há OCR, OFX, sincronização bancária, juros/rotativo automáticos, fechamento por regra do emissor, saldo por conta, limite de crédito, transferências entre contas ou carregamento de crédito negativo entre faturas. Faturas com total negativo podem permanecer em revisão, mas não são fechadas ou pagas nesta etapa. Metas continuam independentes das contas. Renomeação/exclusão individual de contas/cartões será tratada com política de histórico; a exclusão global já os inclui.
