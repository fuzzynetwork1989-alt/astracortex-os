from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1_openai import create_key_for_user
from app.core.config import get_settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db.models import OrgMember, Organization, User
from app.db.session import get_db

router = APIRouter()


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = None
    org_name: str = "Personal"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    org_id: str
    email: str
    name: str | None
    api_key: str | None = None
    token_balance: int | None = None


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        email=body.email.lower(),
        name=body.name,
        password_hash=hash_password(body.password),
        role="user",
    )
    org = Organization(name=body.org_name, plan="pro")
    db.add(user)
    db.add(org)
    await db.flush()
    db.add(OrgMember(org_id=org.id, user_id=user.id, org_role="owner"))
    settings = get_settings()
    api_row, raw_key = await create_key_for_user(
        db,
        org_id=org.id,
        user_id=user.id,
        name="default",
        tier="nexus",
        grant=settings.default_token_balance,
    )
    await db.commit()

    token = create_access_token(str(user.id), {"org_id": str(org.id)})
    return TokenOut(
        access_token=token,
        user_id=str(user.id),
        org_id=str(org.id),
        email=user.email,
        name=user.name,
        api_key=raw_key,
        token_balance=api_row.token_balance,
    )


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)):
    from app.db.models import ApiKey

    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    membership = await db.execute(select(OrgMember).where(OrgMember.user_id == user.id).limit(1))
    member = membership.scalar_one_or_none()
    if not member:
        raise HTTPException(400, "User has no organization")

    # Surface balance (raw key is only shown once at create — never re-hash recoverable)
    key_row = (
        await db.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user.id, ApiKey.org_id == member.org_id, ApiKey.is_active.is_(True))
            .order_by(ApiKey.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    token = create_access_token(str(user.id), {"org_id": str(member.org_id)})
    return TokenOut(
        access_token=token,
        user_id=str(user.id),
        org_id=str(member.org_id),
        email=user.email,
        name=user.name,
        api_key=None,  # cannot re-show hashed key
        token_balance=key_row.token_balance if key_row else None,
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await db.execute(select(OrgMember).where(OrgMember.user_id == user.id).limit(1))
    member = membership.scalar_one_or_none()
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "org_id": str(member.org_id) if member else None,
        "org_role": member.org_role if member else None,
    }
