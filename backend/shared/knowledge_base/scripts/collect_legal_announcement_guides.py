"""Collecte des guides pratiques officiels sur l'annonce légale (service
1.1.5, copilot) -> `legal_announcement_guides`.

Lancement : `python -m backend.shared.knowledge_base.scripts.collect_legal_announcement_guides`
depuis `wink/`.

Principe (repris du 1.1.10) : `texte_brut` ne provient QUE d'un vrai
`fetch_page()` (robots.txt, rate-limit, User-Agent identifiant) — jamais écrit
à la main ni par un LLM. Liste d'URLs curatée, pas de crawling, pas de filtre
LLM (sobre : la pertinence est vérifiée à la curation).

Commit PAR SOURCE : un échec sur une source garde les précédentes.
Ensuite : relecture humaine (`/knowledge-base/legal-announcement-guides/...`),
puis `chunk_and_embed_legal_announcement_guides`.
"""
import sys

import scrapers.bpifrance.pages_annonce_legale as bpifrance
import scrapers.economie_gouv.pages_annonce_legale as economie_gouv
import scrapers.service_public.pages_annonce_legale as service_public
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_announcement_guides_service import upsert_guide
from scrapers.shared.guide_page import GuidePage
from scrapers.shared.web_fetch import fetch_page

# Ajouter une source = ajouter une ligne ici (Open/Closed).
SOURCES: list[tuple[str, list[GuidePage]]] = [
    (service_public.NOM_SOURCE, service_public.PAGES),
    (economie_gouv.NOM_SOURCE, economie_gouv.PAGES),
    (bpifrance.NOM_SOURCE, bpifrance.PAGES),
]


def run() -> None:
    total = 0
    for nom_source, pages in SOURCES:
        db = SessionLocal()
        try:
            print(f"\n=== Source : {nom_source} ({len(pages)} page(s)) ===")
            for guide in pages:
                page = fetch_page(guide.url)
                if page is None:
                    print(f"  [SKIP] {guide.url} inaccessible (robots.txt, réseau ou contenu vide).")
                    continue
                _, cree = upsert_guide(
                    db,
                    source_nom=nom_source,
                    source_url=guide.url,
                    titre=page.titre,
                    sous_theme=guide.sous_theme,
                    texte_brut=page.texte_extrait,
                )
                print(f"  ✓ {'créé' if cree else 'mis à jour'} : {page.titre!r} ({len(page.texte_extrait)} caractères)")
                total += 1
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    print(f"\nTerminé — {total} page(s) en 'extrait_automatique'. Relecture humaine avant embedding.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — arrêt de la collecte (les sources déjà commitées restent en base) : {exc}", file=sys.stderr)
        sys.exit(1)
