"""Orchestrateur collecte SecNumCloud — ANSSI (service 3.3.11). Même

structure que collect_rgpd_guides.py (seul autre pipeline "guides/PDF"
du repo, pas d'articles de loi structurés ici non plus).

Lancement :
  python -m backend.shared.knowledge_base.scripts.collect_secnumcloud_guides
depuis `wink/`. Seul GROQ_API_KEY est requis (filtre + classification LLM).

Ecrit dans `legal_texts` (domaine_reglementaire='certification_secnumcloud',
meme valeur que la CheckConstraint content_embeddings.domaine ajoutée par la
migration q4d6f8a0b2c4 -- `chunk_and_embed_legal_texts.py` est déjà
générique et n'a besoin d'aucune modification pour ce nouveau domaine, voir
sa fonction `_domaine_embedding`, qui laisse passer `domaine_reglementaire`
tel quel sauf pour le cas particulier assurance).

`code_source` = l'URL de la page elle-même (idempotent, comme collect_rgpd_guides.py).
Pas de crawling (toutes les PageSeed de pages_secnumcloud.py ont
max_liens_a_suivre=0).

FICHIERS DU PIPELINE :
  scrapers/anssi/pages_secnumcloud.py                              — URLs curées
  scrapers/shared/web_fetch.py                                     — fetch_page()
  agents/ingestion/legal_text_structuring_service_secnumcloud.py   — filtre + classification
  backend/shared/knowledge_base/services/legal_texts_service.py    — upsert_legal_text()
  backend/shared/knowledge_base/scripts/chunk_and_embed_legal_texts.py — étape suivante (inchangée)
  backend/.env (GROQ_API_KEY)

Préalable : migration q4d6f8a0b2c4 appliquée (domaine 'certification_secnumcloud').

Commit PAR PAGE (pas par lot) — même raison que collect_rgpd_guides.py.
"""
import sys

from agents.ingestion.legal_text_structuring_service_secnumcloud import classify_article, filter_article_relevance
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import upsert_legal_text
from scrapers.anssi.pages_secnumcloud import NOM_SOURCE, PAGES
from scrapers.shared.web_fetch import fetch_page

_TEXTE_CLASSIFICATION_LONGUEUR_MAX = 3000


def _type_source(html_brut: str) -> str:
    return "pdf" if not html_brut else "guide_pratique"


def _extrait_representatif(texte: str, longueur_max: int) -> str:
    """Echantillonne le debut ET le milieu du texte, jamais seulement le
    debut brut (`texte[:longueur_max]`).

    Necessaire pour les referentiels PDF (ANSSI, etc.) : leurs premiers
    milliers de caracteres sont systematiquement page de garde + sommaire +
    acronymes, jamais le contenu normatif lui-meme -- un simple `[:N]`
    envoie donc au LLM un extrait qui semble "non pertinent" alors que le
    document entier l'est (constate sur le referentiel SecNumCloud v3.2).
    Prendre debut+milieu plutot qu'un decalage fixe (ex: `[3000:6000]`) evite
    de calibrer ce nombre sur la longueur du sommaire d'un seul document --
    ca ne generaliserait pas a un futur PDF avec un sommaire plus court/long.
    """
    if len(texte) <= longueur_max:
        return texte
    moitie = longueur_max // 2
    debut_milieu = len(texte) // 2 - moitie // 2
    return texte[:moitie] + "\n\n[...]\n\n" + texte[debut_milieu : debut_milieu + moitie]


def _process_page(db, url: str) -> str:
    page = fetch_page(url)
    if page is None:
        return "ignore_inaccessible"
    if not page.texte_extrait:
        return "ignore_texte_vide"

    extrait = _extrait_representatif(page.texte_extrait, _TEXTE_CLASSIFICATION_LONGUEUR_MAX)
    relevance = filter_article_relevance(extrait)
    if not relevance.pertinent:
        return "ignore_non_pertinent"

    classification = classify_article(extrait)
    upsert_legal_text(
        db,
        domaine_reglementaire="certification_secnumcloud",
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
