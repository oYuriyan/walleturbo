# Migrações de banco

Arquivos SQL imutáveis em `app/migrations/`, com ordem numérica, SHA-256 registrado em `schema_migrations` e lock de transação PostgreSQL. O runner rejeita mudança de checksum, versão de banco mais recente que o código e adoção implícita de banco legado. Todas as migrações pendentes e seus registros são confirmados na mesma transação; uma falha desfaz o lote.

## Instalação nova

`docker compose up --build -d` inicia o banco, executa o serviço `migrate` e só inicia a API depois da conclusão bem-sucedida. O healthcheck da API consulta o schema necessário, além do Redis. O antigo bind de `infra/001_initial.sql` foi removido; esse arquivo permanece apenas como referência histórica da versão 0.1.

## Atualizar instalação 0.1

1. Faça backup e valide sua restauração em ambiente isolado antes de atualizar dados reais.
2. Construa a nova imagem: `docker compose build api migrate`.
3. Em janela de manutenção, interrompa escritores e execute `docker compose run --rm migrate python -m app.migrate --adopt-initial`.
4. A adoção exige exatamente os conjuntos de colunas do schema inicial em `transactions` e `goals`. Isso não substitui uma revisão de constraints/permissões de uma instalação modificada manualmente.
5. O runner registra o baseline e aplica as migrações pendentes, preservando lançamentos e metas. `account_id` legado fica nulo. Execute `docker compose up -d` e confira a prontidão.

Não remova volumes nem apague dados para atualizar o schema. Não edite migrações já aplicadas: crie o próximo arquivo. Em versões posteriores, `python -m app.migrate` aplica somente as pendências. O flag de adoção deixa de ter efeito após o baseline estar registrado.

## Operação de produção

O Compose continua sendo de desenvolvimento. Em produção, separe credenciais de migração e de aplicação, aplique privilégios mínimos e use um job de implantação. Não execute migrações automaticamente em cada réplica da API. Rollback de schema não é automático: planeje migrações compatíveis, restauração e roll-forward. Backup/restore operacional ainda precisa ser implementado e homologado.

## Evidência

`tests/integration_migrations.py` cria um banco temporário próprio para testar atualização de legado, preservação de valores, repetição, rollback de um lote inválido e rejeição de checksum alterado. Exige `WALLETURBO_INTEGRATION=1`, privilégios de criação de banco e ambiente de testes. Nunca execute esse roteiro em produção. O banco temporário é removido ao final.

## Incremento 0.5

A migração 004 cria `opening_balances` e `transfers`, preservando contas e lançamentos existentes. Não deduz saldo inicial nem atribui conta a registros sem vínculo. Contas antigas exibem saldo desconhecido até a definição explícita da referência. O teste de migração passa por um schema 003 com conta/lançamento vinculados e verifica a preservação na versão 004.

## Migração 005 — ciclo de vida

Adiciona estado ativo/arquivado e versão de metadados em contas/cartões. Registros existentes ficam ativos na versão 0; IDs, nomes, vencimentos e vínculos são preservados. Readiness exige as novas colunas. Política em [CADASTROS.md](CADASTROS.md).

## Migração 006 — metas

Adiciona estado ativo/arquivado e versão em metas. Mantém nome, objetivo, reserva, prazo e ID. Readiness exige o novo schema; interface e API de edição devem ser atualizadas juntas, pois agora exigem `expected_version` e `archived`. O teste de upgrade preserva uma meta criada no schema inicial.

## Migração 007 — histórico financeiro

Cria financial_audit e índice por proprietário/instante/ID. Não altera valores existentes nem reconstrói estados anteriores. Atualizar a aplicação junto do schema habilita a instrumentação ORM. Readiness exige a tabela. Teste de upgrade verifica histórico inicialmente vazio e preservação de registros legados.

## Migração 008 — parcelas e recibos de envio

Adiciona versão (inicial 1) e motivo nullable às parcelas e cria request_receipts. Preserva IDs/valores e preenche recibos de compras manuais/pagamentos ativos. Reserva UUIDs de exclusões encontradas no histórico 0.8, sem inventar hashes originais; recibos ativos têm precedência. Exclusões sem histórico não são reconstruídas. O roteiro de migração simula upgrade de 007 para 008, com registros ativos e excluídos, repetição e rollback. Readiness exige a nova tabela/colunas; aplicar junto da aplicação.
