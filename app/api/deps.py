"""Dependências: sessão de banco, usuário autenticado (JWT) e autorização por perfil."""
import jwt
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.enums import Perfil
from app.domain.errors import NaoAutenticado, SemPermissao
from app.infrastructure.database import SessionLocal
from app.infrastructure.models import Usuario
from app.infrastructure.security import decodificar_token

bearer = HTTPBearer(auto_error=False, description="Informe o accessToken retornado em POST /auth/login")


def get_db():
    with SessionLocal() as db:
        yield db


def usuario_atual(cred: HTTPAuthorizationCredentials = Depends(bearer),
                  db=Depends(get_db)) -> Usuario:
    if cred is None:
        raise NaoAutenticado()
    try:
        payload = decodificar_token(cred.credentials)
        user = db.get(Usuario, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise NaoAutenticado()
    if not user or not user.ativo:
        raise NaoAutenticado()
    return user


def exigir(*perfis: Perfil):
    def _dep(user: Usuario = Depends(usuario_atual)) -> Usuario:
        if user.perfil not in perfis:
            raise SemPermissao()
        return user
    return _dep


class Paginacao:
    def __init__(self, page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
        self.page, self.limit = page, limit
