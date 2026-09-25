"""Collecte des articles de loi de l'annonce légale (service 1.1.5, copilot).

Lancement : `python -m backend.shared.knowledge_base.scripts.collect_legal_texts_annonce_legale`
depuis `wink/`.

Même pipeline que le pacte (1.1.13) : liste curatée, pas d'appel LLM.
Insertion dans `legal_texts` (domaine `annonce_legale`, déjà accepté par
`ck_content_embeddings_domaine`) en `extrait_automatique`. Ensuite :
1. relecture humaine : dashboard `/admin/legal-texts` (déjà générique) ;
2. embedding : `python -m backend.shared.knowledge_base.scripts.chunk_and_embed_legal_texts`
   (déjà générique par domaine, aucune modification).

Garde-fou repris du pacte : `legal_texts` n'a qu'un domaine par ligne
(unicité sur `(code_source, article_numero)`). Si un article existe déjà sous
un AUTRE domaine, on ne le re-tague jamais silencieusement : il est signalé
et laissé tel quel.

Préalables .env : LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET.
"""
import sys

from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import get_legal_text, upsert_legal_text
from scrapers.legifrance.articles_annonce_legale import SECTIONS_ANNONCE_LEGALE
from scrapers.legifrance.legifrance_client import fetch_articles_in_block

_DOMAINE = "annonce_legale"


def _normaliser_numero(numero: str | None) -> str:
    # « R. 210-4 » / « R210-4 » -> « R210-4 » (même normalisation que le pacte pour L227-13).
    return (numero or "").replace(" ", "").replace(".", "")


def run() -> None:
    compteurs = {"insere": 0, "deja_autre_domaine": 0, "introuvable": 0}
    for section in SECTIONS_ANNONCE_LEGALE:
        db = SessionLocal()
        try:
            articles = fetch_articles_in_block(section.legifrance_source_id, section.legifrance_section_id)
            par_numero = {_normaliser_numero(a.get("article_numero")): a for a in articles}
            print(f"Section '{section.description}' : {len(articles)} article(s) en vigueur.")
            for numero, sous_theme in section.articles.items():
                article = par_numero.get(numero)
                if article is None or not article.get("texte_brut"):
                    print(f"  [ABSENT] {numero} introuvable dans la section — vérifier l'identifiant LEGISCTA.")
                    compteurs["introuvable"] += 1
                    continue
                existant = get_legal_text(db, code_source=section.code_source, article_numero=numero)
                if existant is not None and existant.domaine_reglementaire != _DOMAINE:
                    print(
                        f"  [IGNORE] {numero} existe déjà sous le domaine "
                        f"{existant.domaine_reglementaire!r} — rien modifié (voir docstring)."
                    )
                    compteurs["deja_autre_domaine"] += 1
                    continue
                upsert_legal_text(
                    db,
                    domaine_reglementaire=_DOMAINE,
                    code_source=section.code_source,
                    article_numero=numero,
                    texte_brut=article["texte_brut"],
                    sous_theme=sous_theme,
                    chunking_suggere="aucun",  # articles courts, un seul sujet
                    date_effet=article.get("date_effet"),
                )
                print(f"  ✓ {numero} ({sous_theme})")
                compteurs["insere"] += 1
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    print(
        f"Terminé — {compteurs}. Relecture humaine obligatoire (/admin/legal-texts), "
        "puis chunk_and_embed_legal_texts."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — arrêt de la collecte (les sections déjà commitées restent en base) : {exc}", file=sys.stderr)
        sys.exit(1)
