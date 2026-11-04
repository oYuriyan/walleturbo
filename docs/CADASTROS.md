# Ciclo de vida de contas e cartões — 0.6

## Contrato e preservação

`PUT /api/accounts/{id}` e `PUT /api/cards/{id}` recebem `name`, `archived` (booleano) e `expected_version` (inteiro). Cadastros existentes começam ativos na versão 0; cada alteração efetiva incrementa a versão. A versão de cadastro é independente da versão da referência de saldo. Um envio sem alterações preserva a versão; envio obsoleto recebe 409 e exige recarga/revisão. Renomear preserva IDs e aplica o novo rótulo também às consultas históricas; ainda não há trilha de nomes anteriores (FIN-04).

Arquivar é reversível e não elimina vínculos, saldos, parcelas ou dívidas. Listas, dashboard, exportação e cálculos incluem os arquivados. Não há movimentação bancária automática. O dia de vencimento não é editável nesta etapa; sua alteração exige uma política para faturas existentes (FAT-02).

| Operação | Conta/cartão arquivado |
| --- | --- |
| Novo lançamento ou importação CSV em conta | Recusado |
| Transferência nova de/para conta | Recusada |
| Primeira referência de saldo | Recusada; corrigir referência existente é permitido |
| Corrigir lançamento mantendo a mesma conta | Permitido; não pode mudar para outra conta arquivada |
| Lançamento sem conta | Continua permitido; pode vincular a uma conta ativa por revisão; segue fora dos saldos até vincular |
| Nova compra/estorno, nova fatura ou CSV/PDF em cartão | Recusado; reativar antes de importar, mesmo com prévia já obtida |
| Consultar/conferir/fechar/reabrir fatura existente | Permitido |
| Pagar fatura de cartão arquivado | Permitido com conta ativa |
| Reverter transferência/pagamento ou corrigir/remover registro existente pelas APIs atuais | Permitido conforme regras da operação |

Reenvios com o mesmo UUID e conteúdo de compra, pagamento, referência e transferência já gravados retornam a operação existente mesmo após arquivamento. Não abrem exceção para registros novos. CSV/PDF requerem cadastro ativo também na confirmação; a prévia não reserva esse direito. Reenvio após exclusão física de outras operações ainda depende da revisão ampla de idempotência (FIN-05).

## Exclusão e concorrência

`DELETE /api/accounts/{id}?expected_version=N` e equivalente de cartões exigem versão atual e cadastro arquivado. Retornam 204 apenas sem vínculos atuais; 409 caso contrário. Conta com lançamento, pagamento, referência de saldo ou transferência (inclusive revertida) não é excluída. Cartão com qualquer fatura, mesmo vazia, não é excluído. Não há exclusão financeira em cascata por esses endpoints. A exclusão integral de privacidade continua sendo uma operação separada.

As rotas filtram proprietário antes de consultar/alterar; IDs de terceiros retornam 404. Escritores de novos vínculos e atualizações de cadastro bloqueiam a mesma linha no PostgreSQL. Assim, um vínculo gravado antes do arquivamento é preservado e impede a exclusão; após arquivamento, novos vínculos são recusados. FKs permanecem como proteção complementar. Versão obsoleta evita sobreposição silenciosa entre sessões.

## Migração e verificação

A migração 005 adiciona `archived=false` e `version=0` sem recriar ou apagar contas/cartões. `integration_migrations.py` verifica valores, IDs e vínculos anteriores. `test_lifecycle.py` cobre regras, isolamento, exportação/exclusão e importação de PDF confirmada depois de arquivar. `integration_lifecycle.py` disputa gravações em PostgreSQL real. `browser_lifecycle.cjs` verifica conflito/recarregamento, renomeação, arquivamento/reativação, exclusão, tela mobile e limpeza na expiração da sessão.

As mutações exigem sessão autenticada, origem válida e token CSRF. As cotas de requisições existentes continuam aplicadas; o gerenciamento de cadastros não possui exceção de limite.

FIN-03 continua parcial: metas ainda precisam de ciclo de vida, critérios de exclusão e revisão da edição. FIN-04 deve fechar histórico mínimo de alterações financeiras, retenção e acesso; esta entrega não substitui esse trabalho.
