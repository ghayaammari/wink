"""Logique métier d'authentification — signup/login (email + Google), JWT, refresh token.

Partagé par les 3 acteurs (I0) : un seul point d'entrée, le `role` choisi à
l'écran 1 détermine quel profil vide est créé automatiquement.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from backend.chercheur.models.researcher_profile import ResearcherProfile
from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.investisseur.models.investor_profile import InvestorProfile
from backend.shared.models.password_reset_token import PasswordResetToken
from backend.shared.models.refresh_token import RefreshToken
from backend.shared.models.user import User
from backend.shared.services import email_service

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
# Configurable via .env : un JWT ne peut pas être révoqué une fois émis (juste
# vérifié par signature) — plus cette durée est longue, plus un token volé
# reste exploitable. 30 min par défaut si la variable est absente.
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = 30
# Courte durée volontaire : un lien de reset qui traîne dans une boîte mail est
# un risque, contrairement au refresh token pensé pour durer.
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.environ.get("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "60"))
# URL du frontend qui affiche le formulaire "nouveau mot de passe" ; le token
# brut est ajouté en query string par request_password_reset.
FRONTEND_RESET_PASSWORD_URL = os.environ.get(
    "FRONTEND_RESET_PASSWORD_URL", "http://localhost:5173/reset-password"
)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")


class AuthError(Exception):
    """Erreur métier d'authentification — traduite en 401 par défaut dans le router."""


class EmailAlreadyExistsError(AuthError):
    """Cas distinct de AuthError : le router la traduit en 409, pas 401 — sémantique HTTP différente."""


# ---------------------------------------------------------------------------
# Mots de passe
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# Access token (JWT, courte durée, jamais stocké côté serveur)
# ---------------------------------------------------------------------------

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Le token a expiré.")
    except jwt.InvalidTokenError:
        raise AuthError("Token invalide.")


# ---------------------------------------------------------------------------
# Refresh token (opaque, longue durée, haché en base, rotation à usage unique)
# ---------------------------------------------------------------------------

def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_refresh_token(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(64)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return raw_token


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str]:
    """Vérifie un refresh token, le révoque, en émet un nouveau.

    Rotation à usage unique : dès qu'un refresh token sert une fois, il devient
    inutilisable. Ça limite la fenêtre d'exploitation d'un token volé — mais on
    ne détecte pas ici la réutilisation d'un token déjà révoqué comme un signal
    d'alerte à part entière (ex: révoquer toutes les sessions de l'utilisateur) ;
    ce raffinement n'est pas nécessaire pour I0, à ajouter si un vrai incident
    de sécurité le justifie un jour.
    """
    token_hash = _hash_refresh_token(raw_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if stored is None:
        raise AuthError("Refresh token invalide.")
    if stored.revoked_at is not None:
        raise AuthError("Refresh token déjà utilisé ou révoqué.")
    if stored.expires_at < datetime.now(timezone.utc):
        raise AuthError("Refresh token expiré.")

    stored.revoked_at = datetime.now(timezone.utc)

    user = db.query(User).filter(User.id == stored.user_id).first()
    if user is None:
        raise AuthError("Utilisateur introuvable.")

    new_raw_token = create_refresh_token(db, user)
    return user, new_raw_token


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    """Logout — révoque un refresh token sans en émettre un nouveau."""
    token_hash = _hash_refresh_token(raw_token)
    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(timezone.utc)


def _revoke_all_refresh_tokens_for_user(db: Session, user_id) -> None:
    """Utilisée par reset_password : après un changement de mot de passe, toute

    session déjà ouverte (y compris celle d'un attaquant ayant volé un refresh
    token avant le reset) doit être coupée — sinon changer son mot de passe ne
    protège pas vraiment le compte.
    """
    now = datetime.now(timezone.utc)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": now})


# ---------------------------------------------------------------------------
# Création automatique du profil selon le rôle (règle actée dans l'architecture)
# ---------------------------------------------------------------------------

def _create_profile_for_role(db: Session, user: User) -> None:
    if user.role == "entrepreneur":
        db.add(EntrepreneurProfile(user_id=user.id))
    elif user.role == "chercheur":
        db.add(ResearcherProfile(user_id=user.id))
    elif user.role == "investisseur":
        db.add(InvestorProfile(user_id=user.id))
    # Pas de `else` : `role` est déjà validé par le schéma Pydantic (Literal) et
    # par le CHECK constraint en base — un 4e cas ne peut pas arriver ici.


# ---------------------------------------------------------------------------
# Signup / login — email
# ---------------------------------------------------------------------------

def signup_with_email(
    db: Session, email: str, password: str, role: str, first_name: str, last_name: str
) -> User:
    if db.query(User).filter(User.email == email.lower()).first() is not None:
        raise EmailAlreadyExistsError("Un compte existe déjà avec cet email.")

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        auth_provider="email",
        role=role,
        first_name=first_name,
        last_name=last_name,
    )
    db.add(user)
    db.flush()  # obtient user.id (généré par la DB) avant de créer le profil lié
    _create_profile_for_role(db, user)
    db.commit()
    db.refresh(user)
    return user


def login_with_email(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    # Message volontairement identique dans les deux cas (email inconnu / mot de
    # passe faux) : ne pas révéler si un email existe déjà en base.
    if user is None or user.password_hash is None:
        raise AuthError("Email ou mot de passe incorrect.")
    if not verify_password(password, user.password_hash):
        raise AuthError("Email ou mot de passe incorrect.")
    return user


# ---------------------------------------------------------------------------
# Signup / login — Google
# ---------------------------------------------------------------------------

def _verify_google_id_token(id_token_str: str) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise AuthError("Connexion Google non configurée (GOOGLE_CLIENT_ID manquant).")
    try:
        return google_id_token.verify_oauth2_token(id_token_str, google_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError:
        raise AuthError("Jeton Google invalide.")


def _verify_and_find_google_user(db: Session, id_token_str: str) -> tuple[dict, User | None]:
    """Partie commune à signup et login Google : vérifie le token, cherche le

    compte existant. Ne décide rien elle-même — juste ce qui serait dupliqué
    si signup_with_google/login_with_google vérifiaient chacune le token de
    leur côté.
    """
    claims = _verify_google_id_token(id_token_str)
    provider_subject = claims["sub"]
    existing = db.query(User).filter(User.provider_subject == provider_subject).first()
    return claims, existing


def signup_with_google(db: Session, id_token_str: str, role: str) -> User:
    """Même sémantique que signup_with_email : échoue si un compte existe déjà."""
    claims, existing = _verify_and_find_google_user(db, id_token_str)
    if existing is not None:
        raise EmailAlreadyExistsError("Un compte existe déjà avec ce compte Google — connecte-toi plutôt.")

    email = claims["email"]
    if db.query(User).filter(User.email == email.lower()).first() is not None:
        raise EmailAlreadyExistsError("Un compte existe déjà avec cet email, via un autre moyen de connexion.")

    user = User(
        email=email.lower(),
        auth_provider="google",
        provider_subject=claims["sub"],
        first_name=claims.get("given_name"),
        last_name=claims.get("family_name"),
        role=role,
    )
    db.add(user)
    db.flush()
    _create_profile_for_role(db, user)
    db.commit()
    db.refresh(user)
    return user


def login_with_google(db: Session, id_token_str: str) -> User:
    """Même sémantique que login_with_email : échoue si aucun compte n'existe."""
    _claims, existing = _verify_and_find_google_user(db, id_token_str)
    if existing is None:
        raise AuthError("Aucun compte trouvé avec ce compte Google — inscris-toi d'abord.")
    return existing


# ---------------------------------------------------------------------------
# Session courante — utilisé par la dépendance FastAPI `get_current_user` du
# router (nom différent ici pour éviter la confusion entre les deux niveaux).
# ---------------------------------------------------------------------------

def get_user_by_access_token(db: Session, access_token: str) -> User:
    payload = decode_access_token(access_token)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None:
        raise AuthError("Utilisateur introuvable.")
    return user


# ---------------------------------------------------------------------------
# Mot de passe oublié / réinitialisation
# ---------------------------------------------------------------------------

def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> None:
    """POST /auth/forgot-password. Ne lève jamais d'erreur métier et ne révèle

    jamais si l'email existe — la réponse HTTP est toujours identique côté
    router, que le compte existe ou non, pour ne pas laisser un attaquant
    énumérer les emails inscrits. Le comportement varie seulement dans
    l'email effectivement envoyé (visible seulement par le propriétaire de la
    boîte mail, jamais par la réponse API) :
      - email inconnu -> rien n'est envoyé
      - compte Google -> email informatif, pas de lien de reset (il n'a pas de mot de passe)
      - compte email -> lien de reset
    """
    user = db.query(User).filter(User.email == email.lower()).first()
    if user is None:
        return

    if user.auth_provider == "google":
        try:
            email_service.send_email(
                to=user.email,
                subject="Réinitialisation de mot de passe — Wink",
                body_text=(
                    "Tu as demandé une réinitialisation de mot de passe, mais ton "
                    "compte Wink est connecté via Google et n'a pas de mot de passe. "
                    "Connecte-toi directement avec le bouton \"Continuer avec Google\"."
                ),
            )
        except email_service.EmailError:
            # Best-effort : un email informatif qui échoue ne doit pas faire
            # planter la requête ni changer la réponse renvoyée à l'appelant.
            pass
        return

    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
    )
    db.commit()

    reset_link = f"{FRONTEND_RESET_PASSWORD_URL}?token={raw_token}"
    try:
        email_service.send_email(
            to=user.email,
            subject="Réinitialisation de mot de passe — Wink",
            body_text=(
                f"Clique sur ce lien pour choisir un nouveau mot de passe : {reset_link}\n\n"
                f"Ce lien expire dans {PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes. "
                "Si tu n'es pas à l'origine de cette demande, ignore cet email."
            ),
        )
    except email_service.EmailError:
        # Le token reste valide en base même si l'email échoue : pas de retry
        # automatique pour I0, l'utilisateur peut relancer /forgot-password.
        pass


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    """POST /auth/reset-password. Lève AuthError si le token est invalide,

    expiré, ou déjà utilisé — le router traduit ça en 400 (erreur côté client,
    pas une histoire d'authentification manquante comme les 401 du reste du
    module).
    """
    token_hash = _hash_reset_token(raw_token)
    stored = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()

    if stored is None:
        raise AuthError("Lien de réinitialisation invalide.")
    if stored.used_at is not None:
        raise AuthError("Ce lien de réinitialisation a déjà été utilisé.")
    if stored.expires_at < datetime.now(timezone.utc):
        raise AuthError("Ce lien de réinitialisation a expiré.")

    user = db.query(User).filter(User.id == stored.user_id).first()
    if user is None:
        raise AuthError("Utilisateur introuvable.")

    user.password_hash = hash_password(new_password)
    stored.used_at = datetime.now(timezone.utc)
    _revoke_all_refresh_tokens_for_user(db, user.id)

    db.commit()
    db.refresh(user)
    return user
