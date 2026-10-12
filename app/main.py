"""Ponto de entrada: API REST da rede Raízes do Nordeste."""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.errors import registrar_handlers
from app.api.routers import auth_usuarios, catalogo, estoque, fidelidade_auditoria, pagamentos, pedidos
from app.infrastructure.database import criar_tabelas

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    criar_tabelas()
    yield


app = FastAPI(
    title="Raízes do Nordeste — API Back-End",
    version="1.0.0",
    description=("API REST da rede de lanchonetes Raízes do Nordeste (canais APP, TOTEM, BALCAO, "
                 "PICKUP e WEB). Autenticação JWT com perfis CLIENTE, ATENDENTE, COZINHA e GERENTE. "
                 "Pagamento SIMULADO (mock)."),
    lifespan=lifespan,
)
registrar_handlers(app)


@app.middleware("http")
async def request_id(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


for r in (auth_usuarios.auth, auth_usuarios.usuarios, catalogo.unidades, catalogo.produtos,
          catalogo.promocoes, estoque.router, pedidos.router, pagamentos.router,
          fidelidade_auditoria.fidelidade, fidelidade_auditoria.auditoria):
    app.include_router(r)


@app.get("/health", tags=["Infra"], summary="Verifica se a API está no ar")
def health():
    return {"status": "ok"}
