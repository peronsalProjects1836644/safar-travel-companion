from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.deps import current_user, get_db, get_settings_dep, limit_ip
from app.models.user import AuthResponse, LoginIn, ProfileUpdate, RefreshIn, RegisterIn, TokenPair, UserOut
from app.repositories import users as users_repo
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=AuthResponse, status_code=201,
    dependencies=[Depends(limit_ip("register", 10, 3600))],
)
async def register(data: RegisterIn, db=Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    user = await auth_svc.register(db, data)
    return {"user": users_repo.to_out(user), "tokens": auth_svc.issue_tokens(settings, user)}


@router.post(
    "/login", response_model=AuthResponse, dependencies=[Depends(limit_ip("login", 10, 900))]
)
async def login(data: LoginIn, db=Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    user = await auth_svc.login(db, data.email, data.password)
    return {"user": users_repo.to_out(user), "tokens": auth_svc.issue_tokens(settings, user)}


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(limit_ip("refresh", 60, 3600))])
async def refresh(data: RefreshIn, db=Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    return await auth_svc.refresh(db, settings, data.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return users_repo.to_out(user)


@router.patch("/me", response_model=UserOut)
async def update_me(data: ProfileUpdate, user: dict = Depends(current_user), db=Depends(get_db)):
    changes: dict = {}
    if data.name is not None:
        changes["name"] = data.name
    if data.preferences is not None:
        changes["preferences"] = data.preferences.model_dump()
    if data.emergency_contacts is not None:
        changes["emergency_contacts"] = [c.model_dump() for c in data.emergency_contacts]
    updated = await users_repo.update(db, str(user["_id"]), changes)
    return users_repo.to_out(updated)
