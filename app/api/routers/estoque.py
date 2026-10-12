from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import Paginacao, exigir, get_db
from app.api.routers._comum import erros
from app.api.schemas import EstoqueOut, MovimentoEstoqueIn, Pagina
from app.application import stock_service
from app.application.pagination import paginar
from app.domain.enums import Perfil
from app.infrastructure.models import Estoque

router = APIRouter(prefix="/estoque", tags=["Estoque"])
EQUIPE = Depends(exigir(Perfil.ATENDENTE, Perfil.COZINHA, Perfil.GERENTE))


def _out(e) -> EstoqueOut:
    return EstoqueOut(unidadeId=e.unidade_id, produtoId=e.produto_id, produtoNome=e.produto.nome,
                      quantidade=e.quantidade)


@router.get("", response_model=Pagina[EstoqueOut], responses=erros(401, 403),
            summary="Saldo de estoque por unidade (equipe)")
def consultar(unidadeId: int | None = Query(None), pag: Paginacao = Depends(),
              db=Depends(get_db), _=EQUIPE):
    stmt = select(Estoque).order_by(Estoque.unidade_id, Estoque.produto_id)
    if unidadeId:
        stmt = stmt.where(Estoque.unidade_id == unidadeId)
    itens, total = paginar(db, stmt, pag.page, pag.limit)
    return Pagina(items=[_out(e) for e in itens], page=pag.page, limit=pag.limit, total=total)


@router.post("/movimentos", response_model=EstoqueOut, status_code=201,
             responses=erros(401, 403, 404, 409, 422),
             summary="Entrada ou saída de estoque (ATENDENTE/GERENTE)")
def movimentar(dados: MovimentoEstoqueIn, db=Depends(get_db),
               ator=Depends(exigir(Perfil.ATENDENTE, Perfil.GERENTE))):
    linha = stock_service.movimentar_manual(
        db, ator, unidade_id=dados.unidadeId, produto_id=dados.produtoId, tipo=dados.tipo,
        quantidade=dados.quantidade, motivo=dados.motivo)
    return _out(linha)
