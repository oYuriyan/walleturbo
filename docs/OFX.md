# Extrato bancário OFX — 0.20

Importa uma conta corrente ou poupança em BRL por arquivo, com prévia sem gravação e confirmação explícita. O primeiro corpus é sintético: não há homologação de um banco/emissor real nem verificação de autenticidade do extrato.

## Uso e formatos

Em **Movimentações → Importar CSV / OFX**, selecione **OFX bancário**, escolha a conta de destino e envie o arquivo. Confira banco/conta mascarada do documento, receitas, despesas e possíveis duplicatas antes de confirmar. Não há inferência de que a conta escolhida corresponde à conta bancária do arquivo. Reenvie sempre no mesmo contexto; trocar a conta local cria outro contexto de identidade e pode duplicar valores.

Suporte declarado: SGML OFXHEADER 100, VERSION 102/103, e XML OFX 2.x com estrutura bancária simples, sem namespaces, atributos no corpo ou extensões. UTF-8 e Windows-1252 declarado no cabeçalho são decodificados pela interface. A API recebe texto Unicode. Limites: 256 KB em UTF-8, 500 lançamentos, profundidade 24 e um único STMTTRNRS/STMTRS/BANKACCTFROM. Respostas de erro do emissor, DTD, declarações de entidades, conteúdo inválido, múltiplas contas e estrutura desconhecida são recusados integralmente, inclusive se uma linha estiver desmarcada.

Cada STMTTRN exige FITID não vazio/único no arquivo, TRNTYPE, DTPOSTED, TRNAMT e MEMO ou NAME. MEMO tem precedência; descrição até 160 caracteres. Identificadores preservam espaços internos e zeros iniciais; somente espaços externos são retirados. Débitos DEBIT/POS/CHECK/FEE/SRVCHG/DIRECTDEBIT exigem valor negativo e viram despesas; CREDIT/DEP/DIRECTDEP/DIV exigem positivo e viram receitas. INT usa o sinal declarado. Zero, mais de duas casas, vírgula decimal, expoente, NaN e sinais contraditórios são recusados; não há arredondamento.

XFER, PAYMENT, REPEATPMT, demais tipos não declarados e comandos CORRECTFITID/CORRECTACTION não são suportados nesta leitura bancária. Não se criam transferências próprias ou pagamentos de faturas a partir do extrato. Créditos/débitos genéricos ainda podem representar movimentos que exigem outra classificação; revise e desmarque o que não deve virar receita/despesa. Para OFX de cartão, use a fatura e o contrato em [OFX_CARTAO.md](OFX_CARTAO.md). Investimento e outras moedas permanecem pendentes.

DTPOSTED conserva a data civil escrita pelo emissor, entre 1900 e 9998. Horário e fuso opcionais são validados, sem conversão para UTC ou para o fuso do servidor. Período DTSTART/DTEND deve ser válido e conter as datas civis das linhas. Outros metadados temporais e saldos auxiliares não comandam operações. LEDGERBAL/AVAILBAL não atualizam referência de saldo nem comprovam conciliação com o banco.

## Identidade e revisão

A identidade combina titular, conta local, BANKID/BRANCHID/ACCTID/ACCTTYPE e FITID. Campos bancários/FITIDs brutos não são retidos: marcas e recibos técnicos existentes guardam hashes/UUIDs derivados. FITIDs diferentes preservam despesas legítimas iguais; um FITID repetido dentro do arquivo torna a origem ambígua e impede a leitura. Ordem, período do arquivo e formato SGML/XML não alteram a identidade quando os identificadores e campos financeiros normalizados coincidem.

O recibo de escopo `ofx` guarda a assinatura original de data civil, centavos com sinal, TRNTYPE e descrição normalizada; a marca aponta para o registro financeiro. Um FITID conhecido com outros dados gera `source_conflicts` na prévia e conflito 409 ao confirmar aquela linha. Não atualiza o lançamento ou a assinatura. Desmarcar a origem divergente permite importar as demais linhas válidas. Não é uma reconciliação automática de retificações bancárias.

Correções do lançamento na aplicação não alteram a assinatura de origem: reenvio do arquivo original preserva a correção. Excluir conserva a marca e impede recriação. Seleção parcial não reserva origens desmarcadas. Vincular a registro existente, desfazer e refazer usam as mesmas revisões de origem/destino e histórico privado do CSV. Só o primeiro vínculo exige data, valor e tipo atuais iguais; descrição pode divergir. Identidade primária, destino excluído/fora do contexto e conta arquivada não são liberados. Após desfazer, nova prévia fornece a revisão para refazer ou criar ocorrência independente; envio antigo recebe 409.

## API e operação

- `POST /api/import/ofx/preview`: `content` e `account_id` obrigatórios. Retorna `entries`, formato, banco, conta mascarada, `source_conflicts`, versões/origens conhecidas e possíveis duplicatas. Não cria recibos, marcas ou registros financeiros.
- `POST /api/import/ofx/confirm`: mesmos campos, `reviewed=true`, `excluded_indices`, `links` e `origin_versions` opcionais, com contratos do CSV. Falha em qualquer linha selecionada reverte o lote inteiro. `created`, `duplicates`, `removed`, `skipped` e `linked` mantêm os significados anteriores.
- `POST /api/import/ofx/unlink`: `content`, `account_id` e `release`, com índice original, destino, revisões e motivo. Exige a assinatura da origem conhecida, preserva o lançamento e grava o desfazimento no histórico.

Conta ativa e titular são verificados nas três rotas. Escritas bloqueiam a conta, reservam recibos e marcas em ordem estável e usam NOWAIT ao vincular destinos, mantendo o protocolo existente contra deadlocks. Exportação/expurgo incluem marcas, recibos e histórico. O arquivo é processado em memória; não é armazenado em banco/disco/Redis pela aplicação. Fechar o diálogo, trocar formato/conta ou perder a sessão invalida a prévia local. Hashes continuam sendo dados sujeitos à proteção e expurgo; não constituem anonimização universal.

Sem migração, serviço ou dependência nova. Atualize API/interface juntas para o novo formato. Ao retornar à 0.19, não haverá leitura OFX, mas os lançamentos e marcas continuam preservados; não apague volumes para atualizar.

## Corpus e aceite

`tests/fixtures/ofx/bank-102.ofx` e `bank-220.ofx` descrevem as mesmas três origens em ordens diferentes. `expected.json` fixa antes da homologação: duas despesas de 1.234 centavos com IDs distintos e receita de 250.000, datas civis e descrições esperadas. Aceite: 100% dos campos e das três origens recuperados por arquivo; reenvio entre formatos cria zero novos registros; entradas inválidas dos testes são recusadas sem escrita parcial. Não mede cobertura de layouts reais.

`test_ofx.py` cobre corpus, recusas, identidade, seleção, correção/exclusão, vínculo, assinatura, privacidade e rollback. `integration_ofx.py` verifica PostgreSQL/Redis, arquivos concorrentes/reordenados, exclusão/reenvio e NOWAIT. `browser_ofx.cjs` cobre Windows-1252, troca de conta, seleção, vínculo/desfazimento, leitura entre formatos e bloqueio da origem divergente no mobile. Resultados finais e commit homologado são registrados no PR da entrega.
