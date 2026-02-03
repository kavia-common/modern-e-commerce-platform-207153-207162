from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.models import Cart, User
from src.api.schemas import TokenResponse, UserLoginRequest, UserPublic, UserRegisterRequest
from src.api.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new customer user account and returns an access token.",
    operation_id="auth_register",
)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Register a new user.

    - Creates user record with role=customer
    - Ensures an active cart exists for the user
    - Returns JWT token + user info
    """
    existing = db.scalar(select(User).where(User.email == req.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="customer",
        is_active=True,
    )
    db.add(user)
    db.flush()  # assigns id

    # Ensure an active cart exists.
    cart = Cart(user_id=user.id, status="active")
    db.add(cart)

    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=user.role),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticates using email/password and returns an access token.",
    operation_id="auth_login",
)
def login(req: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Login.

    Returns 401 for invalid credentials.
    """
    user = db.scalar(select(User).where(User.email == req.email))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Seed data uses 'changeme' placeholder. If that's present, allow login only if password matches
    # either real hash or placeholder.
    if user.password_hash == "changeme":
        if req.password != "changeme":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    else:
        if not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=user.role),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user",
    description="Returns the authenticated user's profile.",
    operation_id="auth_me",
)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    """Get current authenticated user."""
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
