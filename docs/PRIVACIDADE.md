# Privacidade e preparação para LGPD

Esta documentação orienta privacidade desde a concepção, mas não representa certificação de conformidade. Controlador, operadores, bases legais e aviso de privacidade precisam ser definidos e revisados antes de tratar dados reais em produção.

| Dados | Finalidade | Destino nesta versão |
|---|---|---|
| Identificador pseudônimo derivado de issuer/sub | Separar contas | PostgreSQL e Redis |
| Descrição, data, valor, categoria e revisão | Controle financeiro | PostgreSQL |
| Apelidos de conta/cartão, vencimentos, parcelas, estornos e pagamentos | Organizar e conferir faturas sem duplicar despesas | PostgreSQL |
| Nome, valor e prazo de meta | Planejamento | PostgreSQL |
| State/nonce/verificador OAuth e sessão | Autenticação e segurança | Redis temporário |
| Hash do IP direto | Contagem de requisições | Redis por 60 segundos |
| Preferência claro/escuro | Apresentação | localStorage |

Não coletar CVV, PAN completo, senha bancária ou documentos de identidade. Descrições financeiras podem revelar saúde, religião ou outros aspectos sensíveis: minimizar os campos e evitar repasse a terceiros. O CSV é processado em memória; o arquivo bruto não é persistido. Exports são JSON para evitar fórmulas de planilha.

## Direitos e controles implementados

Exportação dos dados financeiros próprios, incluindo contas, cartões, parcelas e pagamentos; correção por edição; exclusão dos registros ativos; revisão humana de categorias. A exclusão não remove a identidade no provedor e não estabelece por si só o prazo de remoção de cópias de segurança. Demonstração sem persistência financeira no navegador. Não há envio a IA ou afiliados.

## Decisões obrigatórias antes da produção

1. Identificar controlador, contato do encarregado/canal de titulares e operadores contratados.
2. Mapear bases legais por finalidade; não usar consentimento genérico como justificativa universal. Separar execução do serviço de marketing, personalização opcional e eventual compartilhamento com IA.
3. Aprovar registro de operações, avaliação de impacto quando aplicável, contratos com operadores, localização de dados e mecanismos para transferência internacional.
4. Publicar aviso com finalidades, categorias, direitos, retenção, compartilhamento e canal de reclamação.
5. Definir retenção de contas inativas, logs, exportações temporárias e backups; automatizar expurgo e registrar evidências. Validar como exclusões serão reaplicadas após uma restauração.
6. Implementar solicitações de titulares, verificação proporcional de identidade e resposta auditável; desativação da conta e revogação de todas as sessões.
7. Definir política para menores, transparência de decisões automatizadas e revisão humana.
8. Antes de habilitar IA: minimização/redação, avaliação do operador, política de treinamento/retenção, região, opt-in quando adequado e alternativa sem IA.

Não habilitar cookies analíticos/marketing ou integrações de oferta automaticamente. Recomendações futuras devem informar patrocínio/afiliação e não incentivar compras que prejudiquem as metas do usuário.

Na leitura assistida de PDF, original e texto completo são processados transitoriamente em memória pelo serviço isolado. O Redis retém metadados pseudônimos e hashes de linhas da prévia por até dez minutos. Não há envio a IA. Consulte PDF.md para limites e retenção.

Planejamento: renda de referência opcional, margem preservada, confirmação mensal e limites por categoria são usados para simulações determinísticas. Não são enviados a terceiros. Estão incluídos na exportação e exclusão financeira.

Saldos e transferências: referências iniciais, motivos e versões de correção, contas de origem/destino e datas de reversão ficam no banco financeiro e integram exportação/exclusão. Não há envio dessas informações a bancos, modelos de IA ou outros fornecedores. Não coletar dados sensíveis desnecessários no motivo/descrição.
