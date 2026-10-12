"""Contratos de request/response (documentados automaticamente no Swagger)."""
import re
from datetime import datetime
from typing import Annotated, Generic, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field, PlainSerializer, field_validator

from app.domain.enums import (CanalPedido, FormaPagamento, Perfil, SimulacaoPagamento,
                              StatusPagamento, StatusPedido, TipoMovimentoEstoque,
                              TipoMovimentoFidelidade)

Dt = Annotated[datetime, PlainSerializer(lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ"), return_type=str)]
T = TypeVar("T")


# ---------- erro padrão ----------
class DetalheErro(BaseModel):
    field: str
    issue: str


class ErroOut(BaseModel):
    error: str
    message: str
    details: list[DetalheErro] = []
    timestamp: str
    path: str
    requestId: str


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    page: int
    limit: int
    total: int


# ---------- entrada ----------
def _senha_forte(v: str) -> str:
    if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
        raise ValueError("A senha deve conter letras e números.")
    return v


class LoginIn(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=64)


class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=64)
    consentimentoLgpd: bool
    consentimentoFidelidade: bool = False
    _v = field_validator("senha")(_senha_forte)


class FuncionarioCriar(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=64)
    perfil: Perfil
    _v = field_validator("senha")(_senha_forte)

    @field_validator("perfil")
    @classmethod
    def _nao_cliente(cls, v):
        if v == Perfil.CLIENTE:
            raise ValueError("Use o cadastro público para clientes.")
        return v


class ConsentimentosIn(BaseModel):
    consentimentoFidelidade: bool


class UnidadeIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    cidade: str = Field(min_length=2, max_length=80)


class ProdutoIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    descricao: Optional[str] = Field(default=None, max_length=500)
    categoria: str = Field(min_length=2, max_length=60)
    preco: float = Field(gt=0, le=10000)


class MovimentoEstoqueIn(BaseModel):
    unidadeId: int
    produtoId: int
    tipo: TipoMovimentoEstoque
    quantidade: int = Field(gt=0, le=100000)
    motivo: Optional[str] = Field(default=None, max_length=120)


class ItemPedidoIn(BaseModel):
    produtoId: int
    quantidade: int = Field(gt=0, le=50)


class PedidoIn(BaseModel):
    canalPedido: CanalPedido
    clienteId: Optional[int] = Field(default=None, description="Obrigatório apenas para ATENDENTE/GERENTE")
    unidadeId: int
    itens: list[ItemPedidoIn] = Field(min_length=1, max_length=30)
    formaPagamento: FormaPagamento = FormaPagamento.MOCK
    codigoPromocao: Optional[str] = Field(default=None, max_length=30)
    resgatarPontos: int = Field(default=0, ge=0)


class StatusIn(BaseModel):
    status: StatusPedido


class PagamentoIn(BaseModel):
    pedidoId: int
    formaPagamento: Optional[FormaPagamento] = None
    simulacao: SimulacaoPagamento = Field(
        default=SimulacaoPagamento.APROVADO,
        description="Controla o resultado do gateway MOCK: APROVADO, RECUSADO ou TIMEOUT.")


class ConfirmarPagamentoIn(BaseModel):
    simulacao: SimulacaoPagamento = SimulacaoPagamento.APROVADO


class PromocaoIn(BaseModel):
    codigo: str = Field(min_length=3, max_length=30)
    descricao: str = Field(min_length=3, max_length=200)
    percentual: int = Field(ge=1, le=100)
    validaAte: Optional[datetime] = None


# ---------- saída ----------
class UsuarioResumo(BaseModel):
    id: int
    nome: str
    perfil: Perfil


class TokenOut(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    expiresIn: int
    user: UsuarioResumo


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    perfil: Perfil
    consentimentoLgpd: bool
    consentimentoFidelidade: bool
    createdAt: Dt


class UnidadeOut(BaseModel):
    id: int
    nome: str
    cidade: str


class ProdutoOut(BaseModel):
    id: int
    nome: str
    descricao: Optional[str]
    categoria: str
    preco: float


class CardapioItemOut(ProdutoOut):
    disponivel: bool


class EstoqueOut(BaseModel):
    unidadeId: int
    produtoId: int
    produtoNome: str
    quantidade: int


class ItemPedidoOut(BaseModel):
    produtoId: int
    quantidade: int
    precoUnitario: float


class PagamentoOut(BaseModel):
    pagamentoId: int
    pedidoId: int
    status: StatusPagamento
    formaPagamento: FormaPagamento
    valor: float
    mensagem: Optional[str]
    referenciaExterna: Optional[str]
    payloadGateway: Optional[dict]
    createdAt: Dt


class PedidoOut(BaseModel):
    pedidoId: int
    clienteId: int
    unidadeId: int
    canalPedido: CanalPedido
    status: StatusPedido
    subtotal: float
    descontoPromocao: float
    descontoFidelidade: float
    total: float
    codigoPromocao: Optional[str]
    pontosResgatados: int
    itens: list[ItemPedidoOut]
    createdAt: Dt


class SaldoOut(BaseModel):
    pontos: int


class MovimentoFidelidadeOut(BaseModel):
    id: int
    tipo: TipoMovimentoFidelidade
    pontos: int
    pedidoId: Optional[int]
    createdAt: Dt


class PromocaoOut(BaseModel):
    id: int
    codigo: str
    descricao: str
    percentual: int
    ativa: bool
    validaAte: Optional[Dt]


class AuditOut(BaseModel):
    id: int
    usuarioId: Optional[int]
    acao: str
    entidade: str
    entidadeId: Optional[int]
    detalhes: Optional[dict]
    createdAt: Dt
