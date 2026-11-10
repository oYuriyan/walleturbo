# Manual de utilização

## Primeiro acesso

Abra a aplicação. **Explorar demonstração** carrega exemplos fictícios na memória da aba. Você pode criar e editar lançamentos/metas; ao recarregar, tudo é descartado. Nenhum exemplo é gravado no banco. Para uso real, selecione **Entrar com segurança** no ambiente local com Keycloak/TOTP configurado. Google e domínio permanecem adiados.

Na visão geral, **Primeiros passos** orienta o cadastro da conta, a referência de saldo inicial e o primeiro lançamento. O guia abre para quem ainda não tem contas; nos acessos seguintes fica recolhido e pode ser aberto pelo título. Use **Conferir saldos** para ir à data de consulta e definir a referência na conta desejada. Para que receitas/despesas alterem o saldo, selecione a conta no lançamento. O guia não aparece na demonstração ou com a sessão encerrada.

## Rotina mensal

Selecione o mês no topo. O resultado mensal é receitas menos despesas diretas e parcelas no mês de vencimento, com estornos. A movimentação de caixa considera pagamentos de fatura na data registrada. Nenhum deles é saldo consultado no banco. Vá a Movimentações para adicionar uma receita ou despesa, informando valor positivo, data, descrição e categoria. Marque a revisão quando tiver conferido a classificação. Para parcelas, estornos e pagamento de cartão, use **Contas e cartões**, conforme [Faturas](FATURAS.md); não registre também o pagamento como despesa direta. Para transferir entre suas contas, use **Registrar transferência**, conforme a seção de saldos abaixo.

A busca filtra descrição e categoria no mês selecionado. **Revisar** permite corrigir todos os campos. **Excluir** solicita confirmação antes de remover o lançamento.

## Importação CSV, OFX e PDF

Baixe o modelo no diálogo de importação. Formato UTF-8 com ponto e vírgula:

```csv
data;descricao;valor;tipo
2026-11-02;Mercado da semana;284,90;despesa
2026-11-03;Salário;6500,00;receita
```

Data ISO, valor sem separador de milhar e com vírgula e dois decimais, tipo `receita` ou `despesa`. Arquivos com até 256 KB/500 registros. Leia a prévia e confirme. Erros de validação impedem toda a importação. A sugestão de categoria usa palavras-chave e permanece pendente de revisão.

Reimportar as mesmas linhas ignora duplicados. Compras idênticas no mesmo arquivo são preservadas por contagem de ocorrência. **Limitação:** arquivos distintos com compras realmente diferentes, mas com mesma data/descrição/valor/tipo, podem colidir; registre manualmente o item após conferir. A seleção de conta e a fatura compõem o contexto de importação. Identificador do emissor e conciliação ampla de fontes divergentes continuam pendentes.

A prévia CSV permite selecionar linhas e vincular uma origem a um registro existente de mesma conta/fatura, data, valor e tipo, mesmo com descrição diferente. Confira os sinais antes de confirmar. Para corrigir uma associação equivocada, abra o mesmo arquivo no mesmo contexto, informe o motivo e use **Desfazer vínculo**. O lançamento permanece; a nova prévia permite escolher outro destino ou importar uma ocorrência independente, que poderá criar outro lançamento. Origens primárias, registros excluídos e faturas conferidas não são liberados. Após conflito, selecione o arquivo novamente e confira o estado atual. Os passos acima descrevem o CSV; o fluxo PDF está descrito abaixo.

Para extrato bancário OFX, use **Importar CSV / OFX**, selecione o formato e uma conta de destino. Confira a conta mascarada do documento antes de confirmar. IDs de origem distintos preservam despesas iguais; um ID já recebido com outros valores é sinalizado, sem sobrescrever o lançamento. Desmarque a linha divergente para importar as demais. Reenvie na mesma conta local. Saldos do arquivo não alteram seu saldo inicial, e transferências/pagamentos não são inferidos. Consulte [OFX](OFX.md) para tipos e layouts suportados.

Para OFX de cartão, selecione o período/fatura em **Contas e cartões**, use **Importar CSV / OFX** e escolha o formato de cartão. Confira final do cartão e competência antes de confirmar. Créditos selecionados exigem confirmação de que são estornos; pagamentos do emissor aparecem à parte e não são importáveis. A origem fica reservada à primeira fatura aceita, inclusive após exclusão/desfazimento. Para o lançamento originalmente criado pelo OFX, releia o arquivo na fatura atual e abra **Corrigir competência do lançamento**: escolha outra fatura em revisão, informe o motivo, simule e confira o efeito nas duas faturas antes de confirmar. Valores e ID são preservados. Vínculos adicionais devem ser desfeitos antes; exclusões e parcelas não são realocadas. Consulte [Correção de competência](OFX_REALOCACAO.md). Consulte [OFX de cartão](OFX_CARTAO.md).

Para PDF com texto selecionável, use **Ler PDF** na fatura e siga [Leitura assistida](PDF.md). Imagens e OCR ainda não são suportados. Não inclua cartão completo, CVV, senha ou dados desnecessários nas descrições. A importação real exige conta conectada; o modo demonstração admite lançamentos manuais.

Na prévia PDF, escolha um destino existente para evitar duplicação quando a descrição do documento divergir. Depois de editar data, valor ou tipo, use **Atualizar possíveis vínculos** e confira novamente. Para corrigir uma associação, informe o motivo e use **Desfazer vínculo**: o lançamento permanece e o arquivo é relido; edições ainda não importadas são descartadas. Confira a nova prévia antes de remapear ou criar uma ocorrência independente. A prévia expira em dez minutos e só pode ser usada na sessão e fatura em que foi lida.

## Metas

Informe nome, valor alvo, valor já reservado e prazo. Use **Gerenciar meta** para corrigir nome, objetivo, reserva ou prazo. Atualize a reserva conforme economiza. A sugestão mensal divide o valor restante pelos meses civis até a data, incluindo o mês atual; não inclui rendimentos nem verifica sua capacidade de poupança. Prazos vencidos aparecem como revisão necessária.

## Privacidade

Use **Baixar meus dados** para obter JSON com lançamentos, metas, contas, cartões, faturas, parcelas e pagamentos. A exportação inclui também planejamento, limites, referências de saldo, transferências e seus estados de arquivamento. Para apagar os dados financeiros, digite `EXCLUIR`. A conta do provedor de identidade não é removida. A implantação final deverá informar prazos de retenção de backup e canal de atendimento ao titular.

O tema é alternado pelo botão ◐. Somente essa preferência fica no localStorage. Navegação e formulários suportam teclado; use Escape para fechar diálogos.

## Saldos e transferências

Em **Contas e cartões**, cadastre as contas e use **Definir saldo inicial**. Informe o saldo no início da data escolhida; movimentos desse dia entram no cálculo. Use **Consultar até a data** para uma posição acumulada independente do mês de faturas. Sem referência, o saldo é desconhecido; registros sem conta impedem afirmar um consolidado completo.

**Corrigir referência** registra nova versão e motivo, preservando as anteriores na exportação. A correção redefine a base do cálculo, não representa receita. **Registrar transferência** exige origem/destino distintos, data, valor e descrição; registra uma operação já realizada fora da aplicação. **Reverter transferência** preserva a original e compensa as contas na data informada. Na mesma data, corrige um registro indevido; em data posterior, representa devolução. Consulte [SALDOS.md](SALDOS.md) para regras e exemplos.

## Gerenciar contas e cartões

Em **Contas e cartões**, use **Gerenciar conta** ou **Gerenciar cartão**. Altere o nome e salve; os vínculos permanecem e o novo nome aparece também nas operações antigas. Marque **Arquivado** e salve para impedir novos registros. Desmarque para reativar.

O arquivamento não zera saldos nem oculta dívidas. Faturas existentes ainda podem ser conferidas e pagas usando uma conta ativa. Correções de lançamentos já vinculados à conta e reversões continuam disponíveis. Para importar CSV/PDF no cartão, reative-o primeiro.

Se outra sessão tiver atualizado o cadastro, a gravação será recusada. **Recarregar cadastro** descarta o formulário atual e busca a versão mais recente; revise antes de salvar novamente. **Excluir cadastro vazio** aparece após salvar o arquivamento; a exclusão é recusada se houver vínculos, inclusive fatura vazia, referência de saldo ou transferência revertida. Consulte [Ciclo de vida](CADASTROS.md) para a política completa.

### Arquivar ou excluir metas

Em **Metas → Gerenciar meta**, marque **Meta arquivada** e salve para pausar sua participação no planejamento. Valores e prazo continuam visíveis no cadastro; desmarque para reativar. Em conflito entre sessões, use **Recarregar meta** e revise novamente.

**Excluir meta arquivada** aparece depois de salvar o arquivamento. Reserva positiva impede a exclusão. Se o valor informado precisar ser corrigido para zero, revise e salve essa alteração antes de excluir. Essas operações não movimentam dinheiro. A exportação e a exclusão integral de privacidade também abrangem metas arquivadas.

## Histórico de alterações

Em **Contas e cartões**, use **Consultar histórico** para ver criações, alterações e exclusões desde a versão 0.8, em todos os meses. Abra um registro para conferir os valores e use **Carregar mais alterações** para páginas anteriores. Atualize a consulta após novas operações. O histórico continua disponível após excluir uma operação isolada e integra a exportação. A exclusão integral de dados financeiros também o remove. Estados anteriores à implantação não são reconstruídos. Consulte [AUDITORIA.md](AUDITORIA.md) para cobertura e limitações.

## Corrigir uma compra completa

Em uma fatura aberta, escolha **Corrigir compra** em uma compra manual. Todos os meses da operação serão considerados. Corrija os campos, informe o motivo e selecione **Conferir alterações**. Revise os totais por fatura antes de **Confirmar correção**. Se outra sessão mudar a compra, use **Recarregar compra** e confira novamente. Cartão arquivado precisa ser reativado; faturas conferidas precisam de revisão/reabertura explícita. Linhas importadas podem ser corrigidas mantendo fatura e parcela única; veja a seção de revisão segura abaixo.

Excluir uma compra ou remover um pagamento mantém seu identificador de envio reservado. Um reenvio antigo não recria o registro. Para uma operação nova, use um novo cadastro pelo formulário. Consulte [CORRECOES.md](CORRECOES.md).

## Corrigir um registro de pagamento

Em **Contas e cartões**, escolha **Corrigir pagamento**. Revise conta, data, valor e data da consulta dos saldos; informe o motivo. **Conferir pagamento** mostra os saldos das contas afetadas, o pago/restante da fatura e as mudanças no caixa mensal. Sem referência, o saldo continua desconhecido. Só confirme após revisar. Isso corrige um registro local e não movimenta dinheiro no banco.

Se outra sessão alterar o pagamento, use **Recarregar pagamento**. A remoção também recusa uma versão desatualizada; atualize a tela antes de tentar novamente. A fatura original permanece. Regras completas em [PAGAMENTOS.md](PAGAMENTOS.md).

## Revisão segura e reimportação

**Revisar lançamento** exige motivo e versão atual; em conflito, **Recarregar lançamento** busca os dados atuais. A exclusão recusa uma tela desatualizada. A interface identifica novos envios por UUID para evitar duplicação por reenvio.

Reimportar linhas reconhecidas já excluídas informa quantas não foram recriadas. Use o mesmo contexto/fatura e a mesma seleção de conta da importação original. Para uma despesa realmente nova com dados iguais, registre explicitamente um lançamento/compra novo.

Em fatura aberta, **Corrigir importado** permite revisar os dados mantendo fatura e parcela única. A origem permanece reservada; a reimportação não desfaz sua correção. A revisão de categoria também verifica a versão; use **Recarregar categoria** em conflito. Detalhes e limitações em [Lançamentos e importação](LANCAMENTOS_E_IMPORTACAO.md).
