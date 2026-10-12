from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import Paginacao, exigir, get_db
from app.api.routers._comum import erros
from app.api.schemas import AuditOut, MovimentoFidelidadeOut, Pagina, SaldoOut
from app.application import loyalty_service
from app.application.pagination import paginar
from app.domain.enums import Perfil
from app.infrastructure.models import AuditLog, MovimentoFidelidade

fidelidade = APIRouter(prefix="/fidelidade", tags=["Fidelidade"])
auditoria = APIRouter(prefix="/auditoria", tags=["Auditoria"])
CLIENTE = Depends(exigir(Perfil.CLIENTE))


@fidelidade.get("/saldo", response_model=SaldoOut, responses=erros(401, 403),
                summary="Saldo de pontos do cliente logado")
def saldo(db=Depends(get_db), user=CLIENTE):
    return SaldoOut(pontos=loyalty_service.saldo(db, user.id))


@fidelidade.get("/historico", response_model=Pagina[MovimentoFidelidadeOut], responses=erros(401, 403))
def historico(pag: Paginacao = Depends(), db=Depends(get_db), user=CLIENTE):
    stmt = select(MovimentoFidelidade).where(MovimentoFidelidade.usuario_id == user.id) \
        .order_by(MovimentoFidelidade.id.desc())
    itens, total = paginar(db, stmt, pag.page, pag.limit)
    return Pagina(items=[MovimentoFidelidadeOut(id=m.id, tipo=m.tipo, pontos=m.pontos,
                                                pedidoId=m.pedido_id, createdAt=m.created_at)
                         for m in itens], page=pag.page, limit=pag.limit, total=total)


@auditoria.get("", response_model=Pagina[AuditOut], responses=erros(401, 403),
               summary="Trilha de auditoria (GERENTE). Filtro opcional: acao")
def listar(acao: Optional[str] = Query(None), pag: Paginacao = Depends(), db=Depends(get_db),
           _=Depends(exigir(Perfil.GERENTE))):
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if acao:
        stmt = stmt.where(AuditLog.acao == acao)
    itens, total = paginar(db, stmt, pag.page, pag.limit)
    return Pagina(items=[AuditOut(id=a.id, usuarioId=a.usuario_id, acao=a.acao, entidade=a.entidade,
                                  entidadeId=a.entidade_id, detalhes=a.detalhes, createdAt=a.created_at)
                         for a in itens], page=pag.page, limit=pag.limit, total=total)
