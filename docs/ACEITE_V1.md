# Aceite técnico — V1 básica local

A versão 1.0 fecha o recorte de [V1_BASICA.md](V1_BASICA.md) quando o PR desta entrega tiver todas as etapas da CI aprovadas. O resultado e o commit exatos ficam no PR. O destino é uma instalação local, com uso controlado e um operador responsável; publicação na Internet continua fora do escopo.

## Critérios de entrega

| Critério | Evidência exigida |
| --- | --- |
| Primeiro uso e rotina financeira | browser_first_steps, browser_cards, browser_balances, browser_goals e correções: conta, saldo, despesa, fatura/pagamento, transferência, metas e histórico |
| Identidade e persistência | browser_oidc/basic_journey: dois logins reais/TOTP, isolamento, logout/nova sessão e exportação idêntica |
| Recuperação utilizável | integration_backup/recovery_browser: GPG, comparação dos bancos, API/Keycloak iniciados no destino, cookie antigo recusado, OTP existente e exportação/resultado preservados; origem reativada |
| Interface essencial | browser_ui: Chromium/Firefox, seis áreas claro/escuro, axe, foco/Tab/Escape, navegação 320/390/768 px, falha/repetição de consulta com bloqueio financeiro e Privacidade acessível; capturas inspecionadas no incremento 0.25 |
| Volume local declarado | integration_volume/browser_volume: cenário abaixo, totais/contagens/exportação e busca mobile, com orçamento de tempo e limpeza da fixture |
| Regressão e operação | 266 testes, auditoria de dependências, PostgreSQL/Redis/migrações/importações, manual e recuperação documentados |

O aceite é técnico: os roteiros de formulários e a inspeção visual cobrem os fluxos essenciais. A preferência pessoal do usuário pode gerar ajustes posteriores. A auditoria automatizada de acessibilidade não é certificação WCAG nem avaliação assistiva completa.

## Volume ensaiado

Um usuário, 24 meses, 10 contas com referências, quatro cartões, 96 faturas, 10 mil lançamentos diretos, 2.400 compras e 10 metas. Novembro/2026 contém 416 lançamentos diretos e 100 compras. Verificam-se valores independentes de resultado/saldo, contagens do mês e integridade da exportação; a busca no celular encontra um lançamento específico e as faturas não apresentam corte horizontal.

Medição local de 11/11/2026, cinco amostras sequenciais por endpoint, API limitada pelo Compose a 1 CPU/512 MiB, PostgreSQL 17/Redis 7 em host compartilhado. Milissegundos, incluindo resposta HTTP; tempos variam por instalação:

| Consulta | Mediana | Máximo observado |
| --- | ---: | ---: |
| Resumo mensal | 53,8 | 139,2 |
| Faturas do mês | 13,8 | 14,8 |
| Saldos das contas | 37,2 | 40,9 |
| Planejamento | 86,0 | 99,1 |
| Exportação (3,83 MB) | 540,3 | 575,7 |

Chromium 390 px: resumo exibido em 648 ms, incluindo abertura/carregamento; busca e leitura dos registros aprovadas. A fixture é inserida diretamente no banco para reduzir custo; o ensaio mede leitura e renderização, não taxa de cadastro/importação. Os testes funcionais existentes continuam verificando a escrita pela API/formulários. Não é carga simultânea, SLA, percentil estatístico nem garantia para um volume maior.

A CI repete o cenário e publica `v1-volume.json` e `volume-mobile.png` com dados sintéticos. Falha se uma leitura superar cinco segundos ou se o resumo mobile superar dez segundos, além de exigir valores/contagens corretos. Esses são orçamentos de regressão, não promessas ao usuário. Antes de ampliar volume ou acessos simultâneos, repetir a medição no equipamento-alvo.

Reprodução em instalação **de testes** com Playwright/Chromium e `artifacts/` preparados:

```bash
docker compose exec -T -e WALLETURBO_INTEGRATION=1 -e VOLUME_BROWSER=1 api python < tests/integration_volume.py | PLAYWRIGHT_MODULE=/caminho/playwright node tests/browser_volume.cjs
```

Manter as cotas reais; usar janela própria, como na CI. A sessão sintética só existe no Redis de testes, dura três minutos e é revogada junto da exclusão da fixture. Nunca logar a saída intermediária do pipe.

## Operação e limites assumidos

- Instalar conforme README/KEYCLOAK.md, substituir credenciais de exemplo e guardar acesso administrativo/TOTP. Recuperação de autenticador é administrativa local; não há recuperação autônoma.
- Fazer backup criptografado antes de atualizar e após alterações importantes, guardar chave/cópia protegidas fora da máquina e repetir o ensaio de recuperação. RPO depende da frequência escolhida; RTO real depende do equipamento/volume. Usar RECUPERACAO_LOCAL.md, sem remover volumes da origem.
- Respeitar os formatos e recusas do manual: CSV declarado, PDF textual e corpus OFX BRL suportado. Bancos/emissores reais adicionais e OCR não foram homologados; lançamento manual é a alternativa.
- Conferir resultado, caixa e saldo conforme DOMINIO_FINANCEIRO.md. Não há cálculo de juros/rotativo, limite bancário, crédito transportado ou fechamento automático por dias úteis.
- IA, ofertas, Google, automações avançadas e infraestrutura pública continuam adiados. As restrições do roadmap geral não exigem implementar essas expansões para este recorte local.

Roteiro de uso: [MANUAL.md](MANUAL.md). Recuperação: [RECUPERACAO_LOCAL.md](RECUPERACAO_LOCAL.md). A ampliação do uso exige nova avaliação; esta entrega não autoriza publicação pública.
