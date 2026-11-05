# Lançamentos versionados e origem de importação — 0.11

## Lançamentos diretos

A interface identifica cada criação e correção com um UUID. Reenviar uma criação aceita retorna o lançamento atual, sem duplicá-lo. Reenviar uma correção aceita não reaplica valores antigos. O UUID original continua no registro; correções usam recibos separados. Excluir preserva o recibo original como cancelado, impedindo recriação pelo mesmo envio. Uma nova despesa/receita exige novo UUID.

**Revisar** agora exige motivo e versão atual. **Recarregar lançamento** descarta o formulário e busca os dados atuais após conflito. A exclusão também exige versão atual, evitando apagar uma correção feita em outra sessão. A versão é monotônica: mudar e depois retornar aos mesmos valores não torna uma edição antiga válida. Antes/depois e motivo permanecem no histórico privado.

Contas arquivadas podem ser mantidas no lançamento existente; mudar para outra conta exige destino ativo. Lançamentos sem conta continuam permitidos e fora dos saldos por conta. Datas de lançamentos/CSV diretos são limitadas a 1900–9998, coerentes com a consulta mensal. Não há consulta ou movimentação bancária.

### Contrato de API

- `POST /api/transactions`: campos de Entry e `request_id` UUID. A interface sempre envia o identificador; a API ainda aceita ausência no modo legado, que não tem garantia de reenvio idempotente.
- `GET /api/transactions/{id}`: estado atual com versão, UUID original e indicação de importação.
- `PUT /api/transactions/{id}`: campos de Entry, `request_id` UUID de correção, `expected_version` e `reason` obrigatórios.
- `DELETE /api/transactions/{id}?expected_version=N`: remove somente a versão revisada.

**Mudanças na 0.11:** edição sem UUID/versão/motivo e remoção sem versão recebem 422. Versão/reuso de UUID incompatíveis recebem 409. IDs de terceiros recebem 404. Recibo aceito retorna estado atual; após exclusão, correção não recria registro. A ausência de cadastros necessários pode causar 404 antes do recibo. Novos clientes devem usar UUID também na criação; não inferir duplicação de lançamentos manuais apenas por seus valores, pois despesas iguais podem ser legítimas.

## Origem de importação preservada

`import_marks` registra, por titular e contexto, a identidade da linha importada e o ID do registro criado. A marca permanece após correção ou exclusão isolada. Reimportar uma origem conhecida não sobrescreve a correção. Reimportar uma origem excluída não a recria. Até a ausência inesperada do registro associado é tratada como impedimento de recriação.

A identidade usa data, descrição com casefold, valor, tipo e número da ocorrência. Linhas iguais legítimas no mesmo arquivo continuam distintas; excluir uma ocorrência não libera sua posição. Acrescentar uma terceira ocorrência permite importar somente a nova, mantendo as posições conhecidas/excluídas. Lotes concorrentes adquirem marcas em ordem estável para evitar deadlocks.

No cartão, o contexto é a fatura. CSV/PDF compartilham identidade quando os campos canônicos reconhecidos coincidem; o PDF mantém a chave da linha original mesmo quando a prévia foi corrigida. Reenvio de PDF com valores diferentes dos já gravados recebe 409, exigindo correção do registro existente, sem substituir valores silenciosamente. CSV preserva a linha existente. Na movimentação direta, a seleção de conta participa da identidade. **Reenvie usando a mesma seleção de conta da importação original**, mesmo após corrigir o vínculo do lançamento.

Diferenças de texto/campos, outro contexto/conta ou formatos com identidade bancária não homologada podem gerar identidades diferentes. Não há garantia universal de reconhecer a mesma compra em documentos distintos. Normalização ampliada, identificadores do emissor/OFX e homologação por fonte continuam em IMP-02/03. Arquivos distintos com compras realmente novas mas idênticas ainda exigem conferência; cadastro manual identificado é a alternativa explícita.

A resposta mantém `created` e `duplicates` (linhas conhecidas ignoradas) e acrescenta `removed` quando houver origens excluídas. `removed` é subconjunto das ignoradas, não uma exclusão nova. A interface informa quantas não foram recriadas. Originais brutos não são armazenados no banco de marcas.

## Correção de importados e cartão

**Corrigir importado** ajusta data, descrição, valor, tipo, categoria/revisão e motivo de uma linha de fatura aberta. Mantém cartão, fatura original e uma única parcela. A interface apresenta prévia; o servidor recusa mudança de contexto ou transformação em parcelamento. Chave de origem, ID e marca permanecem ligados ao registro. Use uma nova operação explícita para outro contexto.

Revisão de categoria passa a exigir `expected_version`. O botão **Recarregar categoria** busca o estado atual antes de nova revisão. Exclusão de compra/estorno exige `expected_revision`, obtida em `GET /api/card-operations/{id}`; a interface consulta e mostra descrição/valor/parcelas atuais antes de pedir confirmação e envia a revisão. Mudança durante a confirmação recebe 409. Clientes antigos dessas rotas precisam atualizar. Faturas conferidas continuam bloqueando alterações/exclusões; cartão arquivado exige reativação para correção integral, conforme CORRECOES.md.

## Migração, atomicidade e privacidade

A migração 010 adiciona versão, UUID nullable e motivo aos lançamentos e cria as marcas a partir dos `import_key` existentes. Preserva valores, contas, datas e IDs, sem criar eventos financeiros fictícios. **Exclusões anteriores à migração não são reconstruídas**, porque o histórico anterior não guardava a chave de origem/ocorrência; não é seguro inferi-la. A proteção permanente começa com as origens existentes no upgrade e com as importações seguintes.

Importações são transacionais: falha em linha/histórico reverte registros e marcas. Correções/exclusões atualizam recibos/marcas com o histórico na mesma transação. SQL externo e escritores antigos sem esse protocolo não são suportados; interrompa escritores na atualização de schema/API. PostgreSQL real verifica concorrência; testes em SQLite não demonstram locks.

Marcas e recibos integram a exportação financeira, com referências aos registros e estado de exclusão; hashes técnicos não são expostos. A exclusão integral de dados financeiros remove marcas/recibos/histórico. Reimportar após esse expurgo é um novo conjunto de dados, não restauração de registros antigos. Retenção de produção/backups, quotas de armazenamento, privilégios mínimos e RLS continuam nas fases operacionais/LGPD. Não há envio a agentes de IA, bancos ou afiliados.

Ao perder a sessão, formulários, IDs e arquivos/prévias de CSV/PDF são limpos; respostas antigas são descartadas pelos controles de geração existentes. Dados financeiros não são persistidos no armazenamento local do navegador.

## Evidências e trabalho restante

`test_entry_import_integrity.py` verifica UUIDs, versões/retorno ao estado anterior, exclusão obsoleta, marcas, ocorrências, CSV/PDF, correção importada, isolamento, expurgo e rollback. `integration_entry_import_integrity.py` disputa criação, edição/exclusão, lotes em ordem inversa e exclusão versus reimportação em PostgreSQL. O upgrade preserva origens ativas legadas. Navegador verifica lançamento/recarga/UUID, aviso de origem excluída, correção importada e arquivos/prévias com sessão encerrada. Roteiros anteriores de cartões e demonstração/XSS passam a fazer parte do CI.

Ainda pendentes: revisão ampla de contratos de competência/vencimento/crédito e atualizações de faturas/cenários, identidade de documentos/fontes divergentes, RLS, backups/restauração, cotas de armazenamento, proteção de produção e demais fases do roadmap. A entrega foi homologada nos cenários declarados pelo CI registrado abaixo; isso não representa liberação pública nem conclusão integral de FIN-04/05 ou REL-07.

**Homologação técnica aprovada:** [CI 42045260683](https://github.com/oYuriyan/walleturbo/actions/runs/42045260683), código `8124548`, com 133 testes em container, concorrência em PostgreSQL/Redis, upgrade de dados e navegador. Capturas mobile de reimportação, correção importada e cartão escuro foram inspecionadas. Contratos incompatíveis com clientes antigos e limites de identidade/legado permanecem conforme descritos acima.
