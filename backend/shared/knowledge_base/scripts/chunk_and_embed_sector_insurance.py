"""Chunking + embedding des recommandations d'assurance sectorielles validees
(service 1.1.10, volet NON-LEGAL uniquement). Meme pattern que
`chunk_and_embed_legal_texts.py` : lit les lignes `valide_humain` → chunk →
embed → upsert dans `content_embeddings`.

Lancement :
  python -m backend.shared.knowledge_base.scripts.chunk_and_embed_sector_insurance
depuis `wink/`.

Prealable obligatoire : migration ajoutant 'assurance_sectorielle' au domaine
de `content_embeddings` (voir migration Alembic correspondante).

CORRECTIF du 11/09/2026 : ce script ignore desormais explicitement les lignes
`a_base_legale=True` (`legal_text_id` non nul) — leur texte est deja embedde
par `chunk_and_embed_legal_texts.py`, a partir de `legal_texts.texte_brut`,
avec `domaine=domaine_reglementaire` (grain fin : assurance_rc_pro,
assurance_fintech, ...). Les reembedder ici les dupliquerait sous un domaine
different (`assurance_sectorielle`, grain grossier) — incoherent pour le
meme texte source. AVANT ce correctif, le filtre se faisait par accident sur
`texte_brut` (toujours vide cote legal depuis que le texte a ete deplace vers
`legal_texts`) : ca fonctionnait, mais fragile — un futur volet legal avec
`texte_brut` renseigne par erreur aurait ete embedde en double sans avertissement.
Desormais le filtre est explicite sur `a_base_legale`, `texte_brut` ne sert
plus qu'a ecarter les lignes non-legales pas encore renseignees.

Ne traite QUE les lignes `statut_contenu = 'valide_humain'`, `a_base_legale =
False`, dont `texte_brut` n'est pas vide.
"""
import sys

from agents.config.loader import get_llm_config
from agents.ingestion.embedding_service import embed_texts
from agents.ingestion.legal_text_chunking_service import chunk_texte_brut
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.content_embeddings_service import upsert_embedding
from backend.shared.knowledge_base.services.sector_insurance_recommendations_service import (
    list_valide_humain,
)

_SOURCE_TYPE = "sector_insurance_recommendations"
_CHAMP_SOURCE = "texte_brut"
_DOMAINE = "assurance_sectorielle"
_CHUNKING_METHOD = "aucun"


def run() -> None:
    modele_utilise = get_llm_config()["embedding"]["model"]

    db = SessionLocal()
    try:
        rows = list_valide_humain(db)
        rows_non_legales = [r for r in rows if not r.a_base_legale]
        rows_with_text = [r for r in rows_non_legales if r.texte_brut]
        skipped_deja_embeddees = len(rows) - len(rows_non_legales)
        skipped_sans_texte = len(rows_non_legales) - len(rows_with_text)
        if not rows_with_text:
            print(
                "Aucune ligne 'valide_humain' non-legale avec texte a traiter "
                f"({skipped_deja_embeddees} legales deja embeddees via legal_texts, "
                f"{skipped_sans_texte} non-legales sans texte_brut)."
            )
            return

        plan: list[tuple] = []
        for row in rows_with_text:
            chunks = chunk_texte_brut(row.texte_brut, _CHUNKING_METHOD)
            for index, chunk_texte in enumerate(chunks):
                plan.append((row, index, chunk_texte))

        textes = [chunk_texte for _, _, chunk_texte in plan]
        vecteurs = embed_texts(textes)

        for (row, chunk_index, chunk_texte), vecteur in zip(plan, vecteurs):
            upsert_embedding(
                db,
                source_type=_SOURCE_TYPE,
                source_id=str(row.id),
                chunk_index=chunk_index,
                chunk_texte=chunk_texte,
                chunk_method=_CHUNKING_METHOD,
                embedding=vecteur,
                modele_utilise=modele_utilise,
                champ_source=_CHAMP_SOURCE,
                domaine=_DOMAINE,
            )

        db.commit()
        print(
            f"OK — {len(rows_with_text)} recommandations traitees, "
            f"{len(plan)} chunks embeddes/upsertes "
            f"({skipped_deja_embeddees} legales ignorees, deja embeddees via legal_texts ; "
            f"{skipped_sans_texte} non-legales sans texte_brut ignorees)."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(
            f"Erreur — rien n'a ete ecrit en base (transaction unique) : {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
