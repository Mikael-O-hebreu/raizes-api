"""Pagamento via gateway externo SIMULADO: registro, resultado e tolerância a falhas."""
from typing import Optional

from sqlalchemy import select

from app.application import audit_service, loyalty_service, order_service
from app.domain.enums import (FormaPagamento, Perfil, SimulacaoPagamento, StatusPagamento,
                              StatusPedido)
from app.domain.errors import Conflito, NaoEncontrado
from app.infrastructure.models import Pagamento, Pedido, Usuario
from app.infrastructure.payment_gateway import GatewayIndisponivel, gateway_pagamento


def _executar(db, ator: Usuario, pedido: Pedido, pagamento: Pagamento,
              simulacao: SimulacaoPagamento) -> Pagamento:
    try:
        resp = gateway_pagamento.cobrar(valor=pedido.total, forma=pagamento.forma_pagamento,
                                        pedido_id=pedido.id, simulacao=simulacao)
    except GatewayIndisponivel as exc:
        # Tolerância a falhas: o pedido não é perdido; o pagamento fica PENDENTE para reconfirmação.
        pagamento.status = StatusPagamento.PENDENTE
        pagamento.mensagem = "Gateway indisponível. Confirme o pagamento novamente em instantes."
        pagamento.payload_gateway = {"gateway": "MockPay", "status": "timeout", "detail": str(exc)}
        audit_service.registrar(db, usuario_id=ator.id, acao="PAGAMENTO_PENDENTE",
                                entidade="pagamento", entidade_id=pagamento.id)
        return pagamento

    pagamento.status = resp.status
    pagamento.referencia_externa = resp.referencia
    pagamento.payload_gateway = resp.payload
    pagamento.mensagem = resp.mensagem
    if resp.status == StatusPagamento.APROVADO:
        pedido.status = StatusPedido.EM_PREPARO
        pontos = loyalty_service.creditar_por_pedido(db, pedido)
        audit_service.registrar(db, usuario_id=ator.id, acao="PAGAMENTO_APROVADO",
                                entidade="pagamento", entidade_id=pagamento.id,
                                detalhes={"pedidoId": pedido.id, "pontosGanhos": pontos})
    else:
        audit_service.registrar(db, usuario_id=ator.id, acao="PAGAMENTO_RECUSADO",
                                entidade="pagamento", entidade_id=pagamento.id,
                                detalhes={"pedidoId": pedido.id})
    return pagamento


def pagar(db, ator: Usuario, *, pedido_id: int, forma: Optional[FormaPagamento],
          simulacao: SimulacaoPagamento, idempotency_key: Optional[str]) -> Pagamento:
    pedido = order_service.obter_pedido(db, ator, pedido_id)

    if idempotency_key:
        existente = db.scalar(select(Pagamento).where(Pagamento.idempotency_key == idempotency_key))
        if existente and existente.pedido_id == pedido.id:
            return existente

    if pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO:
        raise Conflito(f"O pedido está {pedido.status.value} e não aceita novo pagamento.",
                       error="PEDIDO_NAO_AGUARDA_PAGAMENTO")
    if any(p.status == StatusPagamento.PENDENTE for p in pedido.pagamentos):
        raise Conflito("Já existe um pagamento pendente para este pedido. Use a confirmação.",
                       error="PAGAMENTO_PENDENTE_EXISTENTE")

    pagamento = Pagamento(pedido_id=pedido.id, status=StatusPagamento.PENDENTE,
                          forma_pagamento=forma or pedido.forma_pagamento, valor=pedido.total,
                          idempotency_key=idempotency_key)
    db.add(pagamento)
    db.flush()
    _executar(db, ator, pedido, pagamento, simulacao)
    db.commit()
    return pagamento


def obter_pagamento(db, ator: Usuario, pagamento_id: int) -> Pagamento:
    pag = db.get(Pagamento, pagamento_id)
    if not pag:
        raise NaoEncontrado("Pagamento não encontrado.", error="PAGAMENTO_NAO_ENCONTRADO")
    order_service.obter_pedido(db, ator, pag.pedido_id)  # garante que o cliente é o dono
    return pag


def confirmar(db, ator: Usuario, pagamento_id: int, simulacao: SimulacaoPagamento) -> Pagamento:
    """Reprocessa um pagamento PENDENTE (equivale ao webhook de confirmação do provedor)."""
    pag = obter_pagamento(db, ator, pagamento_id)
    if pag.status != StatusPagamento.PENDENTE:
        raise Conflito("Somente pagamentos pendentes podem ser confirmados.",
                       error="PAGAMENTO_NAO_PENDENTE")
    pedido = db.get(Pedido, pag.pedido_id)
    if pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO:
        raise Conflito("O pedido não aguarda mais pagamento.", error="PEDIDO_NAO_AGUARDA_PAGAMENTO")
    _executar(db, ator, pedido, pag, simulacao)
    db.commit()
    return pag
