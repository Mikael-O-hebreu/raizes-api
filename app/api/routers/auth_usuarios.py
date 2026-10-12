from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.api import serializers as ser
from app.api.deps import Paginacao, exigir, get_db, usuario_atual
from app.api.routers._comum import erros
from app.api.schemas import (ConsentimentosIn, FuncionarioCriar, LoginIn, Pagina, TokenOut,
                             UsuarioCriar, UsuarioOut, UsuarioResumo)
from app.application import audit_service, auth_service
from app.application.pagination import paginar
from app.domain.enums import Perfil
from app.infrastructure.models import Usuario

auth = APIRouter(prefix="/auth", tags=["Auth"])
usuarios = APIRouter(prefix="/usuarios", tags=["Usuários"])


@auth.post("/login", response_model=TokenOut, responses=erros(401, 422),
           summary="Autentica o usuário e retorna o token JWT")
def login(dados: LoginIn, db=Depends(get_db)):
    token, user = auth_service.login(db, dados.email, dados.senha)
    return TokenOut(accessToken=token, expiresIn=auth_service.expira_em(),
                    user=UsuarioResumo(id=user.id, nome=user.nome, perfil=user.perfil))


@usuarios.post("", response_model=UsuarioOut, status_code=201, responses=erros(409, 422),
               summary="Cadastro público de cliente (exige consentimento LGPD)")
def cadastrar(dados: UsuarioCriar, db=Depends(get_db)):
    user = auth_service.cadastrar_cliente(
        db, nome=dados.nome, email=dados.email, senha=dados.senha,
        consentimento_lgpd=dados.consentimentoLgpd,
        consentimento_fidelidade=dados.consentimentoFidelidade)
    return ser.usuario(user)


@usuarios.post("/funcionarios", response_model=UsuarioOut, status_code=201,
               responses=erros(401, 403, 409, 422), summary="GERENTE cria ATENDENTE, COZINHA ou GERENTE")
def criar_funcionario(dados: FuncionarioCriar, db=Depends(get_db),
                      ator: Usuario = Depends(exigir(Perfil.GERENTE))):
    user = auth_service.criar_funcionario(db, ator, nome=dados.nome, email=dados.email,
                                          senha=dados.senha, perfil=dados.perfil)
    return ser.usuario(user)


@usuarios.get("/me", response_model=UsuarioOut, responses=erros(401),
              summary="Dados do usuário logado")
def meu_perfil(user: Usuario = Depends(usuario_atual)):
    return ser.usuario(user)


@usuarios.patch("/me/consentimentos", response_model=UsuarioOut, responses=erros(401, 422),
                summary="Concede ou revoga o consentimento do programa de fidelidade")
def consentimentos(dados: ConsentimentosIn, db=Depends(get_db),
                   user: Usuario = Depends(usuario_atual)):
    return ser.usuario(auth_service.atualizar_consentimento_fidelidade(
        db, user, dados.consentimentoFidelidade))


@usuarios.delete("/me", status_code=204, responses=erros(401),
                 summary="Elimina os dados pessoais do usuário (anonimização - LGPD)")
def anonimizar_conta(db=Depends(get_db), user: Usuario = Depends(usuario_atual)):
    auth_service.anonimizar(db, user)
    return Response(status_code=204)


@usuarios.get("", response_model=Pagina[UsuarioOut], responses=erros(401, 403),
              summary="Lista usuários (GERENTE) — acesso a dados pessoais é auditado")
def listar(pag: Paginacao = Depends(), db=Depends(get_db),
           ator: Usuario = Depends(exigir(Perfil.GERENTE))):
    itens, total = paginar(db, select(Usuario).order_by(Usuario.id), pag.page, pag.limit)
    audit_service.registrar(db, usuario_id=ator.id, acao="LEITURA_DADOS_PESSOAIS",
                            entidade="usuario", detalhes={"qtd": len(itens)})
    db.commit()
    return Pagina(items=[ser.usuario(u) for u in itens], page=pag.page, limit=pag.limit, total=total)


@usuarios.get("/{usuario_id}", response_model=UsuarioOut, responses=erros(401, 403, 404),
              summary="Consulta um usuário (GERENTE) — acesso é auditado")
def obter(usuario_id: int, db=Depends(get_db), ator: Usuario = Depends(exigir(Perfil.GERENTE))):
    user = auth_service.obter_usuario(db, usuario_id)
    audit_service.registrar(db, usuario_id=ator.id, acao="LEITURA_DADOS_PESSOAIS",
                            entidade="usuario", entidade_id=user.id)
    db.commit()
    return ser.usuario(user)
