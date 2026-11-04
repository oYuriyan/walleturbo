# Relatório de validação — fundação 0.1.0

Data: 03/11/2026 (America/Sao_Paulo). Ambiente: workspace cloud Linux, Python 3.12, Docker 29.9.2. Dados exclusivamente sintéticos. **Resultado: base funcional validada; produto não homologado para produção.**

## Evidências executadas

| Verificação | Resultado |
|---|---|
| Testes de domínio/API/segurança no host | 26 aprovados |
| Mesma suíte em container sem privilégios, filesystem somente leitura e capabilities removidas | 26 aprovados |
| Build da imagem de aplicação e da imagem de testes com dependências/hashes | Concluído após correção de ownership nos COPY |
| PostgreSQL 17 e Redis 7 reais | Readiness, sessão sintética, importação, deduplicação, saldo, exportação e exclusão aprovados |
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

Esta alternativa valida execução containerizada, mas não equivale a verificar o comando padrão da imagem de testes. O CI foi preparado para executar a imagem diretamente em runner com espaço suficiente; seu resultado deve ser conferido no GitHub.

O volume local de PostgreSQL precisou da aplicação manual da migração inicial depois de falhas de permissão e espaço. O SQL foi envolvido em transação para evitar migração parcial em instalações futuras. Não houve dados reais. A inicialização automática em volume novo ainda precisa ser repetida em ambiente com espaço adequado.

Integração real reproduzível apenas em ambiente de testes próprio (o script cria sessão sintética diretamente no Redis e limpa os dados que criou):

```sh
docker compose exec -T -e SMOKE_BASE_URL=http://localhost:8000 api python < tests/integration_real.py
```

O roteiro de navegador está em `tests/browser.cjs`. Requer Playwright e Chromium disponíveis, diretório `artifacts/` e aplicação iniciada. Aceita `PLAYWRIGHT_MODULE`, `CHROMIUM_PATH` e `APP_URL`. Capturas locais em `artifacts/desktop.png`, `artifacts/mobile.png` e `artifacts/mobile-dark.png`, ignoradas no Git.

## Não homologado

Google/OIDC real, criptografia/token/state/nonce ponta a ponta, configuração MFA/recuperação, testes de carga/DoS, pentest externo, backup/restore, scanners de imagem, acessibilidade WCAG completa, LGPD jurídica/operacional, publicação e escalabilidade. Os testes de callback simulam a resposta do provedor e verificam somente a política local de ACR/issuer e rotação de sessão.

Não foram implementados OCR/PDF/OFX, agentes de IA, ofertas/cupons, orçamento, contas/cartões/parcelas nem recomendações completas por perfil. Consulte os critérios de aceite no roadmap. A ausência de vulnerabilidades conhecidas no auditor não constitui garantia de ausência de falhas.
