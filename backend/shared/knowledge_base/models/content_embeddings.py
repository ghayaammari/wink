"""Table `content_embeddings` — magasin vectoriel générique du copilot.

Une ligne = un chunk de texte indexé pour la recherche sémantique, quel que
soit son origine (`source_type`/`source_id`) : `roadmap_node` dès le Groupe 1,
puis `legal_texts`, `contract_clauses_library`, etc. avec le Groupe 5 et les
suivants. Table partagée, pas propre à un acteur — placée sous
`backend/shared/knowledge_base/` (et non `backend/shared/models/`) pour
séparer ce corpus copilot de l'identité/auth qui occupe le reste de `shared/`
(ce dossier est créé dès maintenant plutôt que d'attendre
que `shared/models/` devienne un fourre-tout).

Nécessite l'extension PostgreSQL `vector` (pgvector) — activée par la migration
Alembic qui crée cette table (`CREATE EXTENSION IF NOT EXISTS vector`), avant le
`CREATE TABLE`.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base

# Dimension figée par le modèle d'embedding retenu (BGE-M3, mode Dense uniquement —
# voir DECISIONS.md). Changer de modèle plus tard impose de re-générer tous les
# embeddings existants (une dimension différente n'est pas compatible avec les
# vecteurs déjà stockés), pas seulement de modifier cette constante.
EMBEDDING_DIMENSION = 1024


class ContentEmbeddings(Base):
    __tablename__ = "content_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Type de la ligne source vectorisée (ex: "roadmap_node", "legal_texts") — pas de FK,
    # volontairement polymorphe : impossible de pointer une seule colonne source_id vers
    # plusieurs tables différentes avec une vraie contrainte FK en PostgreSQL.
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Id de la ligne source. VARCHAR et non UUID : certaines sources ont un id métier
    # (ex: roadmap_nodes.id = "e1_choix_forme_juridique"), d'autres un UUID — String
    # accepte les deux sans caster.
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_texte: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Ex: "aucun" (tout le texte source en un seul chunk, cas roadmap_node), ou une
    # vraie stratégie de découpage pour les sources plus longues (legal_texts...).
    chunk_method: Mapped[str] = mapped_column(String(50), nullable=False)
    position_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    modele_utilise: Mapped[str] = mapped_column(String(100), nullable=False)
    # Ajouté par le Groupe 5 (contract_clauses_library) : quel champ de la ligne source a
    # été vectorisé (ex: "scenario_description", "texte_clause") — utile dès qu'une source
    # a plusieurs champs textuels candidats à l'embedding. Colonne créée dès maintenant par
    # décision explicite (schéma complet, pas de version minimale), même si le premier usage
    # réel (roadmap_node = un seul texte aplati par nœud) n'en a pas vraiment besoin.
    champ_source: Mapped[str] = mapped_column(String(100), nullable=False)
    # Domaine réglementaire/fonctionnel de la source, lu par l'orchestrateur (domaines_config)
    # avant de composer une réponse. Liste fermée (voir CheckConstraint ck_content_embeddings_domaine
    # ci-dessous) : les valeurs du schéma I1 (dbe, annonce_legale, statuts, pre_depot, rejet,
    # tarifs, pacte_fondateurs) + "roadmap" (Groupe 1) + "forme_juridique"/"statuts_societe"
    # (service 1.1.1, Phase 3 — mêmes valeurs que legal_texts.domaine_reglementaire).
    # Toute nouvelle source (contract_clauses_library...) devra ajouter sa valeur ici ET dans
    # la contrainte — sinon l'insertion échoue au lieu de laisser passer une valeur incohérente.
    domaine: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # Absente du schéma d'origine, ajoutée ici : sans elle, relancer le service
        # d'embedding après une correction du texte source (ex: typo dans le JSON roadmap)
        # crée un doublon au lieu de remplacer l'ancien embedding. chunk_index est inclus
        # pour ne pas bloquer une future source à plusieurs chunks (roadmap_node n'en a
        # qu'un seul, chunk_index=0 toujours, mais legal_texts en aura plusieurs).
        UniqueConstraint(
            "source_type", "source_id", "chunk_index", name="uq_content_embeddings_source_chunk"
        ),
        # Liste fermée normalisée (schéma I1, infra copilot transversale) + "roadmap" (Groupe 1)
        # + "forme_juridique"/"statuts_societe" (service 1.1.1, Phase 3 — migration 6f1a2c9d3e5b)
        # + "assurance_sectorielle" (service 1.1.10 — migration a7b3c8d1e4f2).
        # À étendre explicitement (jamais en silence) quand un nouveau source_type/domaine est
        # introduit — voir commentaire sur la colonne domaine.
        CheckConstraint(
            "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
            "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
            "'assurance_sectorielle')",
            name="ck_content_embeddings_domaine",
        ),
    )
