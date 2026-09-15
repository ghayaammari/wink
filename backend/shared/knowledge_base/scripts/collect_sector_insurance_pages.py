"""Orchestrateur de collecte web du volet non-legal de
`sector_insurance_recommendations` (service 1.1.10, Groupe 2). Remplace
l'ancien `seed_sector_insurance_non_legal.py` (supprime — contenu non
verifie, redige a la main plutot qu'extrait de vraies pages).

Principe central, pour ne jamais reproduire cette erreur : `texte_brut` ne
provient QUE d'un `fetch_page()` reel (voir `scrapers/shared/web_fetch.py`).
Aucun texte n'est ecrit par le LLM ni par un humain ici — le LLM ne fait que
FILTRER (pertinent/non pertinent) et CLASSIFIER (quel type d'assurance) du
texte deja extrait d'une vraie page.

Lancement :
  python -m backend.shared.knowledge_base.scripts.collect_sector_insurance_pages
depuis `wink/`.

Commit PAR SOURCE (meme convention que les autres scripts de collecte) : un
echec sur une source garde les sources precedentes deja commitees.

LOGS (ajoute le 12/09/2026, sur demande — l'execution etait trop silencieuse
pour suivre ce qui se passait reellement) : chaque etape imprime une ligne —
recuperation de la page racine, nombre de liens decouverts, page traitee,
resultat du filtre par secteur, resultat de la classification, upsert final.
Les pauses liees au rate-limit Groq sont loggees dans
`sector_insurance_structuring_service.py` (elles s'affichent entrelacees ici).

FICHIERS DU PIPELINE :

  scrapers/shared/web_fetch.py
      fetch_page() (robots.txt + rate-limit + cache + extraction HTML/PDF),
      discover_links() (crawling borne, meme domaine uniquement).

  scrapers/shared/page_seed.py
      Dataclass PageSeed (url, secteurs_cibles, max_liens_a_suivre).

  scrapers/<source>/pages_assurance.py
      URLs de depart par source de confiance, curees a la main.

  agents/ingestion/sector_insurance_structuring_service.py
      filter_page_relevance() (filtre bon marche) puis classify_insurance_text()
      (classification complete), tous deux deja existants pour le volet Legifrance.
      Contient aussi le rate-limiting Groq (voir sa docstring, correctif du
      12/09/2026).

  backend/shared/knowledge_base/services/sector_insurance_recommendations_service.py
      upsert_sector_insurance() — meme fonction de persistance que le volet legal.
"""
import sys

from agents.ingestion.sector_insurance_structuring_service import (
    classify_insurance_text,
    filter_page_relevance,
)
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.sector_insurance_recommendations_service import (
    upsert_sector_insurance,
)
from scrapers.shared.page_seed import PageSeed
from scrapers.shared.web_fetch import discover_links, fetch_page

import scrapers.bpifrance.pages_assurance as bpifrance
import scrapers.cci_paris_idf.pages_assurance as cci_paris_idf
import scrapers.france_assureurs.pages_assurance as france_assureurs

# Chaque entree = (nom affiche de la source, liste de PageSeed). Ajouter une
# nouvelle source = ajouter une ligne ici, aucune autre logique a toucher
# (Open/Closed) — meme principe que BLOCS_ASSURANCE pour le volet Legifrance.
SOURCES: list[tuple[str, list[PageSeed]]] = [
    (bpifrance.NOM_SOURCE, bpifrance.PAGES),
    (france_assureurs.NOM_SOURCE, france_assureurs.PAGES),
    (cci_paris_idf.NOM_SOURCE, cci_paris_idf.PAGES),
]

# Plafond de securite par source : borne le volume total (au-dela du plafond
# par seed deja impose par max_liens_a_suivre), le cout LLM, et la charge sur
# les serveurs distants.
MAX_PAGES_PER_SOURCE = 15
# Longueur de l'extrait passe au filtre LLM bon marche (avant classification
# complete) — pas la peine d'envoyer toute la page pour decider pertinent/non.
_EXTRAIT_FILTRE_LONGUEUR = 500
# Longueur max du texte envoye a la classification complete (distincte de
# _EXTRAIT_FILTRE_LONGUEUR ci-dessus). Ajoutee le 12/09/2026 suite a une 413
# Groq (tier on_demand, gpt-oss-120b, limite 8000 tokens/minute) : le guide
# PDF France Assureurs, envoye en entier, demandait a lui seul plus de 10000
# tokens. `texte_brut` stocke en base reste le texte COMPLET reellement
# extrait par fetch_page() (voir upsert plus bas) — seul l'appel de
# classification est tronque. Dette technique assumee : une reference legale
# situee au-dela de cette longueur pourrait etre manquee (a_base_legale
# resterait `false`) — ne fait que renforcer la prudence deja voulue par le
# projet (jamais presume `true` par defaut), jamais la relacher.
#
# A elle seule, cette troncature n'a PAS suffi (voir
# sector_insurance_structuring_service.py) : le plafond Groq est cumule par
# minute, pas par requete — le vrai correctif est le rate-limiting ajoute
# dans ce module. Elle reste utile en defense complementaire (garde chaque
# requete individuellement legere).
_TEXTE_CLASSIFICATION_LONGUEUR_MAX = 3000


def _collect_candidate_urls(seed: PageSeed) -> list[str]:
    print(f"  Seed racine : {seed.url}")
    page_racine = fetch_page(seed.url)
    if page_racine is None:
        print(f"    [SKIP] inaccessible (robots.txt, erreur reseau, ou contenu vide).")
        return []

    urls = [seed.url]
    if seed.max_liens_a_suivre > 0:
        liens = discover_links(page_racine.html_brut, seed.url, seed.max_liens_a_suivre)
        print(f"    {len(liens)} lien(s) decouvert(s) (plafond seed : {seed.max_liens_a_suivre}).")
        urls += liens
    else:
        print("    0 lien a suivre (PDF ou max_liens_a_suivre=0).")

    urls = urls[:MAX_PAGES_PER_SOURCE]
    print(f"    → {len(urls)} page(s) au total a traiter pour cette seed (plafond source : {MAX_PAGES_PER_SOURCE}).")
    return urls


def _process_source(db, nom_source: str, pages: list[PageSeed]) -> int:
    print(f"\n=== Source : {nom_source} ({len(pages)} seed(s)) ===")
    count = 0
    for seed in pages:
        candidate_urls = _collect_candidate_urls(seed)
        for url in candidate_urls:
            print(f"  Page : {url}")
            page = fetch_page(url)
            if page is None:
                print("    [SKIP] page inaccessible ou vide.")
                continue
            print(f"    {len(page.texte_extrait)} caractere(s) extrait(s) — titre : {page.titre!r}")

            # CORRECTIF du 11/09/2026 : `sector_insurance_recommendations`
            # stocke desormais `secteurs` en array (1 ligne par
            # (type_assurance, source_url), voir le modele et le correctif
            # du volet Legifrance). Une meme page est souvent pertinente pour
            # plusieurs secteurs a la fois (ex: guide RC Pro generaliste vise
            # SaaS + E-commerce + Conseil), et classify_insurance_text() est
            # appele par secteur — le LLM peut en theorie renvoyer un
            # type_assurance different selon le secteur. On regroupe donc les
            # secteurs pertinents PAR type_assurance obtenu avant d'ecrire :
            # un upsert par secteur ecraserait a chaque fois les secteurs
            # deja stockes pour la meme page (upsert_sector_insurance
            # remplace `secteurs`, il ne fusionne pas).
            par_type_assurance: dict[str, dict] = {}
            for secteur in seed.secteurs_cibles:
                print(f"    Secteur '{secteur}' : filtrage...", end=" ")
                relevance = filter_page_relevance(
                    secteur, page.titre, page.texte_extrait[:_EXTRAIT_FILTRE_LONGUEUR]
                )
                if not relevance.pertinent:
                    print(f"non pertinent ({relevance.justification})")
                    continue
                print(f"pertinent ({relevance.justification}) → classification...", end=" ")

                classification = classify_insurance_text(
                    page.texte_extrait[:_TEXTE_CLASSIFICATION_LONGUEUR_MAX], secteur
                )
                print(
                    f"type_assurance='{classification.type_assurance}', "
                    f"a_base_legale={classification.a_base_legale}"
                )
                groupe = par_type_assurance.setdefault(
                    classification.type_assurance,
                    {"secteurs": [], "a_base_legale": classification.a_base_legale},
                )
                if secteur not in groupe["secteurs"]:
                    groupe["secteurs"].append(secteur)

            for type_assurance, groupe in par_type_assurance.items():
                upsert_sector_insurance(
                    db,
                    secteurs=groupe["secteurs"],
                    type_assurance=type_assurance,
                    a_base_legale=groupe["a_base_legale"],
                    source_nom=nom_source,
                    source_url=url,
                    texte_brut=page.texte_extrait,
                )
                print(f"    ✓ Upsert : '{type_assurance}' — secteurs={groupe['secteurs']}")
                count += 1
    return count


def run() -> None:
    total_inserts = 0
    for nom_source, pages in SOURCES:
        db = SessionLocal()
        try:
            inserted = _process_source(db, nom_source, pages)
            db.commit()
            total_inserts += inserted
            print(f"Source '{nom_source}' — OK ({inserted} lignes inserees/mises a jour).")
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(f"\nTermine — {total_inserts} lignes inserees/mises a jour en 'extrait_automatique'.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(
            f"Erreur — arret de la collecte (les sources deja commitees restent en base) : {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
