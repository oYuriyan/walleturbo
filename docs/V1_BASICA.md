# Primeira versão básica — decisão de 10/11/2026

A primeira versão será para uso financeiro local controlado. A decisão do responsável é reduzir custos e entregar o funcionamento básico antes de ampliar o produto. Este recorte substitui a exigência de concluir todas as funcionalidades das fases 1–5 do roadmap para essa primeira versão. As demais funcionalidades continuam no backlog; não são requisitos de aceite desta V1.

## Escopo de uso

- Login local existente com Keycloak/TOTP; cadastro e manutenção de contas e cartões.
- Saldo inicial datado, receitas/despesas manuais, transferências e correções com histórico.
- Compras, parcelas, estornos, conferência e pagamentos de faturas pelos fluxos já suportados.
- Importação assistida opcional nos formatos CSV, PDF textual e OFX declarados no manual, com revisão, recusa de divergências e proteção contra duplicação. Cadastro manual é a alternativa quando o documento não é suportado.
- Resumo mensal, limites e metas simples existentes, com distinção entre resultado, caixa e saldo.
- Exportação/exclusão financeira e limites de acesso já existentes.

Sem expansão de serviços pagos ou dependências por conveniência. Não há publicação pública ou contratação nesta decisão.

## Trabalho necessário para fechar a V1

1. **Primeiro uso e clareza:** orientar conta → referência de saldo → lançamento e corrigir problemas que impeçam a jornada básica em celular e desktop. O incremento 0.23 entrega os atalhos iniciais; não equivale ao aceite completo de interface/acessibilidade.
2. **Recuperação local:** comprovar backup e restauração dos dados financeiros e da identidade, documentar recuperação de acesso e instalação/reinício. Exportar JSON não substitui backup restaurável.
3. **Jornada básica integrada:** executar login, cadastro, saldo, lançamento/correção, compra/fatura/pagamento, transferência, planejamento simples, exportação e nova sessão. Verificar isolamento entre usuários, preservação após reinício e coerência de valores entre telas.
4. **Aceite e limites:** fechar erros bloqueantes, navegação por teclado/foco, leitura no celular, limites de volume compatíveis com o ambiente e instruções de operação/recuperação. Registrar o volume validado, os formatos suportados e as restrições financeiras antes de chamar a versão de pronta.

Os quatro itens são pacotes de aceite, não uma promessa de quatro commits. Priorizar evidências e correções necessárias; reaproveitar testes e componentes existentes.

## Adiado para depois da V1

IA e perfil personalizado, preços/cupons/ofertas, OCR, novos emissores e integrações bancárias/Google, importações em lote e mapeamento genérico de arquivos, automações de recorrência/alertas, projeções avançadas e metas vinculadas a contas. Também ficam adiados redesign amplo, realocação de formatos legados e resolução sofisticada de colisões CSV, pois há cadastro manual e revisão explícita disponíveis.

Regras automáticas de fechamento, dias úteis, limite de crédito, juros/rotativo e transporte de saldo credor não serão desenvolvidas agora. Casos não suportados devem continuar recusados ou claramente identificados; não presumir pagamento, renda ou transporte de crédito. Melhorias de infraestrutura pública, escala, RLS e operação de produção serão reavaliadas antes de ampliar o uso; a V1 local não representa aprovação de publicação ou conformidade jurídica.

## Situação

Base 0.22 integrada pelo PR #13, CI 42679157365, com 257 testes. Primeiro uso 0.23 em validação; evidências finais e commit serão registrados no PR. Os pacotes de recuperação e aceite integrado ainda estão pendentes. Nenhuma estimativa de prazo/custo foi fixada.
