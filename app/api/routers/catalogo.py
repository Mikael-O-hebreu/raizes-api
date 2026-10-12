from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from app.api import serializers as ser
from app.api.deps import Paginacao, exigir, get_db
from app.api.routers._comum import erros
from app.api.schemas import (CardapioItemOut, Pagina, ProdutoIn, ProdutoOut, PromocaoIn,
                             PromocaoOut, UnidadeIn, UnidadeOut)
from app.application import catalog_service
from app.application.pagination import paginar
from app.domain.enums import Perfil
from app.infrastructure.models import Produto, Promocao, Unidade

unidades = APIRouter(prefix="/unidades", tags=["Unidades e Cardápio"])
produtos = APIRouter(prefix="/produtos", tags=["Produtos"])
promocoes = APIRouter(prefix="/promocoes", tags=["Promoções"])
GERENTE = Depends(exigir(Perfil.GERENTE))


@unidades.get("", response_model=Pagina[UnidadeOut], summary="Lista as unidades da rede")
def listar_unidades(pag: Paginacao = Depends(), db=Depends(get_db)):
    itens, total = paginar(db, select(Unidade).where(Unidade.ativa.is_(True)).order_by(Unidade.id),
                           pag.page, pag.limit)
    return Pagina(items=[UnidadeOut(id=u.id, nome=u.nome, cidade=u.cidade) for u in itens],
                  page=pag.page, limit=pag.limit, total=total)


@unidades.post("", response_model=UnidadeOut, status_code=201, responses=erros(401, 403, 409, 422),
               summary="GERENTE cadastra unidade")
def criar_unidade(dados: UnidadeIn, db=Depends(get_db), ator=GERENTE):
    u = catalog_service.criar_unidade(db, ator, dados.nome, dados.cidade)
    return UnidadeOut(id=u.id, nome=u.nome, cidade=u.cidade)


@unidades.get("/{unidade_id}/cardapio", response_model=list[CardapioItemOut], responses=erros(404),
              summary="Cardápio da unidade (disponibilidade conforme estoque)")
def cardapio(unidade_id: int, db=Depends(get_db)):
    return [CardapioItemOut(**ser.produto(p).model_dump(), disponivel=qtd > 0)
            for p, qtd in catalog_service.cardapio(db, unidade_id)]


@produtos.get("", response_model=Pagina[ProdutoOut], summary="Lista produtos (paginado)")
def listar_produtos(pag: Paginacao = Depends(), categoria: str | None = Query(None),
                    db=Depends(get_db)):
    stmt = select(Produto).where(Produto.ativo.is_(True)).order_by(Produto.id)
    if categoria:
        stmt = stmt.where(Produto.categoria == categoria)
    itens, total = paginar(db, stmt, pag.page, pag.limit)
    return Pagina(items=[ser.produto(p) for p in itens], page=pag.page, limit=pag.limit, total=total)


@produtos.get("/{produto_id}", response_model=ProdutoOut, responses=erros(404))
def obter_produto(produto_id: int, db=Depends(get_db)):
    return ser.produto(catalog_service.obter_produto(db, produto_id))


@produtos.post("", response_model=ProdutoOut, status_code=201, responses=erros(401, 403, 409, 422),
               summary="GERENTE cadastra produto")
def criar_produto(dados: ProdutoIn, db=Depends(get_db), ator=GERENTE):
    return ser.produto(catalog_service.criar_produto(db, ator, **dados.model_dump()))


@produtos.put("/{produto_id}", response_model=ProdutoOut, responses=erros(401, 403, 404, 422),
              summary="GERENTE atualiza produto")
def atualizar_produto(produto_id: int, dados: ProdutoIn, db=Depends(get_db), ator=GERENTE):
    return ser.produto(catalog_service.atualizar_produto(db, ator, produto_id, **dados.model_dump()))


@produtos.delete("/{produto_id}", status_code=204, responses=erros(401, 403, 404),
                 summary="GERENTE desativa produto (exclusão lógica)")
def desativar_produto(produto_id: int, db=Depends(get_db), ator=GERENTE):
    catalog_service.desativar_produto(db, ator, produto_id)
    return Response(status_code=204)


@promocoes.get("", response_model=list[PromocaoOut], summary="Lista campanhas ativas")
def listar_promocoes(db=Depends(get_db)):
    return [ser.promocao(p) for p in db.scalars(select(Promocao).where(Promocao.ativa.is_(True)))]


@promocoes.post("", response_model=PromocaoOut, status_code=201, responses=erros(401, 403, 409, 422),
                summary="GERENTE cria campanha (desconto percentual aplicado no pedido via codigoPromocao)")
def criar_promocao(dados: PromocaoIn, db=Depends(get_db), ator=GERENTE):
    return ser.promocao(catalog_service.criar_promocao(
        db, ator, codigo=dados.codigo, descricao=dados.descricao, percentual=dados.percentual,
        valida_ate=dados.validaAte))
