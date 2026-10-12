"""Auditoria: registra ações sensíveis em tabela e em log de aplicação."""
import logging
from typing import Optional

from app.infrastructure.models import AuditLog

logger = logging.getLogger("raizes.audit")


def registrar(db, *, usuario_id: Optional[int], acao: str, entidade: str,
              entidade_id: Optional[int] = None, detalhes: Optional[dict] = None) -> None:
    db.add(AuditLog(usuario_id=usuario_id, acao=acao, entidade=entidade,
                    entidade_id=entidade_id, detalhes=detalhes))
    logger.info("AUDIT acao=%s entidade=%s id=%s usuario=%s", acao, entidade, entidade_id, usuario_id)
