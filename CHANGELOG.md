# Histórico de alterações

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
