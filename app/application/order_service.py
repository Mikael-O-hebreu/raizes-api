"""Fluxo crítico: criação de pedido (estoque, promoção, fidelidade), consulta e status."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select

from app.application import audit_service, catalog_service, loyalty_service, stock_service
from app.application.pagination import paginar
from app.domain import rules
from app.domain.enums import (Perfil, StatusPagamento, StatusPedido, TipoMovimentoEstoque)
from app.domain.errors import Conflito, NaoEncontrado, RegraInvalida, SemPermissao
from app.infrastructure.models import ItemPedido, Pedido, Produto, Promocao, Usuario


def _cliente_do_pedido(db, ator: Usuario, cliente_id: Optional[int]) -> Usuario:
    if ator.perfil == Perfil.CLIENTE:
        if cliente_id not in (None, ator.id):
            raise SemPermissao("Cliente só pode criar pedidos para si mesmo.")
        return ator
    if cliente_id is None:
        raise RegraInvalida("clienteId é obrigatório para pedidos feitos pela equipe.",
                            error="CLIENTE_OBRIGATORIO",
                            details=[{"field": "clienteId", "issue": "Campo obrigatório"}])
    cliente = db.get(Usuario, cliente_id)
    if not cliente or cliente.perfil != Perfil.CLIENTE or not cliente.ativo:
        raise NaoEncontrado("Cliente não encontrado.", error="CLIENTE_NAO_ENCONTRADO")
    return cliente


def _promocao(db, codigo: Optional[str]) -> Optional[Promocao]:
    if not codigo:
        return None
    promo = db.scalar(select(Promocao).where(Promocao.codigo == codigo.upper().strip()))
    expirada = promo and promo.valida_ate and promo.valida_ate < datetime.utcnow()
    if not promo or not promo.ativa or expirada:
        raise RegraInvalida("Código de promoção inválido ou expirado.", error="PROMOCAO_INVALIDA",
                            details=[{"field": "codigoPromocao", "issue": "Inválido"}])
    return promo


def criar_pedido(db, ator: Usuario, dados, idempotency_key: Optional[str] = None):
    """Retorna (pedido, criado). `criado=False` quando é repetição idempotente."""
    cliente = _cliente_do_pedido(db, ator, dados.clienteId)

    if idempotency_key:
        existente = db.scalar(select(Pedido).where(Pedido.cliente_id == cliente.id,
                                                   Pedido.idempotency_key == idempotency_key))
        if existente:
            return existente, False

    catalog_service.obter_unidade(db, dados.unidadeId)

    # Junta itens repetidos do mesmo produto, guardando o índice da 1ª ocorrência (p/ erros)
    agregados: dict[int, list] = {}
    for idx, item in enumerate(dados.itens):
        if item.produtoId in agregados:
            agregados[item.produtoId][1] += item.quantidade
        else:
            agregados[item.produtoId] = [idx, item.quantidade]

    linhas, insuficientes, subtotal = [], [], Decimal("0.00")
    for produto_id, (idx, qtd) in agregados.items():
        produto = db.get(Produto, produto_id)
        if not produto or not produto.ativo:
            raise NaoEncontrado("Produto não encontrado.", error="PRODUTO_NAO_ENCONTRADO",
                                details=[{"field": f"itens[{idx}].produtoId", "issue": "Inexistente"}])
        estoque = stock_service.obter_linha(db, dados.unidadeId, produto_id, travar=True)
        if estoque is None:
            raise NaoEncontrado("Produto não é vendido nesta unidade.",
                                error="PRODUTO_INDISPONIVEL_NA_UNIDADE",
                                details=[{"field": f"itens[{idx}].produtoId", "issue": "Fora da unidade"}])
        if estoque.quantidade < qtd:
            insuficientes.append({"field": f"itens[{idx}].quantidade",
                                  "issue": f"Disponível: {estoque.quantidade}"})
        linhas.append((produto, qtd))
        subtotal += rules.dinheiro(produto.preco) * qtd
    if insuficientes:
        raise Conflito("Não há quantidade suficiente para um ou mais itens.",
                       error="ESTOQUE_INSUFICIENTE", details=insuficientes)

    promo = _promocao(db, dados.codigoPromocao)
    desc_promo = rules.desconto_promocao(subtotal, promo.percentual) if promo else Decimal("0.00")
    base = subtotal - desc_promo

    desc_fid = Decimal("0.00")
    if dados.resgatarPontos:
        loyalty_service.validar_resgate(db, cliente, dados.resgatarPontos)
        desc_fid = rules.desconto_resgate(dados.resgatarPontos)
        if desc_fid >= base:
            raise RegraInvalida("O desconto de fidelidade não pode zerar o pedido.",
                                error="RESGATE_EXCEDE_VALOR",
                                details=[{"field": "resgatarPontos", "issue": "Excede o valor"}])

    pedido = Pedido(cliente_id=cliente.id, unidade_id=dados.unidadeId,
                    canal_pedido=dados.canalPedido, status=StatusPedido.AGUARDANDO_PAGAMENTO,
                    forma_pagamento=dados.formaPagamento, subtotal=subtotal,
                    desconto_promocao=desc_promo, desconto_fidelidade=desc_fid,
                    total=base - desc_fid, codigo_promocao=promo.codigo if promo else None,
                    pontos_resgatados=dados.resgatarPontos or 0, idempotency_key=idempotency_key)
    for produto, qtd in linhas:
        pedido.itens.append(ItemPedido(produto_id=produto.id, quantidade=qtd,
                                       preco_unitario=rules.dinheiro(produto.preco)))
    db.add(pedido)
    db.flush()

    for produto, qtd in linhas:  # reserva o estoque no momento do pedido
        stock_service.movimentar(db, unidade_id=dados.unidadeId, produto_id=produto.id,
                                 tipo=TipoMovimentoEstoque.SAIDA, quantidade=qtd,
                                 motivo="PEDIDO", usuario_id=ator.id, pedido_id=pedido.id)
    if dados.resgatarPontos:
        loyalty_service.registrar_resgate(db, cliente.id, pedido.id, dados.resgatarPontos)

    audit_service.registrar(db, usuario_id=ator.id, acao="PEDIDO_CRIADO", entidade="pedido",
                            entidade_id=pedido.id,
                            detalhes={"canalPedido": dados.canalPedido.value,
                                      "total": float(pedido.total)})
    db.commit()
    return pedido, True


def obter_pedido(db, ator: Usuario, pedido_id: int) -> Pedido:
    pedido = db.get(Pedido, pedido_id)
    if not pedido or (ator.perfil == Perfil.CLIENTE and pedido.cliente_id != ator.id):
        raise NaoEncontrado("Pedido não encontrado.", error="PEDIDO_NAO_ENCONTRADO")
    return pedido


def listar_pedidos(db, ator: Usuario, *, canal=None, status=None, unidade_id=None,
                   page: int = 1, limit: int = 10):
    stmt = select(Pedido).order_by(Pedido.id.desc())
    if ator.perfil == Perfil.CLIENTE:
        stmt = stmt.where(Pedido.cliente_id == ator.id)
    if canal:
        stmt = stmt.where(Pedido.canal_pedido == canal)
    if status:
        stmt = stmt.where(Pedido.status == status)
    if unidade_id:
        stmt = stmt.where(Pedido.unidade_id == unidade_id)
    return paginar(db, stmt, page, limit)


def _cancelar(db, pedido: Pedido) -> None:
    for item in pedido.itens:  # devolve o estoque reservado
        stock_service.movimentar(db, unidade_id=pedido.unidade_id, produto_id=item.produto_id,
                                 tipo=TipoMovimentoEstoque.ENTRADA, quantidade=item.quantidade,
                                 motivo="CANCELAMENTO_PEDIDO", pedido_id=pedido.id)
    for pag in pedido.pagamentos:  # estorno (mock) de pagamento já aprovado
        if pag.status == StatusPagamento.APROVADO:
            pag.status = StatusPagamento.ESTORNADO
    loyalty_service.estornar_pedido(db, pedido)


def mudar_status(db, ator: Usuario, pedido_id: int, novo: StatusPedido) -> Pedido:
    pedido = obter_pedido(db, ator, pedido_id)
    atual = pedido.status
    if not rules.transicao_existe(atual, novo):
        raise Conflito(f"Transição de {atual.value} para {novo.value} não é permitida.",
                       error="TRANSICAO_INVALIDA",
                       details=[{"field": "status", "issue": f"Atual: {atual.value}"}])
    if not rules.perfil_pode_transicionar(ator.perfil, atual, novo):
        raise SemPermissao(f"O perfil {ator.perfil.value} não pode mudar o pedido para {novo.value}.")
    if novo == StatusPedido.CANCELADO:
        _cancelar(db, pedido)
    pedido.status = novo
    audit_service.registrar(db, usuario_id=ator.id, acao="PEDIDO_STATUS_ALTERADO",
                            entidade="pedido", entidade_id=pedido.id,
                            detalhes={"de": atual.value, "para": novo.value})
    db.commit()
    return pedido
