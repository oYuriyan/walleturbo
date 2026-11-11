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

IA e perfil personalizado, preços/cupons/ofertas, OCR, novos emissores e integrações bancárias/Google, importações em lote e mapeamento genérico de arquivos, automações de recorrência/alertas, projeções avançadas e metas vinculadas a contas. A revisão direcionada de UI/UX foi incluída pelo responsável nesta continuação, sem novos serviços ou funcionalidades. Ficam adiados realocação de formatos legados e resolução sofisticada de colisões CSV, pois há cadastro manual e revisão explícita disponíveis.

Regras automáticas de fechamento, dias úteis, limite de crédito, juros/rotativo e transporte de saldo credor não serão desenvolvidas agora. Casos não suportados devem continuar recusados ou claramente identificados; não presumir pagamento, renda ou transporte de crédito. Melhorias de infraestrutura pública, escala, RLS e operação de produção serão reavaliadas antes de ampliar o uso; a V1 local não representa aprovação de publicação ou conformidade jurídica.

## Situação

Base 0.24 integrada pelos PRs #15 (CI 42857495727) e #16 (CI 42864510569), com 265 testes. Primeiro uso 0.23 integrado pelo PR #14. Backup financeiro/identidade restaurado e comparado no cenário sintético; jornada com dois logins reais, TOTP e nova sessão aprovada, conforme [JORNADA_BASICA.md](JORNADA_BASICA.md).

Interface 0.25 integrada pelo PR #17, CI 42880867890: seis áreas em claro/escuro, Chromium/Firefox, axe, teclado/foco, mobile e proteção contra resposta de período obsoleto.

A entrega 1.0 de 11/11/2026 fecha os critérios técnicos restantes quando a CI integral do PR for aprovada: promoção/login no destino restaurado, uso do `.env` recuperado, volume de um usuário com 10 mil lançamentos/2.400 compras em 24 meses e regressão dos fluxos essenciais. Critérios, medição local, reprodução e limites em [ACEITE_V1.md](ACEITE_V1.md). Evidência e commit finais no PR.

O aceite permite uso local controlado no recorte documentado. Ajustes por preferência pessoal, medição no equipamento de instalação e rotina de guarda/ensaio de backups continuam responsabilidades operacionais; recursos avançados e publicação pública permanecem fora deste marco.
