"""Regras de negócio puras (sem banco, sem HTTP). Fáceis de testar e explicar."""
from decimal import Decimal, ROUND_HALF_UP

from app.domain.enums import Perfil, StatusPedido

CENTAVO = Decimal("0.01")

# Fidelidade: 1 ponto por R$ 1,00 pago; 100 pontos = R$ 5,00 de desconto.
PONTOS_POR_REAL = 1
BLOCO_RESGATE_PONTOS = 100
VALOR_BLOCO_RESGATE = Decimal("5.00")

# Transições manuais de status e quem pode executá-las.
# (AGUARDANDO_PAGAMENTO -> EM_PREPARO só acontece via pagamento aprovado.)
TRANSICOES = {
    (StatusPedido.EM_PREPARO, StatusPedido.PRONTO): {Perfil.COZINHA, Perfil.GERENTE},
    (StatusPedido.PRONTO, StatusPedido.ENTREGUE): {Perfil.ATENDENTE, Perfil.GERENTE},
    (StatusPedido.AGUARDANDO_PAGAMENTO, StatusPedido.CANCELADO):
        {Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE},
    (StatusPedido.EM_PREPARO, StatusPedido.CANCELADO): {Perfil.ATENDENTE, Perfil.GERENTE},
    (StatusPedido.PRONTO, StatusPedido.CANCELADO): {Perfil.GERENTE},
}


def dinheiro(valor) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def transicao_existe(atual: StatusPedido, novo: StatusPedido) -> bool:
    return (atual, novo) in TRANSICOES


def perfil_pode_transicionar(perfil: Perfil, atual: StatusPedido, novo: StatusPedido) -> bool:
    return perfil in TRANSICOES.get((atual, novo), set())


def desconto_promocao(subtotal: Decimal, percentual: int) -> Decimal:
    return dinheiro(subtotal * Decimal(percentual) / Decimal(100))


def resgate_valido(pontos: int) -> bool:
    return pontos > 0 and pontos % BLOCO_RESGATE_PONTOS == 0


def desconto_resgate(pontos: int) -> Decimal:
    return VALOR_BLOCO_RESGATE * (pontos // BLOCO_RESGATE_PONTOS)


def pontos_ganhos(valor_pago: Decimal) -> int:
    return int(valor_pago) * PONTOS_POR_REAL
