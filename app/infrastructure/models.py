"""Modelo de dados (ORM). Espelha o DER entregue na documentação."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Enum as SAEnum,
                        ForeignKey, Integer, Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (CanalPedido, FormaPagamento, Perfil, StatusPagamento,
                              StatusPedido, TipoMovimentoEstoque, TipoMovimentoFidelidade)
from app.infrastructure.database import Base


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _enum(e):
    return SAEnum(e, native_enum=False, length=30, validate_strings=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    perfil: Mapped[Perfil] = mapped_column(_enum(Perfil))
    consentimento_lgpd: Mapped[bool] = mapped_column(Boolean, default=False)
    consentimento_lgpd_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consentimento_fidelidade: Mapped[bool] = mapped_column(Boolean, default=False)
    consentimento_fidelidade_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    anonimizado_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Unidade(Base):
    __tablename__ = "unidades"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    cidade: Mapped[str] = mapped_column(String(80))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Produto(Base):
    __tablename__ = "produtos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    descricao: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    categoria: Mapped[str] = mapped_column(String(60))
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Estoque(Base):
    """Saldo de um produto em uma unidade (cada unidade tem estoque próprio)."""
    __tablename__ = "estoques"
    __table_args__ = (UniqueConstraint("unidade_id", "produto_id"),
                      CheckConstraint("quantidade >= 0"))
    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    produto: Mapped[Produto] = relationship()


class MovimentoEstoque(Base):
    __tablename__ = "movimentos_estoque"
    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    tipo: Mapped[TipoMovimentoEstoque] = mapped_column(_enum(TipoMovimentoEstoque))
    quantidade: Mapped[int] = mapped_column(Integer)
    motivo: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    pedido_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pedidos.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Promocao(Base):
    __tablename__ = "promocoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    descricao: Mapped[str] = mapped_column(String(200))
    percentual: Mapped[int] = mapped_column(Integer)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    valida_ate: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Pedido(Base):
    __tablename__ = "pedidos"
    __table_args__ = (UniqueConstraint("cliente_id", "idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"), index=True)
    canal_pedido: Mapped[CanalPedido] = mapped_column(_enum(CanalPedido), index=True)
    status: Mapped[StatusPedido] = mapped_column(_enum(StatusPedido), index=True)
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(_enum(FormaPagamento))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    desconto_promocao: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    desconto_fidelidade: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    codigo_promocao: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    pontos_resgatados: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=agora)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=agora, onupdate=agora)
    itens: Mapped[list["ItemPedido"]] = relationship(cascade="all, delete-orphan",
                                                    order_by="ItemPedido.id")
    pagamentos: Mapped[list["Pagamento"]] = relationship(order_by="Pagamento.id")


class ItemPedido(Base):
    __tablename__ = "itens_pedido"
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    quantidade: Mapped[int] = mapped_column(Integer)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class Pagamento(Base):
    """Pagamento desacoplado do pedido (um pedido pode ter várias tentativas)."""
    __tablename__ = "pagamentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), index=True)
    status: Mapped[StatusPagamento] = mapped_column(_enum(StatusPagamento))
    forma_pagamento: Mapped[FormaPagamento] = mapped_column(_enum(FormaPagamento))
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    referencia_externa: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    payload_gateway: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    mensagem: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=agora)


class MovimentoFidelidade(Base):
    __tablename__ = "movimentos_fidelidade"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    pedido_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pedidos.id"), nullable=True)
    tipo: Mapped[TipoMovimentoFidelidade] = mapped_column(_enum(TipoMovimentoFidelidade))
    pontos: Mapped[int] = mapped_column(Integer)  # positivo = crédito, negativo = débito
    created_at: Mapped[datetime] = mapped_column(DateTime, default=agora)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    acao: Mapped[str] = mapped_column(String(60), index=True)
    entidade: Mapped[str] = mapped_column(String(40))
    entidade_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=agora)
