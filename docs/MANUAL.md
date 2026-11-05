# Manual de utilização

## Primeiro acesso

Abra a aplicação. **Explorar demonstração** carrega exemplos fictícios na memória da aba. Você pode criar e editar lançamentos/metas; ao recarregar, tudo é descartado. Nenhum exemplo é gravado no banco. Para uso real, selecione **Entrar com segurança** no ambiente local com Keycloak/TOTP configurado. Google e domínio permanecem adiados.

## Rotina mensal

Selecione o mês no topo. O resultado mensal é receitas menos despesas diretas e parcelas no mês de vencimento, com estornos. A movimentação de caixa considera pagamentos de fatura na data registrada. Nenhum deles é saldo consultado no banco. Vá a Movimentações para adicionar uma receita ou despesa, informando valor positivo, data, descrição e categoria. Marque a revisão quando tiver conferido a classificação. Para parcelas, estornos e pagamento de cartão, use **Contas e cartões**, conforme [Faturas](FATURAS.md); não registre também o pagamento como despesa direta. Para transferir entre suas contas, use **Registrar transferência**, conforme a seção de saldos abaixo.

A busca filtra descrição e categoria no mês selecionado. **Revisar** permite corrigir todos os campos. **Excluir** solicita confirmação antes de remover o lançamento.

## Importação CSV

Baixe o modelo no diálogo de importação. Formato UTF-8 com ponto e vírgula:

```csv
data;descricao;valor;tipo
2026-11-02;Mercado da semana;284,90;despesa
2026-11-03;Salário;6500,00;receita
```

Data ISO, valor sem separador de milhar e com vírgula e dois decimais, tipo `receita` ou `despesa`. Arquivos com até 256 KB/500 registros. Leia a prévia e confirme. Erros de validação impedem toda a importação. A sugestão de categoria usa palavras-chave e permanece pendente de revisão.

Reimportar as mesmas linhas ignora duplicados. Compras idênticas no mesmo arquivo são preservadas por contagem de ocorrência. **Limitação:** arquivos distintos com compras realmente diferentes, mas com mesma data/descrição/valor/tipo, podem colidir; registre manualmente o item após conferir. A próxima versão precisa incorporar identidade de conta/fatura e identificador bancário.

Para PDF com texto selecionável, use **Ler PDF** na fatura e siga [Leitura assistida](PDF.md). Imagens, OCR e OFX ainda não são suportados. Não inclua cartão completo, CVV, senha ou dados desnecessários nas descrições. A importação real exige conta conectada; o modo demonstração admite lançamentos manuais.

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

Em uma fatura aberta, escolha **Corrigir compra** em uma compra manual. Todos os meses da operação serão considerados. Corrija os campos, informe o motivo e selecione **Conferir alterações**. Revise os totais por fatura antes de **Confirmar correção**. Se outra sessão mudar a compra, use **Recarregar compra** e confira novamente. Cartão arquivado precisa ser reativado; faturas conferidas precisam de revisão/reabertura explícita. A correção integral de linhas importadas ainda não está disponível.

Excluir uma compra ou remover um pagamento mantém seu identificador de envio reservado. Um reenvio antigo não recria o registro. Para uma operação nova, use um novo cadastro pelo formulário. Consulte [CORRECOES.md](CORRECOES.md).

## Corrigir um registro de pagamento

Em **Contas e cartões**, escolha **Corrigir pagamento**. Revise conta, data, valor e data da consulta dos saldos; informe o motivo. **Conferir pagamento** mostra os saldos das contas afetadas, o pago/restante da fatura e as mudanças no caixa mensal. Sem referência, o saldo continua desconhecido. Só confirme após revisar. Isso corrige um registro local e não movimenta dinheiro no banco.

Se outra sessão alterar o pagamento, use **Recarregar pagamento**. A remoção também recusa uma versão desatualizada; atualize a tela antes de tentar novamente. A fatura original permanece. Regras completas em [PAGAMENTOS.md](PAGAMENTOS.md).
