# Walleturbo

Controle financeiro pessoal em português do Brasil. A proposta é reduzir o tempo de registro, tornar os gastos compreensíveis e ajudar a planejar metas sem depender de funcionalidades pagas de outros aplicativos.

**Estado: fundação funcional em desenvolvimento, não liberada para produção.** A demonstração visual é independente do login e usa dados fictícios em memória. A operação real exige PostgreSQL, Redis e um provedor OpenID Connect configurado. Google, MFA real, extração de PDF, agentes de IA e busca de ofertas não estão homologados.

## Executar com Docker

1. Copie `.env.example` para `.env` e substitua a senha do PostgreSQL tanto em `POSTGRES_PASSWORD` quanto em `DATABASE_URL`.
2. Configure o provedor conforme [Autenticação](docs/AUTENTICACAO.md). Sem ele, a interface e a demonstração abrem; login real retorna indisponibilidade.
3. Execute `docker compose up --build -d`.
4. Abra `http://localhost:8000` e escolha **Explorar demonstração** ou **Entrar com segurança**.
5. Para testes: `docker compose --profile test run --build --rm tests`.

O PostgreSQL só aplica `infra/001_initial.sql` quando o volume é novo. Não remova volumes com dados para aplicar alterações: futuras migrações devem ser incrementais e testadas. O Compose é de desenvolvimento; não é um manifesto de produção.

Em ambiente cloud com inspeção TLS, use o certificado do ambiente como secret BuildKit:

```sh
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt --target test -t walleturbo-test .
docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges walleturbo-test
```

## Recursos desta entrega

- Visão mensal de entradas, saídas, saldo e distribuição por categoria.
- Lançamentos manuais, revisão, edição e exclusão; busca por descrição/categoria.
- CSV UTF-8 com prévia, limites de tamanho, validação integral e deduplicação.
- Sugestões de categoria por regras, sempre pendentes de revisão.
- Alertas de assinaturas e despesas acima das receitas; sem promessas de economia.
- Metas com atualização da reserva e estimativa mensal sem rendimentos.
- Exportação JSON e exclusão dos dados financeiros ativos.
- Sessão opaca no Redis, CSRF, verificação OIDC/ACR, limites de requisição e corpo.
- Layout responsivo, claro/escuro, navegação por teclado e mensagens acessíveis.

## Documentação de engenharia

- [Arquitetura e decisões](docs/ARQUITETURA.md)
- [Autenticação e identidade](docs/AUTENTICACAO.md)
- [Segurança e ameaças](docs/SEGURANCA.md)
- [Privacidade e preparação LGPD](docs/PRIVACIDADE.md)
- [Manual de utilização](docs/MANUAL.md)
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
