# Autenticação, Google e MFA

## Contrato implementado

A aplicação delega identidade a um provedor OpenID Connect (por exemplo, Keycloak ou serviço gerenciado compatível). Não há integração Google direta nesta entrega: o provedor deve federar o Google e exigir um segundo fator próprio. MFA/2FA representam o mesmo requisito quando são exatamente dois fatores; não são duas funcionalidades distintas.

O backend valida o retorno com Authlib (assinatura, emissor, audiência, nonce e expiração do ID token conforme metadados OIDC) e exige `iss` igual ao issuer configurado e `acr` igual a `REQUIRED_ACR` (padrão `2`). `acr=2` é um contrato local com o provedor, não uma garantia universal de dois fatores. **Não mapear esse valor como claim constante.** Sem a claim exigida, o callback retorna 403.

## Provisionamento necessário

1. Criar tenant/realm exclusivo e cliente confidencial para aplicação web.
2. Registrar exatamente `BASE_URL/auth/callback` como redirect URI; sem curingas. Habilitar Authorization Code e PKCE S256; desabilitar fluxo implícito e password grant.
3. Registrar projeto OAuth no Google, tela de consentimento e callback do broker OIDC. Guardar client secret apenas no provedor.
4. Exigir TOTP ou WebAuthn/passkey no fluxo, inclusive depois do login social. Permitir recuperação com códigos de uso único e políticas contra tomada de conta. Evitar SMS como fator principal.
5. Configurar nível de autenticação para emitir `acr=2` somente após o fator adicional. Verificar o ID token em homologação sem registrar seu conteúdo em logs.
6. Preencher `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` pelo gerenciador de segredos. Produção exige HTTPS em issuer e aplicação.
7. Validar login Google, recusa sem MFA, state/nonce inválidos, rotação de JWKS, token expirado, sessão expirada, recuperação e revogação.

Os testes automatizados do callback usam claims simuladas para verificar a política local. Eles não certificam o comportamento do provedor, o login Google ou a validação criptográfica ponta a ponta.

## Sessões

Cookie HttpOnly, SameSite=Lax, Secure quando BASE_URL usa HTTPS. Identificador aleatório de 256 bits; apenas seu hash é usado como chave de Redis. TTL ocioso de 30 minutos, absoluto de oito horas. Redis indisponível bloqueia acesso. Logout encerra a sessão Walleturbo; não encerra a sessão Google/provedor. O próximo login solicita `prompt=login`.

Antes da produção: revogação de todas as sessões por usuário, step-up recente para exclusão/exportação, logout federado, cookies com prefixo `__Host-`, detecção de sessões concorrentes e testes de recuperação do segundo fator.
