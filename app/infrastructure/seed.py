"""Dados iniciais para demonstração/testes. Execute: python -m app.infrastructure.seed"""
from sqlalchemy import select

from app.domain.enums import Perfil
from app.infrastructure.database import SessionLocal, criar_tabelas
from app.infrastructure.models import Estoque, Produto, Promocao, Unidade, Usuario, agora
from app.infrastructure.security import hash_senha

UNIDADES = [("Raízes Fortaleza - Aldeota", "Fortaleza"), ("Raízes Fortaleza - Centro", "Fortaleza"),
            ("Raízes Recife - Boa Viagem", "Recife")]
PRODUTOS = [
    ("Baião de Dois", "Arroz, feijão de corda, queijo coalho e nata", "Pratos", "28.90"),
    ("Cuscuz com Carne de Sol", "Cuscuz nordestino com carne de sol e manteiga de garrafa", "Pratos", "32.50"),
    ("Sanduíche de Carne de Sol", "Pão artesanal, carne de sol, queijo coalho e vinagrete", "Lanches", "27.00"),
    ("Tapioca de Queijo Coalho", "Tapioca recheada com queijo coalho", "Lanches", "14.50"),
    ("Macaxeira Frita", "Porção de macaxeira frita crocante", "Porções", "18.00"),
    ("Suco de Cajá", "Suco natural 400ml", "Bebidas", "9.50"),
    ("Caldo de Cana", "Caldo de cana gelado 400ml", "Bebidas", "8.00"),
    ("Bolo de Rolo", "Fatia de bolo de rolo pernambucano", "Sobremesas", "12.00"),
]
USUARIOS = [
    ("Gerente Raízes", "gerente@raizes.com", "Gerente@123", Perfil.GERENTE, False),
    ("Atendente Raízes", "atendente@raizes.com", "Atendente@123", Perfil.ATENDENTE, False),
    ("Cozinha Raízes", "cozinha@raizes.com", "Cozinha@123", Perfil.COZINHA, False),
    ("Maria Cliente", "cliente@raizes.com", "Cliente@123", Perfil.CLIENTE, True),
]


def executar() -> None:
    criar_tabelas()
    with SessionLocal() as db:
        if db.scalar(select(Unidade.id).limit(1)):
            print("Seed já aplicado — nada a fazer.")
            return
        unidades = [Unidade(nome=n, cidade=c) for n, c in UNIDADES]
        produtos = [Produto(nome=n, descricao=d, categoria=cat, preco=p) for n, d, cat, p in PRODUTOS]
        db.add_all(unidades + produtos)
        db.flush()
        for u in unidades:
            for p in produtos:
                db.add(Estoque(unidade_id=u.id, produto_id=p.id, quantidade=50))
        for nome, email, senha, perfil, cliente in USUARIOS:
            db.add(Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), perfil=perfil,
                           consentimento_lgpd=cliente, consentimento_lgpd_em=agora() if cliente else None,
                           consentimento_fidelidade=cliente,
                           consentimento_fidelidade_em=agora() if cliente else None))
        db.add(Promocao(codigo="RAIZES10", descricao="10% de desconto no pedido", percentual=10))
        db.commit()
        print("Seed aplicado: 3 unidades, 8 produtos, 4 usuários, 1 promoção.")


if __name__ == "__main__":
    executar()
