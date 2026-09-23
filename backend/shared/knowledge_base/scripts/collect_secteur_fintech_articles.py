"""Orchestrateur collecte FinTech — Code monétaire et financier, Chapitre II
(service 3.3.6, diagnostic d'écart, volet FinTech du diagnostic sectoriel
3.3.5). Lancement : `python -m backend.shared.knowledge_base.scripts.
collect_secteur_fintech_articles` depuis `wink/` (même convention que les
autres scripts de ce dossier).

Mirror direct de collect_legal_texts_formes_juridiques.py, pas de
collect_ai_act_articles.py : le bloc FinTech (Chapitre II, L522-1 à L522-20,
~20 articles, voir blocs_secteur_fintech.py) est du même ordre de grandeur que
les 3 blocs formes juridiques (66 articles au total) — pas besoin de
l'infrastructure heuristique construite pour l'AI Act (119 articles, quota
Groq épuisé par une classification 100% LLM, voir docstring de
collect_ai_act_articles.py). Les 2 appels LLM par article (filter_article_
relevance + classify_article, agents/ingestion/legal_text_structuring_
service.py) restent donc utilisés tels quels ici.

Pas de mécanisme de reprise (même limite assumée que
collect_legal_texts_formes_juridiques.py) : un échec en cours de bloc oblige
à retraiter (et re-facturer en appels LLM) tout le bloc au prochain run — non
bloquant vu le faible volume (1 seul bloc, ~20 articles).

FICHIERS DU PIPELINE :
  scrapers/legifrance/blocs_secteur_fintech.py    — bloc à collecter (pure donnée)
  scrapers/legifrance/legifrance_client.py        — fetch_articles_in_block()
  agents/ingestion/legal_text_structuring_service.py — filter_article_relevance() + classify_article()
  backend/shared/knowledge_base/models/legal_texts.py
  backend/shared/knowledge_base/services/legal_texts_service.py
  backend/.env (LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET / GROQ_API_KEY)

Aucun forme_juridique_concernee ici (champ propre au volet formes juridiques,
laissé à sa valeur par défaut '{}' pour ce domaine — voir legal_texts.py).
"""
import sys

from agents.ingestion.legal_text_structuring_service import classify_article, filter_article_relevance
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import upsert_legal_text
from scrapers.legifrance.blocs_secteur_fintech import BLOCS_SECTEUR_FINTECH
from scrapers.legifrance.legifrance_client import fetch_articles_in_block


def _process_article(db, bloc, article: dict) -> str:
    texte_brut = article["texte_brut"]
    if not texte_brut:
        return "ignore_texte_vide"

    relevance = filter_article_relevance(texte_brut)
    if not relevance.pertinent:
        return "ignore_non_pertinent"

    classification = classify_article(texte_brut)
    upsert_legal_text(
        db,
        domaine_reglementaire=bloc.domaine_reglementaire,
        code_source=bloc.code_source,
        article_numero=article.get("article_numero"),
        texte_brut=texte_brut,
        sous_theme=classification.sous_theme,
        chunking_suggere=classification.chunking_suggere,
        date_effet=article.get("date_effet"),
    )
    return "insere"


def run() -> None:
    compteurs = {"insere": 0, "ignore_non_pertinent": 0, "ignore_texte_vide": 0}
    for bloc in BLOCS_SECTEUR_FINTECH:
        db = SessionLocal()
        try:
            articles = fetch_articles_in_block(bloc.legifrance_source_id, bloc.legifrance_section_id)
            for article in articles:
                resultat = _process_article(db, bloc, article)
                compteurs[resultat] = compteurs.get(resultat, 0) + 1
            db.commit()
            print(f"Bloc '{bloc.description}' — OK ({len(articles)} articles traités).")
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
        print(f"Erreur — arrêt de la collecte (les blocs déjà commités restent en base) : {exc}", file=sys.stderr)
        sys.exit(1)
