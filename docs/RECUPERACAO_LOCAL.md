# Backup e recuperação local — 0.24

Para a configuração local padrão deste repositório: PostgreSQL financeiro `db`, PostgreSQL da identidade `auth-db`, API e Keycloak. Requer Python 3.11+, Git, Docker Compose, GPG e gpgconf no computador operador. Não instala pacotes, contrata serviços ou envia dados para fora da máquina. Procedimento validado em Linux, com permissões POSIX e filesystem que suporte hardlinks para publicar a cópia sem sobrescrever. Use o mesmo usuário local com acesso autorizado ao Docker.

## Preparação e guarda

Gere uma chave uma vez, em um arquivo novo e privado fora do repositório:

```bash
python scripts/local_backup.py keygen --key /caminho/seguro/walleturbo.backup-key
```

A chave é aleatória (256 bits), não é exibida nem incluída no backup. Guarde uma segunda cópia protegida separada dos arquivos de backup. Perder a chave impede a restauração; guardá-la junto da única cópia reduz a proteção. Arquivo existente é preservado; chave com permissão para grupo/outros ou symlink é recusada. Diretórios `backups/`, `recovery/`, arquivos `.gpg` e `.backup-key` são ignorados pelo Git.

## Captura completa

Execute com os bancos financeiro e de identidade já em execução, usando `.env` e `.env.auth` da instalação:

```bash
python scripts/local_backup.py backup --key /caminho/seguro/walleturbo.backup-key --output backups/copia-2026-11-10.gpg
```

`--project` permite indicar o nome Compose de origem (padrão `walleturbo`); `--config` indica o diretório das configurações. Não executar outros escritores SQL nem editar configurações durante a manutenção. O script pausa somente API/Keycloak que já estavam em execução, faz `pg_dump` custom dos dois bancos, copia configurações e registra checksums, horários UTC e commit do código. Reativa os mesmos containers mesmo se o dump falhar. Se a reativação falhar, o comando retorna erro: confira `docker compose ps` e inicie os containers originais antes de retomar o uso.

Criptografa com OpenPGP/GPG simétrico AES256, com verificação de integridade na leitura. Publica a cópia com permissão 0600 e sem sobrescrever arquivos existentes. Dumps temporários ficam sem criptografia em diretório privado 0700 e são removidos ao terminar. Use disco local protegido e com espaço livre; unlink não é apagamento forense nem protege contra acesso administrativo ao computador. Falta de espaço/chave ou erro de dump não publica uma cópia completa.

Sem identidade instalada, use explicitamente `--finance-only`. Essa modalidade não é backup completo e é recusada se o banco de identidade do projeto estiver ativo. Redis, sessões e cotas não são copiados. Arquivos personalizados, volumes externos e configurações fora de `.env`/`.env.auth` não integram este formato; ele atende a instalação padrão local. O repositório e suas imagens/dependências precisam continuar disponíveis para recuperação.

## Restauração de ensaio

Use um nome e um diretório novos; a origem continua preservada:

```bash
python scripts/local_backup.py restore --key /caminho/seguro/walleturbo.backup-key --input backups/copia-2026-11-10.gpg --project walleturbo-restore-ensaio --directory recovery/ensaio
```

Crie antes somente o diretório pai `recovery`, se necessário. O destino deve começar com `walleturbo-restore-`. A operação recusa projetos com qualquer container, volume ou rede existente e diretório de saída existente. Autentica/decripta o arquivo antes de criar o diretório durável; verifica nomes, tipos, membros e checksums e não extrai links ou caminhos livres do arquivo. Chave errada ou cópia corrompida falham antes da criação dos bancos.

Inicia apenas bancos novos, sem portas publicadas. Confirma que estão vazios e usa `pg_restore --exit-on-error`, sem limpar ou sobrescrever tabelas. API e Keycloak não são iniciados no destino. Uma falha após a criação pode deixar um projeto parcial para diagnóstico; não trate essa tentativa como recuperada. Confira o nome antes de remover exclusivamente os volumes de um ensaio descartável. Não execute `down -v` no projeto original.

O diretório de recuperação contém dumps/configurações descriptografados, privados (0700/0600). Restrinja o acesso e remova a cópia de ensaio quando não for mais necessária. Segredos `.env.auth`, hashes de senha e credenciais TOTP são dados sensíveis. Nunca envie esse diretório, a chave ou backups reais para Git/CI/chat.

## Conferência e promoção

Confira o commit em `manifest.json`, use o código correspondente e valide valores, contas, pagamentos, marcas de importação e identidade. Não faça downgrade/migração automática de um banco recuperado. Compare com os registros esperados e teste login/MFA antes de voltar ao uso. A restauração de um backup anterior também recupera dados que possam ter sido excluídos depois: reaplique essas exclusões antes de liberar o acesso.

Somente depois da conferência, pare API/Keycloak da origem para liberar as portas locais. Para iniciar o ambiente recuperado completo (mantenha a cópia original preservada), use o nome de projeto escolhido e os arquivos recuperados:

```bash
docker compose --project-name walleturbo-restore-ensaio --env-file recovery/ensaio/.env --env-file recovery/ensaio/.env.auth -f compose.yaml -f compose.auth.yaml up --no-build -d --wait
```

A imagem `walleturbo-api` deve corresponder ao código validado. Consulte KEYCLOAK.md para o endereço de identidade local. Redis novo encerra sessões anteriores; autentique novamente. O script não faz essa promoção nem remove a instalação original.

Para perda do autenticador, a V1 mantém o procedimento administrativo local de KEYCLOAK.md: confirmar a identidade, acessar o console pelo administrador autorizado e exigir novo cadastro OTP. Preserve o acesso administrativo e as configurações fora da máquina. Backup não substitui esse procedimento e não cria bypass ou códigos de recuperação automáticos. Antes de uso público, recuperação autônoma e administração precisam de homologação própria.

## Aceite e limites operacionais

`python -m tests.integration_backup` ensaia o financeiro; `--identity` inclui identidade e exige Keycloak previamente inicializado com credenciais sintéticas. Compara todas as tabelas financeiras e realm/usuários/credenciais/clientes do Keycloak, verifica configurações, chave incorreta, corrupção, repetição recusada e reativação dos escritores. Cria e remove apenas o projeto aleatório de ensaio e seus volumes; uma linha financeira sintética é removida da origem no final. Não rodar esse teste com dados pessoais antes de revisar o ambiente.

O ensaio financeiro local sintético levou 17 segundos, incluindo backup, casos negativos, restauração e comparação. Não é uma promessa de tempo para bases reais. A CI registra o ensaio completo. RPO é o instante do último backup válido; RTO depende do volume, imagens e operador e deve ser medido na instalação. Até existir agendamento, faça a captura antes de atualizar e após alterações importantes; guarde cópia criptografada fora da máquina, defina retenção e teste-a periodicamente. Não existe garantia de recuperação sem cópia íntegra, chave e ensaio.
