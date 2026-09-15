"""Seed idempotent de `roadmap_nodes`/`roadmap_node_dependencies` depuis le JSON

source (`data/wink_roadmap_creation_juridique.json`), puis génération/upsert de
l'embedding de chaque nœud dans `content_embeddings` (service 1.1.x, Groupe 1).

Lancement : `python -m backend.entrepreneur.scripts.seed_roadmap_nodes` depuis
`wink/` (même convention que `uvicorn backend.main:app` — voir backend/main.py).

Idempotent par construction : upsert par `id` (clé métier du JSON, pas un UUID
généré) — relancer ce script après une correction du JSON met à jour les nœuds
existants au lieu d'échouer sur un doublon de clé primaire, et resynchronise
les dépendances (ajout/suppression) plutôt que de seulement en ajouter.

Une seule transaction, commit unique à la fin : soit tout le seed réussit, soit
rien n'est écrit — évite un état à moitié chargé si le script plante au milieu
(ex: échec d'appel au modèle d'embedding sur le 15e nœud).
"""
import json
import sys
from pathlib import Path

from agents.ingestion.embedding_service import embed_texts
from agents.config.loader import get_llm_config
from backend.entrepreneur.models.roadmap_node import RoadmapNode
from backend.entrepreneur.models.roadmap_node_dependency import RoadmapNodeDependency
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.content_embeddings_service import upsert_embedding

_DATA_PATH = Path(__file__).parent / "data" / "wink_roadmap_creation_juridique.json"

# Contenu concaténé pour l'embedding — un seul chunk par nœud (décision actée, voir
# DECISIONS.md). "texte_aplati" et non un nom de champ unique (contrairement à
# contract_clauses_library) : il n'y a pas UNE colonne source, mais plusieurs
# concaténées — la colonne champ_source documente ce cas plutôt que de forcer un
# nom de champ qui n'existe pas.
_CHAMP_SOURCE = "texte_aplati"
_DOMAINE = "roadmap"
_CHUNK_METHOD = "aucun"


class SeedError(Exception):
    """Erreur de validation du JSON source, avant toute écriture en base."""


def _load_nodes() -> list[dict]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["noeuds"]


def _validate_graph(nodes: list[dict]) -> None:
    """Vérifie que chaque `depends_on` pointe vers un id existant et qu'il n'y a

    aucun cycle. Rien de tout ça n'est imposé par la base (une FK empêche une
    référence vers un id inexistant, mais pas un cycle) — seule protection réelle.
    """
    ids = {n["id"] for n in nodes}
    for node in nodes:
        for dep in node["depends_on"]:
            if dep not in ids:
                raise SeedError(f"{node['id']} dépend de '{dep}', qui n'existe pas dans le JSON.")

    # Détection de cycle par coloriage DFS (blanc=non visité, gris=en cours, noir=fini).
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n["id"]: WHITE for n in nodes}
    deps_by_id = {n["id"]: n["depends_on"] for n in nodes}

    def visit(node_id: str, path: list[str]) -> None:
        color[node_id] = GRAY
        for dep in deps_by_id[node_id]:
            if color[dep] == GRAY:
                raise SeedError(f"Cycle détecté : {' -> '.join(path + [dep])}")
            if color[dep] == WHITE:
                visit(dep, path + [dep])
        color[node_id] = BLACK

    for node in nodes:
        if color[node["id"]] == WHITE:
            visit(node["id"], [node["id"]])


def _flatten_node_text(node: dict) -> str:
    """Aplatit un nœud en un seul texte pour l'embedding — nom, description,

    details_pratiques, administration_liee, source_legale, input concaténés.
    Les colonnes structurées d'origine ne sont jamais fusionnées en base, seule
    cette version texte sert à l'embedding (voir discussion Groupe 1/2).
    """
    parts = [
        node["nom"],
        node["description"],
        node.get("details_pratiques"),
        node.get("administration_liee"),
        node.get("source_legale"),
        node.get("input"),
    ]
    return "\n".join(p for p in parts if p)


def _upsert_node(db, node: dict, ordre: int) -> RoadmapNode:
    existing = db.query(RoadmapNode).filter(RoadmapNode.id == node["id"]).first()
    new_values = dict(
        groupe=node["groupe"],
        # Position dans le JSON source (index de la liste `noeuds`) — utilisée
        # pour l'affichage ordonné de la roadmap (voir migration 03ef7cc7d535,
        # ajoutée après coup : absente du schéma initial du Groupe 1).
        ordre=ordre,
        nom=node["nom"],
        input=node.get("input"),
        description=node["description"],
        details_pratiques=node.get("details_pratiques"),
        administration_liee=node.get("administration_liee"),
        source_legale=node.get("source_legale"),
        applicable_if=node.get("applicable_if") or {},
        bloquant=node.get("bloquant", True),
        parallele_avec=node.get("parallele_avec") or [],
        recommande_avant=node.get("recommande_avant") or [],
    )
    if existing is None:
        row = RoadmapNode(id=node["id"], status="draft", **new_values)
        db.add(row)
        return row

    # Si le contenu a réellement changé, on repasse le nœud en "draft" : une
    # validation humaine faite sur l'ancien texte ne garantit rien sur le nouveau.
    # Si rien n'a changé (relance à vide du script), le statut existant est conservé.
    # `ordre` est inclus dans cette comparaison comme le reste : un JSON réordonné
    # sans changement de texte repasserait donc aussi le nœud en "draft" — accepté
    # tel quel, cas rare et sans conséquence pratique (juste une relecture de plus).
    content_changed = any(getattr(existing, k) != v for k, v in new_values.items())
    for k, v in new_values.items():
        setattr(existing, k, v)
    if content_changed:
        existing.status = "draft"
    return existing


def _sync_dependencies(db, node: dict) -> None:
    current = {
        row.depends_on_node_id
        for row in db.query(RoadmapNodeDependency).filter(RoadmapNodeDependency.node_id == node["id"])
    }
    wanted = set(node["depends_on"])

    for dep_id in current - wanted:
        db.query(RoadmapNodeDependency).filter(
            RoadmapNodeDependency.node_id == node["id"],
            RoadmapNodeDependency.depends_on_node_id == dep_id,
        ).delete()

    for dep_id in wanted - current:
        db.add(RoadmapNodeDependency(node_id=node["id"], depends_on_node_id=dep_id))


def run() -> None:
    nodes = _load_nodes()
    _validate_graph(nodes)

    modele_utilise = get_llm_config()["embedding"]["model"]

    db = SessionLocal()
    try:
        for ordre, node in enumerate(nodes):
            _upsert_node(db, node, ordre)
        db.flush()  # les FK de roadmap_node_dependencies exigent que les nœuds existent déjà

        for node in nodes:
            _sync_dependencies(db, node)

        # Un seul appel groupé au modèle d'embedding plutôt que 24 appels séparés —
        # coût réseau/CPU négligeable ici, mais reste la bonne pratique par défaut.
        textes = [_flatten_node_text(node) for node in nodes]
        vecteurs = embed_texts(textes)

        for node, texte, vecteur in zip(nodes, textes, vecteurs):
            upsert_embedding(
                db,
                source_type="roadmap_node",
                source_id=node["id"],
                chunk_index=0,
                chunk_texte=texte,
                chunk_method=_CHUNK_METHOD,
                embedding=vecteur,
                modele_utilise=modele_utilise,
                champ_source=_CHAMP_SOURCE,
                domaine=_DOMAINE,
            )

        db.commit()
        print(f"OK — {len(nodes)} nœuds upsertés, dépendances resynchronisées, {len(nodes)} embeddings upsertés.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        run()
    except SeedError as exc:
        print(f"Erreur de validation du JSON — rien n'a été écrit en base : {exc}", file=sys.stderr)
        sys.exit(1)
