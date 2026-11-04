# Segurança e modelo de ameaças

Não existe garantia de barrar toda entrada indesejada. O objetivo é reduzir a superfície de ataque, detectar abuso, limitar impacto e recuperar o serviço com evidências.

| Ameaça | Controle implementado | Validação / trabalho restante |
|---|---|---|
| IDOR / acesso entre usuários | Filtro owner em leitura, edição, exclusão e exportação; FKs compostas nas relações novas | Testes de dois usuários; adicionar RLS |
| CSRF | Origem exata e token de sessão nas mutações | Testes de origem e token inválidos |
| XSS persistente | Renderização com textContent; CSP sem scripts inline | Teste de navegador pendente |
| SQL injection | ORM com parâmetros, schemas restritos | Não há SQL dinâmico com entrada do usuário |
| Fixação / furto de sessão | Cookie HttpOnly, rotação, TTL, sessão no Redis | Secure em HTTPS; revogação global pendente |
| Bypass de MFA | Claim ACR exigida e issuer fixado | Keycloak/TOTP real validado; Google, recuperação e testes criptográficos ampliados pendentes |
| Abuso de upload | Corpo 300 KB (PDF: 2 MB) com prazo total de envio de 10s, CSV 256 KB/500 linhas, campos limitados | PDF textual em leitor isolado; ver PDF.md |
| Abuso de tráfego | Limite Redis atômico por IP (120/min), proprietário (90/min) e importação (10/min) | WAF, CDN, quotas persistentes e carga pendentes |
| Falha de Redis | Resposta 503, sem fallback permissivo | Teste automatizado |
| Cadeia de suprimentos | Dependências com hashes, auditoria em CI | Actions fixadas por SHA; imagens por digest, scans e política de atualização pendentes |

## Produção: condições obrigatórias

- Borda gerenciada com mitigação DDoS, WAF, TLS, proteção de origem e limite de conexões. Uma API sozinha não resolve ataques volumétricos.
- Banco e Redis privados, autenticação/TLS, privilégios mínimos e criptografia em repouso. Redis do Compose não possui senha porque não expõe porta ao host; isso não serve como configuração de produção.
- Limites por usuário/endpoint, tratamento confiável de IP atrás de ingress, timeout de upload e cotas. `infra/nginx.conf` é uma referência de limites, não um deployment pronto.
- Logs estruturados com request-id, eventos de segurança e métricas sem valores, descrições, tokens ou conteúdo de fatura. O acesso padrão do Uvicorn foi desabilitado para evitar registrar códigos OAuth em query strings.
- Gestão de segredos, rotação, backups criptografados e teste documentado de restauração.
- Scans de imagem, SAST, DAST em homologação e revisão externa direcionada a isolamento, login e importação.
- Testes de carga somente em ambiente próprio/autorizado, com limites de tráfego e critérios de parada. Nenhum teste ofensivo foi executado contra terceiros.

## Reposta a incidentes

Conter o endpoint ou credencial afetados; preservar evidências sem ampliar exposição; revogar sessões; avaliar titulares e dados afetados; acionar responsáveis técnicos e jurídicos; cumprir comunicação aplicável à ANPD/titulares; registrar causa, correção, teste de regressão e restauração. Prazos legais devem ser confirmados na política de incidentes vigente antes do lançamento.

As respostas de rejeição também recebem cabeçalhos de segurança. Uma resposta concorrente não recria a sessão removida por logout (renovação condicionada à existência da chave no Redis). Revogação global de sessões continua pendente.
