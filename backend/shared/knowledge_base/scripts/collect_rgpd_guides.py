"""Orchestrateur collecte RGPD — partie CNIL (service 3.3.1). Complète
collect_rgpd_articles.py (Légifrance) : ici, du texte éditorial (guides HTML,
PDF), pas des articles de loi structurés.

Lancement :
  python -m backend.shared.knowledge_base.scripts.collect_rgpd_guides
depuis `wink/`. Aucune clé PISTE nécessaire (indépendant de Légifrance) —
seul GROQ_API_KEY est requis (filtre + classification LLM).

DIFFÉRENCE avec collect_sector_insurance_pages.py (le seul autre pipeline de
collecte web du repo) : celui-ci écrit dans une table dédiée
(sector_insurance_recommendations), clé par (type_assurance, source_url).
Ici on écrit dans `legal_texts` (décision du 15/09/2026 : type_source
distingue article_loi/guide_pratique/pdf, pas de table séparée) — legal_texts
est clé sur (code_source, article_numero), sans colonne source_url dédiée à
l'unicité. Pour rester idempotent (relancer ce script met à jour, ne duplique
pas), `code_source` = l'URL de la page elle-même (article_numero reste NULL
pour toutes) : chaque URL curée dans pages_rgpd.py produit une ligne stable et
distincte, comme le ferait un vrai identifiant métier.

Pas de crawling (discover_links) ici : toutes les PageSeed de pages_rgpd.py
ont max_liens_a_suivre=0 (curation stricte, voir ce fichier) — contrairement
à collect_sector_insurance_pages.py qui découvre des liens depuis une seed.

type_source déterminé par page.html_brut vide ou non (voir FetchedPage dans
web_fetch.py : vide seulement pour un PDF) — pas par une valeur portée par
PageSeed (qui n'a pas ce champ, voir pages_rgpd.py).

Troncature de l'extrait envoyé au LLM (_TEXTE_CLASSIFICATION_LONGUEUR_MAX) :
même précaution que collect_sector_insurance_pages.py (correctif du
12/09/2026 sur un 413 Groq, guide PDF trop long envoyé en entier à la
classification) — texte_brut stocké en base reste le texte COMPLET, seul
l'appel LLM est tronqué.

FICHIERS DU PIPELINE :
  scrapers/cnil/pages_rgpd.py                                — URLs curées
  scrapers/shared/web_fetch.py                                — fetch_page()
  agents/ingestion/legal_text_structuring_service_rgpd.py     — filtre + classification
  backend/shared/knowledge_base/services/legal_texts_service.py — upsert_legal_text()
  backend/.env (GROQ_API_KEY)

Préalable : migration d3a9f21c6b48 appliquée (type_source + domaine 'rgpd').

Commit PAR PAGE (pas par lot) : une page qui échoue (LLM, réseau) n'annule pas
les pages déjà traitées avant elle dans cette même exécution.
"""
import sys

from agents.ingestion.legal_text_structuring_service_rgpd import classify_article, filter_article_relevance
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import upsert_legal_text
from scrapers.cnil.pages_rgpd import NOM_SOURCE, PAGES
from scrapers.shared.web_fetch import fetch_page

_TEXTE_CLASSIFICATION_LONGUEUR_MAX = 3000


def _type_source(html_brut: str) -> str:
    return "pdf" if not html_brut else "guide_pratique"


def _process_page(db, url: str) -> str:
    page = fetch_page(url)
    if page is None:
        return "ignore_inaccessible"
    if not page.texte_extrait:
        return "ignore_texte_vide"

    extrait = page.texte_extrait[:_TEXTE_CLASSIFICATION_LONGUEUR_MAX]
    relevance = filter_article_relevance(extrait)
    if not relevance.pertinent:
        return "ignore_non_pertinent"

    classification = classify_article(extrait)
    upsert_legal_text(
        db,
        domaine_reglementaire="rgpd",
        code_source=url,
        article_numero=None,
        texte_brut=page.texte_extrait,
        sous_theme=classification.sous_theme,
        chunking_suggere=classification.chunking_suggere,
        type_source=_type_source(page.html_brut),
        source_url=url,
    )
    return "insere"


def run() -> None:
    compteurs = {"insere": 0, "ignore_non_pertinent": 0, "ignore_texte_vide": 0, "ignore_inaccessible": 0}
    for seed in PAGES:
        db = SessionLocal()
        try:
            print(f"Page : {seed.url}")
            resultat = _process_page(db, seed.url)
            compteurs[resultat] = compteurs.get(resultat, 0) + 1
            db.commit()
            print(f"  → {resultat}")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(
        f"\nTerminé ({NOM_SOURCE}) — {compteurs['insere']} page(s) insérée(s)/mise(s) à jour, "
        f"{compteurs['ignore_non_pertinent']} écartée(s) (non pertinentes), "
        f"{compteurs['ignore_texte_vide']} écartée(s) (texte vide), "
        f"{compteurs['ignore_inaccessible']} inaccessible(s)."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — arrêt de la collecte (les pages déjà commitées restent en base) : {exc}", file=sys.stderr)
        sys.exit(1)
