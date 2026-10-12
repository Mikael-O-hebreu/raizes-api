"""Padrão ÚNICO de erro: {error, message, details[], timestamp, path, requestId}."""
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import AppError

logger = logging.getLogger("raizes.api")

_CODIGOS_HTTP = {404: "ROTA_NAO_ENCONTRADA", 405: "METODO_NAO_PERMITIDO", 401: "NAO_AUTENTICADO",
                 403: "SEM_PERMISSAO"}


def _resposta(request: Request, status: int, error: str, message: str, details=None):
    return JSONResponse(status_code=status, content={
        "error": error, "message": message, "details": details or [],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path": request.url.path,
        "requestId": getattr(request.state, "request_id", ""),
    })


def _campo(loc) -> str:
    partes = [p for p in loc if p not in ("body",)]
    texto = ""
    for p in partes:
        texto += f"[{p}]" if isinstance(p, int) else (f".{p}" if texto else str(p))
    return texto or "body"


def _traduzir(erro: dict) -> str:
    if erro["type"] == "missing":
        return "Campo obrigatório"
    if erro["type"] in ("enum", "literal_error"):
        return f"Valor inválido. Esperado: {erro.get('ctx', {}).get('expected', '')}"
    return erro["msg"]


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return _resposta(request, exc.status_code, exc.error, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, exc: RequestValidationError):
        detalhes = [{"field": _campo(e["loc"]), "issue": _traduzir(e)} for e in exc.errors()]
        return _resposta(request, 422, "VALIDACAO_FALHOU",
                         "Os dados enviados são inválidos.", detalhes)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codigo = _CODIGOS_HTTP.get(exc.status_code, "ERRO_HTTP")
        return _resposta(request, exc.status_code, codigo, str(exc.detail))

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):
        logger.exception("Erro inesperado")
        return _resposta(request, 500, "ERRO_INTERNO", "Erro interno. Tente novamente mais tarde.")
