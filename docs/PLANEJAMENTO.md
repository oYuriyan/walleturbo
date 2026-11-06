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

## Versão mensal e histórico — 0.13

GET /api/planning/{month} devolve version (0 para mês ainda sem configuração). PUT plan e PUT budget exigem expected_version inteiro no JSON; DELETE budget exige expected_version na query. Ausência ou formato inválido recebe 422; versão desatualizada recebe 409. A versão pertence ao conjunto de configurações do usuário/mês: alterar qualquer limite ou cenário invalida as telas antigas desse mês. Meses e titulares são independentes. Clientes antigos precisam atualizar.

O registro do mês é criado sob demanda por INSERT ON CONFLICT e bloqueado antes da comparação. A versão aumenta em cada escrita aceita, inclusive salvamento repetido, e permanece após remover todos os limites. Recriar um limite não restaura versões antigas. Um reenvio com versão antiga recebe conflito; não há recibo idempotente para essas configurações. A remoção de limite inexistente com versão atual recebe 404. O expurgo financeiro apaga configurações, versões e histórico; o conjunto seguinte começa novamente em 0.

A interface guarda mês/versão da resposta carregada, desabilita os formulários enquanto carrega e recusa respostas antigas após mudança de geração ou fim da sessão. Recarregar planejamento descarta edições ainda não salvas. Em conflito, recarregue e revise os campos antes de novo envio. Exclusão usa o mês/versão da lista exibida.

Cenários e limites passam ao histórico ORM transacional. Eventos de cenário usam entity=month_plan e entity_id=AAAA-MM; limites usam entity=budget e entity_id=AAAA-MM:categoria. A criação técnica do registro mensal padrão não inventa um evento financeiro; a primeira configuração registra antes/depois dos padrões, e os limites têm criação/alteração/exclusão. Incrementos da versão compartilhada também geram evento do mês. Falha no histórico reverte escrita e versão. Exportação e expurgo abrangem esses dados.

Migração 012 adiciona version=0 aos cenários existentes, preservando parâmetros e limites. Não reconstrói eventos antigos. PostgreSQL verifica disputa da primeira criação. SQLite verifica conflitos, exclusão/recriação, isolamento, rollback e privacidade; navegador cobre edição em outra sessão e recarga. 140 testes locais aprovados; homologação completa depende do CI deste incremento.

A versão protege configurações; não bloqueia lançamentos financeiros enquanto uma simulação é calculada. A confirmação de completude conserva a assinatura dos agregados do método existente, sem provar identidade de cada documento ou constituir snapshot bancário imutável. Revisão ampla de competência, confirmação entre alterações financeiras, projeções/recorrências e identidade de fontes continuam no roadmap.

## Confirmação dos registros — 0.14

O relatório fornece records_revision, vinculado ao usuário/mês e ao conteúdo, IDs e versões de lançamentos, faturas, compras e pagamentos relevantes. PUT plan com records_complete=true exige expected_records_revision. Ausência recebe 422; divergência recebe 409 sem avançar a versão do cenário. Salvar cenário não confirmado continua permitido sem esse campo. A interface envia a revisão carregada; em conflito exige recarga e nova conferência.

A assinatura persistida passa a representar registros, incluindo alterações sem mudança dos agregados e retorno a valores anteriores. Confirmações antigas baseadas só em agregados deixam de ser aceitas como atuais e exigem reconferência. Não há alteração de valores financeiros ou migração destrutiva. PostgreSQL usa REPEATABLE READ para relatório e salvamento; conflitos de serialização recebem 409. Uma mudança financeira concorrente posterior ao snapshot pode invalidar a confirmação na consulta seguinte. Não há bloqueio permanente nem garantia de completude documental/bancária. O relatório ainda carrega registros do mês; limites de volume seguem em REL-04/08.

142 testes locais aprovados com avisos tratados como erro; PostgreSQL e navegador ampliados aguardam CI. Esta entrega não conclui o contrato financeiro amplo nem a identidade entre documentos divergentes.
