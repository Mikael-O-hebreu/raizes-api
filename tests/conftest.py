import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.infrastructure import seed  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    seed.executar()
    with TestClient(app) as c:
        yield c


def _login(client, email, senha):
    r = client.post("/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture(scope="session")
def cliente_h(client):
    return _login(client, "cliente@raizes.com", "Cliente@123")


@pytest.fixture(scope="session")
def gerente_h(client):
    return _login(client, "gerente@raizes.com", "Gerente@123")


@pytest.fixture(scope="session")
def cozinha_h(client):
    return _login(client, "cozinha@raizes.com", "Cozinha@123")


@pytest.fixture(scope="session")
def atendente_h(client):
    return _login(client, "atendente@raizes.com", "Atendente@123")


def novo_pedido(client, headers, produto=4, qtd=1, unidade=1, canal="TOTEM", **extra):
    body = {"canalPedido": canal, "unidadeId": unidade,
            "itens": [{"produtoId": produto, "quantidade": qtd}], "formaPagamento": "MOCK", **extra}
    return client.post("/pedidos", json=body, headers=headers)
