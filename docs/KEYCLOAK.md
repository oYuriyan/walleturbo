# Identidade local com Keycloak

Este ambiente usa Keycloak 26.8.1 e PostgreSQL exclusivo para identidade. É um ambiente de desenvolvimento/homologação local: `start-dev`, HTTP e cookies sem Secure não são adequados à publicação. As portas são expostas somente no loopback. A aplicação mantém suas sessões no Redis e delega credenciais e TOTP ao Keycloak.

## Inicialização

Com Docker Compose v2 e Python 3 disponíveis, na raiz do repositório:

```sh
cp .env.example .env # somente se .env ainda não existir
python scripts/setup_auth.py
docker compose --env-file .env --env-file .env.auth -f compose.yaml -f compose.auth.yaml up --build -d --wait --wait-timeout 240
```

O script cria `.env.auth` com segredos aleatórios e permissão 0600, sem sobrescrever arquivo existente nem mostrar valores. O arquivo é ignorado pelo Git. Proteja também os volumes e backups: a base de identidade contém hashes de senha e segredos TOTP. O Compose lê `.env.auth` explicitamente e injeta o segredo do cliente no Keycloak e na API.

Abra a aplicação em `http://localhost:8000`. O provedor usa `http://auth.walleturbo.localhost:8080`, nome que o Chromium resolve para loopback; a rede Docker tem alias equivalente para a API. Em outro navegador, se esse nome não resolver, configure-o como `127.0.0.1` no arquivo hosts do sistema. Não troque o hostname apenas de um lado: o issuer deve ser idêntico para navegador, metadados e backend.

Abra a administração em `http://auth.walleturbo.localhost:8080/admin/`, usando as credenciais locais de `.env.auth` somente nessa interface. O administrador bootstrap é temporário; configure um administrador nominal e remova o bootstrap antes de qualquer homologação compartilhada. Selecione o realm `walleturbo`, crie uma conta própria de teste, defina senha conforme a política e marque a ação obrigatória Configure OTP. Não utilize o administrador como usuário financeiro. O cadastro público está desabilitado.

A importação ocorre apenas quando o realm ainda não existe. Alterar o JSON não atualiza um volume existente. Revise mudanças pelo console/admin API e registre o procedimento de migração. Não apague volumes para aplicar atualizações em ambientes com dados; a destruição só cabe a ambientes descartáveis explicitamente identificados.

## Segundo fator e ACR

O cliente é confidencial, aceita apenas Authorization Code com PKCE S256 e callback exato `http://localhost:8000/auth/callback`. Implicit flow, password grant e service accounts estão desabilitados no cliente Walleturbo. O login administrativo de preparação do CI usa outro cliente, `admin-cli`, exclusivamente no realm master.

O fluxo local tem etapas de nível 1 (senha) e 2 (TOTP), com autenticadores condicionais de nível do próprio Keycloak e validade de nível zero para pedir autenticação recente. O cliente exige nível mínimo 2. O mapper ACR deriva o valor do contexto de autenticação; não existe mapper com claim constante `acr=2`. A API só aceita o issuer configurado e ACR exigido depois da validação do ID token pela biblioteca OIDC.

Cadastro TOTP exige inserir um código do autenticador; senha isolada não deve liberar a aplicação. A versão inicial não configura recuperação de TOTP por e-mail nem códigos de recuperação. Em desenvolvimento, um administrador pode remover a credencial OTP após confirmar a identidade por procedimento controlado e exigir novo cadastro; isso não constitui recuperação homologada para produção. Códigos de uso único, proteção da recuperação e testes correspondentes são a próxima extensão de identidade.

## Conexão com Google

O arquivo `infra/keycloak/google.example.json` é um modelo desabilitado, sem credenciais. Na administração do realm, adicione o provedor Google e configure:

1. Projeto OAuth sob a conta do responsável pelo produto, tela de consentimento e usuários de teste.
2. Cliente OAuth do tipo aplicação web. Callback local do broker: `http://auth.walleturbo.localhost:8080/realms/walleturbo/broker/google/endpoint`. Se o Google recusar esse domínio local, use um domínio HTTPS de homologação autorizado e ajuste issuer, callbacks e origens integralmente.
3. Client ID e secret somente no provedor/gerenciador de segredos; não os insira no JSON versionado, chat ou logs.
4. Post Login Flow `walleturbo-broker-mfa`, tokens externos sem armazenamento e vínculo de contas com verificação de identidade. Nunca habilite associação automática somente por e-mail.
5. Validação com contas reais de teste: login social, cadastro e cobrança de TOTP, cancelamento, conta já vinculada e tentativas de associação indevida. Só então habilite Google para usuários.

O modelo declara o fluxo adicional de TOTP após o broker, mas Google permanece não homologado até esses testes. O segundo fator interno do Google não substitui automaticamente o contrato ACR do Walleturbo.

## Testes e operação

O CI sobe o provedor real, cria usuário sintético e executa `tests/browser_oidc.cjs` com Chromium. A fixture com senha passa por stdin; não há inserção direta de sessão no Redis, screenshots do QR, gravação de tokens ou credenciais em artefatos. O teste exercita PKCE, cadastro TOTP, recusa de código incorreto/ausente, troca e validação do ID token assinado, rotação da sessão, logout e state inválido. A execução deve ser considerada aprovada somente quando o check do commit estiver verde.

Parar serviços preservando dados:

```sh
docker compose --env-file .env --env-file .env.auth -f compose.yaml -f compose.auth.yaml down
```

Antes de produção: imagem otimizada por digest com avaliação de vulnerabilidades, HTTPS, administração restrita, MFA administrativo, cofre e rotação de segredos, backups com restauração testada, política de recuperação, entrega de e-mail, regras de associação de contas, monitoramento e teste do Google real. O Keycloak local exige gravação no filesystem para preparar o modo de desenvolvimento; o isolamento read-only deve ser aplicado à imagem otimizada de produção. Não encaminhe a porta 8080 para a Internet.
