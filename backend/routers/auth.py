from fastapi import APIRouter, Depends

from auth import verify_user

router = APIRouter(prefix="/api")


@router.get("/auth/check")
async def auth_check(user: dict = Depends(verify_user)):
    return {"id": user["id"], "username": user["username"]}
