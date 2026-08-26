"""Upload d'images vers Cloudinary — utilisé par `entrepreneur` (logo du projet, écran 9),

réutilisable par les autres acteurs plus tard (mêmes credentials, même config).
Placé dans `shared/services/` comme `email_service.py` : outil d'infra partagé,
pas une responsabilité propre à un acteur.
"""
import os

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
)


class CloudinaryError(Exception):
    """Échec de configuration ou d'upload — au service appelant de décider comment réagir."""


def upload_image(file_bytes: bytes, *, folder: str = "wink") -> str:
    if not cloudinary.config().cloud_name:
        raise CloudinaryError("Cloudinary non configuré (CLOUDINARY_CLOUD_NAME manquant dans .env).")

    try:
        result = cloudinary.uploader.upload(file_bytes, folder=folder, resource_type="image")
    except Exception as exc:
        # Large sur `Exception` volontairement : cloudinary.uploader.upload peut lever son
        # propre cloudinary.exceptions.Error, mais aussi des erreurs réseau (requests) selon
        # où ça échoue — capter les deux ici plutôt que de laisser fuiter un 500 générique.
        raise CloudinaryError(f"Échec de l'upload du logo vers Cloudinary : {exc}") from exc

    return result["secure_url"]


def upload_raw_file(file_bytes: bytes, *, folder: str = "wink") -> dict:
    """Pour les documents (PDF...), pas des images — `resource_type="raw"`, sinon

    Cloudinary tente de les traiter comme une image et échoue. Retourne aussi
    `public_id` (pas seulement l'URL) : `document_versions.cloudinary_public_id`
    en a besoin pour générer une URL signée si le document passe en privé.
    """
    if not cloudinary.config().cloud_name:
        raise CloudinaryError("Cloudinary non configuré (CLOUDINARY_CLOUD_NAME manquant dans .env).")

    try:
        result = cloudinary.uploader.upload(file_bytes, folder=folder, resource_type="raw")
    except Exception as exc:
        raise CloudinaryError(f"Échec de l'upload du document vers Cloudinary : {exc}") from exc

    return {"public_id": result["public_id"], "secure_url": result["secure_url"]}
