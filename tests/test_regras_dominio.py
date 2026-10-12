from decimal import Decimal

from app.domain import rules
from app.domain.enums import Perfil, StatusPedido


def test_desconto_promocao():
    assert rules.desconto_promocao(Decimal("100.00"), 10) == Decimal("10.00")


def test_resgate_fidelidade():
    assert rules.resgate_valido(100) and not rules.resgate_valido(150)
    assert rules.desconto_resgate(200) == Decimal("10.00")


def test_transicoes_por_perfil():
    assert rules.perfil_pode_transicionar(Perfil.COZINHA, StatusPedido.EM_PREPARO, StatusPedido.PRONTO)
    assert not rules.perfil_pode_transicionar(Perfil.CLIENTE, StatusPedido.EM_PREPARO, StatusPedido.PRONTO)
    assert not rules.transicao_existe(StatusPedido.AGUARDANDO_PAGAMENTO, StatusPedido.ENTREGUE)
