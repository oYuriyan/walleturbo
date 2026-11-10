# Operação e versionamento

## GitHub

Repositório `oYuriyan/walleturbo`, licença original preservada. Branches por entrega (`feat/`, `fix/`, `docs/`), commits com assunto em pt-BR e pull requests com problema, comportamento entregue e evidências. Proteger a branch principal com revisão, CI obrigatório e proibição de force-push. As proteções devem ser configuradas no GitHub; não estão ativadas apenas por este documento existir.

Não versionar segredos, dados de usuários, exports ou screenshots com dados reais. `.env.example` documenta nomes de configuração; `.env` é ignorado. Dependências Python travadas com hashes. Para atualizar: executar pip-compile com hashes, revisar changelog/avisos, executar suíte e auditoria, registrar PR.

## Desenvolvimento containerizado

`docker compose up --build -d` inicia PostgreSQL/Redis, executa o serviço de migração e inicia a API. Consulte MIGRACOES.md antes de atualizar um volume 0.1. Porta da aplicação vinculada ao loopback; banco e Redis sem portas públicas. `docker compose logs api` auxilia diagnóstico; não habilitar logs de corpo ou código OAuth. `docker compose down` preserva o volume; **não usar `down -v` com dados que devam ser mantidos**.

A API usa usuário sem privilégios, filesystem somente leitura, capabilities removidas e tmpfs limitado. Banco requer volume persistente. Os serviços usam imagens versionadas por tag; fixação de digest e scanner de imagens são pendências antes da produção.

## Saúde e recuperação

`/health/live`: processo atendendo. `/health/ready`: conexão com banco e Redis. Monitorar latência p95, erros 5xx, recusas 429, tamanho das filas futuras e saturação de banco/Redis. Nenhuma informação financeira deve aparecer como label de métrica.

Perder Redis encerra sessões e zera contadores temporários, sem perder os registros financeiros. Backups de PostgreSQL devem ser criptografados, retidos por política aprovada, testados em ambiente isolado e associados a RPO/RTO acordados. A versão 0.24 oferece captura criptografada e restauração isolada em projeto novo, com ensaio dos bancos financeiro/identidade. Procedimento e limites em [RECUPERACAO_LOCAL.md](RECUPERACAO_LOCAL.md). Agendamento, cópia fora da máquina e política de retenção permanecem responsabilidades locais.

## Promoção de versão

CI aprovado → revisão técnica → ambiente de homologação → checklist funcional/segurança/LGPD → backup e migração ensaiados → deploy progressivo → verificação de saúde → acompanhamento. Rollback de aplicação precisa respeitar compatibilidade de schema; não reverter migração destrutiva automaticamente. Não há deployment automático de produção nesta entrega.
