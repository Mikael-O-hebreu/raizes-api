"""Cadastro, login e gestão de dados pessoais (LGPD)."""
import secrets
from typing import Optional

from sqlalchemy import select

from app.application import audit_service
from app.config import settings
from app.domain.enums import Perfil
from app.domain.errors import Conflito, NaoAutenticado, NaoEncontrado, RegraInvalida
from app.infrastructure.models import Usuario, agora
from app.infrastructure.security import criar_token, hash_senha, verificar_senha


def _email_existe(db, email: str) -> bool:
    return db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None


def cadastrar_cliente(db, *, nome: str, email: str, senha: str,
                      consentimento_lgpd: bool, consentimento_fidelidade: bool) -> Usuario:
    if not consentimento_lgpd:
        raise RegraInvalida(
            "É necessário aceitar o tratamento de dados pessoais para se cadastrar.",
            error="CONSENTIMENTO_LGPD_OBRIGATORIO",
            details=[{"field": "consentimentoLgpd", "issue": "Deve ser true"}])
    email = email.lower().strip()
    if _email_existe(db, email):
        raise Conflito("Já existe um usuário com este e-mail.", error="EMAIL_JA_CADASTRADO",
                       details=[{"field": "email", "issue": "Já cadastrado"}])
    agora_ = agora()
    user = Usuario(nome=nome.strip(), email=email, senha_hash=hash_senha(senha),
                   perfil=Perfil.CLIENTE, consentimento_lgpd=True, consentimento_lgpd_em=agora_,
                   consentimento_fidelidade=consentimento_fidelidade,
                   consentimento_fidelidade_em=agora_ if consentimento_fidelidade else None)
    db.add(user)
    db.flush()
    audit_service.registrar(db, usuario_id=user.id, acao="USUARIO_CADASTRADO", entidade="usuario",
                            entidade_id=user.id,
                            detalhes={"consentimentoLgpd": True,
                                      "consentimentoFidelidade": consentimento_fidelidade})
    db.commit()
    return user


def criar_funcionario(db, ator: Usuario, *, nome: str, email: str, senha: str,
                      perfil: Perfil) -> Usuario:
    email = email.lower().strip()
    if _email_existe(db, email):
        raise Conflito("Já existe um usuário com este e-mail.", error="EMAIL_JA_CADASTRADO",
                       details=[{"field": "email", "issue": "Já cadastrado"}])
    user = Usuario(nome=nome.strip(), email=email, senha_hash=hash_senha(senha), perfil=perfil)
    db.add(user)
    db.flush()
    audit_service.registrar(db, usuario_id=ator.id, acao="FUNCIONARIO_CRIADO", entidade="usuario",
                            entidade_id=user.id, detalhes={"perfil": perfil.value})
    db.commit()
    return user


def login(db, email: str, senha: str) -> tuple[str, Usuario]:
    user = db.scalar(select(Usuario).where(Usuario.email == email.lower().strip()))
    if not user or not user.ativo or not verificar_senha(senha, user.senha_hash):
        audit_service.registrar(db, usuario_id=user.id if user else None, acao="LOGIN_FALHA",
                                entidade="usuario", entidade_id=user.id if user else None)
        db.commit()
        raise NaoAutenticado("E-mail ou senha inválidos.", error="CREDENCIAIS_INVALIDAS")
    audit_service.registrar(db, usuario_id=user.id, acao="LOGIN_SUCESSO", entidade="usuario",
                            entidade_id=user.id)
    db.commit()
    return criar_token(user.id, user.perfil.value), user


def atualizar_consentimento_fidelidade(db, user: Usuario, consentimento: bool) -> Usuario:
    user.consentimento_fidelidade = consentimento
    user.consentimento_fidelidade_em = agora()
    audit_service.registrar(db, usuario_id=user.id, acao="CONSENTIMENTO_FIDELIDADE_ALTERADO",
                            entidade="usuario", entidade_id=user.id,
                            detalhes={"consentimentoFidelidade": consentimento})
    db.commit()
    return user


def anonimizar(db, user: Usuario) -> None:
    """Direito de eliminação (LGPD art. 18): remove dados pessoais, mantém pedidos
    (retenção por obrigação fiscal/legal) sem vínculo identificável."""
    user.nome = "Usuário anonimizado"
    user.email = f"anonimo-{user.id}@anonimizado.invalid"
    user.senha_hash = hash_senha(secrets.token_urlsafe(24))
    user.ativo = False
    user.anonimizado_em = agora()
    audit_service.registrar(db, usuario_id=user.id, acao="USUARIO_ANONIMIZADO",
                            entidade="usuario", entidade_id=user.id)
    db.commit()


def obter_usuario(db, usuario_id: int) -> Usuario:
    user = db.get(Usuario, usuario_id)
    if not user:
        raise NaoEncontrado("Usuário não encontrado.", error="USUARIO_NAO_ENCONTRADO")
    return user


def expira_em() -> int:
    return settings.JWT_EXPIRES_SECONDS
