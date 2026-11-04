# Histórico de alterações

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
