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

## Prévia de possíveis duplicatas CSV — 0.15

As prévias de CSV direto e de fatura devolvem possible_duplicates. Cada sinal contém source_index (índice zero na lista de lançamentos), até cinco matches com ID, data, descrição, valor e tipo, e more quando existem outros candidatos. A consulta procura igualdade de data civil, centavos e tipo, mesmo com descrições diferentes. Restringe titular e conta exata (inclusive sem conta) ou fatura exata; não pesquisa outras contas, cartões ou meses de fatura. Não compara linhas entre si dentro do arquivo. A consulta usa ranking SQL com seis resultados por grupo para detectar truncamento, sem carregar todo o histórico. O CSV continua limitado a 500 linhas. Índices e volume-alvo amplos seguem em REL-04/08.

Sinais são indícios, não identidade: compras legítimas podem coincidir. A interface mostra os candidatos como texto e exige marcar a conferência antes de habilitar Importar. Para excluir linhas, ajuste o arquivo e selecione-o novamente. Trocar a conta refaz a prévia e descarta a conferência anterior. Encerrar sessão limpa arquivo e candidatos. A prévia não grava, não vincula origens e não modifica a deduplicação da confirmação. O aviso é consultivo: clientes da API podem confirmar sem ele; alterações concorrentes após a prévia não são cobertas por este sinal. Não se deve interpretar ausência de sinal como garantia de ausência de duplicatas.

Esta primeira etapa de IMP-02/03 não resolve vínculo persistente entre fontes, correspondências com datas/valores distintos, escolha individual importar/vincular/ignorar, PDF/OFX ou legítimas ocorrências idênticas em documentos separados. Esses itens continuam pendentes. A API permanece compatível com clientes existentes. Não há migração de schema. Testes incluem isolamento, limite de candidatos, ausência de gravação, consulta PostgreSQL real e conferência no navegador mobile; evidência final será registrada no PR.

## Seleção de lançamentos CSV — 0.16

Cada lançamento da prévia tem uma seleção independente, inicialmente marcada. O total selecionado é anunciado; zero selecionados impede confirmar. A conferência de possíveis duplicatas permanece obrigatória na interface. Trocar arquivo/conta refaz a prévia e a seleção; encerrar sessão descarta ambas. O retorno informa quantos não foram selecionados.

POST confirm direto ou de fatura aceita excluded_indices opcional, lista de índices zero na lista original de lançamentos. Inteiros estritos, únicos, entre 0 e 499 e dentro do arquivo; rejeita seleção vazia de importáveis, duplicação de índices e tipos/coerções indevidos com 422 sem gravar. O padrão vazio preserva clientes existentes. As chaves de origem e números de ocorrência são calculados sobre o arquivo integral antes da seleção; ignorar a primeira de duas linhas iguais não transforma a segunda na primeira. Somente selecionadas reservam marcas e são importadas atomicamente.

A resposta mantém created, duplicates e removed; skipped aparece quando há linhas não selecionadas. duplicates conta apenas as selecionadas já conhecidas, não as excluídas da seleção. Uma linha não selecionada não é marcada como removida nem vira vínculo de duplicidade: selecionar depois permite importá-la, e repetir a mesma seleção não duplica as aceitas. É uma decisão para este envio, sem retenção persistente de decisão por documento. Vincular origem divergente a registro existente e resolver identidade entre CSV/PDF/manual continuam em IMP-03. Não há migração de schema. Evidências de ocorrências iguais, reenvio, rejeição atômica, PostgreSQL e seleção no navegador ficam no PR da entrega.

## Vínculo explícito de origem CSV — 0.17

Na prévia, cada sinal oferece um destino opcional. Selecionar um registro e confirmar associa a origem CSV ao registro existente, sem criar lançamento, alterar valores ou converter parcelas. O padrão continua criar/reconhecer pela chave de origem. A conferência explícita e a seleção por linha continuam obrigatórias na interface.

POST confirm direto/de fatura aceita links opcional: source_index inteiro estrito zero na lista original, resource_id UUID e expected_version inteiro positivo. Cada origem/destino só pode aparecer uma vez no envio; não aceita vínculo para linha não selecionada ou fora do arquivo. O primeiro vínculo exige registro atual do mesmo titular e conta exata (inclusive sem conta) ou mesma fatura, com data, valor e tipo iguais. Descrições podem diferir. Versão obsoleta ou incompatibilidade recebem 409; seleção estrutural inválida recebe 422. Não vincula estorno a despesa nem parcela de outra fatura.

Marcas de origem são reservadas em ordem estável. Alvos de novos vínculos são bloqueados em ordem de ID com NOWAIT no PostgreSQL; disputa devolve 409 e reverte o lote, sem aguardar em ordem inversa aos escritores existentes. Cartão/fatura mantêm seus locks. Histórico import_link e marca são gravados na mesma transação; falha reverte também linhas criadas no lote. Nenhuma mudança de schema é necessária. Não execute escritores SQL externos ignorando esse protocolo.

Origem já conhecida não pode ser reassociada a outro ID. Reenvio do mesmo vínculo reconhece a marca, mesmo se o destino tiver sido corrigido depois; a versão serve à primeira associação. Reimportar sem links também reconhece a origem. Após exclusão do destino, a marca é conservada e passa a removed quando a reimportação constata a ausência; não recria o registro. Não há FK polimórfica de marca para destino nem atualização imediata de todos os aliases na exclusão. A resposta linked conta associações reconhecidas/aceitas no envio e é subconjunto das linhas consideradas conhecidas em duplicates, não novos lançamentos.

Histórico privado, exportação e expurgo abrangem os vínculos. O evento contém contexto, destino e índice da origem, sem conteúdo bruto do arquivo ou chave técnica. Não é prova da identidade de documento bancário. Na 0.17 não havia desfazimento individual; o fluxo da 0.18 abaixo permite revisar essa decisão. Origem diferente e compra legítima coincidente devem continuar como operações independentes.

Esta entrega cobre associação explícita CSV→registro manual/importado existente no contexto compatível. PDF, identificadores de emissor/OFX, datas/valores divergentes, remapeamento/desfazimento versionado de vínculos, corpus real e resolução de ocorrências idênticas que já colidam na chave legada permanecem em IMP-02/03. Sem comparação automática conclusiva. Evidências de isolamento, reenvio, exclusão, rollback, concorrência/NOWAIT PostgreSQL e navegador serão registradas no PR.

## Desfazer e refazer vínculos CSV — 0.18

A prévia informa `origin_versions` (na ordem original das linhas) e `known_origins`, com destino atual, revisão, disponibilidade e indicação `releasable`. Consultar a prévia continua sem gravar. Associações a registros existentes oferecem **Desfazer vínculo**, motivo obrigatório e confirmação. O lançamento financeiro é preservado. Depois do sucesso a interface solicita uma nova prévia: escolha outro destino compatível para remapear ou confirme uma importação independente, que poderá criar outro lançamento. O remapeamento usa duas transações explícitas; se a segunda falhar, a origem permanece liberada.

`POST /api/import/unlink` aceita `content`, `account_id` opcional e `release`. Para cartão use `POST /api/statements/{id}/import/unlink`, sem `account_id`. `release` exige `source_index`, `resource_id`, `expected_version` do destino, `expected_origin_version` e `reason` (3–240 caracteres após remoção de espaços externos). Somente associações em que a chave primária do destino difere da origem selecionada podem ser desfeitas. Não libera origem primária de importação nem marca removida, destino excluído/fora do contexto, conta/cartão arquivado ou fatura conferida. Correções de data/valor/descrição são permitidas quando a prévia já contém a versão atual; mudar o contexto requer resolução futura própria.

Marcas são bloqueadas antes do destino, com NOWAIT e ordem já existente. Divergências retornam 409 e estrutura inválida retorna 422. Desfazer incrementa a revisão, limpa somente o destino da marca e grava evento privado `import_link`/`deleted` com motivo na mesma transação. Repetir o desfazimento recebe 409; não gera evento adicional. Exportação e expurgo incluem revisões e histórico. Falha no histórico reverte a liberação.

`links` passa a aceitar `expected_origin_version` (padrão 0 para primeira associação). A revisão avança em cada associação/liberação. Reenvio aceito do mesmo vínculo é reconhecido, mas um envio anterior ao desfazimento não restaura a decisão, mesmo após refazê-la para o mesmo destino. Ao confirmar uma ocorrência independente liberada, envie `origin_versions` da nova prévia. Clientes antigos recebem 409 para origens liberadas e devem atualizar a prévia; importações comuns mantêm o contrato anterior. PDF não libera nem recria uma origem desfeita: resolve-se primeiro pela revisão CSV.

Migração 013 inicia marcas associadas na revisão 1 e marcas livres na 0, sem reconstruir decisões históricas ou alterar valores. Aplicação, clientes e schema devem ser atualizados juntos, com escritores antigos interrompidos; readiness exige a nova coluna. Não remove volumes nem marcas. PDF, OFX, identidade de emissor e colisões legítimas da identidade legada continuam pendentes. Evidências de testes e homologação são registradas no PR da entrega.

## Extensão ao PDF — 0.19

O PDF textual passa a consultar destinos compatíveis com os campos revisados e a reutilizar associação/desfazimento, revisões de origem/destino, histórico privado e locks do CSV. Índices e chaves continuam sendo os da linha original do PDF, inclusive em seleção parcial ou reordenada. Após desfazer, um novo upload captura a revisão atual antes de recriar ou remapear; uma consulta ao token antigo não permite recriação. Aliases reconhecidos preservam correções do destino, enquanto a identidade primária mantém a comparação estrita do PDF. Sem alteração de schema. Contrato, passos da interface e limites em [PDF.md](PDF.md).

## Identidade OFX — 0.20

Extrato bancário OFX usa FITID e contexto bancário/conta local para distinguir origens, inclusive compras idênticas legítimas. Reutiliza marcas do escopo transaction e recibos do novo escopo ofx para assinatura original imutável, sem nova tabela. Edição/exclusão de lançamentos continua protegida pelo protocolo existente; arquivo original não sobrescreve correções nem recria exclusões. Arquivo alterado para uma origem conhecida recebe conflito atômico. Seleção, vínculo, desfazimento, histórico, exportação e expurgo mantêm seus contratos. Tipos, limites e corpus em [OFX.md](OFX.md); identidade universal entre bancos e colisões legadas CSV/PDF continuam pendentes.
