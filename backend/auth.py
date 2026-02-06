from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import bcrypt

from db_models import User

security = HTTPBasic()


async def verify_user(
    credentials: HTTPBasicCredentials = Depends(security),
) -> dict:
    """Verify HTTP Basic credentials against the database.

    Returns a dict with user id and username on success.
    Raises 401 on failure.
    """
    user = await User.filter(username=credentials.username).first()
    if user is None or not bcrypt.checkpw(credentials.password.encode(), user.password_hash.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return {"id": user.id, "username": user.username}
