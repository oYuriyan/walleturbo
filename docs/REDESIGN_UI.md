# Redesign de interface do Walleturbo

Data: 11/11/2026, America/Sao_Paulo. Implementação do [design system aprovado](../design-system/walleturbo/MASTER.md), mantendo HTML, CSS e JavaScript sem compilação. Ambiente local: `http://localhost:18000`. Esta entrega sucede a [auditoria da etapa 1](AUDITORIA_UI_UX.md).

A versão 1.1.0 reúne o redesign e a [composição compacta do dashboard com a referência dos cartões](../design-system/walleturbo/pages/dashboard.md). Versão declarada em `pyproject.toml` e nos metadados FastAPI; alterações resumidas em `CHANGELOG.md`. A branch `redesign/ui-ux` segue o fluxo de PR e CI do projeto, com homologação integral pendente até a execução correspondente.

## Implementação

| Área | O que mudou |
|---|---|
| Navegação | Links de destino, URL com seção/mês e histórico de voltar/avançar. Sidebar no desktop; quatro destinos no celular, com Planejamento, Metas e Privacidade em Mais. Título, foco e `aria-current` acompanham a seção. |
| Visão geral | Acesso direto a Novo lançamento e importação. Saldo das contas em primeiro nível, com data e cobertura. Resultado mensal, receitas, despesas e caixa separados. Saldo desconhecido/parcial não vira zero. Pendências e resultado negativo aparecem fora do painel recolhido. Categorias com créditos líquidos usam lista de valores sem percentuais enganosos. |
| Temas | Tokens semânticos claros/escuros, bordas de controle distintas de divisores, preferência Sistema/Claro/Escuro e aplicação do tema no head. A troca não interpola cores de texto e fundo, evitando contraste transitório ruim. |
| Componentes | Campos de 16 px, controles de 48 px, foco de 3 px, ícones SVG locais, cartões, badges, estados vazios, mensagens, disclosures e diálogos compartilhados. Botões ocupados preservam a largura do conteúdo original. |
| Movimentações | Valores com sinal e tipo textual, ações em disclosure nomeado, contagem de resultados e limpar busca. Entrada monetária aceita agrupamento pt-BR com validação estrita e centavos inteiros. |
| Contas e faturas | Saldos e referência datada preservados, cartões com seção própria, ações e revisão consistentes. Conferência da fatura e situação de pagamento são descritas separadamente. Estorno mantém nome de estorno. |
| Planejamento | Campos, limites, avisos e simulações usam o mesmo padrão. Rascunhos do mês são preservados ao navegar; recarregar ou mudar o período com alterações pendentes pede confirmação. Falha de consulta deixa orientação de recuperação. |
| Metas e privacidade | Cartões, progresso, campos e ações compartilham os tokens. Arquivamento, exclusão protegida, exportação e confirmação explícita de exclusão total continuam usando suas regras existentes. |
| Importações | CSV, OFX e PDF mantêm prévias, seleção, revisão e invalidação existentes. Campos e erros seguem os componentes compartilhados; indisponibilidade da demonstração é explicada. Desfazer vínculo e exclusões usam a confirmação comum. |

A **regra de 8** orienta gaps, margens e paddings principais: 8/16/24/32/40/48 px, com ajustes de 4 px. Raios de controles são 8 px e de cartões/diálogos, 16 px. Tipografia, bordas e contorno de foco têm escalas próprias.

Os estados cobertos incluem vazio, ausência de referência, saldo parcial, zero, negativo, carregamento, ocupado, erro de campo, erro de servidor, conflito, sucesso e confirmação/cancelamento. Quando uma alteração foi concluída e a consulta seguinte falha, a mensagem informa que os dados foram salvos e oferece nova consulta, sem repetir a mutação.

## Arquitetura e regras preservadas

- [web/tokens.css](../web/tokens.css) é a fonte dos tokens em uso. [style.css](../web/style.css) consolida a cascata anterior e os componentes.
- [theme.js](../web/theme.js) resolve somente a preferência visual; [ui.js](../web/ui.js) reúne ícones, erros, estados ocupados, confirmação, rotas e apresentação da cobertura do saldo.
- Os módulos financeiros permanecem separados e continuam usando os mesmos endpoints, payloads, CSRF, versões, UUIDs de envio e recibos de idempotência.
- Em `app/`, apenas o metadado de versão do FastAPI foi atualizado para 1.1.0. Migrações, autenticação, saldos, cálculo de parcelas, limites da API e persistência financeira permanecem iguais. O parser de entrada da interface preserva centavos e rejeita formatos ambíguos; `1.23` continua aceito por compatibilidade, e `1.234` representa agrupamento de milhar.
- A demonstração continua em memória e não passa a simular saldo bancário. O alerta de resultado negativo é montado depois de agregar as compras de cartão, para acompanhar o total final da demo.
- A política CSP continua ativa; não foram adicionadas fontes, scripts ou bibliotecas de runtime de terceiros. Playwright e axe são dependências locais de teste em `artifacts/`.

## Tarefas executadas

As tarefas de `.vscode/tasks.json` foram executadas pelo mesmo comando e pelos mesmos argumentos da configuração, sem abrir o VS Code pela automação.

**Walleturbo: iniciar ambiente local**

```powershell
docker compose --env-file .env --env-file .env.auth `
  -f compose.yaml -f compose.auth.yaml `
  -f artifacts/walleturbo-local/compose.yaml `
  up --build -d --wait --wait-timeout 240
```

Resultado: build concluído; API, parser, PostgreSQL, Redis, banco de autenticação e Keycloak saudáveis; migração concluída. Volumes existentes preservados. A consulta HTTP confirmou que os 15 arquivos HTML/CSS/JS servidos são os mesmos arquivos locais, normalizando BOM e quebras de linha.

**Walleturbo: executar testes no Docker**

```powershell
docker compose --project-name walleturbo-tests --profile test run --build --rm tests
```

Resultado final: **266 testes aprovados em 29,96 s**, além do tempo de build. O projeto de testes é separado do ambiente local. Log: `artifacts/redesign-docker-tests.log`.

Na preparação do versionamento 1.1.0, a mesma tarefa foi repetida: **266 testes aprovados em 31,07 s**. Log: `artifacts/version-1.1-docker-tests.log`. A sintaxe de todos os módulos JavaScript e roteiros CJS foi conferida, assim como o YAML do workflow ampliado.

O ambiente foi reconstruído novamente com a versão 1.1.0. Foram repetidos com sucesso o redesign autenticado em Chromium (37 auditorias axe), os estados (7 grupos/6 auditorias) e o dashboard em Chromium/Firefox (20 combinações de largura/tema). O roteiro autenticado usa a mesma espera por cotas configurada na CI.

## Validação em navegador

Foram usados navegadores reais em modo headless pelo Playwright, com capturas inspecionadas visualmente. Isso evita o bloqueio de controle nativo do Firefox identificado na etapa 1. A aplicação foi acessada em localhost; não foi publicada.

| Matriz | Cobertura | Resultado |
|---|---|---|
| Chromium, demonstração | Seis áreas, claro/escuro, 1440×1000 e 390×844, formulários, erro e confirmação | 36 auditorias axe sem violações A/AA nos estados verificados; zero erros JS. |
| Chromium, sessão sintética | Mesma matriz e prévia CSV com API real | 37 auditorias axe sem violações nos estados verificados; zero erros JS. |
| Firefox, demonstração | Mesma matriz da demonstração | 36 auditorias axe sem violações nos estados verificados; zero erros JS. |
| Firefox, sessão sintética | Mesma matriz autenticada | 37 auditorias axe sem violações nos estados verificados; zero erros JS. |

O roteiro está em [browser_redesign.cjs](../tests/browser_redesign.cjs). Além da matriz acima, percorre os seis destinos em 320×568, 375×812, 768×1024, 1024×768 e 844×390, verificando ausência de overflow horizontal. Exercita skip link, foco no título, Tab/Shift+Tab dentro do diálogo, Escape, foco inicial em Cancelar na confirmação, cancelamento sem mutação, busca vazia, limpar busca e voltar pelo histórico.

Na demonstração, uma compra de R$ 8.000,01 valida entrada agrupada, resultado negativo e alerta coerente. Na sessão sintética, o roteiro confere saldo de R$ 2.965,00 separado de resultado de R$ 1.935,00 e caixa de R$ 1.965,00. Também salva um lançamento de R$ 1.234,56, simula falha somente no GET seguinte e verifica que tentar novamente não repete o POST. A falha 503 é uma simulação de teste; o salvamento e a consulta de recuperação usam a API real.

As capturas e resultados JSON ficam em `artifacts/redesign-<motor>-<demo|auth>/`. Os logs principais são `redesign-chromium-demo.log`, `redesign-chromium-auth.log`, `redesign-firefox-demo.log` e `redesign-firefox-auth.log`, no mesmo diretório de artefatos. As capturas contêm somente exemplos fictícios.

### Jornadas financeiras e importações

As regressões existentes foram adaptadas a links de navegação, menu Mais, ações em disclosure e confirmações em `<dialog>`. Os testes passaram a aceitar `APP_URL`, permitindo usar a porta local 18000.

**13 jornadas aprovadas**, incluindo o primeiro uso. As três jornadas que exigiram repetição também passaram após corrigir o harness e preparar as fixtures. Logs: `artifacts/redesign-regression-final.log` e `artifacts/redesign-regression-rerun.log`.

| Roteiro | Verificação |
|---|---|
| `browser_first_steps.cjs` | Primeiro uso em celular: conta, referência, despesa, saldo de R$ 975 e guia contextual. |
| `browser_cards.cjs` | Conta/cartão, parcelas, divergência, conferência, pagamento parcial, caixa e mês seguinte. |
| `browser_balances.cjs` | Referências, transferência, conservação/reversão de saldos e limpeza de sessão. |
| `browser_planning.cjs` | Limite excedido, confirmação do cenário, conflito, recarga e capacidade conservadora. |
| `browser_goals.cjs` | Criação, conflito, arquivamento/reativação, exclusão protegida, planejamento e histórico. |
| `browser_lifecycle.cjs` | Renomeação, arquivamento/reativação e exclusão com/sem vínculos. |
| `browser_corrections.cjs` | Correção integral, prévia, centavos, conflito e reenvio cancelado. |
| `browser_payment_corrections.cjs` | Prévia de saldos, confirmação, conflito, recarga e exclusão obsoleta. |
| `browser_entry_import_integrity.cjs` | UUID/versão, conflito, exclusão obsoleta e reimportação sem recriação. |
| `browser_pdf.cjs` | PDF real no leitor isolado: revisão, estorno, correção, exclusão e vínculos sem duplicação. |
| `browser_ofx.cjs` | OFX bancário, Windows-1252, conta/contexto, seleção, vínculo e identidade por FITID. |
| `browser_ofx_card.cjs` | OFX de cartão, pagamentos/estornos, revisão, vínculos e bloqueio de outra fatura. |
| `browser_ofx_relocation.cjs` | Prévia das duas faturas, invalidação por edição, identidade/origem/histórico e descarte de resposta após fechar. |

O roteiro adicional [browser_ui_states.cjs](../tests/browser_ui_states.cjs) passou com **7 grupos de estados e 6 auditorias axe sem violações**. Ele intercepta respostas apenas no navegador de teste para verificar ausência de contas, cobertura parcial, zero completo, carregamento com conteúdo anterior inerte, erro de consulta/recuperação, envio ocupado, bloqueio de reenvio e erro 422 associado ao campo sem perder o valor. Também verifica Mais por teclado e a preferência Sistema. Seus resultados ficam em `artifacts/redesign-states/results.json`.

As sessões sintéticas recebem identificadores aleatórios, e as suítes removem seus próprios dados ao terminar. A opção de teste `WALLETURBO_BROWSER_SESSION_TTL=900` permite esperar cotas sem expirar a sessão; o padrão do gerador permanece 180 s. Isso não altera a duração de sessões reais da aplicação.

O helper `UI_RATE_RETRY=1` respeita respostas 429 e o cabeçalho Retry-After, repetindo a mesma requisição somente após a espera. Atua apenas na execução de testes; não desativa nem altera os limites de 120 requisições/IP, 90/conta e 10/importações por minuto. As primeiras tentativas de regressão encontraram seletores antigos e cotas atingidas; foram corrigidos os seletores e adicionada a espera no harness, sem mudar a política da API.

### Reprodução local

```powershell
npm install --prefix artifacts/walleturbo-e2e --no-audit --no-fund playwright@1.58.2 axe-core@4.10.3
node artifacts/walleturbo-e2e/node_modules/playwright/cli.js install chromium firefox

$env:APP_URL = 'http://localhost:18000'
$env:PLAYWRIGHT_MODULE = (Resolve-Path artifacts/walleturbo-e2e/node_modules/playwright).Path
$env:AXE_PATH = (Resolve-Path artifacts/walleturbo-e2e/node_modules/axe-core/axe.min.js).Path
$env:BROWSER_ENGINE = 'chromium' # Repetir com firefox
$env:UI_AUTH = '0'
node tests/browser_redesign.cjs
```

Para sessão sintética em ambiente de desenvolvimento:

```powershell
$env:UI_AUTH = '1'
Get-Content tests/browser_seed.py -Raw |
  docker exec -i -e WALLETURBO_INTEGRATION=1 -e WALLETURBO_BROWSER_SESSION_TTL=900 walleturbo-api-1 python |
  node tests/browser_redesign.cjs
```

Não imprimir a saída intermediária do gerador de sessão. Executar suítes autenticadas em sequência e respeitar as cotas antes da próxima. Os artefatos são ignorados pelo Git; a documentação e os roteiros ficam no repositório.

## Limites da verificação

Celular foi avaliado por viewport e orientação no navegador automatizado, sem aparelho físico nem teclado virtual de sistema. Foram inspecionadas capturas de desktop/celular e temas; não houve pesquisa moderada com cinco pessoas, auditoria manual completa por leitor de tela, medição de latência em dispositivo real ou certificação WCAG. O axe não cobre todos os critérios de acessibilidade. Login real/OIDC não foi rehomologado por estas sessões sintéticas; a autenticação não foi alterada.

Os problemas encontrados durante os testes — contraste transitório de tema, corrida de fechamento/reabertura de confirmações no Chromium e limpeza prematura do formulário capturado para o indicador ocupado — foram corrigidos e seus casos passaram novamente. O documento de auditoria inicial continua como registro histórico, não como lista de falhas ainda abertas.
