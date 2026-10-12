"""Gera postman/raizes-do-nordeste.postman_collection.json (python scripts/gerar_postman.py)."""
import json
from pathlib import Path

ERRO_PADRAO = ('pm.test("Erro no formato padrão", () => { const b = pm.response.json(); '
               'pm.expect(b).to.have.all.keys("error","message","details","timestamp","path","requestId"); });')


def req(nome, metodo, caminho, token=None, body=None, status=200, extra="", headers=None, erro=False):
    h = [{"key": "Content-Type", "value": "application/json"}] + (headers or [])
    item = {"name": nome, "request": {"method": metodo, "header": h,
            "url": {"raw": "{{baseUrl}}" + caminho, "host": ["{{baseUrl}}"],
                    "path": [p for p in caminho.split("?")[0].split("/") if p],
                    "query": [{"key": k, "value": v} for k, v in
                              (q.split("=") for q in caminho.split("?")[1].split("&"))] if "?" in caminho else []}},
            "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": [
                f'pm.test("Status {status}", () => pm.response.to.have.status({status}));', extra]
                + ([ERRO_PADRAO] if erro else [])}}]}
    if token:
        item["request"]["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": "{{" + token + "}}", "type": "string"}]}
    else:
        item["request"]["auth"] = {"type": "noauth"}
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2, ensure_ascii=False),
                                   "options": {"raw": {"language": "json"}}}
    return item


def login(nome, email, senha, var, status=200, test_id=""):
    return req(nome, "POST", "/auth/login", None, {"email": email, "senha": senha}, status,
               f'pm.collectionVariables.set("{var}", pm.response.json().accessToken); '
               'pm.test("Retornou accessToken", () => pm.expect(pm.response.json().accessToken).to.be.a("string"));')


def pedido(canal="TOTEM", produto=4, qtd=1, unidade=1, **extra):
    return {"canalPedido": canal, "unidadeId": unidade,
            "itens": [{"produtoId": produto, "quantidade": qtd}], "formaPagamento": "MOCK", **extra}


def set_var(var, campo):
    return f'pm.collectionVariables.set("{var}", pm.response.json().{campo});'


pasta = lambda nome, itens: {"name": nome, "item": itens}

colecao = {
    "info": {"name": "Raízes do Nordeste — API Back-End",
             "description": "Execute as pastas NA ORDEM (Auth → Cardápio e Estoque → Pedidos e Pagamentos → Erros). "
                            "Pré-requisito: API rodando e seed aplicado. Variável baseUrl = http://localhost:8000.",
             "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
    "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}],
    "item": [
        pasta("1 - Auth", [
            login("T01 - Login válido (CLIENTE)", "cliente@raizes.com", "Cliente@123", "tokenCliente"),
            login("Setup - Login GERENTE", "gerente@raizes.com", "Gerente@123", "tokenGerente"),
            login("Setup - Login COZINHA", "cozinha@raizes.com", "Cozinha@123", "tokenCozinha"),
            login("Setup - Login ATENDENTE", "atendente@raizes.com", "Atendente@123", "tokenAtendente"),
            req("T05 - Cadastro de cliente com consentimento LGPD", "POST", "/usuarios", None,
                {"nome": "Cliente Postman", "email": "postman{{$timestamp}}@teste.com",
                 "senha": "Senha@1234", "consentimentoLgpd": True, "consentimentoFidelidade": True}, 201,
                'pm.test("Não expõe senha", () => pm.expect(pm.response.text()).to.not.include("senha"));'),
        ]),
        pasta("2 - Cardápio e Estoque", [
            req("T23 - Cardápio da unidade 1 (público)", "GET", "/unidades/1/cardapio", None, status=200,
                extra='pm.test("Tem itens", () => pm.expect(pm.response.json().length).to.be.above(0));'),
            req("Listar produtos (paginado)", "GET", "/produtos?page=1&limit=5", None, status=200,
                extra='pm.test("Paginação", () => pm.expect(pm.response.json()).to.have.keys("items","page","limit","total"));'),
            req("GERENTE cria produto", "POST", "/produtos", "tokenGerente",
                {"nome": "Produto Postman {{$timestamp}}", "descricao": "Teste", "categoria": "Teste", "preco": 15.5}, 201),
            req("T24 - Entrada de estoque (GERENTE)", "POST", "/estoque/movimentos", "tokenGerente",
                {"unidadeId": 3, "produtoId": 1, "tipo": "ENTRADA", "quantidade": 10, "motivo": "Reposição"}, 201),
            req("Consultar estoque da unidade 1 (equipe)", "GET", "/estoque?unidadeId=1&limit=20", "tokenAtendente"),
        ]),
        pasta("3 - Pedidos e Pagamentos (Fluxo A)", [
            req("T08 - Criar pedido (canal TOTEM)", "POST", "/pedidos", "tokenCliente", pedido("TOTEM", 4, 2), 201,
                set_var("pedidoId", "pedidoId") + 'pm.test("Status inicial e canal", () => { const b = pm.response.json(); '
                'pm.expect(b.status).to.eql("AGUARDANDO_PAGAMENTO"); pm.expect(b.canalPedido).to.eql("TOTEM"); });'),
            req("Criar pedido com promoção RAIZES10 (canal APP)", "POST", "/pedidos", "tokenCliente",
                pedido("APP", 1, 1, codigoPromocao="RAIZES10"), 201,
                'pm.test("Desconto aplicado", () => pm.expect(pm.response.json().descontoPromocao).to.eql(2.89));'),
            req("T15 - Filtrar pedidos por canal (TOTEM)", "GET", "/pedidos?canalPedido=TOTEM", "tokenCliente", status=200,
                extra='pm.test("Só TOTEM", () => pm.response.json().items.forEach(p => pm.expect(p.canalPedido).to.eql("TOTEM")));'),
            req("T18 - Pagamento mock APROVADO", "POST", "/pagamentos", "tokenCliente",
                {"pedidoId": "{{pedidoId}}", "simulacao": "APROVADO"}, 201,
                'pm.test("Aprovado + payload do gateway", () => { const b = pm.response.json(); '
                'pm.expect(b.status).to.eql("APROVADO"); pm.expect(b.payloadGateway.status).to.eql("approved"); });'),
            req("Pedido passou para EM_PREPARO", "GET", "/pedidos/{{pedidoId}}", "tokenCliente", status=200,
                extra='pm.test("EM_PREPARO", () => pm.expect(pm.response.json().status).to.eql("EM_PREPARO"));'),
            req("COZINHA marca PRONTO", "PATCH", "/pedidos/{{pedidoId}}/status", "tokenCozinha", {"status": "PRONTO"}),
            req("ATENDENTE marca ENTREGUE", "PATCH", "/pedidos/{{pedidoId}}/status", "tokenAtendente", {"status": "ENTREGUE"}, 200,
                'pm.test("ENTREGUE", () => pm.expect(pm.response.json().status).to.eql("ENTREGUE"));'),
            req("Saldo de fidelidade", "GET", "/fidelidade/saldo", "tokenCliente", status=200,
                extra='pm.test("Tem pontos", () => pm.expect(pm.response.json().pontos).to.be.above(0));'),
            req("Criar pedido p/ pagamento recusado", "POST", "/pedidos", "tokenCliente", pedido("WEB", 7), 201, set_var("pedidoId2", "pedidoId")),
            req("T19 - Pagamento mock RECUSADO", "POST", "/pagamentos", "tokenCliente",
                {"pedidoId": "{{pedidoId2}}", "simulacao": "RECUSADO"}, 201,
                'pm.test("Recusado com mensagem", () => { const b = pm.response.json(); pm.expect(b.status).to.eql("RECUSADO"); pm.expect(b.mensagem).to.include("recusado"); });'),
            req("Pedido segue AGUARDANDO_PAGAMENTO", "GET", "/pedidos/{{pedidoId2}}", "tokenCliente", status=200,
                extra='pm.test("Aguardando", () => pm.expect(pm.response.json().status).to.eql("AGUARDANDO_PAGAMENTO"));'),
            req("Criar pedido p/ timeout do gateway", "POST", "/pedidos", "tokenCliente", pedido("PICKUP", 8), 201, set_var("pedidoId3", "pedidoId")),
            req("T20 - Gateway indisponível → PENDENTE", "POST", "/pagamentos", "tokenCliente",
                {"pedidoId": "{{pedidoId3}}", "simulacao": "TIMEOUT"}, 202,
                set_var("pagamentoId3", "pagamentoId") + 'pm.test("Pendente", () => pm.expect(pm.response.json().status).to.eql("PENDENTE"));'),
            req("Confirmar pagamento pendente", "POST", "/pagamentos/{{pagamentoId3}}/confirmar", "tokenCliente", {"simulacao": "APROVADO"}, 200,
                'pm.test("Aprovado", () => pm.expect(pm.response.json().status).to.eql("APROVADO"));'),
            req("T22 - Cancelar pedido (devolve estoque)", "POST", "/pedidos/{{pedidoId2}}/cancelar", "tokenCliente", None, 200,
                'pm.test("Cancelado", () => pm.expect(pm.response.json().status).to.eql("CANCELADO"));'),
            req("T25 - Auditoria registra PEDIDO_CRIADO (GERENTE)", "GET", "/auditoria?acao=PEDIDO_CRIADO", "tokenGerente", status=200,
                extra='pm.test("Há registros", () => pm.expect(pm.response.json().total).to.be.above(0));'),
        ]),
        pasta("4 - Erros (cenários negativos)", [
            req("T02 - Listar pedidos sem token (401)", "GET", "/pedidos", None, status=401, erro=True),
            req("T03 - Login com senha errada (401)", "POST", "/auth/login", None,
                {"email": "cliente@raizes.com", "senha": "senhaerrada1"}, 401, erro=True),
            req("T04 - CLIENTE tenta criar produto (403)", "POST", "/produtos", "tokenCliente",
                {"nome": "Proibido", "categoria": "X", "preco": 10}, 403, erro=True),
            req("T06 - Cadastro sem consentimento LGPD (422)", "POST", "/usuarios", None,
                {"nome": "Sem Consent", "email": "sc{{$timestamp}}@teste.com", "senha": "Senha@1234", "consentimentoLgpd": False}, 422, erro=True),
            req("T07 - E-mail inválido (422)", "POST", "/usuarios", None,
                {"nome": "Email Ruim", "email": "nao-e-email", "senha": "Senha@1234", "consentimentoLgpd": True}, 422, erro=True),
            req("T09 - Pedido sem canalPedido (422)", "POST", "/pedidos", "tokenCliente",
                {"unidadeId": 1, "itens": [{"produtoId": 4, "quantidade": 1}]}, 422, erro=True),
            req("T11 - Quantidade negativa (422)", "POST", "/pedidos", "tokenCliente", pedido("APP", 4, -1), 422, erro=True),
            req("T12 - Produto inexistente (404)", "POST", "/pedidos", "tokenCliente", pedido("APP", 9999), 404, erro=True),
            req("T13 - Unidade inexistente (404)", "POST", "/pedidos", "tokenCliente", pedido("APP", 4, 1, 9999), 404, erro=True),
            req("T14 - Estoque insuficiente (409)", "POST", "/pedidos", "tokenCliente",
                {"canalPedido": "APP", "unidadeId": 2, "itens": [{"produtoId": 5, "quantidade": 50}, {"produtoId": 5, "quantidade": 50}]},
                409, 'pm.test("ESTOQUE_INSUFICIENTE", () => pm.expect(pm.response.json().error).to.eql("ESTOQUE_INSUFICIENTE"));', erro=True),
            req("T21 - Transição de status inválida (409)", "PATCH", "/pedidos/{{pedidoId3}}/status", "tokenCozinha", {"status": "ENTREGUE"}, 409, erro=True),
            req("Pedido inexistente (404)", "GET", "/pedidos/999999", "tokenCliente", status=404, erro=True),
        ]),
    ],
}
saida = Path(__file__).resolve().parent.parent / "postman" / "raizes-do-nordeste.postman_collection.json"
saida.write_text(json.dumps(colecao, indent=2, ensure_ascii=False), encoding="utf-8")
print("Coleção gerada:", saida)
