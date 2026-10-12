from typing import Optional

from fastapi import APIRouter, Depends, Header, Response

from app.api import serializers as ser
from app.api.deps import exigir, get_db, usuario_atual
from app.api.routers._comum import erros
from app.api.schemas import ConfirmarPagamentoIn, PagamentoIn, PagamentoOut
from app.application import payment_service
from app.domain.enums import Perfil, StatusPagamento

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos (mock)"])
PAGADORES = Depends(exigir(Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE))


@router.post("", response_model=PagamentoOut, status_code=201,
             responses={**erros(401, 403, 404, 409, 422),
                        202: {"description": "Gateway indisponível: pagamento PENDENTE"}},
             summary="Solicita pagamento ao gateway SIMULADO (APROVADO / RECUSADO / TIMEOUT)")
def pagar(dados: PagamentoIn, response: Response,
          idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key", max_length=80),
          db=Depends(get_db), ator=PAGADORES):
    pag = payment_service.pagar(db, ator, pedido_id=dados.pedidoId, forma=dados.formaPagamento,
                                simulacao=dados.simulacao, idempotency_key=idempotency_key)
    if pag.status == StatusPagamento.PENDENTE:
        response.status_code = 202
    return ser.pagamento(pag)


@router.get("/{pagamento_id}", response_model=PagamentoOut, responses=erros(401, 404))
def obter(pagamento_id: int, db=Depends(get_db), ator=Depends(usuario_atual)):
    return ser.pagamento(payment_service.obter_pagamento(db, ator, pagamento_id))


@router.post("/{pagamento_id}/confirmar", response_model=PagamentoOut,
             responses=erros(401, 403, 404, 409),
             summary="Reprocessa pagamento PENDENTE (equivale ao webhook de confirmação)")
def confirmar(pagamento_id: int, dados: ConfirmarPagamentoIn, db=Depends(get_db), ator=PAGADORES):
    return ser.pagamento(payment_service.confirmar(db, ator, pagamento_id, dados.simulacao))
