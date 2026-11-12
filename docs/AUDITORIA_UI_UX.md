# Auditoria de interface do Walleturbo — etapa 1

Registro histórico da etapa 1. A implementação posterior e sua validação estão no [relatório do redesign](REDESIGN_UI.md).

Data: **11/11/2026**, America/Sao_Paulo. Revisão de código: `318e2ab`. Escopo: `web/index.html`, `web/style.css` e os dez módulos JavaScript carregados pela página. Entrega: diagnóstico, proposta de design system e critérios de validação. **Não foram feitas alterações na interface ou no domínio financeiro.**

## Resultado e grau de evidência

A interface tem uma fundação útil: português do Brasil, distinção explícita entre resultado e caixa, valores em centavos, controles nativos, foco visível e correções recentes de acessibilidade. As prioridades são tornar saldo e ação principal mais encontráveis, melhorar recuperação de erros e consolidar a consistência dos componentes nos dois temas.

**A avaliação visual/interativa solicitada em desktop e celular está pendente.** A demonstração respondeu em `http://localhost:18000`, mas a ferramenta de navegador por DOM retornou `The browser access host is unavailable`. A alternativa de controle do Firefox foi encerrada pela ferramenta porque a política de URLs não é suportada nesse navegador Windows. Nenhum fluxo foi clicado ou homologado nesta sessão. Não foram produzidas capturas atuais nem executados testes de navegador por outra via após esse bloqueio.

| Evidência | Situação nesta sessão | Alcance |
|---|---|---|
| Leitura do HTML, CSS final e pontos relevantes dos dez módulos | Executada | Estrutura, regras declaradas e caminhos de interação; não prova aparência renderizada. |
| GET `/`, `/assets/style.css`, `/assets/app.js` | HTTP 200; texto igual ao arquivo local após normalizar quebras de linha | Confirma que a demonstração serve as três entradas auditadas. Não é teste de fluxo. |
| Cálculo de contraste de cores atuais e propostas | Executado por luminância sRGB | Cores sólidas declaradas. Não inclui composição, capturas, estados nativos ou opacidade. |
| Avaliação em 1440 px e celular | Bloqueada antes de abrir a aplicação no navegador | Permanecem pendentes visual, toque, teclado, zoom e leitura assistiva. |
| Scripts de testes do repositório | Lidos, não executados | A existência de um teste ou de relatório anterior não comprova aprovação da revisão atual. |
| Busca CLI da skill ui-ux-pro-max | Indisponível | `python` não está no PATH e o Python da `.venv` aponta para instalação ausente. A proposta foi elaborada manualmente com o checklist da skill e fontes primárias; não é saída gerada pela CLI. |

Classificação usada abaixo: **C** = constatado no código; **M** = medido nas cores declaradas; **H** = hipótese de usabilidade a confirmar. Não há P0 comprovado. **P1** afeta leitura financeira, registro ou recuperação; **P2** afeta consistência, navegação e eficiência; **P3** é melhoria condicionada a medição. A ordem considera alcance e consequência, não só esforço.

O [design system proposto](../design-system/walleturbo/MASTER.md) contém a hierarquia e os contratos. Os [tokens](../design-system/walleturbo/tokens.css) são referência documental e não estão importados pela aplicação. As [medições de contraste](../design-system/walleturbo/CONTRASTES.json) permitem revisar as escolhas.

## O que preservar

- `lang="pt-BR"`, viewport sem bloqueio de zoom, `Intl.NumberFormat("pt-BR")`, datas de calendário e centavos inteiros.
- Skip link, h1 focalizável, `aria-current` atualizado e foco no título ao mudar de seção (`app.js:394–433`).
- `<dialog>` com `showModal()`, nome associado e contenção de Tab; o teste existente verifica Escape e retorno ao acionador em um fluxo. Não registrar “falta modal acessível” como diagnóstico genérico.
- `main[aria-busy]`, status e botão de tentar novamente; bloqueio `inert` de áreas com dados antigos após falha de consulta (`app.js:144–198`).
- **CSS efetivo no fim do arquivo:** botões/summary com mínimo de 44 px, ícones de fechar com 44×44 px, entradas de 16 px e números tabulares (`style.css:978–1018`). O tamanho inicial de 32 px do ícone é sobrescrito; não é o tamanho final.
- Grade móvel de navegação em três colunas e duas linhas (`style.css:1079–1105`); as regras finais substituem a faixa horizontal anterior. Não há overflow comprovado nessa grade.
- Adaptações escuras para receita, despesa e pendência (`style.css:1063–1073`) e seletor de tema móvel criado em `app.js:570`.
- Prévia de operações, invalidação após edição, controle de versão e preservação de origem nos módulos financeiros. O refinamento visual deve manter essas proteções.

## Problemas priorizados

### U01 · P1 · Saldo das contas fora da hierarquia principal e ação de registro dispersa — C/H

**Evidência:** o cartão dominante da visão geral é `Resultado do mês` (`index.html:115`). O saldo datado fica em outra seção (`index.html:225–241`; `balances.js:38–132`). O guia de primeiros passos fica oculto na demonstração e pode estar recolhido na conta conectada (`app.js:200–209`). O CTA estável `Novo lançamento` está em Movimentações (`index.html:195`). A ausência é estrutural; a confusão e o custo de descoberta são hipóteses.

**Impacto:** quem chega ao app precisa localizar como registrar e quanto há nas contas; um resultado mensal destacado pode ser interpretado como dinheiro disponível apesar do rótulo atual correto.

**Proposta:** título + mês + `Novo lançamento`; saldo calculado com data e cobertura como valor principal; resultado mensal, receitas e despesas em segundo nível; caixa com explicação própria. Se saldo for desconhecido ou parcial, exibir a limitação com ação para completar referência. Não inventar saldo na demonstração.

**Validação:** E2, testes V01 e V02. Comparar reconhecimento de saldo, resultado e caixa em desktop e celular; manter as respostas corretas do contrato financeiro.

### U02 · P1 · Identificação visual de campos com contraste insuficiente nas cores declaradas — M

**Evidência:** campos usam `--line` na borda e `--bg` no preenchimento (`style.css:561–570`). No claro, a borda tem **1,206:1** com o preenchimento e **1,304:1** com a superfície externa; no escuro, **1,772:1** e **1,574:1**. O preenchimento também é próximo à superfície. Isso é diferente dos textos: principal/secundário sobre superfície atingem 14,666/6,026:1 no claro e 14,112/8,625:1 no escuro.

**Impacto:** dificuldade para perceber onde digitar, sobretudo em baixa visão. Não é correto afirmar que todo o tema escuro tem texto de baixo contraste.

**Proposta:** separar `border-subtle`, para divisores, de `border-control`, para identificação dos campos. Validar a borda necessária com ≥3:1 contra cores adjacentes, sem escurecer todos os divisores. Botões de texto identificáveis pelo próprio texto não precisam de borda artificial.

**Validação:** E1, V03. Conferir campo vazio/preenchido/focado/erro em ambos os temas e medir o resultado renderizado. Referência: [W3C — contraste não textual](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html). Os números aqui não constituem laudo de conformidade da página.

### U03 · P1 · Erros de aplicação sem associação consistente ao campo — C

**Evidência:** `api()` reduz detalhes estruturados a uma mensagem genérica (`app.js:52–85`). `action()` publica status global e acrescenta `.dialog-error` ao final do diálogo (`app.js:87–102`), sem mapa de campos, `aria-invalid` ou `aria-describedby`. A validação HTML nativa existe e é uma base positiva; o problema é a recuperação de erros do JavaScript/API, especialmente em formulários longos.

**Impacto:** o usuário pode saber que ocorreu erro sem identificar o que corrigir, ou precisar rolar até depois das ações para encontrá-lo.

**Proposta:** componente de campo com ajuda/erro associado; resumo de erros no início em falhas de múltiplos campos; foco no resumo após envio inválido. Preservar dados preenchidos. Erros gerais permanecem contextuais no diálogo, sem exigir associação artificial a campo.

**Validação:** E3, V04. Enviar valor inválido, descrição vazia após trim, conflito de versão e resposta 503. Conferir texto, foco, leitura assistiva e preservação do formulário. Referência: [W3C — identificação de erro](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html).

### U04 · P1 · Salvamento e atualização da tela compartilham o mesmo caminho de falha — C/H

**Evidência:** após salvar lançamento, o código fecha o diálogo, chama `refresh()` e só então publica sucesso (`app.js:668–690`). Padrão semelhante aparece no saldo inicial (`balances.js:203–225`), correções e confirmação de PDF (`pdf.js:361–415`). Se persistir com sucesso e a consulta seguinte falhar, o catch apresenta o erro da consulta sem comunicar claramente o salvamento já concluído.

**Impacto:** incerteza sobre se o registro foi salvo; pode incentivar repetição manual. Isso não demonstra duplicação no banco, que possui proteções de idempotência.

**Proposta:** separar estado “salvo” de estado “lista atualizada”; oferecer `Atualizar lista` na falha posterior e impedir reapresentação do formulário como se o envio tivesse falhado.

**Validação:** E3, V05. Confirmar uma mutação sintética e falhar somente o GET seguinte; verificar aviso de salvamento concluído, ação de nova consulta e ausência de novo POST.

### U05 · P1 · Semântica de resultado e barras não cobre todos os sinais — C/H

**Evidência:** seta `↑` fixa no cartão (`index.html:117`), sem comparação histórica; `progress()` usa máximo mínimo de 1 (`app.js:250–256`). Categorias representam despesa líquida e podem receber valores negativos por estornos (`cards.js:85–101`). Na demonstração, os insights são criados por `summary()` antes de somar as compras de cartão em `applyDemoCards()` (`app.js:113–142`, `174`). Assim, uma compra de cartão que torne o resultado negativo pode não produzir o alerta correspondente.

**Impacto:** uma seta pode sugerir tendência inexistente e uma barra não traduzir créditos líquidos; alertas da demonstração podem ficar inconsistentes com o total exibido.

**Proposta:** remover seta de tendência sem comparação; usar sinal e rótulo do resultado. Definir barras só para denominador positivo e categorias compatíveis; mostrar valores e explicação para saldo credor. Calcular alertas após o agregado final na demonstração. Investigar o agregado real separadamente, sem extrapolar a constatação da demo.

**Validação:** E2, V06. Receita R$ 100,00 + compra de cartão R$ 200,00 deve mostrar resultado −R$ 100,00 e atenção correspondente; despesas zero e estornos superiores às compras não geram barra enganosa. Testar ambos os temas.

### U06 · P2 · Entrada monetária diverge de uma forma comum de copiar valores pt-BR — C

**Evidência:** `cents()` aceita uma única vírgula ou ponto decimal, sem agrupamento (`app.js:510–516`); os patterns HTML também rejeitam `1.234,56` (`index.html:399–401` e outros formulários). A exibição, por sua vez, usa agrupamento brasileiro. Saldo inicial suporta sinal negativo por tratamento específico em `balances.js:209–211`; isso deve ser preservado.

**Impacto:** copiar da própria exibição ou de um extrato pode resultar em erro sem instrução específica.

**Proposta:** parser estrito e documentado para pt-BR, aceitando formas sem e com agrupamento, com exemplo persistente. Não mudar o valor silenciosamente em formatos ambíguos. Negativo somente nas operações que já o permitem.

**Validação:** E3, V07. Testar `0,01`, `1234,56`, `1.234,56`, negativos de referência, excesso de casas e `1,234.56`; sem perda de centavos e com erro claro onde aplicável.

### U07 · P2 · Navegação de seções não participa da URL/histórico — C

**Evidência:** `showView()` altera visibilidade e título, mas não rota/hash/histórico (`app.js:394–421`). Os destinos são botões (`index.html:27–42`). Não há `popstate`, `hashchange` ou restauro de rota. Recarregar descarta a navegação e, na demonstração, também os dados por contrato já avisado.

**Impacto:** voltar, recarregar e compartilhar contexto não acompanham a expectativa da navegação web.

**Proposta:** rotas por hash ou History API, com restauração de seção/mês; usar links para destinos. Não incluir dados financeiros, descrições ou pesquisa sensível na URL. Preservar `aria-current`, título e foco.

**Validação:** E4, V08. Abrir link para Movimentações, navegar, voltar/avançar e recarregar; restaurar seção/período sem anunciar estado incorreto ou recuperar dados efêmeros da demo.

### U08 · P2 · Navegação móvel e cabeçalho podem consumir espaço de tarefa — C/H

**Evidência:** seis destinos em grade de duas linhas no celular, acima de topbar, título, período e aviso (`style.css:1079–1138`). O seletor de mês passa a ocupar uma linha inteira em até 420 px. Isso está implementado; o quanto empurra saldo/CTA para baixo depende da renderização, altura e tamanho de texto.

**Impacto:** possível aumento de rolagem antes da primeira tarefa e repetição de cabeçalho a cada seção. Não foi observado corte ou overflow atual.

**Proposta:** avaliar quatro destinos, com `Mais` para seções secundárias; compactar cabeçalho e manter ação principal próxima ao contexto. A grade atual é o baseline de comparação.

**Validação:** E4, V09. Comparar 320×568, 375×812 e 390×844, retrato/paisagem e zoom; medir passos até saldo/registro e descoberta de Planejamento, Metas e Privacidade antes de adotar Mais.

### U09 · P2 · Tokens e estados estão distribuídos em regras sobrepostas — C

**Evidência:** `--purple` cobre ação, texto, seleção e progresso; cores de despesa/perigo estão em seletores. Há blocos de tema em `style.css:27`, `788` e `1063`, além de múltiplas versões de grids, ícones e breakpoints. No escuro, `body.dark .button` sobrepõe a regra genérica de hover por especificidade; falta um contrato explícito de pressionado/ocupado para todas as variantes.

**Impacto:** uma mudança local pode afetar vários papéis, perder estados ou reintroduzir problemas já corrigidos no fim do arquivo.

**Proposta:** três camadas de tokens e um bloco de componente com estados completos. Consolidar CSS mantendo as regras finais efetivas e a classe `body.dark` durante a migração. Não substituir tema escuro por inversão de cores.

**Validação:** E1, V03 e V10. Galeria de componentes com todos os estados nos dois temas, diff visual e revisão de referências a cores. A proposta inclui 56 verificações de pares sólidos aprovadas; isso ainda exige revisão no navegador.

### U10 · P2 · Disponibilidade da demonstração é explicada depois de algumas tentativas — C/H

**Evidência:** importação é oferecida e só ao abrir mostra a limitação (`app.js:800–819`); PDF tem fluxo semelhante (`pdf.js:21–29`). Planejamento desabilita os formulários e explica a exigência (`planning.js:25–52`). Saldos e transferências são bloqueados (`balances.js:38–49`). A demo cobre lançamentos, cartões e metas, mas não todos os destinos apresentados.

**Impacto:** expectativa de exploração completa e cliques sem progressão útil. O bloqueio é legítimo; a proposta é explicá-lo no lugar e momento adequados.

**Proposta:** indicar `Disponível com conta conectada` junto ao recurso, manter explicação acessível e oferecer caminho manual quando existir. Estado vazio específico para recurso ausente, sem confundir com erro ou zero.

**Validação:** E3/E4, V11. Em cada destino da demo, identificar o que pode ser feito antes de iniciar operação; nenhum botão desabilitado sem motivo local.

### U11 · P2 · Tipografia e iconografia ainda não têm papéis únicos — C/H

**Evidência:** corpo de 15 px e muitos detalhes de 12–13 px (`style.css:23`, `449–452`, `498–523`); campos já foram elevados a 16 px. Navegação, saldos e ações usam glifos como `◫`, `⇄`, `↑` e `◎`, dependentes da fonte. Tipografia pequena não é, isoladamente, violação WCAG; sua leitura precisa ser avaliada.

**Impacto:** variação entre sistemas e menor conforto em instruções financeiras densas.

**Proposta:** corpo de 16 px, rótulos/metadados de 14 px e 12 px só para legenda complementar; fonte de sistema, números tabulares e uma família SVG local. Preservar os ícones de navegação já ocultos de tecnologias assistivas; ocultar os decorativos gerados em JS quando houver texto equivalente.

**Validação:** E4/E5, V12. Zoom, texto longo, nomes de conta de 80 caracteres, números extensos e leitura dos nomes acessíveis sem glifos redundantes.

### U12 · P2 · Confirmações e ações secundárias têm padrões diferentes — C

**Evidência:** Movimentações mostra `Revisar` e `Excluir` diretamente (`app.js:279–300`); compras usam disclosure nomeado (`cards.js:345–350`). Exclusões usam `confirm()` com níveis variados de contexto. Exclusão total tem diálogo próprio e digitação explícita (`index.html:1020–1041`). `openDialog()` sempre prioriza primeiro campo, inclusive confirmações longas.

**Impacto:** padrões variados de revisão e confirmação; o usuário precisa reaprender onde procurar ações e como avaliar o alcance.

**Proposta:** disclosure consistente para ações secundárias; confirmação com entidade, valor e alcance; preservar digitação explícita para exclusão total. Adequar foco ao tipo de diálogo e testar retorno após lista ser recriada. Não remover as confirmações existentes antes de ter substituição validada.

**Validação:** E3, V13. Teclado completo em lançamento, compra parcelada, pagamento e exclusão total usando somente dados sintéticos; foco de retorno tem destino lógico. Cancelar nunca muda dados.

### U13 · P3 · Renderização integral de listas pode limitar eficiência em volume — C/H

**Evidência:** `renderTransactions()` recria as listas completas a cada busca (`app.js:301–324`); faturas também desenham todas as linhas. Já existem paginação para transferências/histórico e ensaio de volume em `tests/browser_volume.cjs`; não foi medida lentidão nesta sessão.

**Impacto:** hipótese de atraso em busca/renderização conforme o volume cresce.

**Proposta:** medir no limite de volume declarado antes de otimizar; preferir paginação explícita a virtualização se ela dificultar foco e leitura assistiva. Não introduzir um framework como pré-requisito desta auditoria.

**Validação:** E5, V14. Medir interação com conjunto sintético de volume, registrar dispositivo/dataset/latências e avaliar busca, rolagem e navegação por teclado. Só abrir trabalho de otimização se houver evidência de atraso.

## Cobertura dos módulos e jornadas

| Arquivo | Jornada examinada no código | Ligação com os achados |
|---|---|---|
| [index.html](../web/index.html) | Estrutura, resumo, destinos, formulários e diálogos | U01, U05, U06, U08, U11, U12 |
| [style.css](../web/style.css) | Cascata final, temas, breakpoints, foco, tamanhos e tipografia | U02, U08, U09, U11 |
| [app.js](../web/app.js) | Navegação, demo, resumo, lançamento, metas, importação, status | U01, U03–U07, U10, U12, U13 |
| [cards.js](../web/cards.js) | Conta/cartão, compra/estorno, conferência, pagamento e ações de linha | U04, U05, U09, U10, U12 |
| [balances.js](../web/balances.js) | Referência, cobertura de saldo, transferência e reversão | U01, U04, U06, U10 |
| [planning.js](../web/planning.js) | Cenário, limites, metas e recorrências | U03, U09, U10 |
| [pdf.js](../web/pdf.js) | Leitura, seleção, total e confirmação de candidatos | U03, U04, U06, U10 |
| [lifecycle.js](../web/lifecycle.js) | Edição, arquivamento, recarga e exclusão de cadastro vazio | U03, U04, U12 |
| [history.js](../web/history.js) | Consulta paginada, antes/depois e tradução de campos | U09, U11; preservar paginação existente |
| [corrections.js](../web/corrections.js) | Simulação de compra, invalidação e confirmação | U03, U04, U09, U12 |
| [payment-corrections.js](../web/payment-corrections.js) | Prévia em contas/fatura/caixa e confirmação | U03, U04, U09, U12 |
| [ofx-relocation.js](../web/ofx-relocation.js) | Mudança de competência com simulação e ciência | U03, U09, U12; preservar invalidação e controle ocupado existentes |

O compartilhamento de funções e estado global exige mudanças coordenadas em `openDialog`, `action`, `money`, `cents` e nos componentes de linha. Migrar esses pontos gradualmente, sem criar cópias por módulo e sem transformar a etapa em reescrita arquitetural.

## Plano de validação por etapa

Todos os casos abaixo estão **planejados, não executados nesta sessão**. Dependências: E1 precede mudanças visuais; E2 e E3 podem evoluir depois da fundação; E4 usa os componentes consolidados; E5 fecha a revisão. Cada etapa deve produzir uma revisão pequena, capturas dos dois temas e resultados de regressão.

| Etapa | Entrega seguinte | Critério de saída |
|---|---|---|
| E1 · Fundação | Tokens, bordas e estados; consolidar CSS preservando acessibilidade atual | V03/V10 aprovados; seis destinos sem regressão nos dois temas; inventário de cores sem valores avulsos injustificados. |
| E2 · Hierarquia financeira | Saldo datado/cobertura, ação principal e estados de resultado/categoria | V01/V02/V06 aprovados; resultado, caixa e saldo não se confundem no teste moderado. |
| E3 · Registro e recuperação | Campos, erros, revisão, confirmação e estado de salvamento | V04/V05/V07/V11/V13 aprovados em demonstração e ambiente autenticado sintético quando necessário. |
| E4 · Navegação e leitura | Rotas, adaptação móvel, tipografia e ícones | V08/V09/V12 aprovados; destinos secundários encontráveis e nenhum conteúdo funcional perdido no zoom. |
| E5 · Revisão integrada | Percorrer jornadas completas, ampliar estados e medir volume | V14 medido; zero erros JS nos fluxos testados, nenhuma violação A/AA no axe nos estados cobertos, inspeção manual concluída com limitações registradas. Isso não é certificação WCAG. |

### Casos e resultados esperados

| Caso | Como validar | Resultado esperado |
|---|---|---|
| V01 · Orientação | Em cada dispositivo/tema, localizar saldo, data, resultado e `Novo lançamento` sem instrução | Teste moderado proposto com 5 pessoas: ≥4 identificam os valores e iniciam registro em até 10 s. Registrar erros de interpretação, não apenas tempo. |
| V02 · Contrato financeiro | Usar exemplo de [SALDOS.md](SALDOS.md): referências R$ 100,00 + R$ 5,00; receita 50; despesa 12,34; cartão 80; pagamento 25; transferência 20 | Saldos R$ 92,66 e R$ 25,00; total R$ 117,66; resultado −R$ 42,34; caixa +R$ 12,66. Sem referência: total indisponível e subtotal conhecido separado. |
| V03 · Contraste | Medir texto, borda, foco e ícones funcionais em campos vazios/preenchidos/erro, botões e overlays | Texto normal ≥4,5:1; identificação essencial de controle ≥3:1 com adjacentes. Capturas não substituem inspeção de cores computadas. |
| V04 · Erros | Submeter inválidos no lançamento, saldo, compra e PDF; simular conflito e erro de servidor em ambiente isolado | Mensagem específica; campo identificado quando aplicável; resumo navegável; valor preservado; anúncio útil sem duplicidade. |
| V05 · Salvo + falha de consulta | Sucesso no POST/PUT, falha apenas no GET posterior | Mensagem distingue os resultados; `Atualizar lista` faz GET, não repete mutação. Reenvio rápido não duplica operação. |
| V06 · Sinais e categorias | Resultado positivo/zero/negativo, despesa líquida zero/negativa, estorno e meta acima de 100% | Texto/sinal correto e representação válida; sem seta de tendência fictícia ou percentual impossível. Demo agrega cartão antes dos alertas. |
| V07 · Dinheiro pt-BR | Digitar/colar formatos descritos em U06 em todas as famílias de formulário | Centavos exatos, limites preservados, formato ambíguo rejeitado com ajuda; sinal negativo restrito ao contrato. |
| V08 · Navegação web | Link direto, voltar/avançar e recarga em seções e meses diferentes | Seção/período restaurados, título e `aria-current` sincronizados; nenhum dado privado em URL. |
| V09 · Adaptação | Percorrer seis destinos e diálogos em 320×568, 375×812, 390×844, 768×1024, 1024×768, 1440×1000; incluir celular em paisagem | Sem rolagem horizontal da página, textos e centavos completos; CTA, fechar e erros alcançáveis com teclado virtual aberto. |
| V10 · Estados | Galeria de botões, campo, badge, status, cartão, disclosure e modal em claro/escuro | Padrão, hover, pressionado, foco, desabilitado, ocupado e erro coerentes; sem mudança de largura, alvo confortável e sem informação só por cor. |
| V11 · Demo e vazios | Visitar demo, mês sem dados, busca sem resultado, saldo sem referência, recurso restrito e falha de rede | Causa e próxima ação distintas; sem tratar indisponível como zero ou falha como vazio. |
| V12 · Leitura ampliada | Zoom de 200%; 400% em viewport inicial de 1280 px; texto ampliado e nomes/valores extremos; NVDA+Firefox e VoiceOver+Safari quando disponíveis | Reflow, ordem de leitura correta, nomes acessíveis úteis e controle focado visível. Sem truncar valor financeiro. |
| V13 · Diálogos | Tab/Shift+Tab/Escape; abrir/fechar/cancelar e concluir revisão/exclusão em dados sintéticos | Foco dentro do modal; restauração lógica após recriação da lista; cancelamento sem mutação; confirmação descreve alcance. |
| V14 · Volume | Reutilizar dataset do ensaio existente e medir busca/renderização em dispositivo definido | Registrar p50/p95 e contagem de registros. Meta proposta: feedback de interação <100 ms; reportar atraso antes de escolher paginação/otimização. |

Reflow e foco devem ser avaliados com o teclado virtual e com zoom real, além de reduzir o viewport. A referência para perda de conteúdo e rolagem em duas dimensões é [W3C — reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).

### Reaproveitamento dos testes existentes

`tests/browser_ui.cjs` já prevê seis áreas nos dois temas, axe, foco em navegação, modal nomeado, Tab/Escape e larguras 320/390/768. O pipeline configura Chromium em demo e Firefox autenticado; a matriz atual não é o produto cartesiano de todos os motores, temas, tamanhos e estados. Acrescentar combinações relevantes a cada alteração.

Usar as jornadas especializadas de `browser_first_steps.cjs`, `browser_cards.cjs`, `browser_balances.cjs`, `browser_goals.cjs`, `browser_planning.cjs`, `browser_pdf.cjs`, `browser_corrections.cjs`, `browser_payment_corrections.cjs`, `browser_ofx*.cjs` e `browser_volume.cjs`. Confirmar as precondições de sessão sintética do pipeline. Algumas suítes autenticadas limpam os dados criados; executar somente em ambiente de teste com usuário descartável, sem apontá-las a uma conta pessoal.

Para a parte de demonstração, quando houver acesso de navegador e dependências existentes:

```powershell
$env:APP_URL = 'http://localhost:18000'
$env:UI_AUTH = '0'
$env:BROWSER_ENGINE = 'chromium'
node tests/browser_ui.cjs
```

Esse comando é roteiro futuro e não foi executado aqui. Requer Playwright, motor instalado, axe-core e diretório de artefatos conforme o pipeline. Não instalar dependências globais como parte da revisão documental. O teste automatizado não substitui a pesquisa de hierarquia nem a avaliação manual de leitura assistiva.

### Evidências a anexar antes de fechar cada etapa

Registrar commit, URL/ambiente, dataset sintético, navegador/versão, viewport, zoom, tema e caso. Salvar capturas de visão geral, lançamento com erro, saldo incompleto, fatura com pendência e revisão antes/depois nos dois temas; log do axe, erros JS e passos de teclado. Não incluir dados pessoais em capturas.

Nesta etapa foram entregues a **auditoria estática e a proposta documentada**. A inspeção visual/interativa da demonstração permanece como pendência explícita de aceite; não atribuir a estes documentos aprovação dos fluxos em desktop ou celular.
