from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Response

from app.api import serializers as ser
from app.api.deps import Paginacao, exigir, get_db, usuario_atual
from app.api.routers._comum import erros
from app.api.schemas import Pagina, PedidoIn, PedidoOut, StatusIn
from app.application import order_service
from app.domain.enums import CanalPedido, Perfil, StatusPedido

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.post("", response_model=PedidoOut, status_code=201,
             responses={**erros(401, 403, 404, 409, 422),
                        200: {"description": "Repetição idempotente (mesmo Idempotency-Key)"}},
             summary="Cria pedido: valida estoque, aplica promoção/fidelidade e registra o canal")
def criar(dados: PedidoIn, response: Response,
          idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key", max_length=80),
          db=Depends(get_db),
          ator=Depends(exigir(Perfil.CLIENTE, Perfil.ATENDENTE, Perfil.GERENTE))):
    pedido, criado = order_service.criar_pedido(db, ator, dados, idempotency_key)
    if not criado:
        response.status_code = 200
    return ser.pedido(pedido)


@router.get("", response_model=Pagina[PedidoOut], responses=erros(401, 422),
            summary="Lista pedidos (cliente vê só os seus). Filtros: canalPedido, status, unidadeId")
def listar(canalPedido: Optional[CanalPedido] = Query(None), status: Optional[StatusPedido] = Query(None),
           unidadeId: Optional[int] = Query(None), pag: Paginacao = Depends(),
           db=Depends(get_db), ator=Depends(usuario_atual)):
    itens, total = order_service.listar_pedidos(db, ator, canal=canalPedido, status=status,
                                                unidade_id=unidadeId, page=pag.page, limit=pag.limit)
    return Pagina(items=[ser.pedido(p) for p in itens], page=pag.page, limit=pag.limit, total=total)


@router.get("/{pedido_id}", response_model=PedidoOut, responses=erros(401, 404))
def obter(pedido_id: int, db=Depends(get_db), ator=Depends(usuario_atual)):
    return ser.pedido(order_service.obter_pedido(db, ator, pedido_id))


@router.patch("/{pedido_id}/status", response_model=PedidoOut, responses=erros(401, 403, 404, 409, 422),
              summary="Atualiza o status (COZINHA: EM_PREPARO→PRONTO; ATENDENTE: PRONTO→ENTREGUE)")
def atualizar_status(pedido_id: int, dados: StatusIn, db=Depends(get_db), ator=Depends(usuario_atual)):
    return ser.pedido(order_service.mudar_status(db, ator, pedido_id, dados.status))


@router.post("/{pedido_id}/cancelar", response_model=PedidoOut, responses=erros(401, 403, 404, 409),
             summary="Cancela o pedido (devolve estoque, pontos e estorna pagamento mock)")
def cancelar(pedido_id: int, db=Depends(get_db), ator=Depends(usuario_atual)):
    return ser.pedido(order_service.mudar_status(db, ator, pedido_id, StatusPedido.CANCELADO))
