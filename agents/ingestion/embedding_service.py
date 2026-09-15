"""Génération d'embeddings — BGE-M3 en local, mode Dense uniquement (Option A,

voir DECISIONS.md : "Point non tranché... embedding" et sa résolution).

Modèle chargé une seule fois par process (singleton module-level `_model`), pas
rechargé à chaque appel. Aucun accès DB ici — voir
`backend/shared/knowledge_base/services/content_embeddings_service.py` pour la
persistance, même séparation que `agents/shared/document_processing/` (calcul IA)
vs `backend/entrepreneur/services/document_service.py` (DB).

Dette technique assumée : lib chargée directement dans le process appelant
(script de seed aujourd'hui). Tient tant qu'aucun endpoint temps réel (copilot,
Groupe 3 — service 1.1.x conversationnel) n'a besoin d'embedder une question
utilisateur à la volée : un modèle de ~2 Go ne doit pas être chargé dans chaque
worker d'une API qui répond aussi à des requêtes HTTP classiques. Le jour venu,
seule l'implémentation de `embed_texts` change (→ appel HTTP vers un service
séparé) — sa signature reste la même, aucun appelant n'a besoin d'être modifié.

CORRECTIF du 11/09/2026 : `use_fp16=True` était codé en dur, y compris sans
GPU. Le fp16 n'accélère que sur GPU (CUDA) — sur CPU, plusieurs opérations
fp16 n'ont pas de noyau vectorisé et retombent sur un chemin scalaire
extrêmement lent (observé : plus de 30 minutes bloqué sur 2 courts textes,
sans jamais planter ni progresser — un faux blocage, pas un crash). Désormais
fp16 n'est activé que si `torch.cuda.is_available()` — sinon fp32 sur CPU.
Logs de progression ajoutés au chargement du modèle et au calcul des
embeddings : sans ça, un blocage réel (comme celui-ci) et un simple temps de
calcul normal sont indiscernables en regardant le terminal.
"""
from agents.config.loader import get_llm_config

_model = None


def _get_model():
    global _model
    if _model is None:
        import torch
        from FlagEmbedding import BGEM3FlagModel

        config = get_llm_config()["embedding"]
        use_fp16 = torch.cuda.is_available()
        print(
            f"Chargement du modele d'embedding ({config['model']}, "
            f"{'GPU/CUDA' if use_fp16 else 'CPU'}) — peut prendre du temps "
            "au premier lancement (telechargement + chargement en memoire)..."
        )
        _model = BGEM3FlagModel(config["model"], use_fp16=use_fp16)
        print("Modele d'embedding charge.")
    return _model


def embed_texts(textes: list[str]) -> list[list[float]]:
    """Retourne un vecteur dense par texte, dans le même ordre que `textes`.

    Mode Dense uniquement : BGE-M3 produit aussi des représentations Sparse et
    ColBERT, ignorées ici (décision actée — voir DECISIONS.md), pour rester
    compatible avec une colonne `VECTOR` simple dans `content_embeddings`.
    """
    if not textes:
        return []
    model = _get_model()
    print(f"Calcul des embeddings pour {len(textes)} chunk(s)...")
    result = model.encode(textes, return_dense=True, return_sparse=False, return_colbert_vecs=False)
    print("Embeddings calcules.")
    return [vec.tolist() for vec in result["dense_vecs"]]
