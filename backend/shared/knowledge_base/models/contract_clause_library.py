"""Table `contract_clauses_library` — bibliothèque de clauses contractuelles types
(Phase collecte, Groupe 5 — services 1.1.13 pacte de fondateurs / 1.1.4 statuts).

Une ligne = une clause type prête à être injectée dans un document, partagée
entre tous les documents-contrats (pacte, statuts, futurs nda/cession_ip en I2).
Contenu de référence externe, jamais saisi à la main : alimenté par le pipeline
de collecte dédié (mêmes sources stables, ex. Bpifrance Création).

Deux usages distincts, d'où les deux champs textuels adjacents :
- `description_clause` sert à MATCHER l'intention utilisateur (vectorisé dans
  `content_embeddings`, champ_source='description_clause') ET sert
  d'explication affichée au copilot avant la question (double usage assumé,
  voir document_generation_service._clause_payload) ;
- `texte_clause` est le CONTENU final injecté dans le document (vectorisé aussi,
  champ_source='texte_clause', mais pour servir le copilot, pas le matcher).

Le retrieval ne sert que les lignes en `statut_contenu='valide_humain'` : toute
ligne insérée par collecte automatique est inutilisable tant qu'une validation
humaine ne l'a pas passée — contrainte applicative, pas de flag distinct.

RENOMMAGE (migration d9c4a6b1f3e8, 20/09/2026, demandé par l'utilisateur) :
`scenario` -> `code_clause` et `scenario_description` -> `description_clause`.
Les anciens noms laissaient penser à un "scénario métier" alors que ce sont
des colonnes purement techniques (clé de référence + texte de matching) —
voir la migration pour le détail. Pas un changement de structure, seulement
de noms.

AJOUT (migration <à définir>, 20/09/2026, ré-extraction du modèle Bpifrance) :
`sous_variantes_candidates` — un SEUL cas réel dans le pacte de fondateurs
(Article 3, 3 des 7 hypothèses de préemption/préférence contiennent chacune
un second choix imbriqué : droit de préemption portant sur la totalité des
Titres uniquement, ou avec faculté d'exercice partiel — deux mécanismes
juridiques réellement différents, pas une simple variable). Vérifié : ce
nesting n'apparaît nulle part ailleurs dans les 10 articles (voir la
segmentation structurelle du 20/09/2026). Plutôt que d'ajouter un second
niveau à `document_templates.variantes_candidates` (qui resterait à plat
pour les 9 autres cas), le second niveau est porté directement par la clause
candidate elle-même : une clause de `contract_clauses_library` peut avoir sa
propre liste de `code_clause` sous-candidats, résolue en cascade par
`document_generation_service._clause_payload`. NULL pour toute clause sans
sous-choix (l'immense majorité).
AJOUT (convention de données, pas de migration — `variables_requises` est déjà
un JSONB libre, 20/09/2026, triage variables pacte de fondateurs cas 58) :
une variable de `variables_requises` peut porter `depend_de_variable` (le `nom`
d'une AUTRE variable de la MÊME clause) + `depend_de_valeurs` (liste des
valeurs de cette autre variable qui rendent celle-ci pertinente). Ex. la
clause de répartition des bénéfices (7.5) : "(l'intégralité/au moins X %) de
la trésorerie disponible..." — une variable `choix` (`intégralité`/`pourcentage
minimum`) + une variable `nombre` (`seuil_pourcentage`) qui ne doit être
demandée QUE si le choix est "pourcentage minimum" (`document_generation_service._validate_variables` applique ce filtre avant de valider les
`variables_requises` manquantes). Décision actée avec l'utilisateur : préféré
à une simple variable `texte` libre (ex. "au moins 60 %" tapé en une seule
chaîne) — un champ structuré permet de valider le pourcentage comme un vrai
`nombre` plutôt que de laisser passer n'importe quel texte. Cas d'usage réel
unique pour l'instant (pas un mécanisme général type `depend_de_section` sur
`document_templates`, qui conditionne des SECTIONS entières — celui-ci
conditionne des VARIABLES individuelles dans une même clause).

(réalisé par OPENCODE)
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ContractClauseLibrary(Base):
    __tablename__ = "contract_clauses_library"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Valeurs fermées évolutives : 'pacte_fondateurs', 'statuts' (I1), futurs 'nda'/'cession_ip' (I2).
    # Pas de CHECK constraint volontairement : le document_type voyage aussi dans
    # contract_clauses_library et content_embeddings avec chacun sa propre contrainte —
    # on attend I2 pour figer la liste complète.
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Clé technique de référence (ex-`scenario`) — jamais affichée telle
    # quelle à l'utilisateur, voir le renommage documenté ci-dessus.
    code_clause: Mapped[str] = mapped_column(String(80), nullable=False)
    description_clause: Mapped[str] = mapped_column(Text, nullable=False)
    titre_clause: Mapped[str] = mapped_column(String(255), nullable=False)
    # Template de clause avec variables à injecter (voir variables_requises) — enrichi
    # au moment de la génération par les données du projet (project_associates, etc.).
    texte_clause: Mapped[str] = mapped_column(Text, nullable=False)
    variables_requises: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source_modele: Mapped[str] = mapped_column(String(120), nullable=False)
    verifie_par_professionnel: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    forme_juridique_concernee: Mapped[str | None] = mapped_column(String(60), nullable=True)
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    derniere_verification: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")
    # Rempli seulement pour une clause candidate qui a elle-même un second
    # niveau de choix (voir docstring ci-dessus) — liste de `code_clause` des
    # sous-candidats, même mécanisme qu'un cran plus haut sur
    # document_templates.variantes_candidates. NULL pour toute clause sans
    # sous-choix (cas normal, immense majorité).
    sous_variantes_candidates: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_contract_clauses_library_statut_contenu",
        ),
    )