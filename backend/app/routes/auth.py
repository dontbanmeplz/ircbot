from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.auth import create_token, verify_password

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    admin: bool


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    is_valid, is_admin = verify_password(req.password)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Wrong password")
    token = create_token(is_admin=is_admin)
    return LoginResponse(token=token, admin=is_admin)
