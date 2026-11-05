# Leitura assistida de PDF — 0.3

O leitor transforma linhas reconhecidas em candidatos editáveis. Nenhum candidato vira despesa sem seleção e confirmação de revisão. Após importar, o usuário deve conferir o total da fatura com o emissor. A leitura não certifica autenticidade nem completude do documento.

## Formato suportado

PDF original com texto selecionável. Data completa, descrição e valor em reais devem estar na mesma linha:

```text
03/11/2026 Mercado 1.234,56
2026-11-04 Estorno loja -23,45
```

O valor negativo vira estorno positivo com tipo `refund`. Datas sem ano, colunas separadas, layouts específicos de emissores e valores em outras moedas não são inferidos. Cada candidato corresponde somente à fatura selecionada; parcelas futuras não são expandidas. A validação atual usa documentos sintéticos: não há homologação de um emissor bancário específico.

## Uso

1. Abra uma fatura em revisão em **Contas e cartões** e escolha **Ler PDF**.
2. Envie um PDF de até 2 MB/30 páginas. Arquivos escaneados exigem OCR, ainda indisponível; protegidos por senha, formulários, ações, links ativos e anexos são recusados.
3. Observe páginas/linhas de origem, linhas não reconhecidas e eventuais páginas sem texto. Cabeçalhos/resumos também entram na contagem de linhas ignoradas.
4. Corrija datas, descrições, valores, categorias e tipo de operação; desmarque linhas indevidas.
5. Marque a confirmação de revisão e importe. Confira o total da fatura com o emissor antes de fechá-la.

A prévia expira em dez minutos. É vinculada à sessão, ao proprietário e à fatura; nova sessão exige nova leitura. Reenvios iguais são deduplicados. Compras idênticas no mesmo documento mantêm sua ocorrência mesmo em seleções parciais. Uma linha importada que seja reenviada com valores diferentes causa conflito, sem gravação parcial; corrija/exclua o lançamento existente antes de reimportar.

## Isolamento e retenção

O serviço `parser` roda sem rede (`network_mode: none`), sem credenciais de banco/Redis, usuário sem privilégios, filesystem somente leitura e capabilities removidas. Recebe documentos exclusivamente por socket Unix compartilhado com a API. Não há porta HTTP pública do leitor.

Cada leitura usa processo separado, com limite de CPU de quatro segundos, memória virtual de 192 MB e prazo de oito segundos. O container limita memória a 256 MB, CPU a 0,5 e processos a 16. O protocolo limita bytes de entrada/saída; o texto extraído é limitado a 100 mil caracteres e 500 candidatos. A API aplica autenticação, proprietário, CSRF, cotas de importação e tempo/tamanho do upload antes de solicitar extração.

O original e o texto completo não são gravados em disco, banco ou logs. O Redis mantém por até dez minutos metadados da prévia: identificador pseudônimo, fatura, vínculo da sessão, contagem e hashes de linhas para deduplicação. Esses metadados continuam sendo dados sujeitos à política de privacidade. Somente os lançamentos revisados são persistidos. Sequências semelhantes a número completo de cartão são ocultadas nas descrições extraídas; isso não substitui revisão de dados pessoais.

## Limites operacionais

Não há OCR, antivírus, garantia contra qualquer PDF malicioso nem suporte universal a faturas. O isolamento limita o impacto; scanners, atualização de dependências, corpus de emissores e revisão especializada continuam necessários antes da produção. O leitor é serial e tem fila curta; quando ocupado/indisponível retorna erro recuperável, sem persistir despesas. Para escala, substituir o socket local por fila e workers com identidade/rede restritas, preservando limites e isolamento.

Os testes unitários usam apenas PDFs sintéticos. `tests/integration_pdf.py` exercita o leitor real isolado e a API. `tests/browser_pdf.cjs` valida prévia, edição e importação no navegador; a sessão sintética é removida com seus dados ao final. O CI salva capturas sem dados reais.

## Origem após correção/exclusão — 0.11

A marca da linha original permanece ligada ao registro, mesmo quando a prévia ou o lançamento forem corrigidos. Confirmar PDF com outros valores para uma origem já gravada recebe 409. Origens excluídas são ignoradas e contadas em removed, sem recriar registros; CSV/PDF compartilham marcas quando seus campos canônicos/contexto coincidem. Diferenças de texto e contexto ainda exigem conferência. Detalhes em LANCAMENTOS_E_IMPORTACAO.md.
