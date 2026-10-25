import os
from dotenv import load_dotenv
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import BaseModel

env_file = (
    ".env.prod"
    if os.getenv("ENV") == "prod"
    else ".env.test"
    if os.getenv("ENV") == "test"
    else ".env.dev"
)
load_dotenv(env_file)

BaseDir = Path(__file__).parent.parent


class DbSetting(BaseModel):
    url: str = os.getenv("DATABASE_URL")
    echo: bool = True


class AuthJWT(BaseModel):
    private_key_path: Path = BaseDir / "certs" / "jwt-private.pem"
    public_key_path: Path = BaseDir / "certs" / "jwt-public.pem"
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 2880
    refresh_token_expire_days: int = 30


class MailSetting(BaseModel):
    # Пустой host: письма не отправляются, а пишутся в лог.
    host: str = os.getenv("MAIL_HOST", "")
    port: int = int(os.getenv("MAIL_PORT", "587"))
    username: str = os.getenv("MAIL_USERNAME", "")
    password: str = os.getenv("MAIL_PASSWORD", "")
    from_address: str = os.getenv("MAIL_FROM", "no-reply@localhost")
    from_name: str = os.getenv("MAIL_FROM_NAME", "Экзаменационный терминал")
    # starttls (порт 587), ssl (порт 465) или none (локальный отладочный сервер).
    security: str = os.getenv("MAIL_SECURITY", "starttls")


class Settings(BaseSettings):
    api_v1_prefix: str = "/api/v1"

    db: DbSetting = DbSetting()
    auth: AuthJWT = AuthJWT()
    mail: MailSetting = MailSetting()


settings = Settings()
