"""Orchestrateur Phase 1 (collecte) — service 1.1.1, forme juridique (Groupe 2).
Lancement : `python -m backend.shared.knowledge_base.scripts.collect_legal_texts_formes_juridiques`
depuis `wink/` (même convention que `seed_roadmap_nodes.py`).

Reprend "Wink — Plan d'action : Collecte, puis Chunking/Embedding des formes
juridiques (4)" (Notion), Étapes 1.1 à 1.5 uniquement — Étape 1.6 (relecture
humaine → valide_humain) dépend du dashboard de validation, pas encore construit.
Ce script s'arrête donc à l'insertion en `statut_contenu='extrait_automatique'` :
RIEN n'est jamais inséré directement en `valide_humain` ici.

RECENTRÉ (page (4)) : 3 blocs seulement, pas 14 — la collecte est restreinte
aux formes réellement proposées par la roadmap (SAS/SASU, SARL/EURL), voir
blocs_formes_juridiques.py pour le détail et les blocs écartés.

FICHIERS DU PIPELINE — pour tout retrouver depuis ce seul point d'entrée, sans
chercher dans plusieurs dossiers de mémoire :

  scrapers/legifrance/blocs_formes_juridiques.py
      Liste des 3 blocs Légifrance à collecter (pure donnée), avec la valeur
      fixe de forme_juridique_concernee pour chacun (voir plus bas).

  scrapers/legifrance/legifrance_client.py
      Parle à l'API PISTE/Légifrance (auth OAuth2 + fetch_articles_in_block()).

  agents/config/llm_config.yaml (section legal_text_structuration)
  agents/config/prompts.yaml (section legal_text_structuration)
      Modèle, température, prompts des 2 appels LLM ci-dessous.

  agents/ingestion/legal_text_structuring_service.py
      Les 2 appels LLM : filter_article_relevance() (Étape 1.3) et
      classify_article() (Étape 1.4 — sous_theme + chunking_suggere
      uniquement ; forme_juridique_concernee N'EST PLUS demandée au LLM, voir
      ci-dessous).

  backend/shared/knowledge_base/models/legal_texts.py
      Le modèle SQLAlchemy de la table cible.

  backend/shared/knowledge_base/services/legal_texts_service.py
      upsert_legal_text() — écriture DB pure, idempotente par
      (code_source, article_numero).

  backend/.env (LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET / GROQ_API_KEY)
      Credentials nécessaires aux 2 fichiers ci-dessus qui en dépendent.

forme_juridique_concernee FIXE par bloc, pas devinée par le LLM (Notion,
Étape 1.4, "Corrigé") : lue directement sur `bloc.forme_juridique_concernee`
dans _process_article() ci-dessous, jamais sur le résultat de classify_article().

Commit PAR BLOC (3 transactions séparées), PAS une seule transaction globale
comme seed_roadmap_nodes.py : un échec sur un bloc garde les blocs précédents
déjà commités. Limite connue : relancer tout le script après un échec retraite
(et re-facture en appels LLM) les blocs déjà réussis, faute de mécanisme de
"reprise" — pas construit pour l'instant (voir compromis).
"""
import sys

from agents.ingestion.legal_text_structuring_service import classify_article, filter_article_relevance
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import upsert_legal_text
from scrapers.legifrance.blocs_formes_juridiques import BLOCS_FORMES_JURIDIQUES
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
        forme_juridique_concernee=bloc.forme_juridique_concernee,
        chunking_suggere=classification.chunking_suggere,
        date_effet=article.get("date_effet"),
    )
    return "insere"


def run() -> None:
    compteurs = {"insere": 0, "ignore_non_pertinent": 0, "ignore_texte_vide": 0}
    for bloc in BLOCS_FORMES_JURIDIQUES:
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
