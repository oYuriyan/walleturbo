# Visão geral — composição compacta

Atualização: 11/11/2026. Este arquivo complementa o [MASTER](../MASTER.md) e substitui apenas a disposição da Visão geral. Tokens, temas, regras financeiras e componentes das outras áreas permanecem os mesmos.

## Ordem de atenção

1. Título, período e ação principal no mesmo cabeçalho. No celular, o botão mantém o nome acessível Novo lançamento e usa o rótulo visual Registrar.
2. Saldo das contas como âncora. O resumo mensal fica no mesmo agrupamento, com escala menor; não compete com o valor principal.
3. Acesso aos cartões ao lado no desktop e logo abaixo no celular. Um cartão fica em foco, com seletor para até dois cartões e contagem explícita; Ver todos continua disponível.
4. Movimentações recentes antes de categorias no DOM e na coluna principal. Categorias funcionam como apoio analítico, sem textos introdutórios repetidos.
5. Metas, sinais complementares e onboarding abaixo do conteúdo diário. Explicação de cálculo e caixa usam disclosures; pendências e resultado negativo continuam visíveis fora deles.

A composição usa proximidade para agrupar dados relacionados, alinhamento para comparar valores e divulgação progressiva para explicações. Não pressupõe um padrão universal de movimento ocular nem substitui um estudo com usuários.

## Densidade e leitura

- Espaços principais em 8/16/24 px; ajustes de 4/12 px onde necessários.
- Saldo em 32–36 px; métricas em 18–24 px; labels secundários menores que os valores.
- No celular, métricas em linhas com valores à direita. Não quebrar centavos para manter três colunas.
- Cartão em preto, camada roxa ao fundo e dados de fatura ao lado, seguindo a referência recebida. Chip e símbolo de aproximação são ilustrações decorativas. A representação é um botão que abre o registro; seletores com estado `aria-pressed` permitem alternar com teclado e toque.
- Informação essencial permanece explícita: data/cobertura do saldo, identificação de valor desconhecido, mês, situação e vencimento da fatura. O restante pode ser expandido com teclado.

## Contrato do acesso a cartões

Reutilizar contas/cartões/faturas já carregados; nenhuma consulta adicional ou mudança de API. Total, valor restante e situação vêm dos registros existentes. Não inventar limite, marca, número de cartão ou saldo disponível.

Ativar um atalho abre Contas e cartões e coloca o foco na fatura correspondente. Sem fatura no período, o foco vai ao cartão; a interação não cria fatura nem pagamento. Na ausência de cartões, oferecer cadastro.

O cabeçalho de ações fica inerte durante atualização ou consulta inconsistente, preservando o bloqueio de operações sobre dados antigos mesmo fora da seção de conteúdo.

## Validação desta composição

Comparação com os mesmos dados da demonstração, topo da página e navegador Chromium:

| Medida | Antes | Depois |
|---|---:|---:|
| Altura da Visão geral em 1440 px | 1635 px | 918 px |
| Início das movimentações em 1440 px | 1561 px | 781 px |
| Altura da Visão geral em 390 px | 2744 px | 1578 px |
| Início das movimentações em 390 px | 2354 px | 1325 px |

Os ganhos medem composição e rolagem dessa amostra, não tempo de tarefa ou melhora de atenção. Evidências locais: `artifacts/dashboard-before.json`, `artifacts/dashboard-after.json` e capturas `dashboard-*.png`.

O roteiro `tests/browser_dashboard.cjs` cobre cinco larguras (320/390/768/1024/1440), dois temas, axe, teclado, ausência de cartões, fatura parcial e consulta sem POST. A versão com a referência passou em Chromium e Firefox, incluindo seleção com `aria-pressed`, preservação de foco, ausência de POST ao consultar e abertura do cadastro pelo botão de adicionar. Os controles têm alvos de 48 px. As legendas e o nome sobre o cartão escuro atingem 10,927:1 e 15,811:1, registrados em `CONTRASTES.json`. Foram verificadas novamente as regressões de estados e cartões/faturas com a API real.

**Referência dos cartões recebida e aplicada:** representação vertical escura, efeito de cartões empilhados, chip decorativo e metadados ao lado. O destaque de fundo usa o roxo da marca. Como o Walleturbo não armazena PAN, validade ou limite, os campos mostram total da fatura, vencimento, situação e restante reais. A seleção permanece apenas na memória da aba e é limpa ao encerrar a sessão. Adicionar cartão abre o formulário existente, sem cadastro automático.

Na validação final após reconstruir o ambiente, Chromium e Firefox passaram nas 20 combinações de largura e tema, com zero violações nos exames axe. Vencimento e centavos permanecem inteiros nas larguras verificadas. As capturas `artifacts/card-reference-*.png` registram o painel final; as medidas da demonstração foram confirmadas novamente. O conjunto de estados de interface e a regressão de cartões/faturas com a API real também passaram nesta adaptação. Na preparação do versionamento 1.1.0, os 266 testes no Docker, os estados e a matriz final do dashboard foram repetidos com sucesso; detalhes em `docs/REDESIGN_UI.md`.
