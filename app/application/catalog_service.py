"""Unidades, produtos, cardápio por unidade e promoções."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.application import audit_service
from app.domain.errors import Conflito, NaoEncontrado
from app.infrastructure.models import Estoque, Produto, Promocao, Unidade


def criar_unidade(db, ator, nome: str, cidade: str) -> Unidade:
    if db.scalar(select(Unidade.id).where(Unidade.nome == nome)):
        raise Conflito("Já existe uma unidade com este nome.", error="UNIDADE_DUPLICADA")
    u = Unidade(nome=nome, cidade=cidade)
    db.add(u)
    db.flush()
    audit_service.registrar(db, usuario_id=ator.id, acao="UNIDADE_CRIADA", entidade="unidade",
                            entidade_id=u.id)
    db.commit()
    return u


def obter_unidade(db, unidade_id: int) -> Unidade:
    u = db.get(Unidade, unidade_id)
    if not u or not u.ativa:
        raise NaoEncontrado("Unidade não encontrada.", error="UNIDADE_NAO_ENCONTRADA")
    return u


def criar_produto(db, ator, **dados) -> Produto:
    if db.scalar(select(Produto.id).where(Produto.nome == dados["nome"])):
        raise Conflito("Já existe um produto com este nome.", error="PRODUTO_DUPLICADO")
    p = Produto(**dados)
    db.add(p)
    db.flush()
    audit_service.registrar(db, usuario_id=ator.id, acao="PRODUTO_CRIADO", entidade="produto",
                            entidade_id=p.id)
    db.commit()
    return p


def obter_produto(db, produto_id: int) -> Produto:
    p = db.get(Produto, produto_id)
    if not p or not p.ativo:
        raise NaoEncontrado("Produto não encontrado.", error="PRODUTO_NAO_ENCONTRADO")
    return p


def atualizar_produto(db, ator, produto_id: int, **dados) -> Produto:
    p = obter_produto(db, produto_id)
    for k, v in dados.items():
        setattr(p, k, v)
    audit_service.registrar(db, usuario_id=ator.id, acao="PRODUTO_ATUALIZADO", entidade="produto",
                            entidade_id=p.id)
    db.commit()
    return p


def desativar_produto(db, ator, produto_id: int) -> None:
    p = obter_produto(db, produto_id)
    p.ativo = False
    audit_service.registrar(db, usuario_id=ator.id, acao="PRODUTO_DESATIVADO", entidade="produto",
                            entidade_id=p.id)
    db.commit()


def cardapio(db, unidade_id: int):
    """Cardápio por unidade: produtos ativos da unidade; `disponivel` reflete o estoque."""
    obter_unidade(db, unidade_id)
    linhas = db.execute(
        select(Produto, Estoque.quantidade)
        .join(Estoque, Estoque.produto_id == Produto.id)
        .where(Estoque.unidade_id == unidade_id, Produto.ativo.is_(True))
        .order_by(Produto.categoria, Produto.nome)).all()
    return linhas


def criar_promocao(db, ator, *, codigo: str, descricao: str, percentual: int,
                   valida_ate: Optional[datetime]) -> Promocao:
    codigo = codigo.upper().strip()
    if db.scalar(select(Promocao.id).where(Promocao.codigo == codigo)):
        raise Conflito("Já existe uma promoção com este código.", error="PROMOCAO_DUPLICADA")
    promo = Promocao(codigo=codigo, descricao=descricao, percentual=percentual,
                     valida_ate=valida_ate)
    db.add(promo)
    db.flush()
    audit_service.registrar(db, usuario_id=ator.id, acao="PROMOCAO_CRIADA", entidade="promocao",
                            entidade_id=promo.id, detalhes={"codigo": codigo})
    db.commit()
    return promo
