# Walleturbo — design system v1.0

Data: 11/11/2026, America/Sao_Paulo. Estado: aprovado pelo usuário e aplicado em `web/`. Escopo: aplicação web financeira pessoal em português do Brasil, com temas claro e escuro. Base técnica: HTML, CSS e JavaScript sem compilação. A [auditoria inicial](../../docs/AUDITORIA_UI_UX.md) preserva o diagnóstico da etapa 1; o [relatório de implementação](../../docs/REDESIGN_UI.md) registra a validação desta entrega.

## Direção e princípios

Conservar a identidade roxa e a aparência sóbria do produto. Usar superfícies planas, espaço para leitura e números em destaque. Evitar efeitos decorativos que concorram com valores, alterações ou alertas. A direção vem da inspeção do produto e do checklist da skill ui-ux-pro-max; não é saída gerada pelo mecanismo de busca da skill.

1. Mostrar **qual valor, de qual período e calculado como**. Saldo de contas, resultado mensal e variação de caixa têm rótulos e contextos diferentes.
2. Dar uma ação principal por contexto. Ações destrutivas entram em área própria e descrevem seu alcance.
3. Não apresentar dados incompletos como zero. Oferecer a ação que permite completar o cálculo.
4. Usar texto e sinais junto às cores. Despesa não significa erro; resultado negativo não deve receber ícone de alta decorativo.
5. Manter os mesmos componentes, ordem de leitura e estados nos dois temas e nas diferentes larguras.

## Arquitetura de informação e hierarquia financeira

Na visão geral, usar esta ordem no DOM e visualmente:

| Ordem | Conteúdo | Tratamento |
|---|---|---|
| 1 | Título, mês consultado e `Novo lançamento` | Uma ação primária. `Importar arquivo` como secundária, com disponibilidade explicada na demonstração. |
| 2 | Saldo calculado das contas | Valor principal de 32–40 px, data explícita, origem “Pelos seus registros; sem consulta bancária” e link `Ver contas`. |
| 3 | Receitas, despesas líquidas e resultado do mês | Valores de 24–28 px, mesma escala entre cartões irmãos e descrição da competência das parcelas. |
| 4 | Variação de caixa e pagamentos de fatura | Bloco complementar, com explicação de que pagamento de fatura não gera nova despesa. |
| 5 | Pendências que exigem ação | Contagem e ação para revisar. Não esconder o único aviso de resultado negativo dentro de um painel recolhido. |
| 6 | Movimentações recentes, categorias e metas | Lista e barras com valores textuais; conteúdo mais extenso pode ficar abaixo. |

**Saldo e data:** manter um controle de data próprio para saldos. Na visão geral, adotar inicialmente a data atual e mostrá-la junto ao valor; trocar o mês do resultado não altera silenciosamente essa data. Em Contas e cartões, a consulta por data continua explícita. Se houver demanda por saldo no encerramento do mês, acrescentar opção com rótulo próprio antes de mudar a regra.

**Cobertura incompleta:** `Saldo total indisponível` é o destaque quando qualquer conta não tem referência aplicável. Abaixo, `Subtotal conhecido: R$ … · 1 conta sem saldo inicial` e `Completar saldo inicial`. Não somar como zero a conta desconhecida. Não chamar esse valor de “disponível para gastar”.

**Demonstração:** identificar permanentemente `Dados fictícios · alterações somente nesta aba`. Para a proposta de saldo principal, ou criar uma amostra sintética coerente com o domínio, ou mostrar `Saldo não disponível na demonstração`; até existir a amostra, não exibir R$ 0,00 como saldo. Saldos, transferências, planejamento e importações não têm cobertura integral hoje.

## Tokens e temas

O arquivo [web/tokens.css](../../web/tokens.css) é a fonte de tokens consumida pela aplicação. Possui primitivos, semânticos e aliases de componentes. O [tokens.css da proposta](tokens.css) permanece como registro da etapa inicial. Tokens de estado são parte do contrato; o componente não recebe valores hexadecimais próprios.

| Papel semântico | Claro | Escuro | Uso |
|---|---|---|---|
| Fundo | `#F5F6F8` | `#101820` | Página |
| Superfície | `#FFFFFF` | `#19232E` | Cartões, campos e painéis |
| Superfície elevada | `#FFFFFF` | `#222F3D` | Diálogos e menus |
| Seleção | `#EFECF7` | `#302B46` | Navegação ativa e seleção |
| Texto | `#202936` | `#EDF2F7` | Valores e conteúdo principal |
| Texto secundário | `#566477` | `#B5C0CE` | Explicações que continuam legíveis |
| Divisor decorativo | `#DCE2E9` | `#354353` | Separadores; não usar como única identificação de campo |
| Borda de controle | `#7B8796` | `#8291A3` | Campo, checkbox customizado e botão delineado |
| Ação primária | `#584098` | `#C5B5FF` | Fundo do botão principal |
| Texto sobre ação | `#FFFFFF` | `#22163B` | Sempre pareado ao fundo da ação |
| Link/foco | `#584098` / `#684AB4` | `#C5B5FF` | Link e contorno de foco |
| Receita/sucesso | `#146B53` / `#E5F6EF` | `#8EE0BC` / `#183D32` | Primeiro valor é texto; segundo é superfície |
| Despesa | `#9A3412` / `#FFF0E7` | `#FFD1B2` / `#3C2B22` | Saída financeira regular, sem semântica de erro |
| Aviso | `#85540D` / `#FFF3D6` | `#F0CB8E` / `#3B301E` | Revisão pendente, cobertura parcial |
| Perigo/erro | `#A73140` / `#FCECEF` | `#FFADB7` / `#49202A` | Falha, ação destrutiva ou resultado negativo identificado |
| Informação | `#1D4E89` / `#EAF2FF` | `#A8CAFF` / `#182F4B` | Orientação contextual |

A cor de receita e a cor de sucesso têm tokens distintos, mesmo com os mesmos valores iniciais. Seleção usa também peso/indicador e `aria-current`, não apenas fundo. Links em parágrafos são sublinhados; não usar roxo como único sinal de que algo é clicável.

As razões de contraste dos pares sólidos estão em [CONTRASTES.json](CONTRASTES.json). O cálculo usa luminância relativa sRGB; não equivale a uma auditoria do CSS renderizado. Alterações de opacidade, imagens ou sobreposição exigem nova medição.

A meta é texto normal ≥4,5:1 e limites essenciais de controles ≥3:1 contra superfícies adjacentes, conforme [WCAG 2.2, 1.4.3 e 1.4.11](https://www.w3.org/TR/WCAG22/#contrast-minimum). Divisores puramente decorativos não precisam funcionar como borda de controle.

**Preferência de tema:** oferecer `Sistema`, `Claro` e `Escuro`. Ausência de preferência significa Sistema; salvar somente a preferência visual. Aplicar a classe antes da primeira pintura, respeitando a CSP existente. Mudanças no sistema acompanham a opção Sistema. O controle deve ser acessível em desktop e celular e anunciar a seleção.

## Tipografia e números

Manter fontes locais do sistema: `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`. Isso preserva o runtime sem fonte remota. Usar `rem`, com raiz respeitando a configuração do navegador.

| Estilo | Tamanho / entrelinha | Peso | Uso |
|---|---|---|---|
| Valor principal | 32–40 px / 1,2 | 700 | Saldo das contas |
| Valor secundário | 24–28 px / 1,25 | 600 | Resultado, receitas e despesas |
| Título de página | 24–32 px / 1,25 | 700 | Um h1 por página |
| Título de seção | 20 px / 1,3 | 600 | h2 |
| Corpo e campos | 16 px / 1,5 | 400 | Instruções, descrição e entrada |
| Rótulo e metadados | 14 px / 1,5 | 500 ou 400 | Rótulos, categoria, data e botões |
| Legenda | 12 px / 1,5 | 400 | Informação complementar; não usar para instruções financeiras essenciais |

Usar `font-variant-numeric: tabular-nums` em valores, totais, comparações e colunas. No desktop, alinhar valores à direita nas listas; no celular, reservar uma linha para valores extensos. Quebrar texto e permitir crescimento, sem cortar centavos ou o sinal. Não diminuir indefinidamente a fonte para acomodar valores. Testar de R$ 0,00 a R$ 999.999.999,99 e valores negativos.

Moeda na exibição: `Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" })`. Preservar centavos inteiros no domínio. Entrada monetária: aceitar `1234,56` e a forma agrupada `1.234,56` após validação estrita; rejeitar `1,234.56` e entradas ambíguas com ajuda concreta. Compatibilidade com ponto decimal simples só permanece se documentada e testada. Não substituir pontuação indiscriminadamente nem usar `parseFloat` para valores financeiros.

Exibir `+ R$ 120,00` para receita e `− R$ 80,00` para despesa. Incluir tipo por texto no nome acessível. Estorno é `Estorno`, sem ser renomeado como receita do usuário. Saldo zero é `R$ 0,00`; ausência de dado é `Não informado` ou `Saldo indisponível`.

Datas de calendário: armazenar ISO, exibir `dd/mm/aaaa`, sem conversão que desloque o dia pelo fuso. Mês: `novembro de 2026` em resumos. Eventos com horário mostram o fuso quando necessário; manter America/Sao_Paulo como referência desta documentação.

## Espaçamento, layout e responsividade

Escala: 4, 8, 12, 16, 20, 24, 32, 40 e 48 px. A regra de 8 orienta os espaços principais; 4 px serve ao ajuste fino. Usar 8 px entre controles, 16 px entre campos e 24–32 px entre seções. Painéis: 16 px de padding no celular e 24 px no desktop. Raio: 8 px para controles, 16 px para cartões e diálogos. Cartões comuns sem sombra; sombra reservada a sobreposições.

| Faixa proposta | Estrutura |
|---|---|
| 320–767 px | Uma coluna; navegação com 4 destinos frequentes (`Visão geral`, `Movimentações`, `Contas e cartões`, `Mais`). Mais abre Planejamento, Metas, Privacidade e tema em painel nomeado. |
| 768–1023 px | Cabeçalho compacto; mesma navegação ou menu nomeado. Duas colunas apenas onde o conteúdo realmente cabe. |
| ≥1024 px | Sidebar de 224 px; conteúdo de até 1216 px, gutters de 32 px; resumo em grade e seções em duas colunas. |

A navegação móvel proposta fica no topo inicialmente. Uma barra inferior fixa é alternativa futura e exige reservar altura no conteúdo e `env(safe-area-inset-bottom)`. Não colocar a nova barra sobre a grade atual. A ordem dos destinos dentro de Mais depende de validação de uso; o menu não pode tornar funções inacessíveis.

`minmax(0, 1fr)`, `min-width: 0` e quebra de texto são os padrões de grade. As métricas secundárias passam a uma coluna quando os valores deixam de caber. Não usar `overflow-x: hidden` para mascarar cortes. Formulários ficam em uma coluna no celular; duas colunas somente para campos curtos em telas maiores. O zoom não é desabilitado.

A proposta de navegação compacta visa reduzir a altura do cabeçalho atual, que contém seis destinos. Essa melhoria é uma hipótese a validar visualmente; não há overflow comprovado da navegação atual.

## Contratos dos componentes

| Componente | Anatomia e variantes | Estados e comportamento obrigatório |
|---|---|---|
| Botão | Texto explícito; ícone opcional; primário, secundário delineado, texto e destrutivo | Altura mínima de produto 48 px, ícone com alvo 48×48, gap 8. Padrão, hover, pressionado, foco, desabilitado e ocupado. Ocupado mantém largura, anuncia `Salvando…` e impede reenvio. |
| Campo | Label persistente, opcional/obrigatório explicado, entrada, ajuda, erro | Fonte 16 px, altura ≥48 px, borda de controle. Erro com `aria-invalid` e `aria-describedby`. Preservar o valor após falha. Checkbox com label clicável ≥44 px. |
| Cartão financeiro | Rótulo, valor, data/período, cobertura/origem, ação contextual | Completo, parcial, carregando, erro, zero e negativo. Sem dado não vira zero. Sem seta de tendência se não existir comparação calculada. |
| Navegação | Destino, indicador ativo e nome acessível | Links/rotas para destinos, botões para abrir menus. `aria-current="page"`, foco visível, voltar/avançar e atualização do título. |
| Linha de movimentação | Descrição, tipo, data, categoria, conta/origem, valor e ações | Sinais de entrada/saída, status textual `Revisão pendente`. Ações em disclosure `Ações de [descrição]`, inclusive revisão/exclusão. Não truncar valor. |
| Status/badge | Texto + ícone opcional | Informativo, revisão pendente, conferido, arquivado, pago e parcialmente pago. Cor acompanha o texto. Estado da fatura e situação do pagamento são campos separados. |
| Mensagem | Título curto, explicação, ação quando útil | Informação, sucesso, aviso e erro. Uma região de anúncio por evento; falha urgente usa alert. Mensagens sobre dados ou erros ficam até resolução, sem sumir por temporizador. |
| Estado vazio | Título específico, motivo e ação | Distinguir “sem registros”, “nenhum resultado da busca”, “recurso indisponível na demonstração”, “sem referência de saldo” e “falha de consulta”. |
| Diálogo | Título, contexto, conteúdo, ações e fechar/cancelar | `<dialog>` com `showModal()`, título associado, foco inicial contextual, Tab/Shift+Tab internos, Escape e devolução de foco. Não perder formulário preenchido sem aviso. |
| Revisão de operação | Resumo, comparação antes/depois, pendências e confirmação | Editar → conferir → confirmar. Confirmar fica desabilitado até prévia válida; editar invalida a prévia. Mostrar conta/fatura e período afetados. |
| Categorias e progresso | Nome, valor, porcentagem e barra para domínio válido | Categoria comum usa barra comparativa com base explícita. Saldo líquido de categoria negativo ou total não positivo exige lista de valores; não representar percentual enganoso. Metas usam progresso limitado e texto com excedente. |
| Busca e filtros | Label, consulta, mês e resultado | Atualizar lista sem perder foco. Mostrar contagem; zero resultado oferece `Limpar busca`. Recuperar filtros ao voltar à tela. |

A altura de 48 px é uma escolha do produto para conforto. O mínimo AA da web para alvo, com exceções, é 24×24 CSS px; 44×44 é o critério aprimorado AAA. Não confundir esses valores com unidades de apps nativos. Referência: [WCAG 2.2, 2.5.8](https://www.w3.org/TR/WCAG22/#target-size-minimum).

### Estados dos controles

| Estado | Regra clara/escura |
|---|---|
| Padrão | Usar o par semântico; secundário com superfície, texto principal e borda de controle. |
| Hover | Primário usa `action-hover`; secundário usa superfície selecionada; link recebe sublinhado. Não alterar dimensões. |
| Pressionado | Primário usa `action-pressed`; secundário mantém fundo selecionado e borda de foco; botão pode usar ícone preenchido sem depender disso para comunicar o estado. |
| Foco | Contorno externo de 3 px, offset 3 px, sobre fundo de página/superfície/elevado. Se ficar sobre fundo roxo ou aviso, usar halo de superfície entre controle e anel e medir os dois limites. |
| Desabilitado | Atributo `disabled`, sem eventos de ação, aparência atenuada; motivo próximo quando não for óbvio. Não usar só opacidade para transmitir indisponibilidade. |
| Ocupado | Atributo `aria-busy`, texto da operação e bloqueio de reenvio, com Cancelar apenas quando a operação puder ser cancelada de fato. |

Botões de perigo usam os tokens `danger`, `danger-hover`, `danger-pressed` e `on-danger`, distintos das despesas. Feedback responde em aproximadamente 120 ms; disclosure pode usar 180 ms. Respeitar `prefers-reduced-motion`. A interface atual quase não usa animação: adicionar movimento não é requisito desta etapa.

### Diálogos e operações delicadas

Manter controles nativos e a infraestrutura de foco existente. Para formulário curto, focar primeiro campo; para revisão longa, título com `tabindex="-1"`; para exclusão irreversível, a opção de cancelar. Ao fechar, devolver foco ao acionador ou a um elemento lógico se ele foi removido após a atualização da lista. Referência: [WAI-ARIA APG — diálogo modal](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).

Erro de envio: mostrar resumo no início do formulário com links aos campos; vincular cada erro ao respectivo campo. Se só houver erro de servidor sem campo identificado, explicar a falha e a próxima ação no próprio diálogo. Não limpar os dados nem focar automaticamente todo status assíncrono.

Um salvamento confirmado e uma falha posterior na atualização da tela são estados distintos. Usar `Lançamento salvo. Não foi possível atualizar a lista.` com `Atualizar lista`, impedindo a percepção de que é preciso salvar outra vez.

Padronizar confirmações com entidade, alcance e consequência: `Excluir “Mercado da semana”, R$ 284,90, de 03/11/2026?`. Compras parceladas mostram quantidade e faturas afetadas. Informar quando uma ação altera só os registros locais. Não oferecer `Desfazer` sem operação de restauração suportada pelo domínio. A confirmação de exclusão de todos os dados mantém a digitação explícita existente.

### Ícones

Usar a família SVG linear local de `web/ui.js`, tamanho 20 px e traço consistente. Não introduzir CDN ou nova biblioteca de runtime apenas para ícones. Ícone junto a texto equivalente recebe `aria-hidden="true"`; botão só com ícone precisa de nome acessível. Não adicionar setas de tendência sem dado de comparação.

## Linguagem e exemplos pt-BR

Usar frases diretas, rótulos em caixa de sentença e termos consistentes: `Receitas`, `Despesas líquidas`, `Resultado do mês`, `Saldo calculado das contas`, `Variação de caixa`, `Fatura`, `Estorno` e `Revisão pendente`. Evitar plural com “(s)” quando a contagem puder definir a frase.

| Situação | Texto proposto |
|---|---|
| Saldo parcial | `Saldo total indisponível. Falta o saldo inicial de 1 conta.` |
| Lançamento sem conta | `Sem conta vinculada. Este lançamento entra no resultado do mês e não altera o saldo de uma conta.` |
| Resultado negativo | `Despesas acima das receitas em R$ 120,00 neste mês.` |
| Campo monetário | `Valor (R$)`; ajuda `Ex.: 1.234,56`; erro `Informe um valor maior que zero, com até duas casas decimais.` |
| Fatura | `Em revisão · 2 categorias pendentes`; pagamento em linha separada `Pago R$ 100,00 de R$ 350,00`. |
| Busca vazia | `Nenhum lançamento para “mercado” neste mês.` + `Limpar busca` |
| Demo sem importação | `Importação disponível ao conectar sua conta. Na demonstração, registre um lançamento manual.` |
| Alteração concorrente | `Este registro mudou em outra sessão. Recarregue os dados para conferir antes de salvar.` |

Não prometer economia, rendimento, sincronização bancária ou pagamento real. Manter as ressalvas já presentes sobre simulação e registro local.

## Aplicação incremental e aceite

1. **Fundação:** introduzir tokens por tema e consolidar regras CSS sem remover as correções finais de acessibilidade. Conferir pares de cores e fazer comparação visual dos seis destinos.
2. **Resumo e ação:** reorganizar visão geral e incluir saldo com data/cobertura corretas; manter o contrato de resultado e caixa. Validar exemplos de domínio antes de aprovar nova hierarquia.
3. **Formulários e revisão:** padronizar campo, erro, operação ocupada e comparação antes/depois. Reusar as invalidações de prévia e controle de versão existentes.
4. **Navegação e adaptação:** definir rota e estado de consulta recuperáveis; avaliar menu móvel Mais com usuários; testar teclado, zoom e orientação.
5. **Acabamento:** ícones, tipografia restante, estados vazios e eventual otimização de listas após medição.

Cada etapa exige os dois temas, valores negativos/extensos, teclado e larguras de 320, 375, 390, 768, 1024 e 1440 px. Rodar axe nos estados abertos/erro/ocupado, além de leitura manual com tecnologia assistiva. Os scripts existentes são ponto de partida; consulte a [matriz de validação da auditoria](../../docs/AUDITORIA_UI_UX.md#plano-de-validação-por-etapa).

Para aprovar a hierarquia, propor teste moderado com 5 pessoas: em até 10 segundos identificar saldo e sua data, distinguir resultado de caixa e iniciar um lançamento; meta de pelo menos 4 de 5 concluindo sem ajuda. É um critério de pesquisa proposto, não um resultado observado.

## Governança

Este MASTER é a referência global do design system. Qualquer exceção futura deve ficar em `pages/<pagina>.md`, com motivo e pares de tema completos. Até existir exceção, aplicar estas regras a todas as telas. Alteração de token exige atualizar a tabela de contraste e a evidência visual correspondente. A aprovação do design system não implica aprovação da implementação ou conformidade WCAG da aplicação.
