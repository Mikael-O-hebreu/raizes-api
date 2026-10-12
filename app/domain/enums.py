"""Enumerações do domínio da rede Raízes do Nordeste."""
from enum import Enum


class Perfil(str, Enum):
    CLIENTE = "CLIENTE"
    ATENDENTE = "ATENDENTE"
    COZINHA = "COZINHA"
    GERENTE = "GERENTE"


class CanalPedido(str, Enum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class StatusPedido(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class StatusPagamento(str, Enum):
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    PENDENTE = "PENDENTE"
    ESTORNADO = "ESTORNADO"


class SimulacaoPagamento(str, Enum):
    """Controla o resultado do gateway mock (útil para testes)."""
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    TIMEOUT = "TIMEOUT"


class FormaPagamento(str, Enum):
    MOCK = "MOCK"
    PIX = "PIX"
    CARTAO = "CARTAO"


class TipoMovimentoEstoque(str, Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class TipoMovimentoFidelidade(str, Enum):
    GANHO = "GANHO"
    RESGATE = "RESGATE"
    ESTORNO = "ESTORNO"
