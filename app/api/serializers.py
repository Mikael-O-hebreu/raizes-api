"""Converte entidades do ORM nos contratos de saída (nunca expõe senha_hash)."""
from app.api import schemas as s


def usuario(u) -> s.UsuarioOut:
    return s.UsuarioOut(id=u.id, nome=u.nome, email=u.email, perfil=u.perfil,
                        consentimentoLgpd=u.consentimento_lgpd,
                        consentimentoFidelidade=u.consentimento_fidelidade, createdAt=u.created_at)


def produto(p) -> s.ProdutoOut:
    return s.ProdutoOut(id=p.id, nome=p.nome, descricao=p.descricao, categoria=p.categoria,
                        preco=float(p.preco))


def pedido(p) -> s.PedidoOut:
    return s.PedidoOut(
        pedidoId=p.id, clienteId=p.cliente_id, unidadeId=p.unidade_id, canalPedido=p.canal_pedido,
        status=p.status, subtotal=float(p.subtotal), descontoPromocao=float(p.desconto_promocao),
        descontoFidelidade=float(p.desconto_fidelidade), total=float(p.total),
        codigoPromocao=p.codigo_promocao, pontosResgatados=p.pontos_resgatados,
        itens=[s.ItemPedidoOut(produtoId=i.produto_id, quantidade=i.quantidade,
                               precoUnitario=float(i.preco_unitario)) for i in p.itens],
        createdAt=p.created_at)


def pagamento(p) -> s.PagamentoOut:
    return s.PagamentoOut(pagamentoId=p.id, pedidoId=p.pedido_id, status=p.status,
                          formaPagamento=p.forma_pagamento, valor=float(p.valor),
                          mensagem=p.mensagem, referenciaExterna=p.referencia_externa,
                          payloadGateway=p.payload_gateway, createdAt=p.created_at)


def promocao(p) -> s.PromocaoOut:
    return s.PromocaoOut(id=p.id, codigo=p.codigo, descricao=p.descricao,
                         percentual=p.percentual, ativa=p.ativa, validaAte=p.valida_ate)
