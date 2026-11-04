# Saldos por conta e transferências — contrato financeiro

O saldo inicial representa o valor informado no **início da data de referência**. Movimentos dessa data entram no cálculo; movimentos anteriores continuam no histórico e no resultado do mês, mas não entram novamente no saldo. A consulta informa a quantidade de movimentos anteriores desconsiderados. Consultas anteriores à referência não estimam saldo retroativo.

Saldo calculado até uma data (inclusive) = saldo inicial + receitas vinculadas − despesas vinculadas − pagamentos de fatura + transferências recebidas − transferências enviadas + reversões correspondentes. Compras/parcelas de cartão afetam o consumo; somente o pagamento afeta a conta. Saldo inicial e transferências não alteram receita, despesa ou resultado mensal.

Conta sem referência tem saldo desconhecido, não zero. Registros antigos sem conta permanecem sem vínculo automático. A visão consolidada indica contas sem referência e lançamentos sem conta: nessas situações mostra subtotal das contas conhecidas e não afirma total completo. O saldo é calculado pelos registros, não consultado no banco; admite negativos e não constitui autorização de pagamento.

Correções de saldo inicial criam revisões preservadas, com motivo e controle de versão. São uma correção da referência, não uma receita nem um ajuste posterior de caixa. Consultas passadas usam a referência corrigida mais recente; o histórico de revisões está disponível na exportação. Reenvio da mesma solicitação retorna a revisão original, mesmo depois de outra correção; versão obsoleta com nova solicitação é recusada. Não há exclusão individual dessas revisões.

Uma transferência registra, atomicamente, origem e destino diferentes do mesmo proprietário, valor positivo e data civil. É um registro do que ocorreu, não uma ordem bancária; não bloqueia saldo negativo ou desconhecido. Taxas devem ser lançadas separadamente como despesa. O identificador da solicitação é preservado; reenvio idêntico não cria outra transferência e reuso com conteúdo diferente é recusado, inclusive depois de reversão.

Reversão preserva a transferência e adiciona o efeito inverso na data informada, que não pode anteceder a original. Uma segunda chamada com a mesma data retorna a mesma reversão; data divergente é conflito. Para corrigir um cadastro que nunca ocorreu, reverta na mesma data e registre uma nova transferência; para devolução posterior, use a data real. Não há edição/exclusão individual da transferência. Exclusão global financeira remove também transferências e revisões, conforme PRIVACIDADE.md; após essa exclusão o registro de idempotência deixa de existir.

Locks de contas em ordem de identificador serializam criação/reversão e revisão da referência. As duas pontas da transferência estão no mesmo registro transacional, com FKs compostas por proprietário. Leituras de saldo usam uma única consulta SQL para obter referência e movimentos em um snapshot consistente.
