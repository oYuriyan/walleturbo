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
