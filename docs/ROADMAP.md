# Plano de entrega e critérios de aceite

O pedido completo é um produto em várias etapas. Esta entrega inicia a base; nenhuma etapa dependente de serviço real é considerada homologada por existir um contrato ou mock.

| Etapa | Escopo | Critério de aceite | Situação |
|---|---|---|---|
| 0 — Fundação | Repositório, decisões, domínio financeiro, interface, containers, CI | Build, testes e documentação reproduzíveis | Implementada; evidências no relatório |
| 1 — Identidade e privacidade | Google, MFA, recuperação, direitos dos titulares e políticas | Login real e ataques de sessão testados; revisão LGPD | Parcial: integração OIDC e controles locais |
| 2 — Controle financeiro | Contas, cartões, parcelas, estornos, recorrência, orçamento, conciliação | Faturas reconciliadas com precisão de centavos | Parcial: lançamentos, CSV, metas, contas, cartões, parcelas, estornos, conferência e pagamentos; recorrência/orçamento/transferências pendentes |
| 3 — Ingestão documental | PDF/OFX/OCR, antivírus, sandbox, armazenamento temporário e filas | Corpus de emissores com exatidão medida e revisão | Parcial: PDF textual genérico isolado com revisão; OCR/OFX e corpus de emissores pendentes |
| 4 — Agentes de IA | Classificação, perfil, explicações e identificação de desperdício | Avaliação anonimizada; confiança calibrada; aprovação humana | Pendente; regras determinísticas disponíveis |
| 5 — Lista de desejos e ofertas | Catálogo, preço histórico, cupons com validade, links verificáveis | Fornecedores autorizados; transparência de afiliados; orçamento respeitado | Pendente |
| 6 — Produção | Infra como código, observabilidade, WAF, backup/restore, RLS, carga | Metas de disponibilidade/custo aprovadas, teste de recuperação e pentest | Pendente |

## Desenho da ingestão futura

Receber upload com limite → validar assinatura/tipo real → quarentena → antivírus → parser/OCR isolado sem rede → normalização em centavos → verificação de total/parcelas → deduplicação por conta/fatura → revisão humana → gravação transacional → expurgo do arquivo. Erros devem ser recuperáveis sem duplicar despesas. Não enviar faturas completas ao modelo por padrão.

## Agentes e personalização

Agente de classificação propõe, não altera silenciosamente. Agente de hábitos apresenta evidências e período analisado. Agente de metas usa perfil informado, renda disponível e restrições explícitas; faltas de dados devem aparecer como incerteza. Agente de ofertas só consulta provedores aprovados, nunca executa compra. Todas as saídas têm schema, limites de tokens/custo/tempo e trilha de versão; dados de faturas não podem comandar ferramentas.

## Decisões necessárias para produção

Região e fornecedor de hospedagem; domínio; provedor OIDC; projeto OAuth Google; e-mail transacional; responsável pelo tratamento de dados; orçamento de infraestrutura/modelos; emissores prioritários de faturas; fornecedores de preços/cupons e contratos. Sem essas definições não há implantação pública segura nem integrações reais a homologar.
