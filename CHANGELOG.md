## 0.23.0 — em validação

- Recorte da V1 para uso financeiro local básico, adiando automações e integrações avançadas.
- Guia de primeiro uso com atalhos para conta, saldo inicial e lançamento; recolhido no retorno e oculto na demonstração/sessão encerrada.
- Jornada mobile reconcilia R$ 1.000 menos R$ 25; componentes existentes, sem nova persistência ou dependência.

## 0.22.0 — em validação

- Correção de competência do lançamento OFX primário junto com sua origem, preservando identidade e correções.
- Simulação das duas faturas, motivo, revisão explícita, versões, idempotência e histórico atômico.
- Bloqueios para parcelas, vínculos adicionais, exclusões, contexto inválido e faturas conferidas.
- Sem migração/dependência nova; 257 testes locais, PostgreSQL/mobile e homologação integral no PR.

## 0.21.0 — em validação

- OFX de cartão BRL na fatura selecionada, com origem reservada contra duplicação em outro mês.
- Créditos exigem conferência como estorno; pagamentos são exibidos sem importação ou movimento no caixa.
- Máscara, corpus SGML/XML, vínculos/revisões/histórico e proteção após exclusão reutilizados.
- Sem migração ou dependência nova; 244 testes locais e homologação completa no PR.

## 0.20.0 — em validação

- OFX bancário 1.x/2.x em BRL com conta obrigatória, prévia, seleção e identidade por FITID.
- IDs distintos preservam despesas iguais; assinatura de origem recusa dados divergentes e conserva correções/exclusões.
- Vínculo/desfazimento, histórico, recibos e marcas reutilizados; corpus sintético SGML/XML com resultados esperados.
- Sem migração ou dependência nova; 226 testes locais, integração PostgreSQL/mobile e homologação no PR.

## 0.19.0 — em validação

- PDF textual oferece possíveis duplicatas e vínculo explícito a compra/estorno existente na mesma fatura, usando os campos revisados.
- Consulta após edição, desfazimento com motivo e releitura para refazer a decisão; identidade original preservada em seleções parciais.
- Histórico, revisões e locks reutilizados do CSV; reenvios antigos não recuperam vínculos desfeitos.
- Sem migração ou dependência nova; 197 testes locais, com regressão completa e evidências no PR da entrega.

## 0.18.0 — em validação

- Prévia CSV mostra o vínculo atual e permite desfazê-lo com motivo, preservando o lançamento financeiro.
- Nova prévia permite remapear ou importar ocorrência independente; revisões impedem restaurar vínculos por reenvios antigos.
- Migração 013, histórico privado transacional, testes de isolamento, rollback, concorrência e fluxo mobile.
- Nenhuma dependência ou serviço novo; homologação final registrada no PR da entrega.

## 0.13.0 — em validação

- Cenários e limites mensais exigem versão atual, preservada após exclusão de limites.
- Histórico transacional para configurações; recarga após conflito e proteção de respostas atrasadas.
- Migração 012 preserva dados existentes; 140 testes locais aprovados, CI pendente.

## 0.12.0 — em validação

- Conferência e reabertura exigem revisão atual; versão monotônica impede aceitar telas anteriores ao ciclo fechar/reabrir.
- Recarga de fatura no formulário; migração 011 preserva dados existentes.
- Contrato de API alterado: expected_revision obrigatório nas duas operações.
- 136 testes locais aprovados; integração concorrente e navegador ampliados, aguardando CI.

# Histórico de alterações

## 0.11.0 — em desenvolvimento

- Lançamentos diretos versionados com motivo, UUIDs de criação/correção e remoção protegida.
- Marcas de origem sobrevivem à exclusão/correção, impedindo recriação de linhas conhecidas em CSV/PDF.
- Correção de importados preserva fatura e parcela única; revisão de categoria e exclusão de compra exigem versão/revisão.
- Migração 010 preserva dados e origens ativas legadas; exportação/expurgo abrangem marcas.
- Limpeza de formulários/prévias ao perder sessão e roteiros adicionais de PostgreSQL, navegador, cartões e demonstração/XSS no CI.

## 0.10.0 — em desenvolvimento

- Correção de conta, data e valor de pagamentos com motivo, prévia de saldos/caixa e limite revalidado na fatura.
- Versão por pagamento evita sobreposição e remoção desatualizada; DELETE passa a exigir expected_version.
- Recibos de correção preservam a idempotência; IDs/UUIDs de criação e histórico mantidos.
- Migração 009 preserva pagamentos legados; testes de saldo desconhecido, referência temporal, concorrência e interface mobile.
- Histórico visual apresenta vínculos às contas; exportação/expurgo abrangem os novos dados. Limites em PAGAMENTOS.md.

## 0.9.0 — em desenvolvimento

- Correção integral de compras manuais com prévia dos totais por mês, motivo e versão contra sobreposição entre sessões.
- Recalcula parcelas atomicamente, preservando IDs sobreviventes; bloqueia faturas de origem/destino conferidas.
- Recibos de envio preservados após exclusão de compra/pagamento, recusando reenvios antigos sem recriar registros.
- Migração 008 preserva valores legados e reserva UUIDs de exclusões auditadas desde 0.8; exportação/expurgo incluem recibos.
- Interface e testes de rollback, concorrência, migração e navegador ampliados. Limites em CORRECOES.md; FIN-04/05 permanecem parciais.

## 0.8.0 — em desenvolvimento

- Histórico privado e transacional para nove tipos de registro financeiro, com estados anterior/posterior.
- Consulta paginada na API/interface, exportação e expurgo de privacidade; migração 007 sem backfill fictício.
- Lock na correção de lançamento, recarga de compras após lock e parâmetros SQL ocultos em exceções.
- Revisão técnica e limitações em AUDITORIA.md; FIN-04/05 permanecem parciais.

## 0.7.0 — em desenvolvimento

- Metas com edição versionada, arquivamento/reativação e exclusão protegida por reserva zero.
- Metas arquivadas saem da simulação de aportes e permanecem no cadastro/exportação.
- Migração 006 preserva metas legadas; interface limpa formulário na expiração da sessão.
- Testes de concorrência, isolamento, migração e jornada de metas no navegador.
- CI 0.6 aprovado no commit 790e362; evidências em HOMOLOGACAO.md.

## 0.6.0 — em desenvolvimento

- Renomeação, arquivamento e reativação de contas/cartões com versão para recusar edições obsoletas.
- Novas operações exigem cadastro ativo; correções, saldos e quitação de faturas existentes preservados.
- Exclusão restrita a cadastro arquivado sem vínculos; migração 005 preserva cadastros existentes.
- Testes de concorrência, importações em andamento, isolamento, migração e gerenciamento no navegador.
- Ciclo de vida de metas e histórico amplo de alterações permanecem pendentes no roadmap.

## 0.5.0 — em desenvolvimento

- Saldo inicial por conta com data de referência, revisões preservadas e controle de versão.
- Saldos calculados por data, com indicação de referências ausentes e registros sem conta.
- Transferências próprias e reversão datada, sem duplicar receitas/despesas e com idempotência preservada.
- Migração 004, exportação/exclusão e interface de contas ampliadas; testes de concorrência e navegador.

## 0.4.0 — em desenvolvimento

- Infraestrutura local Keycloak/PostgreSQL com realm versionado, TOTP e níveis ACR.
- Teste OIDC com provedor real no navegador e roteiro para conexão Google.

- Migração do transporte HTTP para httpx2, removendo avisos de depreciação de Starlette/Authlib.
- Regressão da troca OAuth com PKCE e recusa de token inválido em transporte simulado.

- Planejamento mensal e limites por categoria com conferência dos agregados.
- Simulação de aportes limitada por receita, resultado, caixa e margem preservada.
- Recorrências de assinaturas com evidências de meses distintos, excluindo parcelas.
- Migração 003, exportação/exclusão ampliadas e teste de planejamento no navegador.

## 0.3.0 — em desenvolvimento

- Leitura assistida de PDF textual com seleção, edição e confirmação de candidatos.
- Leitor isolado sem rede/credenciais, limites de páginas, tamanho, memória, CPU e tempo.
- Prévia temporária vinculada à sessão/fatura; deduplicação preserva ocorrências em seleções parciais.
- Testes sintéticos de PDF e roteiro de navegador conectado à API; sem homologação de emissores específicos ou OCR.

## 0.2.0 — em desenvolvimento

- Contas, cartões, parcelas exatas em centavos e estornos em faturas explícitas.
- Conferência por total, revisão obrigatória, pagamento parcial e correção de registros sem duplicar despesas.
- Idempotência de compras/pagamentos, locks de concorrência e relações protegidas por proprietário no banco.
- Migrações transacionais com checksum e adoção explícita do schema legado.
- Cotas por usuário/importação, timeout de upload, cabeçalhos em rejeições e prevenção de restauração de sessão revogada.
- Exportação/exclusão ampliadas e fluxo de navegador autenticado com dados sintéticos.

## 0.1.0 — 03/11/2026 — em desenvolvimento

- Fundação do Walleturbo com API FastAPI, PostgreSQL, Redis e interface responsiva em pt-BR.
- Controle mensal, lançamentos, CSV com revisão e deduplicação, metas e alertas por regras.
- Contrato OIDC/MFA, sessões no servidor, CSRF e controles básicos de abuso.
- Exportação/exclusão financeira, documentação de privacidade, containers e pipeline de validação.
- Produção, Google/MFA reais, agentes de IA e ofertas ainda pendentes de implementação/configuração e homologação.
