"""Gateway de pagamento SIMULADO (mock). Nenhum pagamento real é processado."""
import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import FormaPagamento, SimulacaoPagamento, StatusPagamento


class GatewayIndisponivel(Exception):
    """Simula timeout/queda do provedor externo."""


@dataclass
class RespostaGateway:
    status: StatusPagamento
    referencia: str
    payload: dict
    mensagem: str


class GatewayPagamentoMock:
    def cobrar(self, *, valor: Decimal, forma: FormaPagamento, pedido_id: int,
               simulacao: SimulacaoPagamento) -> RespostaGateway:
        if simulacao == SimulacaoPagamento.TIMEOUT:
            raise GatewayIndisponivel("Gateway de pagamento não respondeu a tempo.")
        ref = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        base = {"gateway": "MockPay", "transactionId": ref, "orderRef": pedido_id,
                "amount": float(valor), "currency": "BRL", "method": forma.value}
        if simulacao == SimulacaoPagamento.RECUSADO:
            return RespostaGateway(
                StatusPagamento.RECUSADO, ref,
                {**base, "status": "declined", "reasonCode": "INSUFFICIENT_FUNDS"},
                "Pagamento recusado pelo emissor (simulação).")
        return RespostaGateway(
            StatusPagamento.APROVADO, ref,
            {**base, "status": "approved", "authorizationCode": uuid.uuid4().hex[:6].upper()},
            "Pagamento aprovado (simulação).")


gateway_pagamento = GatewayPagamentoMock()
