"""Chunking + embedding des guides de l'annonce légale validés (service
1.1.5, copilot). Même pattern que `chunk_and_embed_sector_insurance.py`.

Lancement : `python -m backend.shared.knowledge_base.scripts.chunk_and_embed_legal_announcement_guides`
depuis `wink/`.

- Ne traite que les lignes `valide_humain`.
- Découpage `par_alinea` (pas `aucun` comme le 1.1.10) : une page de guide
  couvre plusieurs sujets (délai, prix, attestation…) ; un chunk par
  paragraphe donne une recherche plus précise. Repli automatique sur un seul
  chunk si aucun séparateur (voir `chunk_texte_brut`).
- Domaine `annonce_legale` (déjà accepté par `ck_content_embeddings_domaine`),
  le même que les articles R210-x : l'orchestrateur filtre par sujet.
- Transaction unique : rien n'est écrit en cas d'erreur.
"""
import sys

from agents.config.loader import get_llm_config
from agents.ingestion.embedding_service import embed_texts
from agents.ingestion.legal_text_chunking_service import chunk_texte_brut
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.content_embeddings_service import upsert_embedding
from backend.shared.knowledge_base.services.legal_announcement_guides_service import list_valide_humain

_SOURCE_TYPE = "legal_announcement_guides"
_CHAMP_SOURCE = "texte_brut"
_DOMAINE = "annonce_legale"
_CHUNKING_METHOD = "par_alinea"


def run() -> None:
    modele_utilise = get_llm_config()["embedding"]["model"]
    db = SessionLocal()
    try:
        lignes = list_valide_humain(db)
        if not lignes:
            print("Aucun guide 'valide_humain' à traiter.")
            return
        plan = [
            (ligne, index, chunk)
            for ligne in lignes
            for index, chunk in enumerate(chunk_texte_brut(ligne.texte_brut, _CHUNKING_METHOD))
        ]
        vecteurs = embed_texts([chunk for _, _, chunk in plan])
        for (ligne, index, chunk), vecteur in zip(plan, vecteurs):
            upsert_embedding(
                db,
                source_type=_SOURCE_TYPE,
                source_id=str(ligne.id),
                chunk_index=index,
                chunk_texte=chunk,
                chunk_method=_CHUNKING_METHOD,
                embedding=vecteur,
                modele_utilise=modele_utilise,
                champ_source=_CHAMP_SOURCE,
                domaine=_DOMAINE,
            )
        db.commit()
        print(f"OK — {len(lignes)} guide(s), {len(plan)} chunk(s) embeddés.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — rien n'a été écrit en base (transaction unique) : {exc}", file=sys.stderr)
        sys.exit(1)
