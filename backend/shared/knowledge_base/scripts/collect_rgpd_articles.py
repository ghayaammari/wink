"""Orchestrateur collecte RGPD — partie Légifrance (service 3.3.1).
Lancement : `python -m backend.shared.knowledge_base.scripts.collect_rgpd_articles`
depuis `wink/` (même convention que collect_legal_texts_formes_juridiques.py).

Filtre pertinence + classification par HEURISTIQUE (pas de LLM), via
legal_article_heuristic_classifier_rgpd.py — CORRECTIF du 18/09/2026 :
cette étape utilisait auparavant le même service LLM que le service 1.1.1
(legal_text_structuring_service_rgpd.py), ce qui épuisait systématiquement
le quota Groq journalier (TPD) rien que pour collecter les articles de la
Loi n°78-17, un texte déjà choisi à la main parce qu'il parle de RGPD — voir
docstring de legal_article_heuristic_classifier_rgpd.py pour le raisonnement
complet et la dette technique assumée. collect_rgpd_guides.py (pages CNIL,
contenu éditorial hétérogène) garde le LLM, lui, car l'heuristique n'y
serait pas fiable. Conséquence pratique : ce script ne nécessite plus
GROQ_API_KEY du tout.
type_source='article_loi' rendu explicite ici (valeur par défaut) pour
lisibilité — cette source ne collecte que des articles de loi, contrairement
à collect_rgpd_guides.py.

FICHIERS DU PIPELINE :
  scrapers/legifrance/texte_loi_rgpd.py                        — texte source (Loi n°78-17 entière)
  scrapers/legifrance/legifrance_client.py                     — fetch_articles_in_text()
  agents/ingestion/legal_article_heuristic_classifier_rgpd.py  — filtre + classification (heuristique, sans LLM)
  backend/shared/knowledge_base/models/legal_texts.py
  backend/shared/knowledge_base/services/legal_texts_service.py
  backend/.env (LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET)

Préalable obligatoire : migration d3a9f21c6b48 appliquée (`alembic upgrade head`)
— sans elle, type_source n'existe pas et la CheckConstraint sur
content_embeddings.domaine rejette 'rgpd' (voir chunk_and_embed_legal_texts.py
pour cette 2e vérification, faite au moment de l'embedding, pas ici).

Commit PAR TEXTE (une seule itération ici puisqu'il n'y a qu'un seul texte
source dans TEXTES_RGPD, mais la boucle est gardée identique à
collect_legal_texts_formes_juridiques.py pour rester cohérente si un 2e texte
Légifrance RGPD est ajouté plus tard, ex: si le LEGITEXT de la loi 2018-493
s'avère nécessaire séparément).
"""
import sys

from agents.ingestion.legal_article_heuristic_classifier_rgpd import (
    classify_article_heuristique,
    filter_article_relevance_heuristique,
)
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import upsert_legal_text
from scrapers.legifrance.legifrance_client import fetch_articles_in_text
from scrapers.legifrance.texte_loi_rgpd import TEXTES_RGPD


def _process_article(db, texte, article: dict) -> str:
    texte_brut = article["texte_brut"]
    if not texte_brut:
        return "ignore_texte_vide"

    relevance = filter_article_relevance_heuristique(texte_brut)
    if not relevance.pertinent:
        return "ignore_non_pertinent"

    classification = classify_article_heuristique(texte_brut)
    upsert_legal_text(
        db,
        domaine_reglementaire=texte.domaine_reglementaire,
        code_source=texte.code_source,
        article_numero=article.get("article_numero"),
        texte_brut=texte_brut,
        sous_theme=classification.sous_theme,
        chunking_suggere=classification.chunking_suggere,
        type_source="article_loi",
        date_effet=article.get("date_effet"),
    )
    return "insere"


def run() -> None:
    compteurs = {"insere": 0, "ignore_non_pertinent": 0, "ignore_texte_vide": 0}
    for texte in TEXTES_RGPD:
        db = SessionLocal()
        try:
            articles = fetch_articles_in_text(texte.legifrance_source_id, fonds=texte.fonds)
            for article in articles:
                resultat = _process_article(db, texte, article)
                compteurs[resultat] = compteurs.get(resultat, 0) + 1
            db.commit()
            print(f"Texte '{texte.description}' — OK ({len(articles)} articles traités).")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(
        f"Terminé — {compteurs['insere']} articles insérés/mis à jour en 'extrait_automatique', "
        f"{compteurs['ignore_non_pertinent']} écartés (non pertinents), "
        f"{compteurs['ignore_texte_vide']} écartés (texte vide)."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — arrêt de la collecte (les textes déjà commités restent en base) : {exc}", file=sys.stderr)
        sys.exit(1)
