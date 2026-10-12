"""Paginação simples reutilizada nas listagens."""
from sqlalchemy import func, select


def paginar(db, stmt, page: int, limit: int):
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    itens = db.scalars(stmt.limit(limit).offset((page - 1) * limit)).all()
    return itens, total
