"""Service — appels LLM (Qwen via Groq) pour l'analyse des papiers de
recherche. Groq est compatible SDK OpenAI (endpoint custom), tier gratuit
sans carte bancaire — voir https://console.groq.com/keys.

Ne touche jamais la base de données : appelle l'API, retourne des dicts.
L'orchestration (session DB, création des enregistrements) reste dans
research_extraction_service.py, qui appelle ce fichier.

Deux usages distincts, correspondant aux deux catégories de champs du schéma
(voir §2 du récap) :
1. extract_direct_fields — champs factuels (titre, auteurs, résumé fourni
   par l'auteur, venue, doi) : le modèle restitue ce qui EST dans le texte,
   sans reformuler. Stockés directement sur research_works, pas de
   validation nécessaire (le chercheur peut corriger via PATCH s'il y a une
   erreur d'extraction).
2. generate_reformulated_fields — champs analytiques (paper_summary,
   methodology, key_findings, application_domains) : le modèle produit un
   texte nouveau, jamais copié tel quel du papier. Toujours en
   pending_confirmation via researcher_field_values (source=llm_generated)
   — même mécanisme de validation que pour un travail extrait de HAL/OpenAlex.

Dette technique assumée : tier gratuit Groq = limites de débit non publiées
précisément par Groq. Si le volume de dépôts augmente, prévoir soit un plan
payant Groq, soit un fallback vers un autre fournisseur — à documenter dans
DECISIONS.md le jour où ça devient un vrai sujet, pas avant (I0 = faible
volume, un seul chercheur de test).
"""
import logging

from backend.chercheur.services.llm_client import LLMExtractionError, call_and_parse

_ALLOWED_PUBLICATION_TYPES = {"article", "communication", "these", "brevet", "rapport"}

logger = logging.getLogger(__name__)


def extract_direct_fields(raw_text: str) -> dict:
    """Champs factuels du papier, restitués tels quels, sans reformulation.
    Toujours dans les ~2 premières pages d'un papier académique standard —
    on tronque pour rester raisonnable en tokens plutôt que d'envoyer le
    papier entier pour ces infos-là."""
    excerpt = raw_text[:15000]
    prompt = f"""Voici le texte extrait d'un papier de recherche. Restitue UNIQUEMENT les champs suivants, EXACTEMENT tels qu'ils apparaissent dans le texte (ne reformule rien, ne résume rien) :
- title : le titre du papier
- authors : liste des noms d'auteurs
- abstract : le résumé fourni par les auteurs, s'il existe, tel quel
- venue : nom de la revue/conférence, si mentionné
- doi : le DOI, si mentionné
- publication_type : un seul choix parmi article, communication, these, brevet, rapport (déduis du contexte)

Si un champ est introuvable, mets null. Réponds UNIQUEMENT en JSON valide, aucun texte autour, aucun bloc de code.

Texte du papier :
{excerpt}"""

    result = call_and_parse(prompt, max_tokens=1000)

    if result.get("publication_type") not in _ALLOWED_PUBLICATION_TYPES:
        # cas limite : le modèle peut halluciner une valeur hors de la liste
        # (ex: "preprint") — mieux vaut null qu'une valeur qui viole le CHECK
        # constraint SQL et fait planter tout le job de fond.
        result["publication_type"] = None

    if not result.get("title"):
        # cas limite : jamais laisser title vide, la colonne est NOT NULL.
        result["title"] = "Titre non détecté"

    return result


def generate_reformulated_fields(raw_text: str, direct_fields: dict) -> dict:
    """Champs analytiques — jamais du texte copié tel quel du papier, toujours
    une synthèse à valider par le chercheur (source=llm_generated).

    paper_summary est rédigé EN DERNIER par le modèle, après methodology/
    key_findings/application_domains : il doit les intégrer pour être
    auto-suffisant, car c'est CE champ qui alimentera le matching
    chercheur-startup (I6) — pas une paraphrase de l'abstract.

    methodology et key_findings peuvent être null si non identifiables dans
    le texte (papier trop court, extraction PDF incomplète...). application_domains
    est toujours une liste, vide si rien de clair ne se dégage — jamais null,
    pour que l'appelant n'ait pas à distinguer null vs liste vide."""
    excerpt = raw_text[:15000]
    title = direct_fields.get("title") or "ce papier"
    prompt = f"""Analyse le texte de recherche suivant ("{title}") et produis, dans cet ordre :

1. methodology : méthodologie utilisée, en 2-3 phrases. Si non identifiable dans le texte, null.
2. key_findings : résultats/conclusions clés du papier, en 2-4 phrases. Si non identifiable, null.
3. application_domains : liste de secteurs d'usage concrets où ce travail pourrait être utile (ex: "santé", "finance", "robotique") — pas le domaine scientifique du papier, des domaines d'APPLICATION potentiels. Liste vide si rien de clair ne se dégage.
4. paper_summary : une fois les 3 champs ci-dessus déterminés, rédige un résumé synthétique en 4-6 phrases qui intègre la méthodologie, les résultats clés et les domaines d'application. Ce résumé sera utilisé pour mettre en correspondance ce chercheur avec des startups ayant un besoin scientifique déclaré — il doit être autonome et donner une image complète et exploitable du travail.

Réponds UNIQUEMENT en JSON valide avec les clés methodology, key_findings, application_domains (liste de strings), paper_summary. Aucun texte autour, aucun bloc de code.

Texte du papier :
{excerpt}"""

    result = call_and_parse(prompt, max_tokens=1000)
    if result.get("application_domains") is None:
        result["application_domains"] = []
    return result