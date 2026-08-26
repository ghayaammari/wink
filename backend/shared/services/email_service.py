"""Envoi d'email via SMTP — utilisé par `shared/auth` (reset de mot de passe),

réutilisable par n'importe quel acteur pour de futures notifications. Placé
dans `shared/services/` (déjà prévu par l'architecture pour "la logique
métier partagée" hors auth) plutôt que dans `shared/auth/` : ce n'est pas une
responsabilité d'authentification, juste un outil que l'auth consomme.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL") or SMTP_USERNAME
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"


class EmailError(Exception):
    """Échec d'envoi — au service appelant de décider comment réagir."""


def send_email(to: str, subject: str, body_text: str) -> None:
    if not SMTP_HOST:
        raise EmailError("Envoi d'email non configuré (SMTP_HOST manquant dans .env).")

    message = EmailMessage()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body_text)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_USE_TLS:
                server.starttls(context=ssl.create_default_context())
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # OSError couvre aussi les erreurs de connexion (host injoignable, timeout).
        raise EmailError(f"Échec de l'envoi de l'email à {to} : {exc}") from exc
