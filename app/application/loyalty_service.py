"""Programa de fidelidade: pontos ganhos por pedido pago e resgate (com consentimento)."""
from sqlalchemy import func, select

from app.domain import rules
from app.domain.enums import TipoMovimentoFidelidade as Tipo
from app.domain.errors import Conflito, RegraInvalida
from app.infrastructure.models import MovimentoFidelidade, Pedido, Usuario


def saldo(db, usuario_id: int) -> int:
    return db.scalar(select(func.coalesce(func.sum(MovimentoFidelidade.pontos), 0))
                     .where(MovimentoFidelidade.usuario_id == usuario_id)) or 0


def validar_resgate(db, cliente: Usuario, pontos: int) -> None:
    if not cliente.consentimento_fidelidade:
        raise RegraInvalida("O cliente não consentiu com o programa de fidelidade.",
                            error="CONSENTIMENTO_FIDELIDADE_NECESSARIO",
                            details=[{"field": "resgatarPontos", "issue": "Sem consentimento"}])
    if not rules.resgate_valido(pontos):
        raise RegraInvalida(f"O resgate deve ser múltiplo de {rules.BLOCO_RESGATE_PONTOS} pontos.",
                            error="RESGATE_INVALIDO",
                            details=[{"field": "resgatarPontos", "issue": "Valor inválido"}])
    if saldo(db, cliente.id) < pontos:
        raise Conflito("Saldo de pontos insuficiente.", error="SALDO_PONTOS_INSUFICIENTE",
                       details=[{"field": "resgatarPontos",
                                 "issue": f"Saldo: {saldo(db, cliente.id)}"}])


def registrar_resgate(db, cliente_id: int, pedido_id: int, pontos: int) -> None:
    db.add(MovimentoFidelidade(usuario_id=cliente_id, pedido_id=pedido_id,
                               tipo=Tipo.RESGATE, pontos=-pontos))


def creditar_por_pedido(db, pedido: Pedido) -> int:
    cliente = db.get(Usuario, pedido.cliente_id)
    if not cliente or not cliente.consentimento_fidelidade:
        return 0
    pontos = rules.pontos_ganhos(pedido.total)
    if pontos > 0:
        db.add(MovimentoFidelidade(usuario_id=cliente.id, pedido_id=pedido.id,
                                   tipo=Tipo.GANHO, pontos=pontos))
    return pontos


def estornar_pedido(db, pedido: Pedido) -> None:
    """Cancelamento: devolve pontos resgatados e retira os pontos ganhos."""
    movs = db.scalars(select(MovimentoFidelidade).where(
        MovimentoFidelidade.pedido_id == pedido.id,
        MovimentoFidelidade.tipo.in_([Tipo.GANHO, Tipo.RESGATE]))).all()
    for m in movs:
        db.add(MovimentoFidelidade(usuario_id=m.usuario_id, pedido_id=pedido.id,
                                   tipo=Tipo.ESTORNO, pontos=-m.pontos))
