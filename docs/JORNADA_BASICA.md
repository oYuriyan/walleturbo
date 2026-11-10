# Jornada financeira integrada — homologação de 10/11/2026

Complementa as jornadas de interface existentes com um cenário financeiro único, na mesma identidade autenticada por Keycloak/TOTP. Reutiliza browser_oidc.cjs e o ambiente da CI; não cria serviço, dependência, endpoint ou funcionalidade de produto. A versão da aplicação permanece 0.24; commits/PR versionam esta ampliação de testes.

## Cenário e resultados esperados

As fixtures criam duas pessoas sintéticas, com senha e cadastro TOTP reais, sem inserir sessão diretamente no Redis para esta jornada. Mantém as recusas de TOTP incorreto/ausente, PKCE, rotação de sessão, logout e state inválido do teste original.

| Passo | Resultado esperado |
| --- | --- |
| Duas contas, referências em 01/11/2026 | Principal R$ 1.000; reserva R$ 0 |
| Receita registrada | R$ 2.000 na principal |
| CSV com despesa de R$ 20, corrigida para R$ 25 | Mesmo lançamento; reenvio reconhece origem sem voltar ao valor anterior |
| Transferência própria de R$ 100 e repetição do pedido | Uma transferência; valor conservado entre contas |
| Compra de R$ 100 em duas parcelas e repetição | Duas parcelas de R$ 50, sem duplicação |
| Estorno de R$ 10 no primeiro mês | Fatura de novembro R$ 40; dezembro R$ 50 |
| Conferência e pagamento parcial de R$ 10, repetido | Um pagamento; novembro ainda deve R$ 30 |
| Meta simples, orçamento de alimentação R$ 30 e margem R$ 100 | Cenário confirmado; capacidade conservadora R$ 1.835 |
| Saldo em 30/11/2026 | Principal R$ 2.865; reserva R$ 100; total R$ 2.965 |
| Resultado de novembro | R$ 1.935 (receita menos despesa direta e cartão) |
| Movimentação de caixa em novembro | R$ 1.965 (pagamento não duplica a despesa de cartão) |
| Exportação | Duas contas/transações; três lançamentos de cartão; um pagamento e uma transferência |

O roteiro executa operações pela API na sessão do navegador, confere os valores na visão geral e exporta os registros. Os testes de primeiro uso/cartões/saldos já existentes continuam validando a interação pelos formulários. Não representa aceite manual de usabilidade ou acessibilidade integral.

## Isolamento e nova sessão

A segunda pessoa autentica com senha/TOTP próprios: a lista de contas fica vazia; leitura de transação/fatura e tentativa de lançamento ligado à conta da primeira pessoa recebem 404. A exportação da primeira identidade permanece idêntica.

Sair revoga a sessão e limpa o resumo da página. Novo login da mesma pessoa exige senha e TOTP de uma janela nova, recuperando uma exportação idêntica à anterior. Quando a execução ocorre na mesma janela de 30 segundos do primeiro login, o teste aguarda o próximo código para respeitar a proteção contra reutilização. Os dados sintéticos permanecem no banco descartável da CI para que o ensaio de backup seguinte restaure também registros ligados a identidades reais de teste. Não gravar senha, tokens, segredo TOTP ou QR em arquivos/artefatos; a fixture chega por stdin.

## Execução e limites

A CI executa `seed_oidc.py | node tests/browser_oidc.cjs` depois de preparar Keycloak, passando as variáveis e o módulo Playwright conforme validacao.yml. `basic_journey.cjs` é o módulo de cenário. Não executar com conta pessoal ou dados reais. A validação financeira local usa sessão sintética e foi aprovada; autenticação/isolamento e nova sessão são homologados na CI completa, com o commit final registrado no PR.

As cotas da aplicação permanecem ativas. Somente ao receber 429 o helper aguarda Retry-After e repete uma vez; resposta diferente continua sendo falha. A interface pode ser recarregada uma vez após uma recusa 429 observada, preservando o teste dos valores esperados. O limite de duração do job passa a 25 minutos para acomodar a jornada e as cotas, com uma janela de 60 segundos antes das regressões de cadastros, necessária após ampliar o tráfego da jornada. Não relaxa os limites da aplicação.

Continuam pendentes para a V1: promoção/login no ambiente efetivamente restaurado, medições no volume-alvo, revisão de teclado/foco/acessibilidade e aceite de uso. Este cenário não declara a V1 pronta nem autoriza publicação.
