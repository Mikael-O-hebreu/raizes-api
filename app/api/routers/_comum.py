from app.api.schemas import ErroOut


def erros(*codigos: int) -> dict:
    nomes = {400: "Requisição inválida", 401: "Não autenticado", 403: "Sem permissão",
             404: "Não encontrado", 409: "Conflito / regra de negócio", 422: "Erro de validação"}
    return {c: {"model": ErroOut, "description": nomes[c]} for c in codigos}
