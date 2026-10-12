"""Exceções de negócio. A camada de API as converte para o JSON de erro padrão."""
from typing import Optional


class AppError(Exception):
    status_code = 400
    error = "ERRO"

    def __init__(self, message: str, *, error: Optional[str] = None,
                 details: Optional[list] = None):
        super().__init__(message)
        self.message = message
        if error:
            self.error = error
        self.details = details or []


class NaoAutenticado(AppError):
    status_code = 401
    error = "NAO_AUTENTICADO"

    def __init__(self, message: str = "Token ausente, inválido ou expirado.", **kw):
        super().__init__(message, **kw)


class SemPermissao(AppError):
    status_code = 403
    error = "SEM_PERMISSAO"

    def __init__(self, message: str = "Seu perfil não tem permissão para esta ação.", **kw):
        super().__init__(message, **kw)


class NaoEncontrado(AppError):
    status_code = 404
    error = "NAO_ENCONTRADO"


class Conflito(AppError):
    status_code = 409
    error = "CONFLITO"


class RegraInvalida(AppError):
    status_code = 422
    error = "REGRA_INVALIDA"
