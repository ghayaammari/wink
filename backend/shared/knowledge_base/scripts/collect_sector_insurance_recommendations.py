"""Orchestrateur de collecte des recommandations d'assurance sectorielles
(service 1.1.10, Groupe 2, volet base legale). Pour chaque bloc, fetch via
Legifrance → 1 seul appel LLM par article (chunking uniquement) → upsert dans
`legal_texts` (source de verite du texte) → 1 seul upsert dans
`sector_insurance_recommendations` par article, avec tous les secteurs
concernes par le bloc dans le meme tableau (juste une FK vers `legal_texts`,
pas de texte duplique).

CORRECTIF du 11/09/2026 (voir plan de correction) — avant cette version :
  - `type_assurance`/`a_base_legale` etaient devines par le LLM, une fois par
    (article x secteur) : redondant (le meme article envoye au LLM jusqu'a
    11 fois) et source d'ecrasement silencieux entre articles (upsert clé sur
    (secteur, type_assurance) seul, sans identifiant d'article).
  - le texte de l'article etait duplique directement dans
    `sector_insurance_recommendations.texte_brut` au lieu de vivre une seule
    fois dans `legal_texts`.
Desormais : `type_assurance`/`a_base_legale` sont fixes par bloc (chaque bloc
est choisi precisement parce qu'il correspond a un type d'obligation connu —
meme principe que `secteurs_concernes`), seul `chunking_suggere` reste un
jugement LLM (1 appel par article, plus par secteur). Correctif
complementaire du meme jour : `secteur` (scalaire) devient `secteurs` (array)
sur `sector_insurance_recommendations` — 1 ligne par article au lieu d'1 ligne
par (article, secteur), voir ce modele.

Lancement :
  python -m backend.shared.knowledge_base.scripts.collect_sector_insurance_recommendations
depuis `wink/`.

Commit PAR BLOC (meme convention que le script forme juridique) : un echec
sur un bloc garde les blocs precedents deja commites.

FICHIERS DU PIPELINE (pour tout retrouver depuis ce seul point d'entree) :

  scrapers/legifrance/blocs_secteurs_assurance.py
      Liste des blocs Legifrance a collecter, avec secteurs_concernes et
      type_assurance fixes.

  scrapers/legifrance/legifrance_client.py
      API PISTE/Legifrance (reutilise tel quel, aucune modification).

  agents/config/llm_config.yaml (section sector_insurance_structuration.chunking)
  agents/config/prompts.yaml (section sector_insurance_structuration.chunking)
      Modele, temperature, prompt de l'appel LLM (chunking uniquement).

  agents/ingestion/sector_insurance_structuring_service.py
      Appel LLM : detect_chunking() → chunking_suggere, sans secteur (fonction
      partagee avec le volet 2, voir ce fichier).

  backend/shared/knowledge_base/models/legal_texts.py
  backend/shared/knowledge_base/services/legal_texts_service.py
      Table et persistance du texte source (reutilises tels quels, deja
      ecrits pour le service 1.1.1).

  backend/shared/knowledge_base/models/sector_insurance_recommendations.py
  backend/shared/knowledge_base/services/sector_insurance_recommendations_service.py
      Modele et persistance de la table de mapping article → secteur.
"""
import sys

from agents.ingestion.sector_insurance_structuring_service import detect_chunking
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import get_legal_text, upsert_legal_text
from backend.shared.knowledge_base.services.sector_insurance_recommendations_service import (
    upsert_sector_insurance,
)
from scrapers.legifrance.blocs_secteurs_assurance import BLOCS_ASSURANCE
from scrapers.legifrance.legifrance_client import fetch_articles_in_block


def _process_article(db, bloc, article: dict) -> int:
    """Traite un article : 1 seul appel LLM (chunking) SI le texte a change
    depuis la derniere collecte, sinon reutilise le chunking_suggere deja en
    base (skip ajoute le 11/09/2026 — evite de regaspiller du quota Groq sur
    des articles deja collectes quand le script est relance apres une erreur
    de quota, voir run()). Puis 1 seul upsert dans
    sector_insurance_recommendations pour cet article, avec tous les secteurs
    du bloc dans le meme tableau. Retourne 1 si une ligne a ete
    inseree/mise a jour, 0 si l'article n'avait pas de texte."""
    texte_brut = article["texte_brut"]
    if not texte_brut:
        return 0

    existing = get_legal_text(db, code_source=bloc.code_source, article_numero=article["article_numero"])
    if existing is not None and existing.texte_brut == texte_brut:
        chunking_suggere = existing.chunking_suggere
    else:
        chunking_suggere = detect_chunking(texte_brut).chunking_suggere

    legal_text, _ = upsert_legal_text(
        db,
        domaine_reglementaire=bloc.domaine_reglementaire,
        code_source=bloc.code_source,
        article_numero=article["article_numero"],
        texte_brut=texte_brut,
        chunking_suggere=chunking_suggere,
        date_effet=article.get("date_effet"),
    )

    upsert_sector_insurance(
        db,
        legal_text_id=legal_text.id,
        secteurs=bloc.secteurs_concernes,
        type_assurance=bloc.type_assurance,
        a_base_legale=True,
    )
    return 1


def run() -> None:
    total_inserts = 0
    total_articles = 0
    for bloc in BLOCS_ASSURANCE:
        db = SessionLocal()
        try:
            articles = fetch_articles_in_block(bloc.legifrance_source_id, bloc.legifrance_section_id)
            total_articles += len(articles)
            for article in articles:
                total_inserts += _process_article(db, bloc, article)
            db.commit()
            print(
                f"Bloc '{bloc.description}' — OK "
                f"({len(articles)} articles, {len(bloc.secteurs_concernes)} secteurs)."
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(
        f"Termine — {total_articles} articles traites, "
        f"{total_inserts} lignes inserees/mises a jour en 'extrait_automatique'."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(
            f"Erreur — arret de la collecte (les blocs deja commites restent en base) : {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
