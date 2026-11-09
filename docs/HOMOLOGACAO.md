# Relatório de validação — fundação 0.1.0

Data: 03/11/2026 (America/Sao_Paulo). Ambiente: workspace cloud Linux, Python 3.12, Docker 29.9.2. Dados exclusivamente sintéticos. **Resultado: base funcional validada; produto não homologado para produção.**

## Evidências executadas

| Verificação | Resultado |
|---|---|
| Testes de domínio/API/segurança no host | 26 aprovados |
| Mesma suíte em container sem privilégios, filesystem somente leitura e capabilities removidas | 26 aprovados, inclusive pela imagem padrão no GitHub Actions |
| Build da imagem de aplicação e da imagem de testes com dependências/hashes | Concluído após correção de ownership nos COPY |
| PostgreSQL 17 e Redis 7 reais | Readiness, sessão sintética, importação, deduplicação, saldo, exportação e exclusão aprovados; inicialização em volume novo também aprovada no CI |
| Chromium desktop e mobile 390 px | Navegação, criação/edição de lançamento, busca, criação de meta e tema escuro aprovados |
| Tentativa de descrição HTML na interface | Exibida como texto; nenhum elemento img inserido |
| JavaScript | `node --check web/app.js` aprovado; zero erros de runtime nos fluxos exercitados |
| Auditoria Python de `requirements.lock` | Nenhuma vulnerabilidade conhecida reportada por pip-audit no momento da consulta |

Dois avisos de depreciação foram emitidos pelas integrações de TestClient/Authlib com httpx. Não causaram falha, mas a migração para o cliente recomendado deve ser acompanhada nas atualizações.

## Limites do ambiente e reprodução

O primeiro teste de container revelou arquivos com permissões restritas ao proprietário; o Dockerfile foi corrigido com ownership explícito para o usuário 10001. O driver VFS do ambiente consumiu o limite de disco durante a criação do container da imagem de testes. A imagem foi construída, mas sua execução direta não pôde ser concluída neste ambiente. A suíte foi executada na imagem de aplicação com código/dependências montados somente para leitura e usuário não privilegiado:

```sh
docker run --rm --read-only --tmpfs /tmp --user 1000:1000 \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount type=bind,src=/workspace/walleturbo,dst=/src,readonly \
  --mount type=bind,src=/workspace/walleturbo/.venv/lib/python3.12/site-packages,dst=/testdeps,readonly \
  -e PYTHONPATH=/src:/testdeps -w /src --entrypoint python \
  walleturbo-api -m pytest -q -p no:cacheprovider
```

Esta alternativa valida execução containerizada, mas não equivale a verificar o comando padrão da imagem de testes. O GitHub Actions executou diretamente a imagem de testes: 26 testes aprovados no job 126309571600. A primeira auditoria do CI falhou ao tentar criar cache em diretório sem permissão; o workflow foi corrigido para usar `/tmp/pip-audit`. A validação de PostgreSQL/Redis com volume novo foi adicionada ao CI para resolver a limitação local.

**Validação independente concluída:** [execução 41749313210](https://github.com/oYuriyan/walleturbo/actions/runs/41749313210), commit `ffdc617`, aprovada em todas as etapas: build, 26 testes pela imagem padrão, auditoria, JavaScript e integração PostgreSQL/Redis com volume novo. As limitações locais acima não impediram a confirmação no runner do GitHub.

O volume local de PostgreSQL precisou da aplicação manual da migração inicial depois de falhas de permissão e espaço. O SQL foi envolvido em transação para evitar migração parcial em instalações futuras. Não houve dados reais. A inicialização automática em volume novo foi posteriormente aprovada no GitHub Actions.

Integração real reproduzível apenas em ambiente de testes próprio (o script cria sessão sintética diretamente no Redis e limpa os dados que criou):

```sh
docker compose exec -T -e SMOKE_BASE_URL=http://localhost:8000 api python < tests/integration_real.py
```

O roteiro de navegador está em `tests/browser.cjs`. Requer Playwright e Chromium disponíveis, diretório `artifacts/` e aplicação iniciada. Aceita `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH` e `APP_URL`. Capturas locais em `artifacts/desktop.png`, `artifacts/mobile.png` e `artifacts/mobile-dark.png`, ignoradas no Git.

## Não homologado

Google/OIDC real, criptografia/token/state/nonce ponta a ponta, configuração MFA/recuperação, testes de carga/DoS, pentest externo, backup/restore, scanners de imagem, acessibilidade WCAG completa, LGPD jurídica/operacional, publicação e escalabilidade. Os testes de callback simulam a resposta do provedor e verificam somente a política local de ACR/issuer e rotação de sessão.

Não foram implementados OCR/PDF/OFX, agentes de IA, ofertas/cupons, orçamento, contas/cartões/parcelas nem recomendações completas por perfil. Consulte os critérios de aceite no roadmap. A ausência de vulnerabilidades conhecidas no auditor não constitui garantia de ausência de falhas.

## Incremento 0.2 — contas e faturas

Validações locais realizadas com dados sintéticos:

- 49 testes aprovados: suíte ampliada para parcelas, calendário, idempotência, estornos, conferência, imutabilidade, pagamentos, segregação, exclusão, envio lento e corpos chunked.
- PostgreSQL/Redis reais: compras concorrentes idempotentes; pagamentos concorrentes limitados ao restante; diferença entre consumo e caixa; FK composta recusando vínculo entre proprietários.
- Migrações: adoção explícita do banco 0.1, preservação de valores, execução repetida, rollback integral de SQL inválido e rejeição de checksum divergente.
- Chromium autenticado com API real: cadastro de conta/cartão, compra parcelada, recusa de total divergente, conferência correta, pagamento parcial e próximo mês. Desktop/mobile escuro sem erros JavaScript.
- Regressão dos fluxos anteriores de demonstração, lançamento, metas, busca e texto não interpretado como HTML.

A sessão do teste visual foi criada diretamente no Redis para usuário sintético com TTL curto e removida com os dados ao final. Isso não homologa login Google/MFA real. Screenshots locais: `artifacts/cards-desktop.png` e `artifacts/cards-mobile-dark.png`.

O ambiente local voltou a atingir seu limite de disco ao duplicar containers pelo driver VFS. A migração foi concluída, e a API nova foi validada usando a imagem de dependências existente com código montado somente para leitura. O CI executa builds completos, banco novo, concorrência e migração de legado. Não foram feitos testes volumétricos/DDoS, pentest nem backup/restore.

As pendências citadas no relatório 0.1 devem ser lidas como estado daquela entrega; parcelas, estornos, cartões e conferência por total foram implementados neste incremento. Permanecem pendentes OCR/PDF/OFX, agentes de IA, preços/cupons, recorrência/orçamentos, integração bancária e homologação de produção/LGPD.

**CI 0.2 aprovado:** [execução 41762142999](https://github.com/oYuriyan/walleturbo/actions/runs/41762142999), commit `166ad99`. Todas as etapas passaram: build completo, 49 testes pela imagem Docker padrão, auditoria de dependências, sintaxe JavaScript, banco novo, pagamentos/compras concorrentes, isolamento por FK e migração de legado com preservação/rollback/checksum.

## Incremento 0.3 — PDF textual assistido

66 testes locais aprovados, incluindo PDFs inválidos, escaneados, protegidos, com ações, excesso de páginas, protocolo limitado, revisão obrigatória, isolamento de usuário/sessão/fatura e deduplicação de seleções parciais. Os documentos são sintéticos; não há homologação de layouts de bancos. O Compose isolado e o navegador foram aprovados no CI, conforme evidência abaixo. O limite de disco do ambiente local motivou a validação integral no runner do GitHub.

**CI 0.3 aprovado:** [execução 41826812495](https://github.com/oYuriyan/walleturbo/actions/runs/41826812495), commit `e60ea41`: build, 66 testes em container, auditoria, JavaScript, banco novo/legado, concorrência, PDF em leitor sem rede e navegador. O navegador confirmou prévia sem persistência, edição de descrição/valor, estorno e importação revisada em desktop/mobile. Capturas sintéticas estão no artefato `revisao-pdf` da execução. O runner foi fixado em Ubuntu 24.04, compatível com a versão de Playwright usada.

## Incremento 0.4 — planejamento

74 testes locais aprovados, incluindo isolamento de cenários/limites, estornos, capacidade de aporte, ausência de receita, invalidação por agregados e recorrência sem parcelas. O pipeline adiciona navegação de cenário e limite mensal, com capturas sintéticas. Não há análise por modelo de IA, certificação financeira ou garantia de economia. Ver PLANEJAMENTO.md.

**CI 0.4 aprovado:** [execução 41830565715](https://github.com/oYuriyan/walleturbo/actions/runs/41830565715), código `af7fc62`: 74 testes em container, auditoria, sintaxe, migração 003 com preservação de legado, concorrência financeira, regressão de PDF e planejamento no Chromium desktop/mobile. O navegador verificou limite excedido, confirmação mensal, capacidade após margem e remoção de dados exibidos ao encerrar sessão. Capturas sintéticas de planejamento estão no artefato da execução. O teste inicial identificou ícones decorativos nos nomes acessíveis; eles foram ocultados de tecnologias assistivas antes da aprovação.

## Revisão do CI e notificações — 04/11/2026

A análise dos logs confirmou que os e-mails `Run failed` correspondiam a falhas reais de versões intermediárias. O aviso de depreciação do Node.js 20 era independente dessas falhas.

| Execução | Diagnóstico | Correção já incorporada |
| --- | --- | --- |
| [41826516838](https://github.com/oYuriyan/walleturbo/actions/runs/41826516838) | Playwright 1.58.2 recusou Ubuntu 26.04 durante instalação do navegador. | Runner fixado em Ubuntu 24.04, commit `e60ea41`. |
| [41829938027](https://github.com/oYuriyan/walleturbo/actions/runs/41829938027) e [41830040265](https://github.com/oYuriyan/walleturbo/actions/runs/41830040265) | Timeout ao localizar botão com nome acessível exato `Planejamento`. | Ícones decorativos com `aria-hidden`, commit `fdab7b7`. |
| [41830448894](https://github.com/oYuriyan/walleturbo/actions/runs/41830448894), [41830565715](https://github.com/oYuriyan/walleturbo/actions/runs/41830565715) e [41830975378](https://github.com/oYuriyan/walleturbo/actions/runs/41830975378) | Execuções posteriores concluídas com sucesso. | Evidência de regressão aprovada após as correções. |

Nesta revisão, `upload-artifact` migrou de v4 para v6, cujo manifesto declara Node.js 24. Checkout v5 e upload v6 ficaram fixados por SHA. Os gatilhos passam a executar em pull requests, pushes na `main` e acionamento manual: branches de desenvolvimento devem possuir PR para validação automática. Isso elimina o par push/PR para a mesma alteração, preservando a validação da integração e do resultado na `main`. Novas alterações cancelam execuções obsoletas do mesmo PR; cancelamento não significa aprovação.

O shell Bash explícito habilita `pipefail`, propagando falhas na criação da sessão sintética antes dos testes de navegador. O job tem limite de 20 minutos e ausência de capturas no upload é erro. Não foram desativados testes, auditoria nem notificações de falha. Execuções históricas continuam vermelhas e os e-mails já enviados não são alterados por uma correção posterior. A aprovação desta revisão deve ser conferida no check do próprio commit no PR #1.

## Migração do cliente HTTP — 04/11/2026

Substituído httpx 0.28.1 por httpx2 2.16.0, suportado por Authlib 1.9.3 e Starlette 1.10.0. Locks de produção/testes regenerados com hashes; scripts de integração usam o novo cliente. A suíte local passou com 76 testes e `pytest -q -W error`, sem avisos. Dois cenários adicionais exercitam o transporte assíncrono real de Authlib com endpoint simulado: envio do verificador PKCE na troca de código e recusa de `invalid_grant`. Isso não homologa assinatura de ID token, Google, MFA ou provedor OIDC real. A validação containerizada completa permanece no check do commit correspondente no PR #1.

O novo transporte usa truststore e certificados do sistema. A verificação TLS continua habilitada; ambientes com CA privada devem instalar essa CA no trust store do sistema. Não foram adicionadas exceções de certificado nem supressões de avisos.

## Infraestrutura de identidade local — validada no CI

Adicionados Keycloak 26.8.1 com banco exclusivo, realm versionado sem usuários/credenciais e gerador de segredos locais. A configuração Compose foi validada sem iniciar serviços locais, devido ao limite de disco. Os 76 testes existentes passaram sem avisos. O CI recebeu um fluxo adicional com provedor real e cadastro TOTP no Chromium; a aprovação depende do resultado do check deste incremento. Google, recuperação e operação pública não são homologados por esse teste local. Roteiro em KEYCLOAK.md.

**OIDC/TOTP real aprovado:** [execução 41837356697](https://github.com/oYuriyan/walleturbo/actions/runs/41837356697), código `2839514`. Todas as etapas passaram: 77 testes em container sem avisos, auditoria, regressão financeira/PDF/planejamento e navegador com Keycloak real. Foram verificados discovery/issuer, PKCE S256, cadastro TOTP, recusa de código incorreto e acesso antes da conclusão, ID token assinado aceito pela aplicação, rotação com invalidação da sessão anterior, logout e state inválido. O realm inclui os escopos profile e acr. Os seletores do teste acompanham o tema atual do provedor. Não foram homologados Google, recuperação, rotação de JWKS, ataques criptográficos abrangentes ou produção.

## Incremento 0.5 — saldos e transferências (homologação técnica local)

89 testes locais aprovados sem avisos: referência ausente/negativa, fronteira da data, registros sem conta, revisão com controle de versão, neutralidade de transferência, reversão datada, idempotência após reversão, pagamento sem dupla despesa e exclusão/isolamento. Novos roteiros verificam PostgreSQL concorrente/FKs e interface desktop/mobile com limpeza após sessão encerrada. A homologação completa depende do check CI deste incremento. O contrato financeiro está em SALDOS.md; saldo calculado não é consulta bancária e aceita negativos.

**CI 0.5 aprovado:** [execução 41875971563](https://github.com/oYuriyan/walleturbo/actions/runs/41875971563), código `4675ba8`: 91 testes em container sem avisos, auditoria, migração 003→004 preservando conta/vínculo/valor, concorrência no PostgreSQL (referência, correção conflitante, transferência/reversão, ordem de locks e FK), regressão financeira/PDF/planejamento e OIDC/TOTP real. O navegador validou referências, saldo conservado, reversão e limpeza de formulário/dados após sessão encerrada, em desktop/mobile sem overflow horizontal. Capturas sintéticas `balances-desktop.png` e `balances-mobile.png` no artefato da execução; a captura mobile foi também inspecionada visualmente.

O teste inicial identificou que mutações após expiração/exclusão da sessão retornavam 403 de CSRF e não acionavam a limpeza da interface. A API passou a responder 401 para sessão ausente, após verificar a origem e antes de CSRF; teste de regressão adicionado. A verificação de origem e a exigência de token para sessões autenticadas permanecem ativas.

Cenário combinado validado: saldos iniciais R$ 100,00 + R$ 5,00; receita R$ 50,00; despesa R$ 12,34; compra em cartão R$ 80,00; pagamento parcial R$ 25,00; transferência R$ 20,00. Saldo final das contas R$ 92,66 e R$ 25,00 (total R$ 117,66), resultado mensal −R$ 42,34 e variação de caixa R$ 12,66. Reverter a transferência redistribui para R$ 112,66 e R$ 5,00, sem alterar o total.

## Incremento 0.6 — ciclo de vida de contas e cartões

99 testes locais aprovados com avisos tratados como erro. As novas verificações cobrem versão obsoleta, arquivamento/reativação, bloqueio de novos vínculos, operações existentes, UUIDs idempotentes, PDF confirmado após arquivar, isolamento e privacidade. Migração 005 e roteiros PostgreSQL/navegador adicionados ao CI; resultado completo ainda pendente nesta revisão. Política e limites em CADASTROS.md. Metas permanecem pendentes em FIN-03.

**Situação operacional desta entrega:** código `5cb3244`, seguido de documentação em `4effa14`. O GitHub confirmou os commits no PR, mas a consulta de Actions não retornou execução para esses SHAs durante a verificação. Tentativa de disparo manual por CLI recusada pela política de rede (`Forbidden`); o conector disponível não oferece workflow_dispatch. A validação completa de 0.6 continua pendente e não deve ser inferida do CI verde de 0.5. O teste adicional local com a imagem existente também não iniciou por falta de disco ao criar a camada Docker; cache/camadas sem uso foram limpos, preservando volumes. Próxima ação operacional: executar `Validação técnica` na branch `feat/base-controle-financeiro` e corrigir eventuais falhas antes da homologação.

**Pendência 0.6 resolvida:** [CI 41882396599](https://github.com/oYuriyan/walleturbo/actions/runs/41882396599), commit `790e362`, aprovado. Confirmados 99 testes em container, auditoria de dependências, PostgreSQL/Redis, migrações, concorrência de edição/arquivamento, PDF, navegador mobile com conflito/recarga/exclusão e OIDC/TOTP real. A ausência inicial de execução foi transitória; o resultado posterior substitui o status operacional pendente acima.

## Incremento 0.7 — ciclo de vida de metas

103 testes locais aprovados com avisos tratados como erro. Metas recebem versão, arquivamento/reativação e exclusão condicionada a arquivamento e reserva zero. Arquivadas permanecem no cadastro/exportação e saem da simulação; nenhum saldo financeiro é movimentado. O roteiro PostgreSQL disputa edição e exclusão versus correção da reserva; migração preserva valores legados; navegador cobre a jornada e expiração de sessão. A homologação completa depende do CI deste incremento.

**CI 0.7 aprovado:** [execução 41886542300](https://github.com/oYuriyan/walleturbo/actions/runs/41886542300), commit `4153e22`: 103 testes em container, auditoria, PostgreSQL/Redis, migração 006 preservando valores de meta legada, concorrência de edição/exclusão versus reserva, navegador de metas e regressão OIDC/TOTP e financeira. FIN-03 homologado no escopo atual; aportes vinculados a contas permanecem em PLA-02.

## Incremento 0.8 — histórico financeiro e revisão técnica

109 testes locais aprovados com avisos tratados como erro. Estados anterior/posterior para nove tipos de entidade; gravação atômica e recusa da operação se o histórico falhar. Consulta paginada, isolamento, exportação/expurgo, no-op e idempotência testados. Roteiros PostgreSQL, migração e navegador foram ampliados; a homologação completa depende do CI deste incremento. AUDITORIA.md registra escopo, retenção local, achados e pendências. Não equivale à conclusão integral de FIN-04/05 ou revisão de segurança de produção.

Revisão visual das capturas de 0.7: formulário mobile de metas funcional, com erro de exclusão por reserva visível. Identificada inconsistência no checkbox de arquivamento (estilo genérico de input); corrigida para usar o componente `.checkbox` existente e a cor da aplicação em 0.8. Captura atualizada será produzida pelo CI.

Revisão de privacidade 0.8: resposta atrasada do dashboard/cadastros poderia restaurar dados após limpeza da sessão. As respostas agora são aplicadas somente se CSRF/modo continuarem correspondendo à sessão de origem. Roteiro de navegador segura uma resposta autenticada anterior, encerra a sessão e a libera; o aceite exige listas e histórico vazios. A confirmação depende do CI do commit final.

**CI 0.8 aprovado:** [execução 41888034624](https://github.com/oYuriyan/walleturbo/actions/runs/41888034624), commit de código `5b7b1b6`: 109 testes em container, auditoria de dependências sem vulnerabilidades conhecidas encontradas, PostgreSQL/Redis, migrações 001–007, histórico JSON/rollback atômico, concorrência, PDF, planejamento, saldos, cadastros e OIDC/TOTP real aprovados. Navegador confirmou consulta de histórico, conteúdo HTML exibido como texto e limpeza de listas/formulário/histórico ao liberar resposta atrasada depois de encerrar a sessão.

Capturas `goals-mobile.png` e `history-mobile.png` do artefato `revisao-pdf` desta execução foram inspecionadas visualmente: checkbox no padrão da aplicação, erro de exclusão legível, histórico com detalhes e conteúdo de teste literal, sem overflow horizontal. A matriz de requisitos/testes está em MATRIZ.md. Documentação posterior não altera o código homologado. FIN-04/05 continuam parciais pelos limites descritos em AUDITORIA.md.

## Incremento 0.9 — correção de compras manuais e recibos de envio

116 testes locais aprovados com avisos tratados como erro (109 anteriores + 7 cenários novos). Correção integral com prévia sem escrita, centavos, IDs, motivo/histórico e versão por parcela; faturas conferidas de origem/destino bloqueiam a transação. Recibos protegem compras/pagamentos excluídos contra reenvio, com backfill de registros ativos e exclusões auditadas. A suíte local e os roteiros PostgreSQL/migração/navegador são verificados neste incremento; homologação completa depende do CI. Escopo e limites em CORRECOES.md.

**CI 0.9 aprovado:** [execução 41892139036](https://github.com/oYuriyan/walleturbo/actions/runs/41892139036), código `961b0e0`: 116 testes em container, auditoria de dependências sem vulnerabilidades conhecidas encontradas, PostgreSQL/Redis, migração 007→008 com dados ativos e exclusões auditadas, correções concorrentes, UUID entre cartões e exclusão versus reenvio aprovados. Regressões de PDF, planejamento, saldos, cadastros, histórico e Keycloak/TOTP também passaram.

O navegador confirmou prévia dos totais, redistribuição de centavos, conflito/recarga, reenvio cancelado e limpeza após expiração de sessão. A captura `corrections-mobile.png` do artefato `revisao-pdf` foi inspecionada visualmente: formulário legível, controles do padrão da aplicação e diálogo com rolagem. O teste verifica ausência de overflow horizontal e interage com os controles de prévia/confirmação. Documentação consolidada em 05/11/2026, sem alterar o código homologado. FIN-04/05 permanecem parciais nos limites de CORRECOES.md.

## Incremento 0.10 — correção de registros de pagamento

123 testes locais aprovados com avisos tratados como erro (116 anteriores + sete novos cenários). No isolamento do ambiente gerenciado, o cliente de teste bloqueou na comunicação entre threads; a suíte passou ao ser executada fora desse isolamento, com SQLite/fakeredis e dados sintéticos. Essa execução não substitui o CI containerizado.

Prévia sem escrita considera referência da conta/data de consulta, preserva saldo desconhecido e mostra efeito no caixa mensal. Conta/data/valor/motivo podem ser corrigidos sem alterar fatura/ID/UUID original. Versões e limite dos demais pagamentos são revalidados; remoção exige versão. Roteiros de PostgreSQL, migração e navegador mobile foram acrescentados ao CI; homologação completa pendente do resultado. Contrato e limites em PAGAMENTOS.md.

**CI 0.10 aprovado:** [execução 42033442245](https://github.com/oYuriyan/walleturbo/actions/runs/42033442245), código `39c0a67`: 123 testes em container, auditoria de dependências sem vulnerabilidades conhecidas encontradas, PostgreSQL/Redis, migrações 001–009, regressões financeiras/PDF/planejamento/cadastros/histórico e Keycloak/TOTP real aprovados.

A integração nova confirmou edição concorrente do mesmo pagamento, dois pagamentos distintos disputando limite, reconciliação dos saldos e remoção versus edição. O navegador confirmou prévia de saldos, ajuste, conflito/recarga, remoção obsoleta e limpeza após encerrar sessão. A captura `payment-corrections-mobile-preview.png`, no artefato `revisao-pdf`, foi inspecionada visualmente: valores antes/depois, caixa mensal, restante da fatura e confirmação legíveis no diálogo com rolagem. Campos de data nativos seguem o navegador; os valores/textos da prévia estão em pt-BR. Documentação posterior não altera o código homologado.

## Incremento 0.11 — lançamentos versionados e marcas de origem

133 testes locais aprovados com avisos tratados como erro, usando dados sintéticos e a execução fora do isolamento local já diagnosticado. Dez casos novos cobrem UUIDs/versões, marca persistente, ocorrências iguais, CSV/PDF, correção importada, revisão/exclusão obsoletas, isolamento, expurgo e rollback. Roteiros de PostgreSQL, migração e navegador ampliados; cartões e demonstração/XSS passam ao CI. Homologação completa depende do check deste incremento. Contrato/limites em LANCAMENTOS_E_IMPORTACAO.md.

Primeira execução da 0.11: [CI 42043717246](https://github.com/oYuriyan/walleturbo/actions/runs/42043717246), código `4783bb3`, aprovou 133 testes, auditoria de dependências, PostgreSQL/Redis e migrações 001–010. O roteiro PDF falhou em `Response.json()` com `Request content was evicted from inspector cache`, no transporte de inspeção do Chromium. A captura de evidência passou a usar o transporte HTTP do Playwright, encaminhando o upload e a resposta reais à interface; captura de criação de lançamento consulta a exportação autenticada pelo UUID. Nenhuma asserção financeira foi removida. A homologação permanece pendente da repetição completa.

Segunda execução: [CI 42044330326](https://github.com/oYuriyan/walleturbo/actions/runs/42044330326), código `09755ab`, resolveu a captura da resposta real. A checagem dos campos de origem ocorreu antes de a consulta assíncrona abrir o diálogo; o roteiro passou a aguardar explicitamente sua visibilidade antes de ler `readOnly`. As checagens de contexto original continuam obrigatórias. Repetição completa pendente.

Revisão adicional dos roteiros existentes: cartões aguardam os cadastros aparecerem na lista antes de abrir a operação seguinte, evitando depender da velocidade do refresh posterior ao fechamento do diálogo. O CI passa a preservar capturas sintéticas disponíveis também quando um teste falha, por sete dias; ausência de imagens não substitui os resultados obrigatórios dos testes nem a inspeção visual para homologação.

**CI 0.11 aprovado:** [execução 42045260683](https://github.com/oYuriyan/walleturbo/actions/runs/42045260683), código `812454894ec82ab8afac822a1c0fd87e1bd99e21`: 133 testes em container, auditoria sem vulnerabilidades conhecidas encontradas, PostgreSQL/Redis, migrações 001–010 e todos os roteiros de navegador aprovados. Inclui UUID/versão, edição versus exclusão, lotes em ordem inversa sem deadlock, correção importada e exclusão versus reimportação. Keycloak/TOTP, PDF, planejamento, saldos, cadastros, histórico e pagamentos passaram nas regressões. Cartões e demonstração/XSS agora são executados pelo CI. Nenhum aviso de Node.js 20 apareceu nesta execução. A execução intermediária 42044881303 foi substituída pela revisão adicional dos testes, sem constituir homologação.

Artefato `revisao-pdf`, ID `13425460778`, SHA-256 `267c2e239b901fd81e18f9ab4d03cf72dd01e4db30f53e11caa1931b1f07f5b6`, retenção de sete dias. Inspecionadas `entry-import-mobile.png`, `import-correction-mobile.png` e `cards-mobile-dark.png`: aviso de origem excluída, valor/totais antes e depois, motivo, confirmação e fatura escura legíveis, sem overflow horizontal nos testes. O diálogo possui rolagem; a captura da correção prioriza os efeitos e a confirmação. Campos nativos de data/mês seguem o idioma do navegador de teste, enquanto valores e textos da aplicação estão em pt-BR. Isso não substitui UX-03/04 nem homologação WCAG. Revisão de singular/plural dos avisos permanece no acabamento UX-02.

Documentação consolidada após essa execução não altera o código homologado. FIN-04/05 e REL-07 permanecem parciais nos limites de ROADMAP.md; não houve publicação, merge ou contratação.

## Incremento 0.12 — conferência de faturas homologada

Código 10bd122, CI aprovado https://github.com/oYuriyan/walleturbo/actions/runs/42085667177: 136 testes em container, PostgreSQL/Redis, migrações 001–011, concorrência de conferência, ciclo fechar/reabrir, conflito/recarga no navegador e regressões completas, incluindo Keycloak/TOTP. PR #2 integrado à main no commit c00f069. Documentação técnica em FATURAS.md. Cenários e contrato financeiro amplo permaneceram pendentes nesse incremento.

## Incremento 0.13 — configurações mensais versionadas

140 testes locais aprovados com avisos tratados como erro. Versão compartilhada de cenário/limites, exclusão/recriação sem retorno à versão antiga, histórico transacional e privacidade; novos roteiros de PostgreSQL e navegador aguardam CI. Contrato e limites em PLANEJAMENTO.md.

## Incremento 0.18 — desfazimento/remapeamento CSV

Validação local de 09/11/2026: 183 testes aprovados com avisos tratados como erro, JavaScript e diff sem erros. PostgreSQL/Redis reais em Compose: migração 013 preservou marcas legadas, repetição/checksum/rollback aprovados; dois desfazimentos concorrentes produziram 200/409, destino bloqueado foi recusado sem escrita, reenvios antigos não restauraram o vínculo e remapeamento para outro destino foi aceito com a revisão atual. Chromium do ambiente executou o roteiro mobile completo, incluindo desfazer/refazer sem alterar a quantidade de lançamentos e limpeza de sessão. A captura geral está no artefato local entry-import-mobile.png; não representa revisão WCAG nem todos os estados novos.

Homologação integral do GitHub Actions em andamento no [PR #9](https://github.com/oYuriyan/walleturbo/pull/9); o resultado final e o commit validado serão registrados no PR. A evidência local não substitui a regressão integral com login real. Contrato, atualização coordenada do schema e limites em LANCAMENTOS_E_IMPORTACAO.md/MIGRACOES.md. Nenhum serviço/dependência de aplicação foi adicionado; publicação e contratação continuam fora desta entrega.

0.18 homologada no CI 42627254915 e integrada à main pelo PR #9; 183 testes e regressão integral aprovados, conforme evidência final no PR.

## Incremento 0.19 — conciliação PDF

197 testes locais aprovados com avisos tratados como erro, incluindo 14 novos casos de conciliação PDF; JavaScript validado. PostgreSQL/Redis e parser isolado aprovados: duas associações concorrentes para destinos diferentes e dois desfazimentos produziram 200/409, sem mudança financeira; envio antigo foi recusado e nova leitura permitiu refazer a associação. Chromium com viewport mobile aprovou consulta dos campos editados, vínculo, motivo, desfazimento, releitura e nova associação, preservando quantidade/valores. A captura sintética pdf-link-mobile.png foi inspecionada; os campos nativos seguem o idioma do navegador e o diálogo tem rolagem.

Homologação integral e commit final serão registrados no PR desta entrega. Contrato e limites em PDF.md; não há migração, novo serviço ou dependência de aplicação. A evidência não constitui homologação de layouts de emissor, OCR, OFX ou WCAG, nem autorização de publicação.

0.19 homologada no CI 42635465140 e integrada à main pelo PR #10; 197 testes e regressão integral aprovados.

## Incremento 0.20 — OFX bancário com identidade de origem

226 testes locais aprovados com avisos tratados como erro, incluindo 29 novos casos OFX. Corpus sintético SGML 102/XML 220 e expected.json fixam três origens equivalentes, datas civis, sinais e valores em centavos. PostgreSQL/Redis reais aprovaram confirmação concorrente/reordenada sem duplicação, assinatura divergente atômica, exclusão versus reenvio e NOWAIT no destino, preservando valores em vínculo/desfazimento. Chromium mobile aprovou Windows-1252, troca de conta, revisão, seleção, identidade entre formatos e bloqueio da origem divergente, com limpeza da prévia após fechamento. Captura sintética ofx-mobile.png inspecionada localmente. Homologação integral e commit final serão registrados no PR.

Sem migração, serviço ou dependência nova. Escopo e limites em OFX.md; bancos reais, OFX de cartão, outros layouts e correções bancárias automáticas não estão homologados nesta entrega.

0.20 homologada no CI 42646344711 e integrada à main pelo PR #11; 226 testes e regressão integral aprovados.

## Incremento 0.21 — OFX de cartão

244 testes locais aprovados com avisos tratados como erro, incluindo 18 casos novos e corpus SGML/XML com três origens financeiras, crédito revisável e pagamento não importável. PostgreSQL/Redis aprovaram a disputa entre duas faturas (200/409), reordenação, exclusão/reenvio, assinatura divergente e NOWAIT com rollback, sem registros de pagamento ou parcelas futuras. Chromium mobile aprovou máscara, confirmação adicional dos créditos, vínculo/desfazimento/reenvio e bloqueio em outro mês; captura ofx-card-mobile.png inspecionada, sem corte horizontal ou impedimento à confirmação. Homologação integral e commit final serão registrados no PR.

Sem migração, serviço ou dependência nova. Contrato em OFX_CARTAO.md. Realocação de origem, ciclos de crédito transportado, bancos reais e layouts adicionais continuam pendentes; os cenários não constituem homologação WCAG ou autenticação bancária.
