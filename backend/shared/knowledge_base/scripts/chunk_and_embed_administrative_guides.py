"""Chunking + embedding de `administrative_guides` vers `content_embeddings` —
meme convention en 2 sessions courtes (lecture puis ecriture) que
`chunk_and_embed_legal_texts.py`, voir son CORRECTIF du 22/09/2026 pour la
raison (pooler Supabase en mode transaction).

Ne traite QUE les lignes `statut_contenu = 'valide_humain'` — prealable
obligatoire : la migration f6a7b8c9d0e1 appliquee, et au moins une page
validee via le dashboard (`administrative_guides_validation_router.py`).

Toujours `chunk_texte_guide()` (jamais `chunk_texte_brut()`) : ce sont des
pages de prose (guides Bpifrance, FAQ), jamais des articles de loi numerotes —
meme branche que `type_source != 'article_loi'` dans
`chunk_and_embed_legal_texts.py`. `chunk_si_trop_long()` en filet de securite,
meme raison (413 Groq deja rencontre ailleurs sur du contenu peu structure).

Lancement : `python -m backend.shared.knowledge_base.scripts.chunk_and_embed_administrative_guides`
depuis `wink/`.
"""
from agents.config.loader import get_llm_config
from agents.ingestion.embedding_service import embed_texts
from agents.ingestion.legal_text_chunking_service import chunk_si_trop_long, chunk_texte_guide
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.administrative_guides_service import list_valide_humain
from backend.shared.knowledge_base.services.content_embeddings_service import get_embedded_chunks, upsert_embedding

_CHAMP_SOURCE = "texte_brut"
_SOURCE_TYPE = "administrative_guides"


def run() -> None:
    modele_utilise = get_llm_config()["embedding"]["model"]

    db_lecture = SessionLocal()
    try:
        rows = list_valide_humain(db_lecture)
        if not rows:
            print("Aucune ligne 'valide_humain' à traiter — rien à faire (voir dashboard de validation).")
            return
        print(f"{len(rows)} page(s) 'valide_humain' trouvée(s) — vérification des chunks déjà à jour...")

        plan: list[tuple] = []  # (row_id, domaine, chunk_index, chunk_texte)
        skipped = 0
        for row in rows:
            chunks_bruts = chunk_texte_guide(row.texte_brut)
            chunks = [c2 for c in chunks_bruts for c2 in chunk_si_trop_long(c)]

            existants = get_embedded_chunks(db_lecture, source_type=_SOURCE_TYPE, source_id=str(row.id))
            deja_a_jour = (
                len(existants) == len(chunks)
                and all(e.chunk_texte == c for e, c in zip(existants, chunks))
                and all(e.modele_utilise == modele_utilise for e in existants)
            )
            if deja_a_jour:
                skipped += 1
                continue
            for index, chunk_texte in enumerate(chunks):
                plan.append((row.id, row.domaine, index, chunk_texte))
    finally:
        db_lecture.close()

    if not plan:
        print(f"Rien à réembedder — {skipped} page(s) déjà à jour.")
        return
    print(
        f"{len(plan)} chunk(s) à (ré)embedder ({skipped} page(s) déjà à jour ignorée(s)) — "
        "démarrage du calcul des embeddings..."
    )

    textes = [chunk_texte for _, _, _, chunk_texte in plan]
    vecteurs = embed_texts(textes)

    db_ecriture = SessionLocal()
    try:
        for (row_id, domaine, chunk_index, chunk_texte), vecteur in zip(plan, vecteurs):
            upsert_embedding(
                db_ecriture,
                source_type=_SOURCE_TYPE,
                source_id=str(row_id),
                chunk_index=chunk_index,
                chunk_texte=chunk_texte,
                chunk_method="par_paragraphe",
                embedding=vecteur,
                modele_utilise=modele_utilise,
                champ_source=_CHAMP_SOURCE,
                domaine=domaine,
            )
        db_ecriture.commit()
        nb_pages_traitees = len({row_id for row_id, _, _, _ in plan})
        print(f"OK — {nb_pages_traitees} page(s) réembeddée(s) ({len(plan)} chunks), {skipped} déjà à jour ignorée(s).")
    except Exception:
        db_ecriture.rollback()
        raise
    finally:
        db_ecriture.close()


if __name__ == "__main__":
    run()
