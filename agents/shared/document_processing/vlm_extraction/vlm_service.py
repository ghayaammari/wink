"""Extrait le texte brut d'un document PDF via un modèle de vision (VLM) hébergé
sur Groq — une page = une image envoyée au modèle, texte concaténé dans l'ordre.

Pourquoi un VLM systématique plutôt qu'une extraction de texte natif avec repli
VLM seulement si besoin : voir "Wink — Extraction de document : deux approches
comparées" (Notion). Approche B retenue — reste simple à ce stade (MVP, faible
volume) plutôt que d'ajouter une détection de qualité (ratio de mots reconnus,
détection de langue) fragile à calibrer et à maintenir.

PDF uniquement pour l'instant (décision explicite) — DOCX/PPTX nécessiteraient une
conversion supplémentaire (LibreOffice headless), écartée pour l'instant faute de
besoin confirmé.
"""

import base64
import io
import os

from groq import Groq
from pdf2image import convert_from_bytes

from agents.config.loader import get_llm_config, get_prompts


class VlmExtractionError(Exception):
    """Échec de conversion PDF→images ou d'appel au VLM — au service appelant de décider comment réagir."""


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise VlmExtractionError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _pdf_to_page_images(pdf_bytes: bytes) -> list[bytes]:
    # POPPLER_PATH optionnel : pdf2image cherche poppler (pdftoppm/pdfinfo) dans le
    # PATH système par défaut. Sur Windows, ajouter poppler au PATH nécessite souvent
    # de rouvrir le terminal (ou les droits admin selon comment le PATH est édité) —
    # POPPLER_PATH permet de pointer directement vers le dossier bin/ de poppler
    # depuis .env, sans toucher au PATH. Absent = comportement inchangé (cherche
    # dans le PATH, cas normal sur Linux/macOS où poppler s'installe via le gestionnaire
    # de paquets système).
    poppler_path = os.environ.get("POPPLER_PATH") or None
    try:
        pages = convert_from_bytes(pdf_bytes, fmt="jpeg", poppler_path=poppler_path)
    except Exception as exc:
        # Large sur `Exception` volontairement : convert_from_bytes peut lever des erreurs
        # de nature très différente (PDF corrompu, poppler absent du système...).
        raise VlmExtractionError(f"Échec de conversion du PDF en images : {exc}") from exc

    images: list[bytes] = []
    for page in pages:
        buffer = io.BytesIO()
        page.save(buffer, format="JPEG")
        images.append(buffer.getvalue())
    return images


def _image_to_data_url(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def extract_text(pdf_bytes: bytes) -> str:
    """Retourne le texte de toutes les pages du PDF, dans l'ordre.

    Découpé en lots de `max_images_per_request` images (limite du modèle Groq,
    voir llm_config.yaml) — un appel par lot, résultats concaténés dans l'ordre.
    """
    config = get_llm_config()["document_processing"]["vlm"]
    client = _get_client()

    page_images = _pdf_to_page_images(pdf_bytes)
    if not page_images:
        raise VlmExtractionError("Le PDF ne contient aucune page exploitable.")

    prompt_text = get_prompts()["document_processing"]["vlm"]["transcription"]

    extracted_pages: list[str] = []
    for batch in _chunk(page_images, config["max_images_per_request"]):
        content = [{"type": "text", "text": prompt_text}]
        for image_bytes in batch:
            content.append({"type": "image_url", "image_url": {"url": _image_to_data_url(image_bytes)}})

        try:
            response = client.chat.completions.create(
                model=config["model"],
                messages=[{"role": "user", "content": content}],
                temperature=config["temperature"],
            )
        except Exception as exc:
            raise VlmExtractionError(f"Échec de l'appel au VLM (Groq) : {exc}") from exc

        extracted_pages.append(response.choices[0].message.content or "")

    return "\n\n".join(extracted_pages)
