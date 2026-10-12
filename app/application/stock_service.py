"""Controle de estoque por unidade (entrada/saída e restrição de venda)."""
from sqlalchemy import select

from app.application import audit_service
from app.domain.enums import TipoMovimentoEstoque
from app.domain.errors import Conflito, NaoEncontrado
from app.infrastructure.models import Estoque, MovimentoEstoque, Produto, Unidade


def obter_linha(db, unidade_id: int, produto_id: int, travar: bool = False):
    stmt = select(Estoque).where(Estoque.unidade_id == unidade_id,
                                 Estoque.produto_id == produto_id)
    if travar:
        stmt = stmt.with_for_update()  # evita corrida em bancos com lock de linha (PostgreSQL)
    return db.scalar(stmt)


def movimentar(db, *, unidade_id: int, produto_id: int, tipo: TipoMovimentoEstoque,
               quantidade: int, motivo=None, usuario_id=None, pedido_id=None) -> Estoque:
    """Aplica um movimento SEM commit (o chamador controla a transação)."""
    linha = obter_linha(db, unidade_id, produto_id, travar=True)
    if linha is None:
        if tipo == TipoMovimentoEstoque.SAIDA:
            raise NaoEncontrado("Produto não é vendido nesta unidade.",
                                error="PRODUTO_INDISPONIVEL_NA_UNIDADE")
        if not db.get(Unidade, unidade_id):
            raise NaoEncontrado("Unidade não encontrada.", error="UNIDADE_NAO_ENCONTRADA")
        if not db.get(Produto, produto_id):
            raise NaoEncontrado("Produto não encontrado.", error="PRODUTO_NAO_ENCONTRADO")
        linha = Estoque(unidade_id=unidade_id, produto_id=produto_id, quantidade=0)
        db.add(linha)
        db.flush()
    if tipo == TipoMovimentoEstoque.SAIDA:
        if linha.quantidade < quantidade:
            raise Conflito("Estoque insuficiente para a saída solicitada.",
                           error="ESTOQUE_INSUFICIENTE",
                           details=[{"field": "quantidade",
                                     "issue": f"Disponível: {linha.quantidade}"}])
        linha.quantidade -= quantidade
    else:
        linha.quantidade += quantidade
    db.add(MovimentoEstoque(unidade_id=unidade_id, produto_id=produto_id, tipo=tipo,
                            quantidade=quantidade, motivo=motivo, usuario_id=usuario_id,
                            pedido_id=pedido_id))
    return linha


def movimentar_manual(db, ator, **dados) -> Estoque:
    linha = movimentar(db, usuario_id=ator.id, **dados)
    audit_service.registrar(db, usuario_id=ator.id, acao="ESTOQUE_MOVIMENTADO", entidade="estoque",
                            entidade_id=linha.id,
                            detalhes={"tipo": dados["tipo"].value, "quantidade": dados["quantidade"]})
    db.commit()
    return linha
