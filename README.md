# Raízes do Nordeste — API Back-End

API REST da rede de lanchonetes **Raízes do Nordeste**, desenvolvida para o Projeto Multidisciplinar (Trilha Back-End, Uninter).
Atende múltiplos canais (`APP`, `TOTEM`, `BALCAO`, `PICKUP`, `WEB`), com autenticação JWT por perfil, controle de estoque por unidade, pedidos, pagamento **simulado (mock)**, fidelidade e auditoria.

## Links e evidências
- Repositório: https://github.com/Mikael-O-hebreu/raizes-do-nordeste-api
- Swagger local: http://localhost:8000/docs (contrato exportado em `docs/openapi.json`)
- Coleção Postman: `postman/raizes-do-nordeste.postman_collection.json`
- DER e diagramas: pasta `docs/`

## Requisitos
- Python 3.11 ou superior (testado em 3.12)
- Banco: SQLite (já incluso no Python, nenhuma instalação). Para PostgreSQL, basta trocar `DATABASE_URL`.
- Dependências em `requirements.txt` (FastAPI, SQLAlchemy, PyJWT, bcrypt, pytest)

## Como executar (passo a passo)
```bash
# 1. clonar e entrar na pasta
git clone https://github.com/Mikael-O-hebreu/raizes-do-nordeste-api.git && cd raizes-do-nordeste-api

# 2. ambiente virtual e dependências
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. variáveis de ambiente
cp .env.example .env               # Windows: copy .env.example .env
# (opcional) edite JWT_SECRET e DATABASE_URL

# 4. criar tabelas e carregar dados iniciais (seed)
python -m app.infrastructure.seed

# 5. iniciar a API
uvicorn app.main:app --reload --port 8000
```
As tabelas também são criadas automaticamente na subida da API (SQLAlchemy ORM).

### Swagger / OpenAPI
Abra http://localhost:8000/docs. Para testar rotas protegidas: faça `POST /auth/login`, copie o `accessToken` e clique em **Authorize**.

### Usuários do seed
| Perfil | E-mail | Senha |
|---|---|---|
| GERENTE | gerente@raizes.com | Gerente@123 |
| ATENDENTE | atendente@raizes.com | Atendente@123 |
| COZINHA | cozinha@raizes.com | Cozinha@123 |
| CLIENTE | cliente@raizes.com | Cliente@123 |

O seed também cria 3 unidades, 8 produtos (50 un. de estoque em cada unidade) e a promoção `RAIZES10` (10%).

## Como rodar os testes
**Automatizados (pytest, usa banco temporário e não precisa da API no ar):**
```bash
pytest -q
```
**Postman/Insomnia:** importe `postman/raizes-do-nordeste.postman_collection.json`, mantenha `baseUrl = http://localhost:8000`, com a API no ar e o seed aplicado, e execute as pastas **na ordem** (1 Auth → 2 Cardápio e Estoque → 3 Pedidos e Pagamentos → 4 Erros) pelo *Collection Runner*. Tokens e ids são salvos automaticamente em variáveis da coleção. Pela linha de comando: `npx newman run postman/raizes-do-nordeste.postman_collection.json`.

## Arquitetura (camadas)
```
app/
├── domain/          # Regras puras: enums, exceções, transições de status, fidelidade, descontos
├── application/     # Casos de uso: pedido, pagamento, estoque, fidelidade, auth, auditoria
├── infrastructure/  # ORM (SQLAlchemy), JWT/bcrypt, gateway de pagamento mock, seed
└── api/             # Routers, schemas (contratos), autenticação/roles, erro padrão
```

## Fluxo crítico entregue (Fluxo A)
`POST /pedidos` (valida itens/estoque, aplica promoção e resgate de pontos, registra `canalPedido`) → `POST /pagamentos` (gateway MOCK: `APROVADO`, `RECUSADO` ou `TIMEOUT`) → status do pedido atualizado (`AGUARDANDO_PAGAMENTO → EM_PREPARO → PRONTO → ENTREGUE`, ou `CANCELADO`).

## Regras de negócio principais
- `canalPedido` é obrigatório e validado (422 se ausente ou inválido); `GET /pedidos?canalPedido=TOTEM` filtra por canal.
- Estoque é por unidade; é reservado na criação do pedido (409 `ESTOQUE_INSUFICIENTE` se faltar) e devolvido no cancelamento.
- Idempotência: header `Idempotency-Key` em `POST /pedidos` e `POST /pagamentos`.
- Pagamento mock: aprovado move o pedido para `EM_PREPARO`; recusado mantém `AGUARDANDO_PAGAMENTO`; `TIMEOUT` deixa o pagamento `PENDENTE` (tolerância a falhas) e `POST /pagamentos/{id}/confirmar` reprocessa.
- Fidelidade: 1 ponto por R$ 1,00 pago; resgate em múltiplos de 100 pontos (= R$ 5,00), somente com consentimento.
- Permissões de status: COZINHA (`EM_PREPARO→PRONTO`), ATENDENTE (`PRONTO→ENTREGUE`), cancelamento conforme perfil.

## Padrão de erro (todas as falhas)
```json
{ "error": "ESTOQUE_INSUFICIENTE", "message": "Não há quantidade suficiente para um ou mais itens.",
  "details": [{"field": "itens[0].quantidade", "issue": "Disponível: 1"}],
  "timestamp": "2026-10-11T12:00:00Z", "path": "/pedidos", "requestId": "uuid" }
```

## Segurança e LGPD
| Dado pessoal | Finalidade | Base legal |
|---|---|---|
| Nome, e-mail | Identificação, login e emissão de pedido | Execução de contrato / consentimento (cadastro) |
| Senha | Autenticação (guardada apenas como **hash bcrypt**) | Execução de contrato |
| Pontos e histórico de pedidos | Programa de fidelidade | **Consentimento** específico (`consentimentoFidelidade`, com data) |

- Consentimento LGPD obrigatório no cadastro (registrado com data/hora); consentimento de fidelidade separado e revogável (`PATCH /usuarios/me/consentimentos`).
- Minimização: o cadastro coleta apenas nome, e-mail e senha; respostas nunca retornam `senha_hash`.
- Direito de eliminação: `DELETE /usuarios/me` anonimiza o usuário (pedidos permanecem sem vínculo identificável, por obrigação fiscal).
- Auditoria (`audit_logs` + `GET /auditoria`): login, criação/cancelamento de pedido, mudança de status, pagamentos, movimentos de estoque e **leitura de dados pessoais** por gerentes.
- JWT com expiração (`JWT_EXPIRES_SECONDS`) e autorização por perfil em cada endpoint.

## Limitações conhecidas (declaradas)
- Pagamento totalmente simulado; não há integração real.
- Sem refresh token / logout (o token expira em 1 hora).
- Migrações via `create_all` do ORM (sem Alembic).
