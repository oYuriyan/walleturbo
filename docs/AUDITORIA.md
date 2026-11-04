# Histórico financeiro e revisão técnica — versão 0.8

## Finalidade e escopo

O histórico permite ao titular consultar o que mudou e recuperar os valores anteriores para conferência. É parte dos dados financeiros privados, separado dos logs operacionais. Não constitui extrato bancário, execução de pagamentos, log de autenticação ou certificação de segurança/LGPD.

Desde a migração 007, as criações, alterações e exclusões ORM de contas, cartões, metas, lançamentos, compras/estornos, faturas, pagamentos, referências de saldo e transferências geram eventos na mesma transação. Um evento guarda ID, proprietário, tipo/ID do registro, ação, instante UTC e estados anterior/posterior. IDs e datas nos estados permitem interpretar vínculos após a remoção de um cadastro. `owner`, hashes de conteúdo e chaves internas de importação não se repetem nos estados. Descrições, motivos e valores necessários à conferência continuam sendo dados pessoais e exigem proteção.

Não há reconstrução de eventos anteriores à migração. O primeiro evento de um registro legado pode ser sua alteração/exclusão. Configuração de cenário mensal e orçamentos ainda não são auditados. A gravação acontece por eventos de mapper SQLAlchemy: SQL externo e operações bulk não passam por essa instrumentação. A exclusão integral de privacidade usa bulk intencionalmente e remove também o histórico. Novos escritores devem preservar esse contrato e possuir testes; jobs/SQL externos exigem instrumentação própria ou controles no banco antes da introdução.

## Atomicidade e concorrência

O evento é inserido pela mesma conexão, sem fila ou segundo commit. Se a operação falhar, ambos são revertidos. Se o histórico falhar, a escrita financeira falha também. Reenvios idempotentes que não alteram registros não criam eventos adicionais; gravações sem mudança efetiva não produzem alterações fictícias.

Correções de lançamento bloqueiam sua linha antes da edição. Revisão/exclusão de compras recarregam os valores após o lock da fatura, para registrar o estado anterior atualizado. Os timestamps representam o instante da gravação do evento na transação, não necessariamente a ordem global dos commits. Ainda são necessários controle de versão e revisão de conflitos mais amplos para todas as operações financeiras (FIN-04), além dos controles já presentes em cadastros e referências de saldo.

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
| Concorrência em correções financeiras — alta | Lock de lançamento e recarga após lock de fatura adicionados; versão e revisão de conflitos amplas ainda pendentes em FIN-04 |
| Reenvio após exclusão de pagamentos/compras — alta | Histórico preserva evidência, mas não substitui tombstones/chaves de idempotência; FIN-05 pendente |
| Alterar valor/data/parcelamento de uma compra existente — alta | Política de meses conferidos e correção atômica ainda pendente em FIN-04; não habilitar edição parcial silenciosa |
| Histórico de cenário/orçamentos e escrita por SQL/jobs — média | Fora da cobertura deste incremento; tratar antes de introduzir novos escritores |
| Proteção contra administrador do banco e acesso cruzado SQL — alta | Permissões mínimas/RLS/restauração continuam em REL-02/03; histórico não resolve esses controles |
| Jornada completa e verificações de interface existentes fora do CI — média | Roteiros de cartões/demonstração e teste XSS persistido abrangente continuam em REL-07; a consulta de histórico recebe regressão HTML neste incremento |
| Resposta atrasada após encerrar sessão — alta | Guardas de sessão em dashboard e cadastros adicionadas; navegador segura uma resposta anterior e verifica ausência de restauração após 401 |
| Volume/armazenamento — média | Consulta de histórico paginada; exportação ainda carrega dados integralmente e precisa REL-04/08 |

## Evidências previstas

`test_audit.py`: estados anteriores/posteriores, exclusão, defaults de metadados, ausência de duplicação, paginação, isolamento, exportação/expurgo e rollback com falha financeira ou do histórico. `integration_lifecycle.py`: JSON e rollback no PostgreSQL real. `integration_migrations.py`: preservação do legado sem inventar eventos. `browser_goals.cjs`: consulta mobile, valor anterior/posterior, texto HTML sem criar elementos e limpeza após expiração. O resultado aprovado deve constar em HOMOLOGACAO.md; testes adicionados não significam homologação antes de sua execução.

**Evidência aprovada:** código `5b7b1b6`, [CI 41888034624](https://github.com/oYuriyan/walleturbo/actions/runs/41888034624). Confirmados 109 testes em container, integração PostgreSQL/Redis, migração 007, rollback/JSON privado e navegador com histórico, HTML literal e resposta atrasada após encerrar sessão. Capturas mobile inspecionadas visualmente. Isso valida os cenários declarados, com as limitações da tabela preservadas.
