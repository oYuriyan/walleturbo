# OFX de cartão — 0.21

Leitura assistida de uma resposta CCSTMTTRNRS/CCSTMTRS em BRL, SGML 102/103 ou XML 2.x, na fatura escolhida pelo usuário. Reutiliza limites, validação, datas civis, assinatura e revisão do OFX bancário; não homologa bancos reais, autenticidade do documento ou todos os layouts de emissores.

## Uso e significado financeiro

Em **Contas e cartões**, selecione o período, abra a fatura em revisão e use **Importar CSV / OFX → OFX de cartão**. Confira emissor, final do cartão e competência da fatura. A data de compra não determina automaticamente o mês da fatura; a associação inicial é uma decisão explícita. Nenhuma parcela futura é expandida.

- DEBIT/POS/FEE/SRVCHG/INT negativos são candidatos a despesa/encargo. CREDIT positivo é candidato a estorno, sujeito a conferência adicional.
- Antes de confirmar créditos selecionados, marque **Conferi que os créditos selecionados são estornos, não pagamentos do cartão**. Alterar a seleção desmarca essa confirmação. Se um crédito genérico representar pagamento, desmarque a linha: não é possível inferir o significado bancário apenas pelo sinal.
- PAYMENT positivo é exibido separadamente como **Pagamento não importável**, sem seleção, registro de pagamento, baixa de dívida ou movimento no caixa. Arquivo só com pagamentos pode ser lido, mas não cria lançamentos. Não reserva identidade para pagamentos ignorados.

MEMO tem precedência sobre NAME. Descrições extraídas e rótulo do emissor ocultam sequências semelhantes a PAN; o ACCTID aparece somente como final mascarado na prévia. Revise texto livre para dados pessoais. Não há persistência do arquivo, identificadores brutos do cartão/FITID ou descrições originais não revisadas como metadados: a assinatura armazena apenas hash. Descrições com números ocultos são as que entram nas despesas/estornos.

Outros tipos, sinais contraditórios, correções CORRECTFITID/CORRECTACTION, formatos mistos, múltiplos extratos, outras moedas e estrutura desconhecida recusam o arquivo inteiro. FI com ORG e/ou FID e CCACCTFROM/ACCTID são obrigatórios. Limites: 256 KB, 500 STMTTRN incluindo pagamentos, profundidade 24, datas de 1900–9998. Nenhum saldo auxiliar ou pagamento do arquivo altera o total dos consumos/estornos; LEDGERBAL não é comparado automaticamente ao total da fatura. Crédito transportado, rotativo e fechamento de faturas negativas continuam na fase 2 do roadmap.

## Origem reservada à fatura

A origem combina titular, cartão local, FI/ORG/FID, ACCTID e FITID. Preserva espaços internos e zeros, sem depender da ordem do arquivo ou da fatura escolhida. Reexports devem conservar esses identificadores; diferenças no contexto do emissor não têm equivalência automática homologada.

O recibo técnico `ofx_card` registra a assinatura original e a primeira fatura aceita em `resource_id`. As marcas continuam no escopo `card`, com a fatura como contexto, conservando versões e tombstones já existentes. A reserva ocorre apenas para linhas selecionadas, na mesma transação dos lançamentos e do histórico; prévia não reserva. Duas confirmações concorrentes para faturas diferentes não podem aceitar a mesma origem em ambas.

Reenvio na fatura original reconhece a origem, preserva correções do lançamento e não recria exclusões. Dados originais divergentes recebem conflito; não substituem a assinatura ou o destino silenciosamente. Vínculo, motivo, desfazimento e nova associação reutilizam o protocolo do CSV. Após desfazer é necessário refazer a prévia para obter a revisão atual.

Desfazer um vínculo ou excluir a compra **não libera a origem para outra fatura**. O mês da primeira associação permanece reservado, inclusive sem o registro financeiro. Isso impede duplicação por reenvio em outro período. Corrigir uma competência escolhida por engano exige um fluxo explícito de realocação, ainda pendente; não tente contornar escolhendo outro cartão local, pois isso cria outro contexto. Identidade primária e destinos excluídos/fora do contexto não são liberados pelo desfazimento.

## API e operação

- `POST /api/statements/{id}/import/ofx/preview`: `content` obrigatório; retorna formato, emissor em `bank_id`, final em `source_account`, `statement_month`, `entries`, `payments`, `source_conflicts`, `context_conflicts`, versões/origens e destinos possíveis. Índices referem-se à lista de lançamentos importáveis, sem os pagamentos exibidos à parte.
- `POST .../confirm`: `content`, `reviewed=true`, `credits_reviewed=true` quando houver estorno selecionado, além de seleção/vínculos/versões do CSV. Crédito sem confirmação recebe 422. Origem já reservada em outra fatura ou com assinatura divergente recebe 409; é possível desmarcá-la e confirmar outras origens válidas.
- `POST .../unlink`: `content` e `release`, com índice, destino, versões e motivo, restritos à fatura original.

Conta do usuário, cartão ativo e fatura aberta são revalidados. Escritores bloqueiam cartão → fatura → recibos → marcas em ordem estável e usam NOWAIT no destino vinculado. Falha reverte todo o lote, inclusive reservas globais e histórico. Exportação/expurgo já abrangem recibos e marcas; nenhum schema, serviço ou dependência nova. Atualize API/interface juntas. Hashes continuam sendo dados sujeitos à proteção; não são prova de autenticidade ou anonimização universal.

## Corpus e aceite

`card-102.ofx`, `card-220.ofx` e `card-expected.json` em tests/fixtures/ofx fixam duas despesas iguais de 12.345 centavos com IDs distintos, crédito de 2.000 e pagamento separado de 5.000, em ordens diferentes. Aceite: 100% das três origens financeiras/valores/datas/tipos e do pagamento recuperados; total dos consumos/estorno de 22.690 centavos, sem abater o pagamento ou criar parcelas; reenvio cria zero registros; disputa entre faturas aceita uma e recusa outra.

`test_ofx_card.py` cobre corpus, sinais, revisão, isolamento, ciclo da fatura, assinatura, correção/exclusão, reserva, rollback e privacidade. PostgreSQL valida concorrência entre faturas, reordenação, exclusão/reenvio e NOWAIT. Mobile valida revisão adicional de créditos, pagamentos não importáveis, máscara, vínculos/desfazimento e bloqueio em outro mês. Evidências e commit final são registrados no PR da entrega, sem declarar homologação WCAG ou de bancos reais.
