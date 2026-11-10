# Correção de competência OFX — 0.22

Move um lançamento originalmente criado pelo OFX de cartão e sua reserva de origem para outra fatura em revisão do mesmo cartão. A seleção do mês é explícita: a data da compra não escolhe a competência automaticamente. CSV, PDF, vínculos a lançamentos manuais, exclusões e parcelas não são realocados por este fluxo.

## Uso

1. Abra previamente a fatura de destino em **Contas e cartões**. Volte à fatura atual e releia o mesmo OFX em **Importar CSV / OFX**.
2. Na origem conhecida, abra **Corrigir competência do lançamento**, escolha a fatura e informe o motivo (3–160 caracteres). A lista apresenta até 120 outras faturas em revisão do mesmo cartão, ordenadas do mês mais recente ao mais antigo.
3. Use **Simular mudança** e confira o lançamento atual, os totais e os valores restantes das duas faturas. Alterar motivo ou destino invalida a simulação e a confirmação.
4. Marque a conferência e confirme. Reenvios dessa origem passam a usar a fatura de destino; na fatura anterior recebem conflito de contexto. Para voltar ao mês anterior, faça outra realocação com nova prévia.

Preserva ID do lançamento/operação, valor, data, descrição, tipo, categoria, conferência e assinatura original, inclusive valores já corrigidos. Atualiza a competência e o motivo da última correção, incrementa as versões do lançamento e da origem, e registra antes/depois e motivo no histórico. Não cria ou exclui lançamentos, pagamentos, parcelas ou movimentos de caixa.

## Proteções e limites

Somente origem primária OFX disponível, sem outras marcas associadas e com uma única parcela/operação. Vínculos adicionais precisam ser desfeitos explicitamente antes; isso não altera o lançamento financeiro. Origem excluída, vínculo a registro manual e destino com marca/identidade ocupada recebem 409. Exclusão não é desfeita por realocação.

As duas faturas devem pertencer ao mesmo titular/cartão ativo e estar em revisão. Fatura com pagamento precisa seguir o fluxo existente: estornar o registro e reabrir antes de alterar lançamentos. A mudança também recusa pagamentos superiores ao total resultante; faturas negativas em revisão não ganham transporte de crédito por esta operação.

Cartão → faturas → recibo da origem → marca → lançamento formam a ordem de bloqueio; o lançamento usa NOWAIT. A versão da origem acompanha a mudança de contexto, inclusive em ida/volta. As revisões completas das duas faturas, motivo, arquivo e versões vinculam a simulação à confirmação: alterações intermediárias exigem nova prévia. Concorrência entre dois destinos aceita um e recusa o outro; falha reverte lançamento, reserva, versões, recibo do pedido e histórico juntos.

O arquivo é relido e sua assinatura validada; não é persistido. A marca muda de contexto e o recibo `ofx_card` aponta para a fatura atual. Não deixa uma marca financeira duplicada no mês anterior: o recibo global continua bloqueando o reenvio naquele contexto. `ofx_card_move` guarda UUID/hash/referência para repetição idempotente; repetir um pedido aceito apenas reconhece o resultado, mesmo após uma realocação posterior. Dados diferentes com o mesmo UUID recebem conflito.

## API e evidências

`POST /api/statements/{id}/import/ofx/relocate/preview`: `content`, `source_index`, `resource_id`, `destination_statement_id`, `expected_version`, `expected_origin_version`, `reason`. Responde `revision`, lançamento atual e efeitos `source`/`destination`, sem persistência. Índices seguem os lançamentos importáveis, sem os pagamentos exibidos.

`POST .../relocate`: mesmos campos, `expected_revision` da simulação, `request_id` UUID novo e `reviewed=true`. Responde `moved=1`, ID do lançamento e das faturas. Conflitos ou resposta incerta exigem conferir o estado atual; repetir o mesmo pedido é seguro. Não há liberação genérica da origem para importar em qualquer mês.

Histórico `import_relocation` e alteração de `card_charge` entram na exportação/expurgo financeiro já existentes. Motivo é dado privado, não deve incluir informação sensível desnecessária. Nenhum schema, serviço ou dependência nova; API e interface devem ser atualizadas juntas.

Aceite: `test_ofx_relocation.py` cobre 13 casos, incluindo preservação de correções, ida/volta, versões antigas, pagamentos, isolamento, vínculos, exclusão e falha de auditoria. `integration_ofx_relocation.py` verifica concorrência 200/409, reenvio e NOWAIT em PostgreSQL. `browser_ofx_relocation.cjs` verifica simulação, revisão invalidada ao editar, preservação de ID/histórico e descarte de resposta após fechar. Evidências finais/commit ficam no PR.
