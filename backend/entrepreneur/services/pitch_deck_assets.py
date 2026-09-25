"""Aide au rendu du logo dans le pitch deck (service 6.6.2) — porte tel quel

depuis le prototype startapini. `brand.logo_url` vient de
ProjectPublicProfile.logo_url (voir pitch_deck_service.py) : une URL Cloudinary
deja utilisee ailleurs dans Wink pour ce meme champ, mais on reste defensif ici
(URL cassee/inaccessible) plutot que de faire echouer toute la generation --
tout echec de recuperation retombe sur un monogramme en initiales.
"""

from __future__ import annotations

import io
import logging

import httpx
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 5.0
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def fetch_logo_image(logo_url: str | None, *, startup_id: str) -> bytes | None:
    """Best-effort fetch + validate of a startup logo. Returns raw image
    bytes on success, or None if the URL is absent, unreachable, too large,
    or not a decodable image -- never raises."""
    if not logo_url:
        return None

    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(logo_url)
            response.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL) as exc:
        # InvalidURL (malformed URL, missing scheme, ...) is a bare Exception
        # in httpx, not an HTTPError -- must be caught separately or a
        # garbage logo_url crashes deck generation instead of falling back.
        logger.warning("Logo fetch failed for startup %s (%s): %s", startup_id, logo_url, exc)
        return None

    content = response.content
    if len(content) > MAX_IMAGE_BYTES:
        logger.warning(
            "Logo for startup %s (%s) exceeds %d bytes, skipping",
            startup_id,
            logo_url,
            MAX_IMAGE_BYTES,
        )
        return None

    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        logger.warning("Logo for startup %s (%s) is not a valid image: %s", startup_id, logo_url, exc)
        return None

    return content


def get_initials(name: str) -> str:
    """Two-letter monogram from a startup/person name, e.g. 'Acme Biotech' -> 'AB'."""
    words = [w for w in name.strip().split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()