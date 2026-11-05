# Plano consolidado de entrega — revisão de 05/11/2026

## Diretriz e evidência atual

Prioridade definida pelo responsável pelo produto: concluir o desenvolvimento e uma jornada end-to-end confiável em ambiente local antes de contratar serviços, adquirir domínio ou conectar Google. Não há autorização de publicação ou contratação nesta revisão. Desenvolvimento, testes e documentação seguem containerizados, em pt-BR, com BRL/centavos e privacidade desde a concepção.

Base de código homologada: `961b0e0`, [CI 41892139036](https://github.com/oYuriyan/walleturbo/actions/runs/41892139036), com 116 testes, integração PostgreSQL/Redis, PDF/planejamento no navegador e login real Keycloak/TOTP. Isso valida os cenários executados; não demonstra produto completo, produção aprovada ou certificação LGPD.

Este documento substitui a ordem do roadmap anterior. Relatórios antigos em HOMOLOGACAO.md são históricos. Uma tarefa só passa a concluída com comportamento implementado, critérios de aceite atendidos, evidências e documentação atualizada. As fases abaixo estão pendentes ou parciais; não são entregas prontas.

## O que já existe

| Área | Entrega existente | Limite atual |
| --- | --- | --- |
| Fundação | FastAPI, PostgreSQL, Redis, Compose, migrações com checksum, CI, PR e documentação | Operação pública, recuperação de desastre e controles de volume incompletos |
| Finanças | Lançamentos, categorias por regras, contas/cartões, parcelas, estornos, conferência e pagamentos parciais | Saldo inicial, saldo por conta e transferências com reversão entregues na 0.5; recorrências automáticas, ciclo de vida de contas/cartões/metas homologado na 0.7; recorrências e alguns ciclos de crédito pendentes |
| Importação | CSV definido e PDF textual genérico isolado, prévia/revisão e deduplicação | Documentos sintéticos; sem emissores homologados, OCR, OFX ou antivírus |
| Planejamento | Metas, limites mensais, simulação conservadora e recorrências de assinaturas com evidências | Metas independentes das contas; sem projeção completa, perfil personalizado ou IA |
| Interface | Web responsiva, claro/escuro, demonstração e formulários funcionais | Jornada completa, acessibilidade e revisão de design ainda não homologadas |
| Identidade | OIDC/PKCE, Keycloak real/TOTP, sessões opacas, CSRF, expiração e logout local | Google, recuperação, revogação global e testes criptográficos amplos pendentes |
| Privacidade | Exportação e exclusão financeira por usuário; arquivos transitórios | Não exclui identidade nem define expurgo de backups; processos LGPD incompletos |
| Segurança | Filtros por proprietário, FKs compostas, cotas temporárias, limites de upload, isolamento do parser, auditoria de dependências | RLS, papéis mínimos, scans adicionais, observabilidade, carga e borda de produção pendentes |

## Marcos de aceite

- **A — Uso financeiro local controlado:** fases 1–5 concluídas, com importação nos formatos declarados, dados reconciliados, restauração testada e jornada completa com login real. Dados sintéticos durante desenvolvimento; uso de dados pessoais somente após os controles locais de proteção e recuperação. Funcionalidades avançadas pendentes devem ser identificadas na interface/manual.
- **B — Escopo funcional completo em homologação local:** marco A + fases 6–7, ingestão avançada e recuperação da fase 8. Engloba IA, perfil e desejos/ofertas do pedido original. Um simulador de provedor não equivale à integração real homologada. Conectores indisponíveis permanecem explicitamente pendentes.
- **C — Publicação:** marco B + fase 8 integral e fase 9, decisões operacionais/jurídicas e autorização de publicação. Domínio, hospedagem e Google podem aguardar até essa preparação.

## Fase 1 — Fechar o modelo financeiro e o saldo confiável (parcialmente concluída)

Dependência: base existente. Origem: completar o controle financeiro já iniciado; alguns itens são requisitos técnicos derivados para viabilizar seu uso.

- **FIN-01 — concluído na 0.5:** definir saldo inicial por conta com data de referência, saldo calculado, ajustes explícitos e política para lançamentos anteriores à referência. Diferenciar saldo informado, saldo calculado, resultado e caixa.
- **FIN-02 — concluído na 0.5:** transferências entre contas próprias, com débito/crédito atômicos, estorno, reenvio idempotente e proteção contra concorrência. Transferência não conta como receita/despesa.
- **FIN-03 — concluído na 0.7:** ciclo de vida de contas, cartões e metas: renomear, arquivar, corrigir e excluir conforme vínculos/histórico; incluir política para lançamentos antigos sem conta. Evitar exclusão silenciosa de histórico.
- **FIN-04 — parcial; histórico homologado na 0.8, correção integral manual homologada na 0.9:** edição consistente de operações parceladas, pagamentos e ajustes, com revisão de efeitos em meses/faturas já conferidos. Histórico mínimo de alterações financeiras com retenção e acesso definidos, sem registrar dados sensíveis em logs gerais.
- **FIN-05 — parcial; recibos para compras/pagamentos após exclusão homologados na 0.9; contrato de saldos/transferências em SALDOS.md:** consolidar invariantes e exemplos em documento de domínio: centavos, sinais, datas civis, competência/vencimento, caixa, saldo, estornos e reversões. Incluir migração de dados existentes e idempotência após exclusão/reenvio tardio.

Aceite: cenário com duas contas, saldo inicial, receitas, despesas, transferência, compra parcelada, pagamento e reversão termina com valores esperados por conta/mês; nenhuma duplicação ou perda por reenvio, concorrência ou migração.

## Fase 2 — Completar faturas, recorrências e planejamento

Dependência: fase 1.

- **FAT-01:** fatura zerada/negativa, crédito carregado para mês seguinte e estorno após quitação. Definir vínculo e conciliação do crédito sem inventar movimentação bancária.
- **FAT-02:** fechamento/vencimento por cartão e limites de crédito/disponibilidade estimada; ajustes explícitos por emissor, dias úteis e feriados quando suportados. Preservar o mês manual como alternativa segura.
- **FAT-03:** registrar encargos, juros e rotativo com origem e revisão. Cálculo automático só com regras conhecidas e testadas do emissor; divergência deve impedir interpretação silenciosa.
- **REC-01:** receitas/despesas recorrentes com frequência, início/fim, vencimento, pausa, cancelamento, exceções e execução idempotente. Distinguir compromisso previsto de pagamento efetivamente realizado.
- **PLA-01:** projeção de caixa com parcelas, faturas e recorrências, margem de segurança e alertas de vencimento/limite na aplicação. Estado de leitura/ação dos alertas; notificações externas ficam na fase 9.
- **PLA-02:** aportes/resgates de metas vinculados a contas, sem dupla contagem ou transferência bancária automática; prioridades e prazos ajustáveis. Definir se planos históricos são snapshots ou simulações atuais, comunicando isso na interface.

Aceite: mês corrente e meses futuros reconciliam obrigações e disponibilidade; recorrência não duplica após reinício; crédito/estorno e aportes não inflam despesas nem saldo. A projeção informa dados ausentes.

## Fase 3 — Importação útil e verificável

Dependência: fases 1–2 para conciliação. Trabalho de pesquisa de formatos pode começar antes.

- **IMP-01:** corpus sintético ou devidamente anonimizado de emissores prioritários, com resultado esperado por documento. Selecionar inicialmente poucos layouts identificados; medir linhas/valores recuperados, rejeições e diferenças de total por formato, com limiares registrados antes da homologação.
- **IMP-02:** importação em lote, identificação do formato, mapeamento CSV, correção acessível da prévia, explicação de rejeições e histórico do resultado. Vincular à conta/cartão correto.
- **IMP-03:** conciliação por identidade de origem e revisão de possíveis duplicatas entre cadastro manual, CSV, PDF e OFX; permitir resolver compras legítimas idênticas. Não multiplicar parcelas futuras ao importar uma parcela já cobrada.
- **IMP-04:** adicionar OFX com identificação da transação de origem, datas/fusos, tipos e sinais validados.
- **IMP-05:** OCR isolado para documentos escaneados, confiança por campo, revisão obrigatória e corpus próprio; não presumir valor/data ausentes. Pode entrar após o marco A, mantendo o limite de formatos explícito.
- **IMP-06:** quarentena, validação de formato/assinatura, antivírus e expurgo temporário; manter parser sem rede/credenciais. Definir estados de processamento, limites por usuário, retentativas, cancelamento e recuperação. Implantar fila/worker para OCR e lotes conforme necessidade demonstrada, com idempotência.

Aceite do marco A: formatos iniciais declarados homologados, prévia não grava, confirmação reconcilia e reenvio não duplica. Aceite do marco B: OFX/OCR e pipeline avançado homologados; falha/timeout preserva dados e libera recursos.

## Fase 4 — Jornada de uso e acabamento de interface

Dependência: fluxos das fases 1–3. A interface de cada recurso é entregue junto ao backend; esta fase integra e revisa a experiência.

- **UX-01:** primeiro uso orientado: conta, saldo inicial, cartão, renda, importação e primeira meta. Separar claramente demonstração e conta autenticada.
- **UX-02:** entrada rápida de gastos, filtros/busca, edição em lote apropriada, navegação consistente e revisão simples de importações; estados vazio, carregando, erro, conflito, offline e sessão expirada.
- **UX-03:** revisar design responsivo inspirado nas referências Nubank/Apple, identidade própria, hierarquia, botões confortáveis e temas claro/escuro. A skill unslop instalada pode apoiar a revisão; instalação não significa que o redesign foi executado.
- **UX-04:** teclado, foco, leitores de tela, contraste, alvos de toque e mensagens acessíveis; testes automáticos e revisão manual orientada a WCAG 2.2 AA. Validar Chromium e ao menos um segundo motor de navegador, desktop/mobile e tamanhos intermediários.
- **UX-05:** resumo mensal acionável com diferenças entre saldo, resultado, compromissos, margem e metas; alertas com evidência e caminho de correção.

Aceite: usuário de teste conclui cadastro financeiro, importação/revisão, pagamento e leitura do planejamento sem assistência; resultados consistentes entre telas; nenhum dado financeiro persiste no navegador após encerramento de sessão.

## Fase 5 — Confiabilidade local, privacidade técnica e aceite end-to-end

Dependência: fases 1–4. Segurança e testes são transversais; esta fase fecha as evidências antes de declarar o marco A.

- **REL-01:** um roteiro integrado com conta nova e login Keycloak/TOTP real: cadastrar contas/saldos/cartão → lançar/importar → revisar → reconciliar → pagar → transferir → planejar/aportar → exportar → encerrar/reabrir sessão. Incluir segundo usuário tentando acessar registros alheios e cenários negativos.
- **REL-02:** backup criptografado e restauração de PostgreSQL financeiro e de identidade em ambiente isolado; ensaio de atualização/migração com dados de versões anteriores, preservação de valores e rollback compatível. Definir RPO/RTO e medir resultados antes do aceite, incluindo guarda das chaves de recuperação.
- **REL-03:** RLS, papéis separados de aplicação/migração e privilégios mínimos; contexto do proprietário seguro no pool de conexões. Testar tentativas de acesso cruzado também por SQL e jobs, sem depender apenas de filtros ORM.
- **REL-04:** paginação, agregação no banco, limites de volume, índices medidos e exportação por lotes/assíncrona quando necessário. Remover carregamento ilimitado de dashboard/exportação e documentar limite do detector de assinaturas.
- **REL-05:** eventos de auditoria e logs estruturados mínimos com request-id, métricas e diagnóstico recuperável, sem descrições financeiras, códigos OAuth ou tokens. Testar indisponibilidade de banco/Redis/parser, falhas parciais, reinício, concorrência e reenvio de operações.
- **REL-06:** exportação/exclusão de todas as novas entidades; política de retenção, eliminação temporária e reaplicação de exclusões após restauração. Diferenciar apagar finanças e encerrar identidade/conta.
- **REL-07:** integrar todos os roteiros relevantes ao CI (incluindo cartões e regressão XSS), fixar imagens por digest, scans de imagens/segredos/SAST e atualização de dependências. Registrar e corrigir vulnerabilidades conforme severidade.
- **REL-08:** carga controlada no ambiente próprio, cotas persistentes contra crescimento de armazenamento e limites por endpoint; definir volume-alvo, orçamento de recursos e limites de latência/erro antes de medir. Otimizar com evidência, mantendo monólito modular até necessidade de separação.
- **REL-09:** instalação reproduzível em máquina limpa, scripts de inicialização/diagnóstico, manual completo, matriz requisito→teste e checklist de aceite. Organizar entregas futuras em PRs revisáveis e configurar proteções/checks obrigatórios da main se disponíveis no plano do GitHub; limitações do plano devem ser documentadas.

Aceite: jornada integrada verde, restauração comprovada, isolamento de usuários no banco, limites testados e nenhuma falha crítica conhecida em aberto. Login Google não bloqueia esse marco local.

## Fase 6 — Perfil e agentes de IA

Dependência: marco A e controles de privacidade técnica. Regras existentes continuam disponíveis como alternativa operacional.

- **IA-01:** perfil explícito de renda, prioridades, objetivos, restrições e preferências de recomendação; edição, exclusão e transparência sobre uso dos dados. Não inferir atributos sensíveis desnecessariamente.
- **IA-02:** camada de provedores, modelos/prompt versionados, tarefas em fila, saída com schema, limites de tempo/tokens/custo, cancelamento, fallback e trilha de decisão. Avaliar modelo local gratuito conforme memória/CPU disponíveis; não presumir que há infraestrutura suficiente ou contratar API sem decisão do usuário.
- **IA-03:** classificação assistida com evidência, confiança calibrada, revisão e aplicação explícita; aproveitar correções pessoais sem compartilhar dados entre usuários.
- **IA-04:** detectar possíveis desperdícios, alterações de padrão, assinaturas e compromissos com período/valores de evidência e estimativas explicadas. Recorrência não prova falta de uso, fraude ou economia.
- **IA-05:** recomendações de metas e perfil sujeitas ao cálculo financeiro determinístico; o modelo não calcula saldo autoritativo nem movimenta dinheiro.
- **IA-06:** minimização/redação antes da inferência, defesa contra instruções embutidas em documentos, ferramentas autorizadas por lista e avaliações com corpus anonimizado. Medir qualidade, falsos positivos e custo; registrar critérios de aceite antes de habilitar a funcionalidade.

Aceite: modelo efetivamente executado e avaliado, respostas estruturadas explicáveis, correções humanas persistidas com isolamento; sem alteração financeira silenciosa ou envio externo não autorizado. Mock de IA valida contrato, não qualidade.

## Fase 7 — Lista de desejos, preços e cupons

Dependência: planejamento confiável; comparação básica pode ser construída em paralelo à IA.

- **OFE-01:** lista de desejos com produto/nicho, prioridade, preço-alvo, prazo e vínculo à meta; inclusão manual funcional sem fornecedor externo.
- **OFE-02:** conectores autorizados para fontes de preço/cupom, normalização de produto/variante, histórico, atualização, validade, frete e custo total. Quotas, cache, indisponibilidade e links verificáveis.
- **OFE-03:** recomendação de momento de compra considerando orçamento e impacto nas metas; alertas sem executar compras. Informar afiliação/patrocínio e tratamento de dados.
- **OFE-04:** homologar fontes gratuitas que permitam esse uso. Caso não haja fonte adequada, manter cadastro/comparação manual e registrar integração automática como pendente, sem inventar ofertas ou considerar o escopo completo.

Aceite: preço/cupom verificável, data de consulta/validade e produto corretos; sugestão respeita caixa/compromissos e degrada claramente quando fonte falha.

## Fase 8 — Fechar identidade e integrar Google (adiada, preservada)

Dependência: jornada do marco A; retomar quando o produto estiver funcionalmente consolidado, conforme decisão do usuário.

- **AUT-01:** recuperação de MFA por códigos de uso único, geração/guarda, consumo atômico, recusa de reutilização, revogação e regeneração; fluxo de recuperação sem reduzir o segundo fator silenciosamente. Testar antes de liberar uso continuado sem intervenção administrativa.
- **AUT-02:** listar/revogar sessões, revogação global por usuário, sessões concorrentes, reautenticação recente para exportação/exclusão e mudanças sensíveis, logout federado e encerramento de conta/identidade.
- **AUT-03:** testes negativos de assinatura, issuer/audience, nonce/state, token expirado, replay e rotação de JWKS; recuperação e associação de contas com verificações proporcionais.
- **AUT-04:** adaptar localhost para Google, criar projeto OAuth em modo de teste, configurar credenciais por canal seguro e validar Google→Keycloak→TOTP→aplicação. Não depende de comprar domínio; depende da participação do titular na conta Google. Testes não interagem automaticamente com a conta pessoal do usuário.
- **AUT-05:** separar configuração local/produção, administrador nominal com MFA, remoção de bootstrap, imagem Keycloak otimizada, cookies __Host-/Secure quando houver HTTPS e migração versionada de realm existente.

Aceite: Google e recuperação reais validados com contas autorizadas, sem bypass de MFA/associação indevida e sem perda de segregação de dados. A recuperação bloqueia marco B; Google pode aguardar preparação do marco C.

## Fase 9 — LGPD operacional e produção

Dependência: marcos anteriores e decisões do responsável. Preparação documental/automação sem custo pode ocorrer antes; aquisição e publicação ficam adiadas.

- **PRO-01:** definir domínio, hospedagem/região, fornecedor de e-mail, orçamento, disponibilidade e responsáveis; infraestrutura como código, ambientes separados, secrets/rotação, TLS e rede privada para bancos/Redis com autenticação e criptografia adequadas.
- **PRO-02:** WAF/mitigação DDoS, proteção da origem, limites de conexões e IP real somente de proxies confiáveis. Homologar regras sem bloquear usuários legítimos; teste volumétrico somente em ambiente autorizado.
- **PRO-03:** observabilidade/alertas operacionais, quotas, capacidade, backups/restauração de produção, resposta a incidentes, deploy progressivo, rollback e continuidade. E-mails e notificações externas com preferências, entrega e prevenção de abuso.
- **LGPD-01:** identificar controlador/operadores/canal do titular, bases legais por finalidade, inventário e registro das operações, avaliação de impacto quando aplicável, política para menores, contratos, região/transferência internacional e avaliação de provedores de IA/ofertas.
- **LGPD-02:** aviso de privacidade e termos, retenção/expurgo por categoria, direitos e solicitações auditáveis, identidade/backup após exclusão, transparência/revisão de decisões automatizadas e comunicações de incidente revisadas juridicamente.
- **PRO-04:** SAST/DAST, scans contínuos, testes de carga/recuperação, revisão especializada e pentest externo antes da abertura pública; fechar achados bloqueantes e registrar riscos residuais e aceite.

Aceite: checklist funcional, segurança e LGPD aprovado com evidências; orçamento/responsabilidades definidos e autorização de publicação. Não existe garantia técnica de impedir todos os ataques; metas de mitigação, detecção e recuperação devem ser medidas.

## Acréscimos de planejamento e limites de escopo

Novos detalhamentos derivados da revisão, sem contratação: saldo com referência temporal; política de histórico/arquivamento; reenvio após exclusão; idempotência entre diferentes formatos; distinção previsto/realizado; cenário E2E único; matriz requisito→teste; restauração conjunta de finanças/identidade; critérios mensuráveis por formato/modelo e proteção contra conta inacessível. Eles fecham lacunas das entregas existentes e não são funcionalidades concluídas.

Preservados integralmente do plano anterior: Google/MFA/recuperação, LGPD, OCR/OFX, quarentena/antivírus, filas, agentes e perfil, desejos/preços/cupons, segurança, RLS, observabilidade, infraestrutura, backup/restore, carga/pentest e documentação profissional.

Integração bancária/Open Finance, aplicativo nativo de loja, sincronização financeira offline, investimentos e execução de pagamentos/compras não fazem parte do escopo mínimo definido nesta conversa. A sincronização bancária foi citada como limitação técnica nas entregas, não como integração já autorizada/obrigatória; permanece como possibilidade futura a definir, sem condicionar os marcos. Uma instalação PWA pode ser avaliada como conveniência do web app após a revisão UX, sem armazenar finanças offline automaticamente.

## Próxima entrega concreta

FIN-01 e FIN-02 foram implementados e homologados no incremento 0.5, com migração, interface, exportação/exclusão e testes de precisão/concorrência/isolamento. A parte correspondente de FIN-05 está em SALDOS.md; a revisão ampla de histórico e idempotência dos demais tipos de operação permanece pendente.

Entrega 0.6: renomeação/arquivamento/reativação de contas e cartões, versão contra edição obsoleta e exclusão de cadastros vazios preservando vínculos (CADASTROS.md). CI aprovado: 41882396599, commit 790e362.

Entrega 0.7: metas com versão, arquivamento/reativação, exclusão condicionada e planejamento apenas com ativas. CI aprovado: 41886542300, commit 4153e22.

Entrega 0.8: histórico privado para nove tipos de registro, consulta paginada, exportação/expurgo e revisão de concorrência (AUDITORIA.md), homologado no CI 41888034624.

Entrega 0.9: correção atômica de compras manuais com prévia, motivo e revisão; recibos de criação/pagamento/correção que preservam UUIDs após exclusão isolada. Migração 008 e testes homologados no CI 41892139036, código 961b0e0 (CORRECOES.md).

Próxima entrega: FIN-04 para edição de pagamentos, versão ampla de lançamentos e correção de importados; FIN-05 para importações após exclusão, idempotência entre formatos e contrato financeiro amplo. Em seguida, fase 2. Não conectar automaticamente o novo saldo à capacidade de aporte antes de fechar compromissos/projeção de caixa. Nenhuma decisão de domínio ou credencial Google bloqueia esse trabalho.
