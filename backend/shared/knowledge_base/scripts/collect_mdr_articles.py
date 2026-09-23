"""Orchestrateur collecte MDR — EUR-Lex (service 3.3.6, volet HealthTech du

diagnostic sectoriel 3.3.5). Lancement : `python -m backend.shared.
knowledge_base.scripts.collect_mdr_articles` depuis `wink/`.

Décision actée le 20/09/2026 : collecte du texte MDR (règlement (UE)
2017/745) ENTIER, pas limité aux 3 chapitres du gap-analysis (voir
healthtech_gap_analysis_chapitres.py) — la RAG de ce service repose de toute
façon sur une recherche sémantique dans tout `content_embeddings` (domaine=
'secteur_healthtech'), pas sur un tag exact par chapitre, donc un corpus plus
large n'est jamais un problème pour la retrieval, seulement pour le coût de
collecte (voir ci-dessous).

Volume potentiellement comparable à l'AI Act (100+ articles) : mêmes
protections que collect_ai_act_articles.py contre l'épuisement de quota
Groq, MAIS sans aucun appel LLM du tout ici (voir
legal_article_heuristic_classifier_mdr.py pour le raisonnement complet —
notamment pourquoi aucune catégorie de risque par plage d'articles n'est
proposée, contrairement à l'AI Act) :
  - REPRISE : `list_article_numeros()` exclut les articles déjà upsertés
    lors d'un run précédent avant tout traitement — relancer ce script après
    une interruption (réseau, DB) est le comportement normal attendu.
  - Pertinence + chunking_suggere : 100% heuristique (mots-clés génériques
    de boilerplate procédural + longueur/marqueurs), zéro appel Groq.

FICHIERS DU PIPELINE :
  scrapers/mdr_dispositifs_medicaux/texte_mdr.py                — texte source (page EUR-Lex)
  scrapers/mdr_dispositifs_medicaux/mdr_client.py                — fetch_articles_in_text() (structure HTML non encore vérifiée sur un vrai appel, voir docstring)
  agents/ingestion/legal_article_heuristic_classifier_mdr.py     — pertinence + chunking_suggere (heuristiques, zéro LLM)
  backend/shared/knowledge_base/models/legal_texts.py
  backend/shared/knowledge_base/services/legal_texts_service.py

Aucune clé Groq requise pour ce script (contrairement à collect_secteur_
fintech_articles.py) — seule la migration h5c7d9e1f3a5 (CheckConstraint
content_embeddings.domaine) doit être appliquée avant chunk_and_embed_
legal_texts.py sur ce domaine, pas avant ce script qui n'écrit que dans
legal_texts (colonne domaine sans CheckConstraint, voir legal_texts.py).
"""
import sys

from agents.ingestion.legal_article_heuristic_classifier_mdr import (
    chunking_suggere_heuristique,
    evaluer_pertinence_heuristique,
)
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import list_article_numeros, upsert_legal_text
from scrapers.mdr_dispositifs_medicaux.mdr_client import fetch_articles_in_text
from scrapers.mdr_dispositifs_medicaux.texte_mdr import TEXTES_MDR


def run() -> None:
    compteurs = {
        "insere": 0,
        "ignore_non_pertinent": 0,
        "ignore_texte_vide": 0,
        "deja_collectes": 0,
    }

    for texte in TEXTES_MDR:
        articles = fetch_articles_in_text(texte.source_url)
        articles_valides = [a for a in articles if a["texte_brut"]]
        compteurs["ignore_texte_vide"] += len(articles) - len(articles_valides)

        db = SessionLocal()
        try:
            deja_collectes = list_article_numeros(db, code_source=texte.code_source)
            a_traiter = [a for a in articles_valides if a["article_numero"] not in deja_collectes]
            compteurs["deja_collectes"] += len(articles_valides) - len(a_traiter)

            for article in a_traiter:
                if not evaluer_pertinence_heuristique(article["texte_brut"]):
                    compteurs["ignore_non_pertinent"] += 1
                    continue
                upsert_legal_text(
                    db,
                    domaine_reglementaire=texte.domaine_reglementaire,
                    code_source=texte.code_source,
                    article_numero=article["article_numero"],
                    texte_brut=article["texte_brut"],
                    sous_theme=None,
                    chunking_suggere=chunking_suggere_heuristique(article["texte_brut"]),
                    type_source="article_loi",
                    source_url=texte.source_url,
                )
                compteurs["insere"] += 1
            db.commit()

            print(
                f"Texte '{texte.description}' — OK ({len(a_traiter)} articles traités ce run, "
                f"{compteurs['deja_collectes']} déjà collectés lors d'un run précédent)."
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(
        f"Terminé — {compteurs['insere']} articles insérés/mis à jour en 'extrait_automatique', "
        f"{compteurs['ignore_non_pertinent']} écartés (non pertinents), "
        f"{compteurs['ignore_texte_vide']} écartés (texte vide), "
        f"{compteurs['deja_collectes']} déjà collectés (sautés)."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(
            f"Erreur — arrêt de la collecte (les articles déjà commités avant cette erreur restent acquis, "
            f"relancer le script reprendra où il s'est arrêté) : {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
