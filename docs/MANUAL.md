# Manual de utilização

## Primeiro acesso

Abra a aplicação. **Explorar demonstração** carrega exemplos fictícios na memória da aba. Você pode criar e editar lançamentos/metas; ao recarregar, tudo é descartado. Nenhum exemplo é gravado no banco. Para uso real, selecione **Entrar com segurança** depois que a equipe configurar OIDC, Google e MFA.

## Rotina mensal

Selecione o mês no topo. O resultado mensal é receitas menos despesas diretas e parcelas no mês de vencimento, com estornos. A movimentação de caixa considera pagamentos de fatura na data registrada. Nenhum deles é saldo consultado no banco. Vá a Movimentações para adicionar uma receita ou despesa, informando valor positivo, data, descrição e categoria. Marque a revisão quando tiver conferido a classificação. Para parcelas, estornos e pagamento de cartão, use **Contas e cartões**, conforme [Faturas](FATURAS.md); não registre também o pagamento como despesa direta. Transferências entre contas ainda não são suportadas.

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

Informe nome, valor alvo, valor já reservado e prazo. Atualize a reserva conforme economiza. A sugestão mensal divide o valor restante pelos meses civis até a data, incluindo o mês atual; não inclui rendimentos nem verifica sua capacidade de poupança. Prazos vencidos aparecem como revisão necessária.

## Privacidade

Use **Baixar meus dados** para obter JSON com lançamentos, metas, contas, cartões, faturas, parcelas e pagamentos. Para excluir lançamentos e metas ativos, digite `EXCLUIR`. A conta do provedor de identidade não é removida. A implantação final deverá informar prazos de retenção de backup e canal de atendimento ao titular.

O tema é alternado pelo botão ◐. Somente essa preferência fica no localStorage. Navegação e formulários suportam teclado; use Escape para fechar diálogos.
