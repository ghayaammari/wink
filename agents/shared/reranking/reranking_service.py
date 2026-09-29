"""Reranking des chunks déjà récupérés par recherche vectorielle -- ajouté

suite à l'évaluation Recall@8/MRR du retrieval (voir
claude/Wink_rag_retrieval_eval_baseline.md côté Projet) : le recall n'est
pas le problème (jamais < 95 % par domaine), mais le RANG du bon chunk sur
les domaines à articles sémantiquement proches (forme_juridique en
particulier, MRR = 0.379 avant reranking). Un reranker cross-encoder,
appliqué uniquement sur les candidats déjà récupérés par
`search_similar_chunks` (jamais un nouvel appel de recherche), corrige ce
rang sans changer l'ensemble des candidats ni le recall.

Séparation identique à embedding_service.py (même dossier logique,
`agents/shared/`) : ce module est un pur calcul IA texte -> score, aucun
accès DB, aucune connaissance du modèle ContentEmbeddings -- l'appelant
(backend/entrepreneur/services/compliance_agent_tools_service.py) reste
seul responsable de réordonner ses propres objets à partir des indices
renvoyés ici.

Modèle : BAAI/bge-reranker-v2-m3 (famille BGE, cohérente avec l'embedding
BGE-M3 déjà utilisé) -- multilingue, adapté au corpus juridique français,
via la même librairie FlagEmbedding (déjà une dépendance du projet pour
l'embedding, aucune nouvelle dépendance ajoutée). Alternative plus légère
écartée (bge-reranker-base, anglais uniquement) : notre corpus est en
français, la précision prime ici sur la latence pour un appel qui ne
reranke que 8 candidats à la fois.

Modèle chargé une seule fois par process (singleton module-level), même
choix que `_get_model()` dans embedding_service.py -- un modèle de
reranking, comme l'embedding, ne doit pas être rechargé à chaque appel.
"""
from agents.config.loader import get_llm_config

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        import torch
        from FlagEmbedding import FlagReranker

        config = get_llm_config()["reranking"]
        use_fp16 = torch.cuda.is_available()
        print(
            f"Chargement du modele de reranking ({config['model']}, "
            f"{'GPU/CUDA' if use_fp16 else 'CPU'}) — peut prendre du temps "
            "au premier lancement (telechargement + chargement en memoire)..."
        )
        _reranker = FlagReranker(config["model"], use_fp16=use_fp16)
        print("Modele de reranking charge.")
    return _reranker


def rerank_indices(requete: str, textes: list[str]) -> list[int]:
    """Retourne les indices de `textes`, triés du plus au moins pertinent par

    rapport à `requete` selon le score du cross-encoder -- ne retire ni
    n'ajoute aucun candidat, seulement un nouvel ordre. Liste vide ou à un
    seul élément renvoyée telle quelle (rien à reranker).

    Desactivable via reranking.enabled (llm_config.yaml, false depuis le
    26/09/2026) : renvoie alors l'ordre d'origine (celui de la similarite
    cosinus de search_similar_chunks) sans charger le modele -- evite aussi
    les ~15-20s de chargement du modele au premier appel, pertinent pour un
    diagnostic deja tendu en nombre d'appels (voir rgpd_service.py).

    L'appelant reste responsable de réordonner ses propres objets
    (ex: `[chunks[i] for i in rerank_indices(requete, [c.chunk_texte for c
    in chunks])]`) -- ce module ne connaît que du texte brut.
    """
    if len(textes) <= 1:
        return list(range(len(textes)))

    if not get_llm_config()["reranking"].get("enabled", True):
        return list(range(len(textes)))

    reranker = _get_reranker()
    paires = [(requete, texte) for texte in textes]
    scores = reranker.compute_score(paires, normalize=True)
    if isinstance(scores, float):
        scores = [scores]

    return sorted(range(len(textes)), key=lambda i: scores[i], reverse=True)
