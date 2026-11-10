# Walleturbo

Controle financeiro pessoal em português do Brasil. A proposta é reduzir o tempo de registro, tornar os gastos compreensíveis e ajudar a planejar metas sem depender de funcionalidades pagas de outros aplicativos.

**Estado: fundação funcional em desenvolvimento, não liberada para produção.** A demonstração visual é independente do login e usa dados fictícios em memória. A operação real exige PostgreSQL, Redis e um provedor OpenID Connect configurado. Login local com Keycloak/TOTP foi homologado no CI. Google, recuperação de MFA, OCR, formatos bancários específicos, agentes de IA e busca de ofertas permanecem pendentes. Contas, cartões, parcelas, conferência de fatura e pagamentos parciais já possuem fluxos funcionais.

## Executar com Docker

1. Copie `.env.example` para `.env` e substitua a senha do PostgreSQL tanto em `POSTGRES_PASSWORD` quanto em `DATABASE_URL`.
2. Configure o provedor conforme [Autenticação](docs/AUTENTICACAO.md). Sem ele, a interface e a demonstração abrem; login real retorna indisponibilidade.
3. Execute `docker compose up --build -d`.
4. Abra `http://localhost:8000` e escolha **Explorar demonstração** ou **Entrar com segurança**.
5. Para testes: `docker compose --profile test run --build --rm tests`.

O serviço `migrate` aplica migrações versionadas antes da API. Para bancos da versão 0.1, siga [Migrações](docs/MIGRACOES.md) e faça a adoção explícita do schema após backup. Não remova volumes para atualizar. O Compose é de desenvolvimento; não é um manifesto de produção.

Em ambiente cloud com inspeção TLS, use o certificado do ambiente como secret BuildKit:

```sh
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt --target test -t walleturbo-test .
docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges walleturbo-test
```

## Recursos desta entrega

- Visão mensal de entradas, saídas, resultado e distribuição por categoria.
- Lançamentos com UUIDs de envio, revisão/edição com motivo e versão, exclusão protegida e busca por descrição/categoria.
- Marcas de origem preservam importações reconhecidas após correção/exclusão; correção de importados mantém fatura e parcela única.
- CSV UTF-8 com prévia, limites de tamanho, validação integral e deduplicação.
- OFX bancário 1.x/2.x em BRL, conta obrigatória e identidade por FITID; corpus sintético, sem homologação de bancos reais.
- OFX de cartão na fatura selecionada, com revisão de créditos e reserva de origem entre meses; pagamentos exibidos não são importados.
- Correção explícita de competência do lançamento OFX original, com simulação das duas faturas e histórico.
- PDF com texto selecionável: leitor isolado sem rede e candidatos editáveis, com revisão obrigatória. Formato limitado, sem OCR.
- Sugestões de categoria por regras, sempre pendentes de revisão.
- Alertas de assinaturas e despesas acima das receitas; sem promessas de economia.
- Metas com atualização versionada, arquivamento/reativação, exclusão protegida e estimativa mensal sem rendimentos.
- Contas, cartões, parcelas exatas em centavos, estornos, conferência e pagamentos parciais sem duplicar despesas.
- Visões separadas de resultado mensal e movimentação líquida de caixa; saldos por conta com referência datada e transferências com reversão.
- Contas/cartões com edição versionada e arquivamento preservando histórico.
- Correção integral de compras manuais com prévia dos totais mensais e recibos contra recriação por reenvio após exclusão de compra/pagamento.
- Correção versionada de pagamentos com prévia de saldos/caixa, motivo e remoção protegida contra versão desatualizada.
- Histórico privado de alterações financeiras, consulta paginada e exportação/expurgo.
- Limites por categoria, cenário mensal e simulação conservadora de aportes; recorrências de assinaturas com evidências.
- Exportação JSON e exclusão dos dados financeiros ativos.
- Sessão opaca no Redis, CSRF, verificação OIDC/ACR, limites de requisição e corpo.
- Layout responsivo, claro/escuro, navegação por teclado e mensagens acessíveis.

## Documentação de engenharia

- [Arquitetura e decisões](docs/ARQUITETURA.md)
- [Autenticação e identidade](docs/AUTENTICACAO.md)
- [Segurança e ameaças](docs/SEGURANCA.md)
- [Privacidade e preparação LGPD](docs/PRIVACIDADE.md)
- [Manual de utilização](docs/MANUAL.md)
- [Contas e faturas](docs/FATURAS.md)
- [Ciclo de vida dos cadastros e metas](docs/CADASTROS.md)
- [Histórico financeiro e revisão técnica](docs/AUDITORIA.md)
- [Correções integrais e recibos de envio](docs/CORRECOES.md)
- [Correção de pagamentos e impacto nos saldos](docs/PAGAMENTOS.md)
- [Lançamentos versionados e origem de importação](docs/LANCAMENTOS_E_IMPORTACAO.md)
- [Matriz de requisitos e testes](docs/MATRIZ.md)
- [Leitura assistida de PDF e limites](docs/PDF.md)
- [Importação OFX, identidade e limites](docs/OFX.md)
- [OFX de cartão e reserva da fatura](docs/OFX_CARTAO.md)
- [Correção de competência OFX](docs/OFX_REALOCACAO.md)
- [Migrações preservando dados](docs/MIGRACOES.md)
- [Planejamento, limites e recorrências](docs/PLANEJAMENTO.md)
- [Plano de entrega e critérios de aceite](docs/ROADMAP.md)
- [Homologação e evidências](docs/HOMOLOGACAO.md)
- [Operação e versionamento](docs/OPERACAO.md)

## Desenvolvimento

Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL 17 e Redis 7. Interface HTML/CSS/JavaScript sem compilação e sem dependências externas em runtime. Essa escolha reduz a superfície inicial de dependências; a evolução para componentes TypeScript será decidida conforme a complexidade da interface crescer.

```sh
python -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-test.lock
.venv/bin/pytest -q
node --check web/app.js
```

Os testes isolados usam SQLite e fakeredis. Eles não substituem validação em PostgreSQL, Redis real, provedor OIDC, navegador e infraestrutura de produção. O pipeline executa a suíte em container e auditoria das dependências.

Licença: [GPL-3.0](LICENSE), preservada do repositório original.

Para configurar login local com Keycloak e TOTP, consulte [Identidade local](docs/KEYCLOAK.md).

Saldos iniciais, posição por conta e transferências com reversão: [contrato financeiro](docs/SALDOS.md).

Primeira versão de uso básico: [escopo e critérios de aceite](docs/V1_BASICA.md). Primeiro uso orientado na visão geral: conta, saldo inicial e lançamento.

Backup e restauração local: [procedimento, proteção da chave e ensaio](docs/RECUPERACAO_LOCAL.md).
