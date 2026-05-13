from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose.exceptions import JWTError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.db.models import User
from app.db.session import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        email = str(payload.get("email") or "").lower().strip()
    except (KeyError, ValueError, JWTError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user and email and user.email != email:
        user = None
    if not user and email:
        user = db.query(User).filter(User.email == email).one_or_none()
    if not user and email:
        # Vercel's demo SQLite database lives in ephemeral serverless storage.
        # A valid token can outlive the local row, so recreate the identity.
        user = User(email=email, password_hash="token-recreated-serverless-user")
        db.add(user)
        db.commit()
        db.refresh(user)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
