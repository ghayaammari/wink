"""Routes d'authentification — partagées par les 3 acteurs (I0).

POST /auth/signup, /auth/signup/google, /auth/login, /auth/login/google,
/auth/refresh, /auth/logout, /auth/forgot-password, /auth/reset-password,
GET /auth/me.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.shared.auth.schemas.auth_schemas import (
    ForgotPasswordRequest,
    GoogleSignupRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from backend.shared.auth.services import auth_service
from backend.shared.auth.services.auth_service import AuthError, EmailAlreadyExistsError
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

# auto_error=False : on veut renvoyer nous-mêmes un 401 avec notre propre message,
# pas la réponse générique de FastAPI si l'en-tête Authorization est absent.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Dépendance FastAPI réutilisable pour protéger n'importe quelle route (pas

    seulement GET /auth/me) : `Depends(get_current_user)` dans un futur
    `project_router.py` suffira à exiger un access token valide.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")
    try:
        return auth_service.get_user_by_access_token(db, credentials.credentials)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(db, user)
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = auth_service.signup_with_email(
            db, body.email, body.password, body.role, body.first_name, body.last_name
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _issue_tokens(db, user)


@router.post("/signup/google", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup_google(body: GoogleSignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = auth_service.signup_with_google(db, body.id_token, body.role)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = auth_service.login_with_email(db, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return _issue_tokens(db, user)


@router.post("/login/google", response_model=TokenResponse)
def login_google(body: GoogleSignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    # body.role n'est pas utilisé ici : au login, le rôle vient du compte déjà
    # créé, pas de la requête (contrairement à /signup/google) — même schéma
    # GoogleSignupRequest réutilisé côté client par simplicité, mais le champ
    # role est ignoré côté serveur pour ce endpoint.
    try:
        user = auth_service.login_with_google(db, body.id_token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user, new_refresh_token = auth_service.rotate_refresh_token(db, body.refresh_token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    access_token = auth_service.create_access_token(user)
    db.commit()
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: Session = Depends(get_db)) -> None:
    # Idempotent volontairement : révoquer un refresh token déjà invalide/expiré
    # ne renvoie pas d'erreur — le résultat souhaité ("cette session n'est plus
    # valide") est déjà acquis, pas la peine d'informer le client de la nuance.
    auth_service.revoke_refresh_token(db, body.refresh_token)
    db.commit()


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    # Réponse volontairement identique que l'email existe ou non — voir le
    # docstring de request_password_reset : ne jamais laisser une réponse HTTP
    # révéler si un email est inscrit.
    auth_service.request_password_reset(db, body.email)
    return {"detail": "Si un compte existe avec cet email, un lien de réinitialisation a été envoyé."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    try:
        auth_service.reset_password(db, body.token, body.new_password)
    except AuthError as exc:
        # 400, pas 401 : ce n'est pas un problème d'authentification manquante,
        # c'est un token de reset invalide/expiré/déjà utilisé — erreur côté client.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
