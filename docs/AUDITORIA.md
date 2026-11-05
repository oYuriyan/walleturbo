# Histórico financeiro e revisão técnica — versão 0.11

## Finalidade e escopo

O histórico permite ao titular consultar o que mudou e recuperar os valores anteriores para conferência. É parte dos dados financeiros privados, separado dos logs operacionais. Não constitui extrato bancário, execução de pagamentos, log de autenticação ou certificação de segurança/LGPD.

Desde a migração 007, as criações, alterações e exclusões ORM de contas, cartões, metas, lançamentos, compras/estornos, faturas, pagamentos, referências de saldo e transferências geram eventos na mesma transação. Um evento guarda ID, proprietário, tipo/ID do registro, ação, instante UTC e estados anterior/posterior. IDs e datas nos estados permitem interpretar vínculos após a remoção de um cadastro. `owner`, hashes de conteúdo e chaves internas de importação não se repetem nos estados. Descrições, motivos e valores necessários à conferência continuam sendo dados pessoais e exigem proteção.

Não há reconstrução de eventos anteriores à migração. O primeiro evento de um registro legado pode ser sua alteração/exclusão. Configuração de cenário mensal e orçamentos ainda não são auditados. A gravação acontece por eventos de mapper SQLAlchemy: SQL externo e operações bulk não passam por essa instrumentação. A exclusão integral de privacidade usa bulk intencionalmente e remove também o histórico. Novos escritores devem preservar esse contrato e possuir testes; jobs/SQL externos exigem instrumentação própria ou controles no banco antes da introdução.

## Atomicidade e concorrência

O evento é inserido pela mesma conexão, sem fila ou segundo commit. Se a operação falhar, ambos são revertidos. Se o histórico falhar, a escrita financeira falha também. Reenvios idempotentes que não alteram registros não criam eventos adicionais; gravações sem mudança efetiva não produzem alterações fictícias.

Correções de lançamento bloqueiam sua linha antes da edição. Revisão/exclusão de compras recarregam os valores após o lock da fatura, para registrar o estado anterior atualizado. Os timestamps representam o instante da gravação do evento na transação, não necessariamente a ordem global dos commits. As versões monotônicas de lançamentos/pagamentos e a revisão das compras/categorias protegem alterações obsoletas na 0.11, além de cadastros e referências de saldo. Conferência/reabertura de fatura e configuração de cenários/orçamentos ainda exigem revisão de contratos e conflitos (FIN-04/05).

## Consulta e privacidade

`GET /api/history` exige sessão e aplica proprietário e cotas existentes. Filtros opcionais: `entity` e `entity_id`. `limit` aceita 1–100 (padrão 30); `before_id` pagina por instante/ID, com cursor pertencente ao mesmo usuário. Cursor de outro usuário retorna 404. Tipos aceitos: `account`, `card`, `goal`, `transaction`, `card_charge`, `statement`, `statement_payment`, `opening_balance`, `transfer`.

Em **Contas e cartões → Histórico de alterações → Consultar histórico**, abra um registro para ver os valores; a consulta inclui todos os meses e pode carregar páginas anteriores. A visualização apresenta campos de uso financeiro; o JSON exportado preserva também identificadores de vínculo. Use nova consulta após registrar mudanças. A interface renderiza conteúdo como texto e limpa a consulta ao encerrar a sessão.

A API não oferece edição/exclusão individual do histórico. Eventos persistem enquanto os dados financeiros forem mantidos, inclusive após excluir uma operação isolada, e integram `financial_history` na exportação. **Apagar dados financeiros** remove eventos e registros do titular na mesma transação. Essa política é de desenvolvimento/homologação local; retenção de produção e backups requerem a definição operacional/jurídica de LGPD-02. O histórico não é imutável contra administradores do banco: papéis mínimos, RLS, proteção de backups e controles adicionais seguem em REL-03/PRO-03.

O engine oculta parâmetros SQL nas mensagens de exceção. Isso reduz exposição acidental de dados em diagnóstico; a revisão ampla de logs estruturados e eventos de segurança permanece pendente.

## Revisão técnica e pendências preservadas

| Achado / prioridade | Tratamento e estado |
| --- | --- |
| Perda do estado anterior em correções/exclusões — alta | Histórico transacional implementado para nove tipos de entidade na 0.8; homologado no CI 41888034624 |
| Atualização desatualizada de cadastros/metas — alta | Versão + lock implementados e homologados em 0.6/0.7 |
| Concorrência em correções financeiras — alta | Versões de lançamentos/pagamentos e revisão de compras/categorias implementadas; conferência/reabertura de faturas e cenários/orçamentos permanecem em FIN-04/05 |
| Reenvio após exclusão de pagamentos/compras — alta | Recibos para compras manuais/pagamentos na 0.9 e lançamentos na 0.11; marcas de origem conhecidas preservadas após exclusão na 0.11. Identidade entre documentos divergentes continua pendente |
| Alterar valor/data/parcelamento de uma compra existente — alta | Compra manual na 0.9, pagamento na 0.10 e linha importada no mesmo contexto na 0.11, com histórico e conflitos. Limites de cada correção estão nos respectivos contratos |
| Histórico de cenário/orçamentos e escrita por SQL/jobs — média | Fora da cobertura deste incremento; tratar antes de introduzir novos escritores |
| Proteção contra administrador do banco e acesso cruzado SQL — alta | Permissões mínimas/RLS/restauração continuam em REL-02/03; histórico não resolve esses controles |
| Jornada completa e verificações de interface existentes fora do CI — média | Cartões/demonstração passam ao CI na 0.11, além do HTML no histórico. Jornada única, segundo motor e XSS persistido abrangente continuam pendentes |
| Resposta atrasada após encerrar sessão — alta | Guardas de sessão em dashboard e cadastros adicionadas; navegador segura uma resposta anterior e verifica ausência de restauração após 401 |
| Volume/armazenamento — média | Consulta de histórico paginada; exportação ainda carrega dados integralmente e precisa REL-04/08 |

## Evidências previstas

`test_audit.py`: estados anteriores/posteriores, exclusão, defaults de metadados, ausência de duplicação, paginação, isolamento, exportação/expurgo e rollback com falha financeira ou do histórico. `integration_lifecycle.py`: JSON e rollback no PostgreSQL real. `integration_migrations.py`: preservação do legado sem inventar eventos. `browser_goals.cjs`: consulta mobile, valor anterior/posterior, texto HTML sem criar elementos e limpeza após expiração. O resultado aprovado deve constar em HOMOLOGACAO.md; testes adicionados não significam homologação antes de sua execução.

**Evidência aprovada:** código `5b7b1b6`, [CI 41888034624](https://github.com/oYuriyan/walleturbo/actions/runs/41888034624). Confirmados 109 testes em container, integração PostgreSQL/Redis, migração 007, rollback/JSON privado e navegador com histórico, HTML literal e resposta atrasada após encerrar sessão. Capturas mobile inspecionadas visualmente. Isso valida os cenários declarados, com as limitações da tabela preservadas.

**Incremento 0.9 aprovado:** código `961b0e0`, [CI 41892139036](https://github.com/oYuriyan/walleturbo/actions/runs/41892139036), 116 testes. Versão monotônica das parcelas impede aceitar revisão antiga mesmo após mudança e retorno aos mesmos valores; revisão de categoria recarrega a fatura atual sob lock. Recibos, parcelas e eventos são revertidos juntos em falha parcial. O upgrade preservou valores/IDs e reservou UUIDs ativos e de exclusões auditadas. Limites restantes em CORRECOES.md e ROADMAP.md.

## Revisão incremental 0.10

Implementadas correção de pagamentos com versão monotônica, remoção com versão obrigatória e revalidação dos demais pagamentos sob lock da fatura. Conta/data/valor/motivo anteriores e posteriores permanecem no histórico; a prévia respeita referência/data e não inventa saldo para contas desconhecidas. Recibos payment_edit preservam reenvios sem reaplicar valores antigos. O histórico visual passou a apresentar vínculos às contas por seus nomes atuais. Homologado no CI 42033442245, código 39c0a67, com 123 testes em container e roteiro mobile. Versão de lançamentos diretos, importados, proteção contra SQL externo, RLS e limites de volume continuam pendentes.

## Revisão incremental 0.11

Implementados controles de versão e UUID para lançamentos, revisão de categoria com versão, exclusão de operação com revisão atual e marcas de origem persistentes. CSV/PDF reconhecidos não recriam linhas excluídas nem desfazem correções. Valores divergentes de confirmação de PDF são recusados. Falhas parciais revertem marcas e finanças. A identidade segue contexto/campos canônicos, sem promessa de reconhecer documentos divergentes; exclusões anteriores à migração não são inferidas sem chave. Homologado no CI 42045260683, código 8124548, com 133 testes em container e concorrência/navegador reais. RLS, SQL externo, restauração, retenção de produção e quotas de armazenamento permanecem pendentes.
