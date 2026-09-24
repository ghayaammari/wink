"""Upload d'images vers Cloudinary — utilisé par `entrepreneur` (logo du projet, écran 9),

réutilisable par les autres acteurs plus tard (mêmes credentials, même config).
Placé dans `shared/services/` comme `email_service.py` : outil d'infra partagé,
pas une responsabilité propre à un acteur.
"""
import os
import uuid

import cloudinary
import cloudinary.uploader
import cloudinary.utils

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


def upload_raw_file(file_bytes: bytes, *, folder: str = "wink", filename: str | None = None) -> dict:
    """Pour les documents (PDF...), pas des images — `resource_type="raw"`, sinon

    Cloudinary tente de les traiter comme une image et échoue. Retourne aussi
    `public_id` (pas seulement l'URL) : `document_versions.cloudinary_public_id`
    en a besoin pour générer une URL signée si le document passe en privé.

    **Bug corrigé (trouvé via le coffre-fort documentaire, service 1.1.17)** :
    sans `public_id` explicite, Cloudinary génère pour un upload `raw` un
    identifiant SANS extension — `secure_url` se retrouve donc sans `.pdf`,
    et un fichier téléchargé depuis ce lien est illisible (l'OS ne sait pas
    quelle application ouvrir). `filename` (nom original envoyé par le
    navigateur, avec son extension) est repris ici tel quel dans `public_id`
    pour que l'URL Cloudinary porte la bonne extension dès l'upload.

    Pour les documents déjà uploadés AVANT ce correctif (donc toujours sans
    extension dans leur `secure_url` stocké), le contournement retenu n'est
    PAS une transformation Cloudinary à la volée (le flag `fl_attachment`
    testé initialement renvoie une erreur 400 sur ce compte, probablement une
    restriction de sécurité Cloudinary sur les transformations appliquées à
    des ressources `raw`) : c'est `document_vault_service.get_document_download()`
    qui télécharge les octets côté backend et les sert avec son propre header
    `Content-Disposition`, indépendamment de ce que Cloudinary expose.
    """
    if not cloudinary.config().cloud_name:
        raise CloudinaryError("Cloudinary non configuré (CLOUDINARY_CLOUD_NAME manquant dans .env).")

    upload_kwargs: dict = {"folder": folder, "resource_type": "raw"}
    if filename:
        _, ext = os.path.splitext(filename)
        if ext:
            upload_kwargs["public_id"] = f"{uuid.uuid4()}{ext}"

    try:
        result = cloudinary.uploader.upload(file_bytes, **upload_kwargs)
    except Exception as exc:
        raise CloudinaryError(f"Échec de l'upload du document vers Cloudinary : {exc}") from exc

    return {"public_id": result["public_id"], "secure_url": result["secure_url"]}


def build_signed_raw_url(public_id: str) -> str:
    """URL de téléchargement pour un fichier `raw` (PDF...) déjà uploadé via
    `upload_raw_file`.

    Depuis avril 2024, Cloudinary bloque par défaut la livraison publique
    (`res.cloudinary.com/.../raw/upload/...`) des ressources `raw`/PDF pour
    les comptes ("Restricted media types", Settings > Security) -- `secure_url`
    stockée en base renvoie donc 401 au téléchargement. **Un simple
    `cloudinary_url(sign_url=True)` ne suffit pas** : la restriction bloque le
    delivery type `upload` (dossier public du CDN) que la requête soit signée
    ou non -- seul le delivery type `authenticated` y échappe, et y passer
    demanderait de ré-uploader chaque fichier existant avec `type="authenticated"`.

    On utilise donc `private_download_url`, qui ne construit pas une URL CDN
    mais un lien vers l'API Cloudinary (`/raw/download`), authentifié par
    signature HMAC (api_key/api_secret, comme un appel Admin API) --
    indépendant du réglage "Restricted media types", qui ne s'applique qu'à
    la livraison CDN directe.
    """
    if not cloudinary.config().cloud_name:
        raise CloudinaryError("Cloudinary non configuré (CLOUDINARY_CLOUD_NAME manquant dans .env).")

    return cloudinary.utils.private_download_url(public_id, None, resource_type="raw", type="upload")
