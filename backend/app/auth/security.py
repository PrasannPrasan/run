import datetime as dt

from jose import jwt
from passlib.exc import UnknownHashError
from passlib.context import CryptContext

from app.settings import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
TOKEN_RECREATED_PASSWORD_HASH = "token-recreated-serverless-user"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except (TypeError, ValueError, UnknownHashError):
        return False


def create_access_token(*, user_id: int, email: str) -> str:
    now = dt.datetime.now(dt.UTC)
    exp = now + dt.timedelta(minutes=settings.jwt_access_token_minutes)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "sub": email,
        "uid": str(user_id),
        "email": email,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
