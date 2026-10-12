"""Cenários T01..T20 do plano de testes (positivos e negativos)."""
from tests.conftest import novo_pedido


# ---- Autenticação e autorização ----
def test_T01_login_valido(client):
    r = client.post("/auth/login", json={"email": "cliente@raizes.com", "senha": "Cliente@123"})
    assert r.status_code == 200 and r.json()["accessToken"] and r.json()["user"]["perfil"] == "CLIENTE"


def test_T02_sem_token_401(client):
    r = client.get("/pedidos")
    assert r.status_code == 401 and r.json()["error"] == "NAO_AUTENTICADO"
    assert set(r.json()) == {"error", "message", "details", "timestamp", "path", "requestId"}


def test_T03_login_invalido_401(client):
    r = client.post("/auth/login", json={"email": "cliente@raizes.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["error"] == "CREDENCIAIS_INVALIDAS"


def test_T04_perfil_sem_permissao_403(client, cliente_h):
    r = client.post("/produtos", headers=cliente_h,
                    json={"nome": "X Teste", "categoria": "Teste", "preco": 10})
    assert r.status_code == 403 and r.json()["error"] == "SEM_PERMISSAO"


# ---- Cadastro / LGPD ----
def test_T05_cadastro_cliente_201_sem_expor_senha(client):
    r = client.post("/usuarios", json={"nome": "Joana Teste", "email": "joana@teste.com",
                                       "senha": "Senha@1234", "consentimentoLgpd": True})
    assert r.status_code == 201 and "senha" not in r.text and "senha_hash" not in r.text


def test_T06_cadastro_sem_consentimento_422(client):
    r = client.post("/usuarios", json={"nome": "Sem Consent", "email": "sc@teste.com",
                                       "senha": "Senha@1234", "consentimentoLgpd": False})
    assert r.status_code == 422 and r.json()["error"] == "CONSENTIMENTO_LGPD_OBRIGATORIO"


def test_T07_email_invalido_422(client):
    r = client.post("/usuarios", json={"nome": "Email Ruim", "email": "nao-e-email",
                                       "senha": "Senha@1234", "consentimentoLgpd": True})
    assert r.status_code == 422 and r.json()["details"][0]["field"] == "email"


# ---- Pedido: regras de negócio ----
def test_T08_pedido_valido_201_com_canal(client, cliente_h):
    r = novo_pedido(client, cliente_h, produto=4, qtd=2, canal="APP")
    assert r.status_code == 201
    b = r.json()
    assert b["status"] == "AGUARDANDO_PAGAMENTO" and b["canalPedido"] == "APP" and b["total"] == 29.0


def test_T09_canal_ausente_422(client, cliente_h):
    r = client.post("/pedidos", headers=cliente_h,
                    json={"unidadeId": 1, "itens": [{"produtoId": 4, "quantidade": 1}]})
    assert r.status_code == 422 and r.json()["details"][0]["field"] == "canalPedido"


def test_T10_canal_invalido_422(client, cliente_h):
    r = novo_pedido(client, cliente_h, canal="TELEGRAMA")
    assert r.status_code == 422 and r.json()["details"][0]["field"] == "canalPedido"


def test_T11_quantidade_negativa_422(client, cliente_h):
    r = novo_pedido(client, cliente_h, qtd=-1)
    assert r.status_code == 422


def test_T12_produto_inexistente_404(client, cliente_h):
    r = novo_pedido(client, cliente_h, produto=9999)
    assert r.status_code == 404 and r.json()["error"] == "PRODUTO_NAO_ENCONTRADO"


def test_T13_unidade_inexistente_404(client, cliente_h):
    r = novo_pedido(client, cliente_h, unidade=9999)
    assert r.status_code == 404 and r.json()["error"] == "UNIDADE_NAO_ENCONTRADA"


def test_T14_estoque_insuficiente_409(client, cliente_h):
    r = novo_pedido(client, cliente_h, produto=5, qtd=50)  # estoque inicial 50, depois de 1 compra falha
    assert r.status_code == 201
    r2 = novo_pedido(client, cliente_h, produto=5, qtd=1)
    assert r2.status_code == 409 and r2.json()["error"] == "ESTOQUE_INSUFICIENTE"
    assert r2.json()["details"][0]["issue"] == "Disponível: 0"


def test_T15_filtro_por_canal(client, cliente_h):
    novo_pedido(client, cliente_h, canal="PICKUP")
    r = client.get("/pedidos?canalPedido=PICKUP", headers=cliente_h)
    assert r.status_code == 200 and r.json()["total"] >= 1
    assert all(p["canalPedido"] == "PICKUP" for p in r.json()["items"])


def test_T16_idempotencia_pedido(client, cliente_h):
    h = {**cliente_h, "Idempotency-Key": "chave-teste-1"}
    a = novo_pedido(client, h, produto=6)
    b = novo_pedido(client, h, produto=6)
    assert a.status_code == 201 and b.status_code == 200
    assert a.json()["pedidoId"] == b.json()["pedidoId"]


def test_T17_promocao_e_fidelidade(client, cliente_h):
    r = novo_pedido(client, cliente_h, produto=1, qtd=1, codigoPromocao="RAIZES10")
    assert r.status_code == 201 and r.json()["descontoPromocao"] == 2.89
    r2 = novo_pedido(client, cliente_h, produto=1, codigoPromocao="NAOEXISTE")
    assert r2.status_code == 422 and r2.json()["error"] == "PROMOCAO_INVALIDA"


# ---- Pagamento mock + status ----
def test_T18_pagamento_aprovado_atualiza_status_e_pontos(client, cliente_h, cozinha_h, atendente_h):
    pontos_antes = client.get("/fidelidade/saldo", headers=cliente_h).json()["pontos"]
    pid = novo_pedido(client, cliente_h, produto=2, qtd=1).json()["pedidoId"]  # R$ 32,50
    pag = client.post("/pagamentos", headers=cliente_h, json={"pedidoId": pid})
    assert pag.status_code == 201 and pag.json()["status"] == "APROVADO"
    assert pag.json()["payloadGateway"]["status"] == "approved"
    assert client.get(f"/pedidos/{pid}", headers=cliente_h).json()["status"] == "EM_PREPARO"
    assert client.get("/fidelidade/saldo", headers=cliente_h).json()["pontos"] == pontos_antes + 32
    # cozinha -> pronto -> atendente entrega
    assert client.patch(f"/pedidos/{pid}/status", headers=cozinha_h, json={"status": "PRONTO"}).status_code == 200
    assert client.patch(f"/pedidos/{pid}/status", headers=atendente_h, json={"status": "ENTREGUE"}).json()["status"] == "ENTREGUE"


def test_T19_pagamento_recusado(client, cliente_h):
    pid = novo_pedido(client, cliente_h, produto=7).json()["pedidoId"]
    pag = client.post("/pagamentos", headers=cliente_h, json={"pedidoId": pid, "simulacao": "RECUSADO"})
    assert pag.status_code == 201 and pag.json()["status"] == "RECUSADO"
    assert "recusado" in pag.json()["mensagem"].lower()
    assert client.get(f"/pedidos/{pid}", headers=cliente_h).json()["status"] == "AGUARDANDO_PAGAMENTO"


def test_T20_gateway_timeout_fica_pendente_e_confirma(client, cliente_h):
    pid = novo_pedido(client, cliente_h, produto=8).json()["pedidoId"]
    pag = client.post("/pagamentos", headers=cliente_h, json={"pedidoId": pid, "simulacao": "TIMEOUT"})
    assert pag.status_code == 202 and pag.json()["status"] == "PENDENTE"
    ok = client.post(f"/pagamentos/{pag.json()['pagamentoId']}/confirmar", headers=cliente_h, json={})
    assert ok.status_code == 200 and ok.json()["status"] == "APROVADO"


def test_T21_transicao_invalida_e_perfil(client, cliente_h, cozinha_h):
    pid = novo_pedido(client, cliente_h, produto=6).json()["pedidoId"]
    r = client.patch(f"/pedidos/{pid}/status", headers=cozinha_h, json={"status": "ENTREGUE"})
    assert r.status_code == 409 and r.json()["error"] == "TRANSICAO_INVALIDA"


def test_T22_cancelamento_devolve_estoque(client, cliente_h, gerente_h):
    antes = client.get("/estoque?unidadeId=2", headers=gerente_h).json()["items"]
    saldo = lambda: next(e["quantidade"] for e in client.get("/estoque?unidadeId=2&limit=100", headers=gerente_h).json()["items"] if e["produtoId"] == 3)
    inicio = saldo()
    pid = novo_pedido(client, cliente_h, produto=3, qtd=2, unidade=2).json()["pedidoId"]
    assert saldo() == inicio - 2
    r = client.post(f"/pedidos/{pid}/cancelar", headers=cliente_h)
    assert r.status_code == 200 and r.json()["status"] == "CANCELADO"
    assert saldo() == inicio and antes is not None


# ---- Estoque, Cardápio, Auditoria ----
def test_T23_cardapio_por_unidade_publico(client):
    r = client.get("/unidades/1/cardapio")
    assert r.status_code == 200 and len(r.json()) == 8 and "disponivel" in r.json()[0]


def test_T24_movimento_estoque_entrada_saida(client, gerente_h):
    e = client.post("/estoque/movimentos", headers=gerente_h,
                    json={"unidadeId": 3, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 10})
    assert e.status_code == 201 and e.json()["quantidade"] == 60
    s = client.post("/estoque/movimentos", headers=gerente_h,
                    json={"unidadeId": 3, "produtoId": 1, "tipo": "SAIDA", "quantidade": 999})
    assert s.status_code == 409


def test_T25_auditoria_registra_acoes_sensiveis(client, gerente_h):
    r = client.get("/auditoria?acao=PEDIDO_CRIADO", headers=gerente_h)
    assert r.status_code == 200 and r.json()["total"] >= 1


def test_T26_anonimizacao_lgpd(client):
    client.post("/usuarios", json={"nome": "Apagar Eu", "email": "apagar@teste.com",
                                   "senha": "Senha@1234", "consentimentoLgpd": True})
    h = {"Authorization": "Bearer " + client.post("/auth/login", json={"email": "apagar@teste.com", "senha": "Senha@1234"}).json()["accessToken"]}
    assert client.delete("/usuarios/me", headers=h).status_code == 204
    assert client.get("/usuarios/me", headers=h).status_code == 401
    assert client.post("/auth/login", json={"email": "apagar@teste.com", "senha": "Senha@1234"}).status_code == 401
