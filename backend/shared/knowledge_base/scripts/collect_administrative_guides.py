"""Orchestrateur de collecte web de `administrative_guides` (domaines
pacte_fondateurs, pre_depot — agent reglementaire, Increment 1).

Contrairement a `collect_sector_insurance_pages.py`, AUCUN appel LLM ici :
le `domaine` est fixe par le fichier `pages_*.py` de la source (voir
`AdministrativeGuideSeed`), pas devine/classifie — meme principe que
`forme_juridique_concernee` sur `legal_texts`. Ce script se contente de
recuperer les pages reelles (`fetch_page()`) et de les inserer telles
quelles en `extrait_automatique` ; la relecture humaine (dashboard,
`administrative_guides_validation_router.py`) est l'unique filtre avant
qu'un texte devienne cherchable par un agent.

Lancement : `python -m backend.shared.knowledge_base.scripts.collect_administrative_guides`
depuis `wink/`.

Commit PAR SOURCE (meme convention que les autres scripts de collecte) : un
echec sur une source garde les sources precedentes deja commitees.
"""
import sys

from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.administrative_guides_service import upsert_administrative_guide
from scrapers.shared.administrative_guide_seed import AdministrativeGuideSeed
from scrapers.shared.web_fetch import discover_links, fetch_page

import scrapers.bpifrance.pages_pacte_fondateurs as bpifrance_pacte_fondateurs
import scrapers.guichet_unique.pages_pre_depot as guichet_unique_pre_depot
import scrapers.bpifrance.pages_statuts as bpifrance_statuts
import scrapers.guichet_unique.pages_tarifs as guichet_unique_tarifs
import scrapers.economie_gouv.pages_annonce_legale as economie_gouv_annonce_legale

# Chaque entree = (nom affiche de la source, domaine fixe, liste de seeds).
# Ajouter une nouvelle source/domaine = ajouter une ligne ici (Open/Closed),
# meme principe que SOURCES dans collect_sector_insurance_pages.py.
SOURCES: list[tuple[str, str, list[AdministrativeGuideSeed]]] = [
    (bpifrance_pacte_fondateurs.NOM_SOURCE, bpifrance_pacte_fondateurs.DOMAINE, bpifrance_pacte_fondateurs.PAGES),
    (guichet_unique_pre_depot.NOM_SOURCE, guichet_unique_pre_depot.DOMAINE, guichet_unique_pre_depot.PAGES),
    (bpifrance_statuts.NOM_SOURCE, bpifrance_statuts.DOMAINE, bpifrance_statuts.PAGES),
    (guichet_unique_tarifs.NOM_SOURCE, guichet_unique_tarifs.DOMAINE, guichet_unique_tarifs.PAGES),
    (economie_gouv_annonce_legale.NOM_SOURCE, economie_gouv_annonce_legale.DOMAINE, economie_gouv_annonce_legale.PAGES),
]

# Plafond de securite par source, meme role que MAX_PAGES_PER_SOURCE dans
# collect_sector_insurance_pages.py.
MAX_PAGES_PER_SOURCE = 15


def _collect_candidate_urls(seed: AdministrativeGuideSeed) -> list[str]:
    print(f"  Seed : {seed.url}")
    page_racine = fetch_page(seed.url)
    if page_racine is None:
        print("    [SKIP] inaccessible (robots.txt, erreur reseau, ou contenu vide).")
        return []

    urls = [seed.url]
    if seed.max_liens_a_suivre > 0:
        liens = discover_links(page_racine.html_brut, seed.url, seed.max_liens_a_suivre)
        print(f"    {len(liens)} lien(s) decouvert(s) (plafond seed : {seed.max_liens_a_suivre}).")
        urls += liens

    return urls[:MAX_PAGES_PER_SOURCE]


def _process_source(db, nom_source: str, domaine: str, pages: list[AdministrativeGuideSeed]) -> int:
    print(f"\n=== Source : {nom_source} (domaine={domaine}, {len(pages)} seed(s)) ===")
    count = 0
    for seed in pages:
        for url in _collect_candidate_urls(seed):
            print(f"  Page : {url}")
            page = fetch_page(url)
            if page is None:
                print("    [SKIP] page inaccessible ou vide.")
                continue
            print(f"    {len(page.texte_extrait)} caractere(s) extrait(s) — titre : {page.titre!r}")
            upsert_administrative_guide(
                db,
                domaine=domaine,
                source_nom=nom_source,
                source_url=url,
                texte_brut=page.texte_extrait,
                titre=page.titre,
            )
            print("    ✓ Upsert en 'extrait_automatique'.")
            count += 1
    return count


def run() -> None:
    total = 0
    for nom_source, domaine, pages in SOURCES:
        db = SessionLocal()
        try:
            inserted = _process_source(db, nom_source, domaine, pages)
            db.commit()
            total += inserted
            print(f"Source '{nom_source}' — OK ({inserted} page(s) inseree(s)/mise(s) a jour).")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(f"\nTermine — {total} page(s) inseree(s)/mise(s) a jour en 'extrait_automatique'.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(
            f"Erreur — arret de la collecte (les sources deja commitees restent en base) : {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
