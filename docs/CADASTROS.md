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

## Metas — incremento 0.7

Metas existentes recebem `archived=false` e `version=0` pela migração 006, preservando valores/prazos. Criação continua recebendo `GoalInput`; edição `PUT /api/goals/{id}` exige os mesmos campos mais `archived` e `expected_version`. O contrato anterior de edição sem versão é recusado com 422. Alteração efetiva incrementa a versão; envio obsoleto recebe 409. A interface oferece **Recarregar meta** para descartar o formulário e revisar a versão atual.

Renomear e corrigir objetivo, reserva ou prazo preserva o ID. A reserva não pode ultrapassar o objetivo. Arquivar é reversível, preserva valores e remove a meta da simulação e da prévia da página inicial. O cadastro e a exportação continuam incluindo arquivadas. Reativar inclui novamente na simulação com os valores atuais. A simulação de meses passados também usa o estado atual, conforme PLANEJAMENTO.md.

`DELETE /api/goals/{id}?expected_version=N` exige versão atual, meta arquivada e `saved_cents=0`. Reserva positiva impede exclusão (409); zerar exige correção explícita. O valor informado não representa depósito, saque ou vínculo bancário. Quando aportes e vínculos forem introduzidos em PLA-02, a exclusão deverá verificar o histórico desses vínculos antes de ser habilitada. Hoje não existem tais entidades.

Edição/exclusão bloqueiam a mesma linha no PostgreSQL, impedindo que uma exclusão desatualizada apague uma correção concorrente de reserva. IDs de terceiros retornam 404; exportação/exclusão de privacidade incluem ambos os estados. Após expiração da sessão, o formulário limpa valores/IDs e fecha.

FIN-03 tem seu escopo atual implementado: contas, cartões, metas e política de lançamentos sem conta. FIN-04 ainda deve fechar histórico mínimo de alterações financeiras, retenção e acesso. Não há registro de versões anteriores de metas ou nomes neste incremento; a versão previne sobrescrita, mas não equivale a uma trilha de auditoria.
