"""Configuração da aplicação (lida de variáveis de ambiente / arquivo .env)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./raizes.db")
    JWT_SECRET: str = os.getenv(
        "JWT_SECRET", "troque-esta-chave-por-um-valor-longo-e-aleatorio-123456"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_SECONDS: int = int(os.getenv("JWT_EXPIRES_SECONDS", "3600"))


settings = Settings()
