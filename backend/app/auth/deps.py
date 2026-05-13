from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose.exceptions import JWTError
from sqlalchemy.orm import Session

from app.auth.security import TOKEN_RECREATED_PASSWORD_HASH, decode_access_token
from app.db.models import User
from app.db.session import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(token)
        raw_sub = str(payload.get("sub") or "")
        email = str(payload.get("email") or "").lower().strip()
    except (KeyError, ValueError, JWTError):
        raise HTTPException(status_code=401, detail="Invalid token")

    if not email and "@" in raw_sub:
        email = raw_sub.lower().strip()

    if email:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user:
            return user

        # Vercel's demo SQLite database lives in ephemeral serverless storage.
        # A valid JWT can outlive the local row, so recreate the identity.
        user = User(email=email, password_hash=TOKEN_RECREATED_PASSWORD_HASH)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    try:
        user_id = int(raw_sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
