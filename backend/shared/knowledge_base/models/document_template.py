"""Table `document_templates` — squelette structurel d'un document type (Phase
collecte, Groupe 5 — services 1.1.13 pacte / 1.1.4 statuts).

Une ligne = une section du document final, dans l'ordre (`ordre`). Le contenu de
chaque section est une référence polymorphe (`reference_type` + `reference_id`) :
- `legal_texts` (mentions obligatoires, ex. les 14 mentions obligatoires SAS),
- `contract_clauses_library` (clauses types),
- `donnee_projet` (données injectées depuis le projet, sans référence),
- `texte_statique` (section fixe).

Non vectorisée : c'est un squelette structurel, pas un contenu interrogeable.
`UNIQUE(document_type, ordre)` garantit un ordre unique par type de document.
(réalisé par OPENCODE)

AJOUT (migration f2c9e0a1b3d4, service 1.1.13) : `type_contenu` gagne la valeur
'variante_obligatoire' (Article 3 du pacte Bpifrance, ex. 7 hypothèses de
préemption/préférence — une seule s'applique, ce n'est ni "obligatoire fixe" ni
"optionnelle inclus/exclus") et la colonne `variantes_candidates` (liste des
`contract_clauses_library.scenario` candidats pour cette section).

`variantes_candidates` remplace une idée écartée : résoudre le groupe par un
préfixe commun de `scenario` (évoquée dans la migration e4a8f1c9b2d7 qui a créé
`document_generation_sessions`). Cette idée ne tient pas sur les données réelles :
plusieurs groupes de variantes partagent le même préfixe thématique sans être le
même groupe (ex. `sortie_conjointe_*` et `sortie_forcee_*` commencent tous deux
par un préfixe "sortie" mais sont deux choix indépendants ; `limitation_participations`
appartient au groupe "inalienabilite" sans partager son préfixe). Une liste
explicite par section est plus verbeuse mais ne dépend d'aucune convention de
nommage implicite des `scenario` — un nom de scénario mal choisi plus tard ne
peut pas silencieusement casser un regroupement.

AJOUT (migration a3d7e1c8f0b2, frontend service 1.1.13) : `titre_affiche` et
`explication` — texte à présenter par le copilot avant une section
(`comportement_section='variante_obligatoire'` ou `'donnee_projet'`, ex.
"Cession de titres — clause d'inaliénabilité"). Pour `mention_obligatoire`/
`clause_optionnelle`, la clause référencée porte déjà `titre_clause`/
`description_clause` — ces 2 colonnes restent NULL dans ce cas (pas de
duplication). Rempli au niveau de `document_templates`, jamais codé en dur
côté frontend : 1.1.4 (statuts) réutilisera le même moteur de session avec un
squelette différent, un texte figé en dur aurait divergé silencieusement du
squelette réel dès qu'il change.

AJOUT (migration f6b3e9a2c5d7, service 1.1.13, Article 3) : `depend_de_section`
/ `depend_de_variantes` — 3e critère d'applicabilité d'une section (après
`forme_juridique_concernee` et `necessite_investisseurs`, migration
d3a7c5e8f1b4), pour les sections qui ne doivent apparaître que si une
certaine variante a été choisie ailleurs (ex. les sections "1er rang"/
"2nd rang" de l'Hypothèse 1/2 d'Article 3, qui n'existent que si cette
hypothèse a été retenue à la section Article 3 de premier niveau).

RENOMMAGE (migration d9c4a6b1f3e8, 20/09/2026, demandé par l'utilisateur) :
`nom_section` -> `code_section` (clé technique jamais affichée, utilisée dans
l'URL de l'API et comme clé du JSON `reponses` — le mot "nom" laissait penser
à un texte affiché, d'où la confusion avec `titre_affiche`) et `type_contenu`
-> `comportement_section` (ce n'est pas un type de contenu façon MIME, c'est
ce qui pilote le comportement de la section : quelle validation, quel
formulaire frontend — voir document_generation_service.py). Pas un
changement de structure, seulement de noms.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base

# Valeurs fermées (schéma Groupe 5) — étendues si une nouvelle forme de section apparaît.
_COMPORTEMENT_SECTION = (
    "('mention_obligatoire', 'clause_optionnelle', 'donnee_projet', 'texte_statique', "
    "'variante_obligatoire')"
)
_REFERENCE_TYPE = "('legal_texts', 'contract_clauses_library')"


class DocumentTemplate(Base):
    __tablename__ = "document_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Clé technique (ex-`nom_section`) — jamais affichée, voir le renommage
    # documenté ci-dessus. Utilisée dans l'URL de l'API et comme clé du JSON
    # `document_generation_sessions.reponses`.
    code_section: Mapped[str] = mapped_column(String(255), nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    # Pilote le comportement de la section (ex-`type_contenu`) — voir le
    # renommage documenté ci-dessus.
    comportement_section: Mapped[str] = mapped_column(String(40), nullable=False)
    # Référence polymorphe : pas de vraie contrainte FK possible en PostgreSQL vers
    # l'une OU l'autre table cible — reference_type dit où pointer, reference_id l'id.
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Si false, l'utilisateur choisit d'inclure la section ou non à la génération.
    obligatoire: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # RENOMMAGE (migration a1c2d4e6f8b0, cases 95-96 service 1.1.13) :
    # forme_juridique_concernee (String, une seule valeur) -> liste JSONB.
    # Première utilisation réelle avec des données de seed a révélé que
    # certaines clauses (ex. "société par action") s'appliquent à une
    # FAMILLE de formes juridiques (SAS, SASU, SA), pas une seule valeur
    # exacte -- une comparaison stricte (`!=`) ne pouvait pas l'exprimer.
    # `_applicable()` compare désormais par appartenance à la liste (voir
    # document_generation_service.py). Limite assumée, hors périmètre de ce
    # service : `project_legal_profiles.legal_form` reste un texte libre
    # sans liste fermée de valeurs -- une saisie mal orthographiée ne
    # matchera aucune entrée ici (sujet de 1.1.1/1.1.4, pas de ce service).
    formes_juridiques_concernees: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # AJOUT (migration d3a7c5e8f1b4, service 1.1.13) — true = cette section ne
    # concerne que les Associés Investisseurs, sautée si le projet n'en a
    # aucun (voir _applicable() dans document_generation_service.py). Même
    # famille que forme_juridique_concernee : un 2e critère indépendant sur
    # le même mécanisme de saut, pas un système de règles séparé.
    necessite_investisseurs: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # AJOUT (migration c3d5e7f9a1b3, service 1.1.13) -- symétrique à
    # necessite_investisseurs : true = section sautée si le projet A des
    # Investisseurs (pas l'inverse). Cas d'usage : variante du Préambule
    # "fondateurs seuls", incompatible avec un projet qui a des investisseurs.
    necessite_absence_investisseurs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # 3e critère d'applicabilité (migration f6b3e9a2c5d7, Article 3 du pacte —
    # Hypothèses 1/2 découpées en sections "1er rang"/"2nd rang" séparées) :
    # cette section n'est posée que si la variante choisie à la section
    # `depend_de_section` (code_section d'une autre section du même
    # document_type, forcément plus tôt dans `ordre`) fait partie de
    # `depend_de_variantes`. Les deux colonnes vont toujours ensemble (une
    # section soit ne dépend de rien, soit dépend d'une section ET d'une
    # liste de variantes précise) — pas de contrainte DB pour l'imposer,
    # même logique que reference_type/reference_id.
    depend_de_section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    depend_de_variantes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    texte_statique: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Rempli seulement si comportement_section='variante_obligatoire' : liste
    # des contract_clauses_library.code_clause candidats pour cette section (ex:
    # ["preemption_1er_rang_fondateurs_2eme_rang_investisseurs", ...]). Pas de
    # contrainte DB pour l'imposer (même logique que reference_type/reference_id,
    # cohérence garantie par le service applicatif, pas par un CHECK inter-colonnes).
    variantes_candidates: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # Métadonnées d'affichage pour le copilot — voir docstring ci-dessus.
    # NULL pour mention_obligatoire/clause_optionnelle (déjà porté par la clause).
    titre_affiche: Mapped[str | None] = mapped_column(String(255), nullable=True)
    explication: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("document_type", "ordre", name="uq_document_templates_type_ordre"),
        CheckConstraint(
            f"comportement_section IN {_COMPORTEMENT_SECTION}", name="ck_document_templates_comportement_section"
        ),
        CheckConstraint(f"reference_type IN {_REFERENCE_TYPE}", name="ck_document_templates_reference_type"),
    )