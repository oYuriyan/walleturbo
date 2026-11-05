# Planejamento e sinais de gastos — 0.4

O planejamento usa regras explícitas e somente registros do proprietário autenticado. Não envia dados a modelos de IA e não altera metas, reservas, compras ou dinheiro no banco.

## Cenário e limites

Em **Planejamento**, selecione o mês e informe opcionalmente uma renda de referência e a margem que deseja preservar. Defina limites por categoria; o gasto líquido considera despesas diretas e parcelas do mês de vencimento, descontando estornos. Pagamentos de faturas não são contados como nova despesa. Limites não são reservas nem autorização de compra.

A confirmação de completude é mensal. Se os agregados ou a contagem de registros do mês mudarem, a confirmação deixa de valer na simulação até nova conferência. Essa verificação usa assinatura dos agregados, não um histórico imutável de cada alteração.

## Simulação das metas

Só há sugestão de aporte quando o usuário confirmou a completude, não há categorias pendentes e existe receita positiva registrada. Renda de referência sozinha não habilita aporte. A capacidade é:

`máximo(0, mínimo(resultado registrado, variação de caixa registrada, renda de referência menos despesas) menos margem preservada)`.

Sem renda de referência, a simulação usa a receita registrada. O cálculo é conservador em relação a esses registros, mas não conhece saldo inicial, obrigações ausentes, gastos futuros ou a disponibilidade real de uma conta bancária. Portanto não comprova que o dinheiro pode ser gasto ou investido.

Somente metas ativas participam da simulação; arquivar preserva seus valores no cadastro/exportação e reativar volta a incluí-las. A versão de cadastro evita sobrescrever outra edição, sem reservar dinheiro.

Metas são ordenadas pelo prazo (e identificador em empate). O valor restante é dividido pelos meses civis até o prazo, incluindo o mês de referência; centavos são arredondados para cima. A capacidade é distribuída nessa ordem, sem superar sua soma. Metas vencidas exigem revisão do prazo; metas alcançadas recebem zero. Não há promessa de atingir o objetivo nem movimentação automática.

A referência temporal é o maior entre o início do mês escolhido e a data atual em America/Sao_Paulo. Meses passados mostram simulação com o estado atual das metas, não uma reconstrução histórica de planos.

## Recorrências para revisão

São mostradas descrições iguais (normalização Unicode, caixa e espaços) na categoria **Assinaturas**, com lançamentos revisados em pelo menos três meses distintos dentro de uma janela de seis meses, incluindo o mês consultado. A evidência inclui meses, valores, origem e identificadores dos lançamentos. Compras em mais de uma parcela são excluídas desse detector, para não confundir parcelamento com assinatura.

Isso identifica repetição observada, não falta de uso, fraude ou economia garantida. Assinaturas com descrições diferentes podem não ser agrupadas; descrições iguais podem corresponder a serviços diferentes. Se a janela exceder mil registros de assinatura, esse detector não calcula recorrências e exibe a limitação. Os totais financeiros e orçamentos continuam agregados integralmente no banco.

## Privacidade e validação

Cenários e limites são segregados por proprietário e incluídos na exportação/exclusão financeira. A migração 003 adiciona tabelas sem modificar lançamentos existentes. Não há cobrança recorrente automática ou recomendação comercial.

Testes cobrem isolamento, renda declarada sem receita, agregados alterados, conservação da capacidade, estornos e recorrência sem parcelas. O pipeline também valida orçamento e cenário no navegador desktop/mobile com dados sintéticos. IA, perfil financeiro completo, recorrências automáticas e recomendações de ofertas permanecem pendentes.
