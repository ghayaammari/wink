"""Moteur de session interactive de génération de document (Phase mécanisme,
service 1.1.13 — pacte de fondateurs ; réutilisable tel quel par 1.1.4/statuts,
voir docstring de DocumentGenerationSession).

Parcourt `document_templates` (squelette, ordre croissant) section par section :
- `mention_obligatoire` : toujours incluse, aucun choix, juste les variables de
  la clause référencée (`contract_clauses_library.variables_requises`) à saisir
  si non vides.
- `clause_optionnelle` : l'utilisateur choisit d'inclure ou non (`inclus`), puis
  saisit les variables si incluse.
- `variante_obligatoire` : l'utilisateur choisit UNE clause candidate parmi
  `document_templates.variantes_candidates` (ou aucune, si `obligatoire=false`
  sur la section — ex. Article 3 n'est pas imposé par la loi), puis saisit les
  variables de la clause choisie. **Cas particulier (Article 3 seulement, voir
  migration `b7e2f4a9c1d6`)** : une clause candidate peut elle-même porter un
  second niveau de choix (`contract_clauses_library.sous_variantes_candidates`)
  — la clause réellement appliquée est alors la sous-variante choisie, pas la
  clause de premier niveau (qui ne sert qu'à regrouper l'affichage).
- `donnee_projet` : pas de clause, rendu directement depuis `project_associates`/
  `projects`/`project_legal_profiles` — aucune saisie ici, juste un passage.
- `texte_statique` : rien à faire, avancement automatique.

Texte libre hors variables (ex. remarque de l'utilisateur ajoutée à une clause)
n'est PAS géré par ce module — c'est le rôle du garde-fou LLM
(agents/contract_agent/legal_clause_guardrail_service.py), appelé par le router
AVANT d'atteindre submit_section ici, jamais après (aucune clause potentiellement
illégale n'est censée atteindre ce module).

RENOMMAGE (migration d9c4a6b1f3e8, 20/09/2026, demandé par l'utilisateur) :
`scenario` -> `code_clause`, `scenario_description` -> `description_clause`,
`nom_section` -> `code_section`, `type_contenu` -> `comportement_section` —
voir les docstrings des modèles pour le pourquoi. La clé `"scenario"` du dict
`reponses` (JSONB, non-colonne mais même concept) est renommée `"code_clause"`
par cohérence, pour éviter de garder l'ancien nom dans les sessions déjà en
cours de développement alors que la colonne source est renommée partout
ailleurs.
"""
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_generation_session import DocumentGenerationSession
from backend.entrepreneur.models.document_generation_variable_value import DocumentGenerationVariableValue
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.services.document_renderer_base import _lit, _val, formater_montant
from backend.shared.utils.formatting import formater_siege_social as _formater_siege_social
from backend.entrepreneur.services.pacte_fondateurs_renderer import pacte_clause_renderer
from backend.entrepreneur.services.pdf_rendering_service import render_document_as_pdf
from backend.entrepreneur.services.project_service import get_owned_project
from backend.entrepreneur.services.statuts_sas_renderer import DOCUMENT_TYPE_STATUTS, statuts_clause_renderer
from backend.shared.knowledge_base.models.contract_clause_library import ContractClauseLibrary
from backend.shared.knowledge_base.models.document_template import DocumentTemplate
from backend.shared.models.user import User
from backend.shared.services import cloudinary_service


class DocumentGenerationError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class SectionNotFoundError(DocumentGenerationError):
    """La section visée n'existe pas dans le squelette de ce document_type."""


class InvalidAnswerError(DocumentGenerationError):
    """Réponse manquante ou incohérente avec le type de la section (variante
    hors liste, variable requise absente, section obligatoire exclue...)."""


class SessionAlreadyCompleteError(DocumentGenerationError):
    """La session est déjà `statut='complete'` — un document a déjà été généré."""


class ValidationFinaleError(DocumentGenerationError):
    """Génération refusée : la validation globale a trouvé au moins un
    problème bloquant. Porte le résultat complet pour le renvoyer au
    frontend (même format que la route …/validation-finale)."""

    def __init__(self, resultat: dict):
        super().__init__("Des points bloquants empêchent de générer le document.")
        self.resultat = resultat


class NoPreviousSectionError(DocumentGenerationError):
    """Aucune section interactive répondue avant la section courante — rien où reculer."""


# ---------------------------------------------------------------------------
# Résolution session
# ---------------------------------------------------------------------------

def get_or_create_session(
    db: Session, user: User, project_id, document_type: str
) -> DocumentGenerationSession:
    project = get_owned_project(db, user, project_id)

    session = (
        db.query(DocumentGenerationSession)
        .filter(
            DocumentGenerationSession.project_id == project.id,
            DocumentGenerationSession.document_type == document_type,
        )
        .first()
    )
    if session is not None:
        return session

    session = DocumentGenerationSession(project_id=project.id, document_type=document_type)
    db.add(session)
    db.flush()
    _advance_to_next_section(db, session)
    db.commit()
    db.refresh(session)
    return session


def _set_reponse(session: DocumentGenerationSession, code_section: str, value: dict) -> None:
    """Écrit `reponses[code_section] = value` en réassignant tout le dict.

    SQLAlchemy ne détecte pas la mutation en place d'une colonne JSONB
    (`session.reponses[x] = y`) sans `flag_modified` — réassigner un nouveau
    dict à l'attribut est la façon la plus simple de garantir que l'UPDATE
    inclut bien cette colonne au prochain commit (sinon la réponse est
    silencieusement perdue au rechargement de la session).
    """
    session.reponses = {**session.reponses, code_section: value}


def _sections(db: Session, document_type: str) -> list[DocumentTemplate]:
    return (
        db.query(DocumentTemplate)
        .filter(DocumentTemplate.document_type == document_type)
        .order_by(DocumentTemplate.ordre)
        .all()
    )


def _applicable(
    section: DocumentTemplate,
    forme_juridique: str | None,
    a_des_investisseurs: bool,
    reponses: dict,
) -> bool:
    """Une section est ignorée si l'un de ses critères d'applicabilité ne
    correspond pas au projet — 3 critères indépendants aujourd'hui, testés
    tous avant d'inclure la section (`ET` logique, pas une union) :

    - `formes_juridiques_concernees` (migration a1c2d4e6f8b0, cases 95-96) :
      liste de formes juridiques (ex. `["SAS","SASU","SA"]`) -- la section ne
      s'applique que si `forme_juridique` du projet y figure. `None`/liste
      vide = aucune restriction (applicable à toutes les formes).
    - `necessite_investisseurs` (migration d3a7c5e8f1b4) : section réservée
      aux droits propres aux Associés Investisseurs — sautée si le projet n'a
      aucun associé investisseur (répartition 100 % Fondateurs), sinon le
      questionnaire poserait des questions incohérentes avec le projet réel.
    - `depend_de_section` / `depend_de_variantes` (migration f6b3e9a2c5d7,
      Article 3) : section qui ne s'applique QUE si la variante réellement
      choisie à la section `depend_de_section` (déjà répondue, forcément plus
      tôt dans `ordre`) est dans `depend_de_variantes`. Cas volontaire : si
      la section dont on dépend a été jugée non applicable ou exclue par
      l'utilisateur, sa réponse n'a pas de clé "code_clause" — `.get()`
      renvoie None, jamais dans la liste, donc cette section-ci est
      automatiquement sautée aussi (la cascade se propage sans code
      spécial).

    NOTE (dette technique assumée, signalée pas cachée) : l'ancien paramètre
    `session_reponses` avait été retiré en ajoutant `necessite_investisseurs`
    (jamais utilisé jusque-là) — il revient ici, cette fois réellement
    utilisé, pour ce 3e critère.
    """
    if section.formes_juridiques_concernees:
        if forme_juridique is None or forme_juridique not in section.formes_juridiques_concernees:
            return False
    if section.necessite_investisseurs and not a_des_investisseurs:
        return False
    if section.necessite_absence_investisseurs and a_des_investisseurs:
        return False
    if section.depend_de_section is not None:
        reponse_dependance = reponses.get(section.depend_de_section) or {}
        if reponse_dependance.get("code_clause") not in (section.depend_de_variantes or []):
            return False
    # Correction #9 (Art. 24 `comite_direction_voix_preponderante` sans
    # Art. 22 `limitation_pouvoirs_president`) : exception migrée le
    # 24/09/2026 vers le référentiel SECTIONS_DERIVEES
    # (statuts_sas_resolvers.py, audit #19), appliqué dans
    # `_advance_to_next_section` -- plus de cas particulier par code_section ici.
    return True


def _reponse_auto_si_rien_a_saisir(
    db: Session, session: DocumentGenerationSession, section: DocumentTemplate
) -> dict | None:
    """Étape 3 de la refonte (24/09/2026) — une `mention_obligatoire` qui n'a
    STRICTEMENT rien à demander à l'utilisateur est générée directement, sans
    être affichée ni exiger un clic "Valider" (ex. `agrement_decision`,
    `domaine_reserve_cloture`, texte fixe d'un article, ou article dont toutes
    les variables sont résolues automatiquement).

    "Rien à demander" est décidé par le MÊME code que la validation d'une
    soumission (`_validate_variables` avec `valeurs={}`) : les deux ne peuvent
    pas diverger. Seul garde-fou : un choix d'associé parmi plusieurs
    candidats (`selections_requises`) reste une question.

    Décision utilisateur (24/09/2026) : AUCUN contrôle ici sur les données
    automatiques manquantes (objet social vide, dirigeant non désigné…) —
    elles seront vérifiées par une PRÉ-VALIDATION au démarrage et une
    VALIDATION GLOBALE avant génération (à construire), qui bloquent
    l'utilisateur. Tant que ces 2 validations n'existent pas, une donnée
    manquante part dans le PDF sous forme de placeholder "(… non renseigné)"
    sans que la section soit affichée — dette assumée, transitoire.

    Renvoie la réponse à enregistrer, ou None si la section doit être posée.
    Limité aux `mention_obligatoire` : une `clause_optionnelle` ou un groupe de
    variantes demande toujours une décision (inclure / laquelle).
    """
    from backend.entrepreneur.services.statuts_sas_resolvers import _selections_requises

    if section.comportement_section != "mention_obligatoire":
        return None
    clause = db.query(ContractClauseLibrary).filter(ContractClauseLibrary.id == section.reference_id).first()
    if clause is None:
        return None
    try:
        _validate_variables(clause, {}, db, session.project_id)
    except InvalidAnswerError:
        return None
    if _selections_requises(db, clause.variables_requises, session.project_id, clause.code_clause):
        return None
    return {"inclus": True, "code_clause": clause.code_clause, "valeurs": {}, "auto_genere": True}


def _advance_to_next_section(db: Session, session: DocumentGenerationSession) -> None:
    """Avance `section_courante` à la prochaine section non traitée (absente de
    `reponses`), en marquant automatiquement `texte_statique`/`donnee_projet`
    comme traitées (rien à saisir) et en sautant les sections non applicables à
    la forme juridique du projet. Passe `statut='complete'` s'il n'en reste
    aucune — ne finalise PAS le document (voir finalize_session, étape séparée
    et explicite côté utilisateur).
    """
    forme_juridique = None
    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()
    )
    if legal_profile is not None:
        forme_juridique = legal_profile.legal_form

    # Calculé une fois par avancement, pas par section (la réponse ne change pas
    # en cours de parcours — les associés ne sont pas modifiables pendant la
    # génération du pacte, seulement depuis "Équipe & capital").
    a_des_investisseurs = (
        db.query(ProjectAssociate)
        .filter(
            ProjectAssociate.project_id == session.project_id,
            ProjectAssociate.est_partie_au_pacte_fondateurs.is_(True),
            ProjectAssociate.est_fondateur.is_(False),
        )
        .first()
        is not None
    )

    sections = _sections(db, session.document_type)
    # AJOUT (24/09/2026, audit #19) : écran de choix des articles facultatifs
    # (statuts uniquement) -- voir "Écran de choix des articles facultatifs"
    # dans statuts_sas_resolvers.py.
    est_statuts = session.document_type == DOCUMENT_TYPE_STATUTS
    if est_statuts:
        from backend.entrepreneur.services.statuts_sas_resolvers import (
            SECTION_PAUSE_FACULTATIFS,
            articles_par_section,
            doit_faire_pause_facultatifs,
            reponse_facultatif_non_choisi,
        )

        article_de = articles_par_section(sections)
        from backend.entrepreneur.services.statuts_sas_resolvers import (
            reponse_selon_dirigeants,
            reponse_selon_types_apport,
            types_dirigeants,
        )

        # Calculé une fois par avancement (comme `a_des_investisseurs`) : les
        # associés ne changent pas pendant la rédaction.
        types_apport = {
            t for (t,) in db.query(ProjectAssociate.type_apport).filter(ProjectAssociate.project_id == session.project_id)
        }
        types_par_role = types_dirigeants(db, session.project_id)

    for section in sections:
        if section.code_section in session.reponses:
            continue
        if est_statuts:
            # Pause juste avant l'Art. 8 : le parcours s'arrête sur l'écran de
            # choix. `submit_facultatifs` marque ensuite le titre de l'Art. 8
            # comme traité, ce qui lève la pause.
            if doit_faire_pause_facultatifs(section.code_section):
                session.section_courante = SECTION_PAUSE_FACULTATIFS
                db.flush()
                return
            exclu = reponse_facultatif_non_choisi(article_de.get(section.code_section), session.reponses)
            if exclu is not None and section.comportement_section in _SECTIONS_INTERACTIVES:
                _set_reponse(session, section.code_section, exclu)
                continue
        if not _applicable(section, forme_juridique, a_des_investisseurs, session.reponses):
            _set_reponse(session, section.code_section, {"applicable": False})
            continue
        # AJOUT (24/09/2026, audit #19) : sections dont la réponse se DÉDUIT
        # des réponses déjà données (statuts uniquement) -- jamais posées à
        # l'utilisateur. Voir SECTIONS_DERIVEES dans statuts_sas_resolvers.py.
        if session.document_type == DOCUMENT_TYPE_STATUTS:
            from backend.entrepreneur.services.statuts_sas_resolvers import reponse_derivee

            derivee = reponse_derivee(section.code_section, session.reponses)
            if derivee is not None:
                _set_reponse(session, section.code_section, derivee)
                continue
            # Lot 4 (24/09/2026) : sections d'apport selon les types d'apport
            # RÉELS des associés (numéraire / nature / industrie) -- ex. pas de
            # question "Évaluation des apports en nature" sans apport en nature.
            derivee = reponse_selon_types_apport(section.code_section, types_apport)
            if derivee is not None:
                _set_reponse(session, section.code_section, derivee)
                continue
            # Lot 5 : variante PP/PM des nominations (Art. 39-41) déduite du
            # dirigeant désigné dans « Informations légales ».
            derivee = reponse_selon_dirigeants(section.code_section, types_par_role)
            if derivee is not None:
                _set_reponse(session, section.code_section, derivee)
                continue
        if section.comportement_section in ("texte_statique", "donnee_projet"):
            _set_reponse(session, section.code_section, {"traite_automatiquement": True})
            continue
        # Étape 3 de la refonte (24/09/2026) : statuts uniquement pour l'instant
        # -- le pacte garde son comportement (clic "Valider" sur chaque
        # section), aucun changement non demandé sur un service déjà livré.
        # Pour l'étendre au pacte : retirer cette condition, rien d'autre.
        if est_statuts:
            auto = _reponse_auto_si_rien_a_saisir(db, session, section)
            if auto is not None:
                _set_reponse(session, section.code_section, auto)
                continue
        session.section_courante = section.code_section
        db.flush()
        return

    session.section_courante = None
    session.statut = "complete"
    # Correction depuis la vérification finale terminée : on revient à l'écran
    # de vérification, la sauvegarde d'annulation n'a plus lieu d'être.
    if CLE_CORRECTION_EN_COURS in session.reponses:
        session.reponses = {k: v for k, v in session.reponses.items() if k != CLE_CORRECTION_EN_COURS}
    db.flush()


# ---------------------------------------------------------------------------
# Lecture de l'état courant (ce que le frontend affiche)
# ---------------------------------------------------------------------------

def _clause_payload(db: Session, clause: ContractClauseLibrary, project_id, legal_profile) -> dict:
    """`legal_profile` (peut être `None`) et `project_id` servent UNIQUEMENT à
    remplir `valeurs_auto_resolues` (24/09/2026) : les variables `auto_*` de
    cette clause (ex. Préambule -- dénomination sociale, capital...) ne sont
    jamais posées à l'utilisateur (voir `_resoudre_variables_auto`), mais
    doivent quand même s'afficher en lecture seule dans le questionnaire --
    avant, seule `_assemble_document_blocks` (assemblage final/aperçu) les
    résolvait, l'étape du formulaire ne recevait que leur définition, jamais
    leur valeur. Champ absent des types non-`auto_*` (dict vide), le frontend
    n'a besoin de le lire que pour ceux-là."""
    # Import local (pas en tête de fichier), conservé tel quel après le
    # correctif du 23/09/2026 (extraction de `_lit`/`_render_clause_texte`
    # vers `document_renderer_base.py`/`statuts_sas_renderer.py`) : la
    # dépendance n'est plus circulaire (statuts_sas_resolvers n'importe plus
    # rien d'ici), mais le style local-import est gardé par cohérence avec
    # les autres appels de ce module vers `statuts_sas_resolvers` ci-dessous
    # -- voir la docstring de module de `statuts_sas_resolvers.py`.
    from backend.entrepreneur.services.statuts_sas_resolvers import _selections_requises

    payload = {
        "code_clause": clause.code_clause,
        "titre_clause": clause.titre_clause,
        "description_clause": clause.description_clause,
        "texte_clause": clause.texte_clause,
        "variables_requises": clause.variables_requises,
        "valeurs_auto_resolues": {
            **_resoudre_variables_auto(clause.variables_requises, legal_profile),
            **_resoudre_variables_associes(db, clause.variables_requises, project_id),
        },
        # AJOUT (23/09/2026, service 1.1.4 statuts, Cas B/C) -- pour chaque
        # variable `auto_identite_associe` dont le filtre `selection` retient
        # PLUSIEURS associés (ex. Article 8 `fondateur_avantage`, plusieurs
        # fondateurs), le frontend doit proposer un choix -- voir
        # `_selections_requises`. Dict vide si aucune variable de la clause
        # n'a besoin d'un choix (cas normal, résolution automatique -- voir
        # `_resoudre_variables_selection_associe`).
        "selections_requises": _selections_requises(db, clause.variables_requises, project_id, clause.code_clause),
        "sous_candidats": None,
    }
    if clause.sous_variantes_candidates:
        # Résolution en cascade (récursive) — un seul niveau existe réellement
        # aujourd'hui (Article 3, voir migration b7e2f4a9c1d6), mais rien
        # n'empêche un futur document_type (1.1.4/statuts) d'en avoir plus —
        # pas de limite arbitraire à 1 niveau codée en dur ici.
        sous_clauses = (
            db.query(ContractClauseLibrary)
            .filter(ContractClauseLibrary.code_clause.in_(clause.sous_variantes_candidates))
            .all()
        )
        by_code = {c.code_clause: c for c in sous_clauses}
        payload["sous_candidats"] = [
            _clause_payload(db, by_code[s], project_id, legal_profile)
            for s in clause.sous_variantes_candidates
            if s in by_code
        ]
    return payload


_SECTIONS_INTERACTIVES = ("mention_obligatoire", "clause_optionnelle", "variante_obligatoire")

# Clé réservée de `session.reponses` (comme `__facultatifs_choisis__`) :
# correction d'une section lancée depuis la vérification finale --
# {"section": code_section, "reponses_avant": copie des réponses} pour
# pouvoir annuler. Retirée quand le parcours se termine à nouveau.
CLE_CORRECTION_EN_COURS = "__correction_en_cours__"
# Réponses calculées par le moteur (jamais saisies par l'utilisateur).
_MARQUEURS_REPONSE_CALCULEE = ("derivee", "auto_genere", "traite_automatiquement")


def _section_progress(db: Session, session: DocumentGenerationSession) -> tuple[int | None, int]:
    """Position (1-based) de `session.section_courante` parmi les sections
    interactives, et total -- pour la barre de progression du formulaire
    (24/09/2026, demande utilisateur).

    `total` est une ESTIMATION, pas un compte final : une section pas encore
    atteinte, dont l'applicabilité dépend d'une réponse à venir
    (`depend_de_section`), est comptée par optimisme comme applicable tant
    qu'elle n'est pas explicitement écartée (`reponses[...] == {"applicable":
    False}`). Le total peut donc légèrement baisser en cours de route si une
    section plus loin s'avère finalement non applicable -- compromis délibéré
    pour éviter de pré-simuler tout l'arbre des branches restantes juste pour
    une barre de progression (complexité que rien ne justifie ici).
    `texte_statique`/`donnee_projet` ne comptent pas : jamais présentées comme
    une "page" du formulaire (traitées automatiquement, pas de saisie).
    """
    total = 0
    position: int | None = None
    for section in _sections(db, session.document_type):
        if section.comportement_section not in _SECTIONS_INTERACTIVES:
            continue
        reponse = session.reponses.get(section.code_section)
        if reponse is not None and reponse.get("applicable", True) is False:
            continue
        total += 1
        if section.code_section == session.section_courante:
            position = total
    return position, total


def _numeros_articles_statuts(db: Session, session: DocumentGenerationSession) -> dict[str, int] | None:
    """Lot B (24/09/2026) : {numéro logique: numéro affiché} des articles
    présents dans les statuts (voir statuts_sas_numerotation.py). `None` pour
    les autres documents : le pacte garde ses numéros écrits dans le texte."""
    if session.document_type != DOCUMENT_TYPE_STATUTS:
        return None
    from backend.entrepreneur.services.statuts_sas_numerotation import numeros_articles
    from backend.entrepreneur.services.statuts_sas_resolvers import articles_par_section

    sections = _sections(db, session.document_type)
    article_courant = articles_par_section(sections).get(session.section_courante or "")
    return numeros_articles(sections, session.reponses, article_courant)


def _nom_article_courant(
    db: Session, document_type: str, ordre_section: float, code_section: str = "", numeros: dict[str, int] | None = None
) -> str | None:
    """Nom de l'article (ex. "Article 2 - Cessions libres et Cessions
    interdites...") auquel appartient la section d'ordre `ordre_section` --
    24/09/2026, demande utilisateur : le titre du formulaire n'affichait que
    le nom de la clause, pas celui de l'article qui la contient, ambigu
    quand plusieurs articles ont des clauses aux intitulés proches.

    Heuristique par convention de nommage (`code_section` préfixé
    `titre_article_`, voir generate_pacte_fondateurs_v2.py), pas une colonne
    dédiée : ajouter une colonne "article" à `document_templates` aurait
    demandé une migration + un reseed pour une seule info d'affichage --
    display-only, dégrade en silence (`None`, pas d'erreur) si un futur
    squelette (1.1.4/statuts) n'a pas de section nommée ainsi. À revoir si un
    2e document_type introduit la même notion d'article ET une structure de
    nommage différente.
    """
    # Lot C (24/09/2026) : une section hors article (clôture des statuts)
    # n'a pas d'article parent -- sans ce cas, le formulaire affichait
    # « Article 44 - Mandat… » au-dessus du bloc de signature.
    if document_type == DOCUMENT_TYPE_STATUTS:
        from backend.entrepreneur.services.statuts_sas_resolvers import SECTIONS_HORS_ARTICLE

        if code_section in SECTIONS_HORS_ARTICLE:
            return "Clôture des statuts"
    row = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.document_type == document_type,
            DocumentTemplate.code_section.like("titre_article_%"),
            DocumentTemplate.ordre < ordre_section,
        )
        .order_by(DocumentTemplate.ordre.desc())
        .first()
    )
    if row is None:
        return None
    if numeros is not None:
        # Lot B : statuts -- « Article {n} – {titre} » avec le numéro affiché
        # (le clausier ne porte plus que l'intitulé).
        from backend.entrepreneur.services.statuts_sas_numerotation import PREFIXE_TITRE_ARTICLE, libelle_article

        return libelle_article(numeros.get(row.code_section[len(PREFIXE_TITRE_ARTICLE):]), row.titre_affiche)
    return row.titre_affiche


def prevalider(db: Session, user: User, project_id, document_type: str) -> dict[str, Any]:
    """Pré-validation au démarrage (24/09/2026, décision utilisateur) : les
    données du projet reprises automatiquement doivent être complètes AVANT
    la première question -- voir statuts_sas_prevalidation.py. Statuts
    uniquement ; les autres documents n'ont pas (encore) de pré-validation :
    toujours prêts, comportement inchangé."""
    project = get_owned_project(db, user, project_id)
    if document_type != DOCUMENT_TYPE_STATUTS:
        return {"pret": True, "problemes": []}
    from backend.entrepreneur.services.statuts_sas_prevalidation import prevalider_statuts

    legal_profile = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()
    siege = _formater_siege_social(legal_profile.registered_address if legal_profile else None)
    problemes = prevalider_statuts(db, project.id, siege)
    return {"pret": not problemes, "problemes": problemes}


def get_current_section_state(db: Session, user: User, project_id, document_type: str) -> dict[str, Any]:
    session = get_or_create_session(db, user, project_id, document_type)
    if session.statut == "complete" or session.section_courante is None:
        return {
            "session_id": session.id,
            "statut": session.statut,
            "section_courante": None,
            # 24/09/2026 (demande utilisateur) — distingue "questionnaire terminé,
            # prêt à finaliser" (False) de "déjà finalisé lors d'une visite
            # précédente" (True) : sans ça, le frontend rouvrait toujours l'écran
            # "Finaliser le pacte" même après finalisation, `finalize_session`
            # refusant alors une 2e finalisation (SessionAlreadyCompleteError)
            # sans que l'utilisateur comprenne pourquoi il est bloqué là.
            "document_deja_genere": session.document_genere_id is not None,
        }

    # AJOUT (24/09/2026, audit #19) : pause sur l'écran de choix des facultatifs.
    if document_type == DOCUMENT_TYPE_STATUTS:
        from backend.entrepreneur.services.statuts_sas_resolvers import (
            SECTION_PAUSE_FACULTATIFS,
            liste_facultatifs,
        )
        from backend.shared.knowledge_base.services.article_explication_service import textes_valides

        if session.section_courante == SECTION_PAUSE_FACULTATIFS:
            _, total = _section_progress(db, session)
            return {
                "session_id": session.id,
                "statut": session.statut,
                "code_section": SECTION_PAUSE_FACULTATIFS,
                "titre_section": "Les protections de vos statuts",
                "explication_section": (
                    "Vos bases sont posées. Choisissez maintenant les articles facultatifs à ajouter : "
                    "seuls ceux que vous cochez vous seront présentés ensuite, à leur place dans les statuts."
                ),
                "position": None,
                "total_sections_estime": total,
                "choix_facultatifs_requis": True,
                # Étape 5 : explications relues (table `article_explications`,
                # nécessite la migration e7b2d4f6a8c1), texte provisoire sinon.
                "facultatifs": liste_facultatifs(
                    session.reponses, textes_valides(db, document_type=document_type)
                ),
            }

    section = (
        db.query(DocumentTemplate)
        .filter(
            DocumentTemplate.document_type == document_type,
            DocumentTemplate.code_section == session.section_courante,
        )
        .first()
    )
    if section is None:
        raise SectionNotFoundError(f"Section '{session.section_courante}' absente du squelette en base.")

    position, total = _section_progress(db, session)

    correction = session.reponses.get(CLE_CORRECTION_EN_COURS)

    state: dict[str, Any] = {
        "session_id": session.id,
        "statut": session.statut,
        "code_section": section.code_section,
        "comportement_section": section.comportement_section,
        "obligatoire": section.obligatoire,
        # Titre/explication à annoncer par le copilot AVANT toute question (scénario
        # fonctionnel, Étape 2 : "explication avant collecte, jamais de question à
        # l'aveugle"). Résolu ici plutôt que laissé au frontend à reconstituer :
        # - mention_obligatoire/clause_optionnelle : une seule clause, donc
        #   titre_clause/description_clause de CETTE clause ;
        # - variante_obligatoire/donnee_projet : pas de clause unique à emprunter
        #   (plusieurs candidats, ou aucune clause) → document_templates.titre_affiche/
        #   explication (voir migration a3d7e1c8f0b2).
        "titre_section": section.titre_affiche,
        "explication_section": section.explication,
        # 24/09/2026 (demande utilisateur) — voir _nom_article_courant/_section_progress.
        "nom_article": _nom_article_courant(
            db, document_type, section.ordre, section.code_section, _numeros_articles_statuts(db, session)
        ),
        "position": position,
        "total_sections_estime": total,
        "correction_en_cours": correction is not None,
    }
    if correction is not None:
        # Formulaire prérempli avec la réponse d'avant la correction (aussi
        # après un rechargement de page) : on ne change que ce qui est faux.
        state["reponse_precedente"] = correction["reponses_avant"].get(section.code_section)

    # AJOUT (24/09/2026, audit #19) : article facultatif coché dans l'écran de
    # choix -> le frontend n'y redemande pas "l'inclure ?" et affiche le badge
    # + "Ne plus inclure cet article".
    if document_type == DOCUMENT_TYPE_STATUTS:
        from backend.entrepreneur.services.statuts_sas_resolvers import (
            articles_par_section,
            code_facultatif_de_l_article,
            est_article_facultatif_choisi,
        )

        article = articles_par_section(_sections(db, document_type)).get(section.code_section)
        state["article_facultatif_choisi"] = est_article_facultatif_choisi(article, session.reponses)
        # Seule la section de BASE de l'article (ex. `droit_preemption`) est
        # incluse d'office ; ses options internes (ex. `preemption_exceptions`)
        # restent de vraies questions oui/non.
        state["section_de_base_facultatif"] = (
            state["article_facultatif_choisi"] and section.code_section == code_facultatif_de_l_article(article)
        )

    if section.comportement_section in ("mention_obligatoire", "clause_optionnelle", "variante_obligatoire"):
        # Chargé une seule fois ici (peut être `None`, un projet peut ne pas
        # encore avoir de profil juridique) plutôt que dans `_clause_payload` —
        # évite une requête par clause/sous-candidat pour la même donnée.
        legal_profile = (
            db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()
        )

    if section.comportement_section in ("mention_obligatoire", "clause_optionnelle"):
        clause = db.query(ContractClauseLibrary).filter(ContractClauseLibrary.id == section.reference_id).first()
        state["clause"] = _clause_payload(db, clause, session.project_id, legal_profile) if clause else None
        if clause is not None:
            state["titre_section"] = clause.titre_clause
            state["explication_section"] = clause.description_clause
    elif section.comportement_section == "variante_obligatoire":
        candidates = (
            db.query(ContractClauseLibrary)
            .filter(ContractClauseLibrary.code_clause.in_(section.variantes_candidates or []))
            .all()
        )
        # Ordre conservé tel que défini dans le squelette (celui de la liste
        # variantes_candidates), pas l'ordre arbitraire renvoyé par la requête SQL.
        by_code = {c.code_clause: c for c in candidates}
        state["candidats"] = [
            _clause_payload(db, by_code[s], session.project_id, legal_profile)
            for s in (section.variantes_candidates or [])
            if s in by_code
        ]

    return state


def go_to_previous_section(db: Session, user: User, project_id, document_type: str) -> dict[str, Any]:
    """Revient à la dernière section interactive répondue par l'utilisateur
    (24/09/2026, demande utilisateur : bouton "Précédent" du formulaire).

    Ce n'est PAS une navigation libre "va à la page N" : reculer retire la
    réponse de cette section ET de toutes celles qui suivent (même
    non-interactives), puis remet `section_courante` dessus. Nécessaire, pas
    juste plus simple : l'applicabilité d'une section peut dépendre de la
    réponse à une section antérieure (`depend_de_section`, voir Article 3) --
    garder les réponses suivantes telles quelles après avoir changé une
    réponse plus tôt aurait pu laisser une incohérence (section restée
    répondue alors qu'elle ne serait plus applicable, ou l'inverse). Les
    sections suivantes seront recalculées par `_advance_to_next_section` au
    fur et à mesure, comme un parcours normal.

    Retourne le même shape que `get_current_section_state`, avec en plus
    `reponse_precedente` (l'ancienne réponse de la section restaurée) pour
    que le frontend puisse préremplir le formulaire plutôt que de le
    rouvrir vide.
    """
    session = get_or_create_session(db, user, project_id, document_type)
    if CLE_CORRECTION_EN_COURS in session.reponses:
        # Reculer effacerait toutes les réponses suivantes -- exactement ce
        # que la correction ciblée évite. Le frontend masque le bouton.
        raise InvalidAnswerError("Correction en cours : utilisez « Revenir à la vérification ».")

    sections = _sections(db, document_type)
    ordre_par_section = {s.code_section: s.ordre for s in sections}

    candidats_retour = [
        s
        for s in sections
        if s.comportement_section in _SECTIONS_INTERACTIVES
        and s.code_section in session.reponses
        and session.reponses[s.code_section].get("applicable", True) is not False
        # AJOUT (24/09/2026, audit #19) : une section déduite n'a pas été
        # remplie par l'utilisateur -- "Précédent" la saute ; elle sera
        # recalculée par `_advance_to_next_section`.
        and not session.reponses[s.code_section].get("derivee")
        # Étape 3 : idem pour une section générée sans saisie (auto-skip).
        and not session.reponses[s.code_section].get("auto_genere")
    ]
    if not candidats_retour:
        raise NoPreviousSectionError("Aucune section précédente à laquelle revenir.")

    cible = max(candidats_retour, key=lambda s: s.ordre)
    reponse_precedente = session.reponses[cible.code_section]

    session.reponses = {
        code: valeur for code, valeur in session.reponses.items() if ordre_par_section.get(code, -1) < cible.ordre
    }
    session.section_courante = cible.code_section
    session.statut = "en_cours"
    db.commit()
    db.refresh(session)

    state = get_current_section_state(db, user, project_id, document_type)
    state["reponse_precedente"] = reponse_precedente
    return state


def restart_session(db: Session, user: User, project_id, document_type: str) -> dict[str, Any]:
    """Repart de zéro sur la MÊME session (24/09/2026, demande utilisateur) --
    "pourquoi je ne peux pas recréer un pacte après en avoir déjà fini un" :
    `document_generation_sessions` a une session unique par (projet,
    document_type) (`UniqueConstraint`, voir son modèle) -- `get_or_create_session`
    renvoie donc toujours la même session, `statut='complete'` ou pas, et
    l'ancien document déjà généré (`document_genere_id`) faisait échouer
    `finalize_session` sur toute nouvelle tentative.

    Vide `reponses` et repart de la 1ère section, comme une toute nouvelle
    session -- ET remet `document_genere_id` à `None`, sinon la prochaine
    `finalize_session` échouerait immédiatement (son garde-fou
    SessionAlreadyCompleteError). Le `Document`/`DocumentVersion` DÉJÀ généré
    n'est ni supprimé ni modifié : rien ici ne touche `documents` -- seul le
    pointeur de LA SESSION vers lui est détaché, le fichier reste consultable
    dans le coffre-fort documentaire (1.1.17) comme n'importe quel document
    généré. Décision actée avec l'utilisateur (24/09/2026) : pas
    d'historique des sessions précédentes (l'option retenue plutôt que
    lever la contrainte unique pour plusieurs sessions par projet) -- les
    réponses du questionnaire qui a produit l'ancien pacte ne sont pas
    conservées, seul le document final l'est.
    """
    session = get_or_create_session(db, user, project_id, document_type)
    session.reponses = {}
    session.section_courante = None
    session.statut = "en_cours"
    session.document_genere_id = None
    db.flush()
    _advance_to_next_section(db, session)
    db.commit()
    db.refresh(session)
    return get_current_section_state(db, user, project_id, document_type)


def rouvrir_section(db: Session, user: User, project_id, document_type: str, code_section: str) -> dict[str, Any]:
    """Rouvre UNE section depuis la vérification finale (« Corriger → »,
    24/09/2026), sans refaire tout le parcours.

    Contrairement à « Section précédente » (qui efface tout ce qui suit),
    seules sont retirées :
    - la réponse de la section ;
    - les réponses CALCULÉES qui la suivent (déduites, générées, non
      applicables) : elles sont recalculées par `_advance_to_next_section`
      avec la nouvelle réponse ;
    - les réponses des sections qui DÉPENDENT d'elle (`depend_de_section`,
      en cascade) : leur existence même peut changer.
    Toutes les autres réponses sont gardées : après validation, le parcours
    se termine tout seul et l'écran de vérification revient.

    Une copie des réponses est gardée sous CLE_CORRECTION_EN_COURS pour
    « Revenir à la vérification » (annuler) et pour préremplir le formulaire.
    """
    session = get_or_create_session(db, user, project_id, document_type)
    if session.document_genere_id is not None:
        raise SessionAlreadyCompleteError("Un document a déjà été généré : recommencez pour le modifier.")
    if session.statut != "complete":
        raise InvalidAnswerError("Une section ne peut être rouverte qu'une fois le parcours terminé.")

    sections = _sections(db, document_type)
    cible = next((s for s in sections if s.code_section == code_section), None)
    if cible is None:
        raise SectionNotFoundError(f"Section '{code_section}' absente du squelette en base.")
    reponse = session.reponses.get(code_section)
    if (
        cible.comportement_section not in _SECTIONS_INTERACTIVES
        or not isinstance(reponse, dict)
        or reponse.get("applicable", True) is False
        or any(reponse.get(m) for m in _MARQUEURS_REPONSE_CALCULEE)
    ):
        raise InvalidAnswerError("Cette section est remplie automatiquement : corrigez plutôt les données du projet.")

    # Sections dépendantes, en cascade (A -> B -> C).
    dependantes = {code_section}
    ajoute = True
    while ajoute:
        ajoute = False
        for s in sections:
            if s.depend_de_section in dependantes and s.code_section not in dependantes:
                dependantes.add(s.code_section)
                ajoute = True

    a_retirer = set(dependantes)
    for s in sections:
        r = session.reponses.get(s.code_section)
        if s.ordre > cible.ordre and isinstance(r, dict) and (
            r.get("applicable", True) is False or any(r.get(m) for m in _MARQUEURS_REPONSE_CALCULEE)
        ):
            a_retirer.add(s.code_section)
    if document_type == DOCUMENT_TYPE_STATUTS:
        # Le titre de l'Art. 8 marque l'écran des facultatifs comme passé :
        # le retirer ferait réapparaître cet écran.
        from backend.entrepreneur.services.statuts_sas_resolvers import _SECTION_AVANT_FACULTATIFS

        a_retirer.discard(_SECTION_AVANT_FACULTATIFS)

    avant = dict(session.reponses)
    session.reponses = {
        **{k: v for k, v in avant.items() if k not in a_retirer},
        CLE_CORRECTION_EN_COURS: {"section": code_section, "reponses_avant": avant},
    }
    session.section_courante = code_section
    session.statut = "en_cours"
    db.commit()
    db.refresh(session)
    return get_current_section_state(db, user, project_id, document_type)


# Types de variable qu'« Appliquer » peut modifier : des saisies simples.
_TYPES_APPLICABLES = ("montant", "nombre", "date", "texte")


def appliquer_correction(
    db: Session, user: User, project_id, document_type: str, code_section: str, variable: str, valeur: str
) -> None:
    """« Appliquer » sur la vérification finale (25/09/2026) : enregistre une
    valeur proposée (ex. somme déposée calculée) directement dans la section
    concernée, sans la rouvrir. Mêmes garde-fous qu'une saisie : section
    répondue par l'utilisateur, variable saisissable de sa clause, règles
    de validité (niveau A) respectées. La vérification est relancée ensuite
    par le frontend."""
    from backend.entrepreneur.services.statuts_sas_regles_validite import GRAVITE_BLOQUANT, verifier_regles
    from backend.shared.knowledge_base.services.clause_validity_criteria_service import list_for_clause

    session = get_or_create_session(db, user, project_id, document_type)
    if session.document_genere_id is not None:
        raise SessionAlreadyCompleteError("Un document a déjà été généré : recommencez pour le modifier.")
    if session.statut != "complete":
        raise InvalidAnswerError("La correction ne peut être appliquée qu'une fois le parcours terminé.")
    reponse = session.reponses.get(code_section)
    if (
        not isinstance(reponse, dict)
        or not reponse.get("inclus")
        or any(reponse.get(m) for m in _MARQUEURS_REPONSE_CALCULEE)
    ):
        raise InvalidAnswerError("Cette section ne peut pas être corrigée ainsi.")
    clause = (
        db.query(ContractClauseLibrary)
        .filter(
            ContractClauseLibrary.document_type == document_type,
            ContractClauseLibrary.code_clause == reponse.get("code_clause"),
        )
        .first()
    )
    definition = next((v for v in (clause.variables_requises if clause else []) if v["nom"] == variable), None)
    if definition is None or definition.get("type") not in _TYPES_APPLICABLES:
        raise InvalidAnswerError(f"La valeur '{variable}' ne peut pas être modifiée ainsi.")

    valeurs = {**(reponse.get("valeurs") or {}), variable: valeur}
    criteres = [
        {"valeur_limite": c.valeur_limite, "base_legale": c.base_legale, "description_critere": c.description_critere}
        for c in list_for_clause(db, clause_library_id=clause.id)
    ]
    bloquants = [p for p in verifier_regles(clause.variables_requises, criteres, valeurs) if p["gravite"] == GRAVITE_BLOQUANT]
    if bloquants:
        raise InvalidAnswerError(f"« {bloquants[0]['libelle']} » : {bloquants[0]['message']}")

    _set_reponse(session, code_section, {**reponse, "valeurs": valeurs})
    db.commit()


def annuler_correction(db: Session, user: User, project_id, document_type: str) -> dict[str, Any]:
    """« Revenir à la vérification » : remet les réponses d'avant la
    correction, telles quelles, et le parcours redevient terminé."""
    session = get_or_create_session(db, user, project_id, document_type)
    correction = session.reponses.get(CLE_CORRECTION_EN_COURS)
    if correction is None:
        raise InvalidAnswerError("Aucune correction en cours.")
    session.reponses = dict(correction["reponses_avant"])
    session.section_courante = None
    session.statut = "complete"
    db.commit()
    db.refresh(session)
    return get_current_section_state(db, user, project_id, document_type)


def resolve_target_clause(
    db: Session,
    document_type: str,
    code_section: str,
    *,
    variante: str | None = None,
    sous_variante: str | None = None,
) -> ContractClauseLibrary | None:
    """Résout la clause concernée par une réponse À VENIR, AVANT tout écriture —
    utilisée par le router pour passer les bonnes `variables_requises` (et donc
    les bons critères de validité) au garde-fou LLM avant d'appeler
    submit_section(). Ne valide rien, ne modifie rien : lecture seule, séparée
    de submit_section() pour que le router puisse l'appeler indépendamment.
    Retourne None pour une section sans clause (texte_statique/donnee_projet)
    ou une variante_obligatoire facultative sans variante choisie.

    Si la clause de premier niveau résolue a elle-même des
    `sous_variantes_candidates` (cas Article 3, voir migration
    `b7e2f4a9c1d6`), la clause RÉELLEMENT appliquée est la sous-variante —
    c'est elle qui est retournée, pas la clause de premier niveau (qui ne
    sert qu'à regrouper l'affichage, voir _clause_payload).
    """
    section = (
        db.query(DocumentTemplate)
        .filter(DocumentTemplate.document_type == document_type, DocumentTemplate.code_section == code_section)
        .first()
    )
    if section is None:
        raise SectionNotFoundError(f"Section '{code_section}' absente du squelette en base.")

    if section.comportement_section in ("mention_obligatoire", "clause_optionnelle"):
        return db.query(ContractClauseLibrary).filter(ContractClauseLibrary.id == section.reference_id).first()
    if section.comportement_section == "variante_obligatoire" and variante:
        clause = (
            db.query(ContractClauseLibrary)
            .filter(ContractClauseLibrary.document_type == document_type, ContractClauseLibrary.code_clause == variante)
            .first()
        )
        if clause is not None and clause.sous_variantes_candidates and sous_variante:
            return (
                db.query(ContractClauseLibrary)
                .filter(
                    ContractClauseLibrary.document_type == document_type,
                    ContractClauseLibrary.code_clause == sous_variante,
                )
                .first()
            )
        return clause
    return None


def list_answered_sections(db: Session, user: User, project_id, document_type: str) -> list[dict]:
    """Historique des sections déjà rédigées (`inclus=True` avec une clause
    réellement appliquée) — service 1.1.15 (26/09/2026, revu suite au retour
    utilisateur sur le hover-sur-titre : il faut pouvoir redemander une
    explication sur une clause DÉJÀ validée, pas seulement celle en cours de
    saisie, sans passer par "Précédent" qui rejoue le questionnaire et efface
    les réponses suivantes).

    Lecture seule : ne touche jamais `session.reponses` ni `section_courante`.
    Une section sans `code_clause` (facultative refusée, texte_statique,
    donnee_projet, non applicable) n'a rien à expliquer, donc absente du
    résultat.

    `variante`/`sous_variante` sont précalculés ici (pas laissés au frontend
    à déduire) pour que l'appel à `explain_section` derrière chaque ligne de
    l'historique soit un simple passe-plat — voir la distinction dans
    `resolve_target_clause` : pour une `variante_obligatoire` à second niveau
    (cas Article 3), `code_clause` pointe déjà la sous-variante réellement
    appliquée, `variante` le candidat de premier niveau qui la regroupe.
    """
    session = get_or_create_session(db, user, project_id, document_type)
    sections_par_code = {s.code_section: s for s in _sections(db, document_type)}

    result: list[dict] = []
    for code_section, reponse in session.reponses.items():
        if not reponse.get("inclus") or not reponse.get("code_clause"):
            continue
        section = sections_par_code.get(code_section)
        if section is None:
            continue
        clause = (
            db.query(ContractClauseLibrary)
            .filter(
                ContractClauseLibrary.document_type == document_type,
                ContractClauseLibrary.code_clause == reponse["code_clause"],
            )
            .first()
        )
        if clause is None:
            continue
        variante = reponse.get("variante")
        result.append(
            {
                "code_section": code_section,
                "titre": clause.titre_clause,
                "ordre": section.ordre,
                "variante": variante,
                "sous_variante": reponse["code_clause"] if variante and reponse["code_clause"] != variante else None,
                "valeurs": reponse.get("valeurs", {}),
            }
        )

    result.sort(key=lambda r: r["ordre"])
    return result


# ---------------------------------------------------------------------------
# Soumission d'une réponse
# ---------------------------------------------------------------------------

def _variable_applicable(v: dict, valeurs: dict) -> bool:
    """Une variable dépendante (`depend_de_variable`/`depend_de_valeurs`, voir
    docstring de `ContractClauseLibrary`) n'est exigée que si la variable dont
    elle dépend — DANS LA MÊME CLAUSE — a déjà reçu une des valeurs listées.
    Ex. cas 58 du triage pacte de fondateurs (7.5, répartition des bénéfices) :
    la variable `seuil_pourcentage` ne s'applique que si `regle_distribution`
    vaut "pourcentage minimum", pas si elle vaut "intégralité".

    Sans dépendance déclarée, une variable est toujours applicable (comportement
    inchangé pour les 100+ autres variables qui n'ont pas ce cas de figure).
    """
    depend_de = v.get("depend_de_variable")
    if depend_de is None:
        return True
    return valeurs.get(depend_de) in v.get("depend_de_valeurs", [])




def _validate_variables(clause: ContractClauseLibrary | None, valeurs: dict, db: Session, project_id) -> None:
    # Import local -- voir la docstring de module de `statuts_sas_resolvers.py`
    # (casse la dépendance circulaire, ces exclusions restent des règles
    # propres au clausier statuts SAS malgré leur emplacement dans cette
    # fonction générique).
    from backend.entrepreneur.services.statuts_sas_resolvers import (
        _CLAUSES_ENTIEREMENT_AUTO_RESOLUES,
        _CLAUSES_REPETEES_PAR_ASSOCIE,
        _VARIABLES_MANDATAIRE,
        _candidats_selection_associe,
    )

    if clause is None:
        # Ne devrait jamais arriver : section.reference_id pointe vers une clause
        # supprimée depuis, ou le seed n'a pas encore tourné — signale une
        # incohérence de données, pas une erreur de saisie utilisateur.
        raise InvalidAnswerError("Clause de référence introuvable pour cette section (squelette incohérent).")

    variables_applicables = [v for v in clause.variables_requises if _variable_applicable(v, valeurs)]

    # AJOUT (23/09/2026, résolution complète dispense L225-8-1) : contrairement
    # aux exclusions ci-dessous qui retirent UNE variable par TYPE ou par NOM,
    # cette clause a désormais TOUTES ses variables résolues automatiquement
    # (voir `_valeurs_dispense_l225_8_1_par_associe` -- montants déterministes
    # au prorata du capital, désignation réutilisée depuis
    # `apport_nature_identite`) : plus aucune saisie manuelle attendue, donc
    # court-circuit avant le contrôle "manquant" plutôt qu'une énième
    # exclusion au cas par cas.
    if clause.code_clause in _CLAUSES_ENTIEREMENT_AUTO_RESOLUES:
        return

    # 'auto_forme_juridique' (cases 95-96, service 1.1.13) : jamais saisie par
    # l'entrepreneur, résolue automatiquement depuis la forme juridique du
    # projet au moment de l'assemblage final (voir _resoudre_variables_auto)
    # -- exclue du contrôle "manquant", sinon la validation échouerait toujours
    # puisque cette variable n'apparaît jamais dans `valeurs`.
    # 'reference_croisee' (ex. préemption/préférence) : même raisonnement que
    # 'auto_forme_juridique' -- jamais saisie ici, résolue à l'assemblage
    # (voir _resoudre_variables_reference_croisee).
    variables_a_saisir = [
        v for v in variables_applicables
        if v["type"] not in (
            "auto_forme_juridique", "auto_nom_societe", "reference_croisee",
            "auto_repartition_associes", "auto_pourcentage_associes",
            "auto_profil_juridique", "auto_siege_social", "auto_poids_participation",
            # AJOUT (23/09/2026, service 1.1.4 statuts) : voir
            # _resoudre_variables_apports_statuts -- résolution déterministe
            # (somme au prorata du capital), jamais un choix à deviner.
            "auto_montant_apports_numeraire", "auto_montant_apports_nature",
            # AJOUT (23/09/2026, service 1.1.4 statuts) : voir
            # _resoudre_variables_officiers_statuts -- identité d'un dirigeant
            # (Président/DG/membre du comité PERSONNE PHYSIQUE, art. 39/40/41)
            # résolue depuis `company_officers`. Exclusion par TYPE valide ici :
            # ces 2 types ne sont utilisés QUE par ces 3 clauses aujourd'hui,
            # contrairement à `auto_identite_associe` ci-dessous.
            "auto_nom_complet_associe", "auto_adresse_associe",
            # AJOUT (24/09/2026, service 1.1.4 statuts, correction #12) : les 8
            # variables PM de `premier_president_personne_morale` (art. 39) --
            # voir _resoudre_variables_officiers_pm_statuts. Type dédié (pas
            # une réutilisation de auto_nom_complet_associe/auto_adresse_associe,
            # qui ne concernent que l'identité d'un ASSOCIÉ personne physique) :
            # ce type n'est utilisé QUE par cette clause, exclusion par TYPE
            # valide ici, même raisonnement que ci-dessus.
            "auto_officier_pm",
            # AJOUT (24/09/2026, demande utilisateur) : `duree_fonctions_
            # premier_president` -- partagée par les 2 variantes du Président
            # (art. 39, personne physique ET morale) -- lue directement sur
            # `company_officers.duree_fonctions` (voir
            # _resoudre_variables_officiers_statuts, champ "duree_fonctions").
            # Type dédié, non réutilisé ailleurs -- exclusion par TYPE valide.
            "auto_duree_fonctions_officier",
            # AJOUT (lot 3-4, 24/09/2026) : sommes, actions, valeur nominale et
            # désignation du bien PAR APPORTEUR (Art. 6.1/6.2) -- calculées ou
            # lues sur `project_associates` par les résolveurs
            # `_valeurs_apports_*_par_associe`, jamais saisies ici.
            "auto_apport_par_associe",
            # AJOUT (lot A, 24/09/2026) : lignes de signature de la clôture,
            # construites depuis les associés et dirigeants
            # (_resoudre_signatures_associes), jamais saisies.
            "auto_signatures_associes",
            # AJOUT (règles A, 24/09/2026) : fin d'exercice calculée depuis le
            # jour + mois d'ouverture (_resoudre_exercice_social).
            "auto_fin_exercice",
        )
        # AJOUT (23/09/2026, service 1.1.4 statuts) : exclusion par NOM DE
        # VARIABLE, pas par type -- `auto_identite_associe` est PARTAGÉ par des
        # variables sans rapport (Article 6 "apports", Article 8
        # "fondateur_avantage") qui restent volontairement en saisie manuelle
        # (Cas B/C, non résolus). Exclure ce type entièrement aurait, à tort,
        # dispensé aussi ces 4 autres variables de saisie -- voir docstring de
        # _resoudre_variables_officiers_statuts.
        and v["nom"] not in _VARIABLES_MANDATAIRE
    ]

    # AJOUT (23/09/2026, service 1.1.4 statuts, Cas B/C) : les variables
    # `auto_identite_associe` restantes (Article 6 apports, Article 8
    # fondateur_avantage) ne sont exigées ici QUE si leur filtre `selection`
    # retient plusieurs candidats -- et dans ce cas, la valeur doit être
    # l'identifiant d'un des candidats proposés (`selections_requises`), pas
    # un texte libre. Un seul candidat -> résolution automatique, jamais
    # demandée (voir `_resoudre_variables_selection_associe`). Aucun candidat
    # -> reste en saisie libre normale (fallback inchangé, cas rare/incohérent
    # signalé ailleurs).
    #
    # EXCEPTION (23/09/2026, résolution Cas B -- clause `apport_nature_identite`,
    # retouche du clausier) : dans CETTE clause précise, `identite_apporteur_nature`
    # n'est JAMAIS un choix -- elle est répétée pour TOUS les apporteurs en
    # nature (voir `_render_apports_nature_statuts`), jamais un seul choisi
    # parmi eux. Exclue ici sans passer par le mécanisme choix/auto-résolution
    # ci-dessus, qui ne s'applique qu'aux clauses "un seul concerné parmi
    # plusieurs candidats" (Article 8, ou les autres variantes Article 6).
    variables_a_saisir_normales = []
    for v in variables_a_saisir:
        if clause.code_clause in _CLAUSES_REPETEES_PAR_ASSOCIE and v["type"] == "auto_identite_associe":
            continue
        if v["type"] == "auto_identite_associe" and v.get("selection"):
            candidats = _candidats_selection_associe(db, project_id, v["selection"])
            if len(candidats) == 1:
                continue
            if len(candidats) > 1:
                if valeurs.get(v["nom"]) not in {str(a.id) for a in candidats}:
                    raise InvalidAnswerError(
                        f"'{v['nom']}' doit être l'identifiant d'un des associés proposés "
                        f"(voir 'selections_requises' de la clause)."
                    )
                continue
        variables_a_saisir_normales.append(v)
    variables_a_saisir = variables_a_saisir_normales

    # AJOUT (23/09/2026, résolution Cas B ; étendu 25/09/2026 à
    # `nombre_par_associe` -- apports en industrie, art. 6.2 bis) :
    # `texte_par_associe`/`nombre_par_associe` ne sont pas UNE valeur mais un
    # DICT `{id_associe: valeur}`, un par candidat du filtre `selection` --
    # validés séparément du contrôle `missing` générique (qui suppose une
    # valeur scalaire). Aucun candidat -> rien à saisir (retiré de la liste,
    # exclu du contrôle "manquant" ci-dessous). Même validation de forme pour
    # les deux types (dict complet) ; seule la vérification "manquant" diffère
    # (`.strip()` pour du texte n'a pas de sens pour un nombre -- `None`/absent
    # suffit à qualifier "manquant" pour `nombre_par_associe`).
    variables_par_associe = [v for v in variables_a_saisir if v["type"] in ("texte_par_associe", "nombre_par_associe")]
    variables_a_saisir = [v for v in variables_a_saisir if v["type"] not in ("texte_par_associe", "nombre_par_associe")]
    for v in variables_par_associe:
        candidats = _candidats_selection_associe(db, project_id, v.get("selection", ""))
        if not candidats:
            continue
        valeur = valeurs.get(v["nom"])
        if not isinstance(valeur, dict):
            raise InvalidAnswerError(
                f"'{v['nom']}' doit être un objet {{id_associé: valeur}}, un par associé proposé."
            )
        if v["type"] == "texte_par_associe":
            manquants = [str(a.id) for a in candidats if not (valeur.get(str(a.id)) or "").strip()]
        else:
            manquants = [str(a.id) for a in candidats if valeur.get(str(a.id)) in (None, "")]
        if manquants:
            raise InvalidAnswerError(
                f"'{v['nom']}' est manquant pour {len(manquants)} associé(s) parmi ceux proposés."
            )

    missing = [v["nom"] for v in variables_a_saisir if v["nom"] not in valeurs]
    if missing:
        raise InvalidAnswerError(f"Variable(s) manquante(s) pour '{clause.titre_clause}' : {missing}")

    # 'choix' : liste fermée d'options embarquée dans la variable elle-même (ex.
    # "minoritaire"/"majoritaire") — à ne pas confondre avec 'reference_croisee',
    # résolue automatiquement depuis la variante choisie ailleurs (jamais saisie
    # ici, donc jamais validée). Une valeur hors options laisserait un texte non
    # prévu par le modèle Bpifrance dans le document final.
    for v in variables_a_saisir:
        if v["type"] == "choix" and valeurs.get(v["nom"]) not in v.get("options", []):
            raise InvalidAnswerError(
                f"Valeur invalide pour '{v['nom']}' — attendu une valeur parmi {v.get('options')}."
            )


def submit_section(
    db: Session,
    user: User,
    project_id,
    document_type: str,
    code_section: str,
    *,
    inclus: bool | None = None,
    variante: str | None = None,
    sous_variante: str | None = None,
    valeurs: dict | None = None,
    controle_juridique_en_attente: list[str] | None = None,
) -> DocumentGenerationSession:
    """`controle_juridique_en_attente` (statuts, niveau B du garde-fou) :
    champs que le garde-fou LLM n'a pas pu vérifier (service indisponible).
    La saisie n'est pas bloquée ; les champs sont notés dans la réponse pour
    être revérifiés par la validation globale avant génération."""
    session = get_or_create_session(db, user, project_id, document_type)
    if session.statut == "complete":
        raise SessionAlreadyCompleteError("Cette session est déjà terminée — un document a déjà été généré.")
    if session.section_courante != code_section:
        raise InvalidAnswerError(
            f"Section attendue : '{session.section_courante}', reçue : '{code_section}'."
        )

    section = (
        db.query(DocumentTemplate)
        .filter(DocumentTemplate.document_type == document_type, DocumentTemplate.code_section == code_section)
        .first()
    )
    if section is None:
        raise SectionNotFoundError(f"Section '{code_section}' absente du squelette en base.")

    valeurs = valeurs or {}
    reponse: dict[str, Any]

    if section.comportement_section == "mention_obligatoire":
        clause = db.query(ContractClauseLibrary).filter(ContractClauseLibrary.id == section.reference_id).first()
        _validate_variables(clause, valeurs, db, project_id)
        reponse = {"inclus": True, "code_clause": clause.code_clause, "valeurs": valeurs}

    elif section.comportement_section == "clause_optionnelle":
        if inclus is None:
            raise InvalidAnswerError("'inclus' est requis pour une section facultative.")
        if not inclus:
            reponse = {"inclus": False}
        else:
            # Correction #9 (audit du 23/09/2026, VERSION FINALE 24/09/2026,
            # décision utilisateur) : `comite_direction_voix_preponderante`
            # (Art. 24) référence dynamiquement `limitation_pouvoirs_president`
            # (Art. 22 -- reference_croisee `reference_article_limitation_
            # pouvoirs`, voir le clausier). Deux solutions écartées : bloquer
            # avec une erreur (mauvaise UX), rouvrir automatiquement le
            # parcours sur l'Art. 22 en effaçant les réponses déjà données
            # (rejeté par l'utilisateur -- perte de réponses). Retenue : cette
            # section n'est désormais même plus PROPOSÉE tant qu'Art. 22 n'est
            # pas inclus -- gérée en amont par SECTIONS_DERIVEES (auto-skip
            # silencieux, comme n'importe quelle autre section non
            # applicable), voir son commentaire dédié. Ce qui suit est donc un
            # garde-fou défensif, pas un flux utilisateur normal : `_applicable`
            # empêche déjà cette section de devenir `section_courante` sans
            # Art. 22 inclus, donc ce cas ne devrait jamais se produire via le
            # parcours standard (seulement en cas d'appel API direct/incohérent).
            if code_section == "comite_direction_voix_preponderante":
                dep = (session.reponses or {}).get("limitation_pouvoirs_president")
                if not dep or not dep.get("inclus"):
                    raise InvalidAnswerError(
                        "Incohérence : 'Comité de direction — voix prépondérante' "
                        "(Article 24) ne peut être incluse sans que 'Limitation de "
                        "pouvoirs du Président' (Article 22) le soit déjà — cette "
                        "section n'aurait pas dû être proposée sans cela."
                    )
            clause = db.query(ContractClauseLibrary).filter(ContractClauseLibrary.id == section.reference_id).first()
            _validate_variables(clause, valeurs, db, project_id)
            reponse = {"inclus": True, "code_clause": clause.code_clause, "valeurs": valeurs}

    elif section.comportement_section == "variante_obligatoire":
        if variante is None:
            if section.obligatoire:
                raise InvalidAnswerError(f"Une variante est requise pour la section '{code_section}'.")
            reponse = {"inclus": False}
        else:
            candidates = section.variantes_candidates or []
            if variante not in candidates:
                raise InvalidAnswerError(f"Variante '{variante}' inconnue pour '{code_section}' (attendu: {candidates}).")
            clause = (
                db.query(ContractClauseLibrary)
                .filter(ContractClauseLibrary.document_type == document_type, ContractClauseLibrary.code_clause == variante)
                .first()
            )
            if clause is not None and clause.sous_variantes_candidates:
                # Cas Article 3 (voir migration b7e2f4a9c1d6) : la clause de
                # premier niveau ne sert qu'à regrouper l'affichage — la
                # clause RÉELLEMENT appliquée est la sous-variante choisie.
                sous_candidats = clause.sous_variantes_candidates
                if sous_variante not in sous_candidats:
                    raise InvalidAnswerError(
                        f"Sous-variante requise pour '{variante}' (attendu: {sous_candidats})."
                    )
                clause = (
                    db.query(ContractClauseLibrary)
                    .filter(
                        ContractClauseLibrary.document_type == document_type,
                        ContractClauseLibrary.code_clause == sous_variante,
                    )
                    .first()
                )
            _validate_variables(clause, valeurs, db, project_id)
            # `variante` (en plus de `code_clause`) : conservé séparément pour que
            # `_resoudre_variables_reference_croisee` puisse retrouver le choix de
            # premier niveau même quand `code_clause` finit par pointer vers une
            # sous-variante (Hyp3/Hyp7) -- voir docstring de cette fonction.
            reponse = {"inclus": True, "code_clause": clause.code_clause, "variante": variante, "valeurs": valeurs}

    else:
        # texte_statique/donnee_projet ne devraient jamais arriver ici : traitées
        # automatiquement par _advance_to_next_section avant de devenir "courante".
        raise InvalidAnswerError(f"La section '{code_section}' ({section.comportement_section}) ne prend pas de réponse.")

    if controle_juridique_en_attente and reponse.get("inclus"):
        reponse["controle_juridique_en_attente"] = controle_juridique_en_attente
    _set_reponse(session, section.code_section, reponse)

    _advance_to_next_section(db, session)
    db.commit()
    db.refresh(session)
    return session


def submit_facultatifs(
    db: Session, user: User, project_id, document_type: str, codes_choisis: list[str]
) -> DocumentGenerationSession:
    """POST .../facultatifs (audit #19) -- enregistre le choix des articles
    facultatifs fait sur l'écran de pause, puis reprend le parcours.

    Les articles non cochés ne sont pas écrits ici un par un : c'est
    `_advance_to_next_section` qui écarte chacune de leurs sections en la
    croisant (`reponse_facultatif_non_choisi`) -- une seule règle, appliquée
    aussi après un retour en arrière."""
    from backend.entrepreneur.services.statuts_sas_resolvers import (
        CLE_FACULTATIFS_CHOISIS,
        SECTION_PAUSE_FACULTATIFS,
        _SECTION_AVANT_FACULTATIFS,
        valider_choix_facultatifs,
    )

    if document_type != DOCUMENT_TYPE_STATUTS:
        raise InvalidAnswerError("Le choix des articles facultatifs n'existe que pour les statuts.")
    session = get_or_create_session(db, user, project_id, document_type)
    if session.statut == "complete":
        raise SessionAlreadyCompleteError("Cette session est déjà terminée — un document a déjà été généré.")
    if session.section_courante != SECTION_PAUSE_FACULTATIFS:
        raise InvalidAnswerError(
            f"Le choix des articles facultatifs n'est pas attendu maintenant (section courante : "
            f"'{session.section_courante}')."
        )
    try:
        choisis = valider_choix_facultatifs(codes_choisis)
    except ValueError as exc:
        raise InvalidAnswerError(str(exc)) from exc

    _set_reponse(session, CLE_FACULTATIFS_CHOISIS, choisis)
    # Lève la pause : le titre de l'Art. 8 est un texte statique, marqué traité
    # comme `_advance_to_next_section` l'aurait fait sans la pause.
    _set_reponse(session, _SECTION_AVANT_FACULTATIFS, {"traite_automatiquement": True})
    _advance_to_next_section(db, session)
    db.commit()
    db.refresh(session)
    return session


def retirer_facultatif_courant(db: Session, user: User, project_id, document_type: str) -> DocumentGenerationSession:
    """POST .../facultatifs/retirer (audit #19) -- bouton "Ne plus inclure cet
    article" : retire l'article de la section courante du choix, écarte cette
    section, et `_advance_to_next_section` écarte les suivantes du même article.

    Limite assumée : des clauses PLACÉES AVANT cet article et qui y renvoient
    (ex. clauses de l'Art. 16 liées à l'agrément de l'Art. 17) ont déjà été
    répondues et ne sont pas retirées -- cas rare, voir l'audit."""
    from backend.entrepreneur.services.statuts_sas_resolvers import (
        CLE_FACULTATIFS_CHOISIS,
        _facultatifs_choisis,
        articles_par_section,
        code_facultatif_de_l_article,
    )

    if document_type != DOCUMENT_TYPE_STATUTS:
        raise InvalidAnswerError("Le retrait d'un article facultatif n'existe que pour les statuts.")
    session = get_or_create_session(db, user, project_id, document_type)
    if session.statut == "complete":
        raise SessionAlreadyCompleteError("Cette session est déjà terminée — un document a déjà été généré.")
    choix = _facultatifs_choisis(session.reponses)
    article = articles_par_section(_sections(db, document_type)).get(session.section_courante or "")
    code = code_facultatif_de_l_article(article)
    if choix is None or code is None or code not in choix:
        raise InvalidAnswerError("La section courante n'appartient pas à un article facultatif choisi.")

    _set_reponse(session, CLE_FACULTATIFS_CHOISIS, [c for c in session.reponses[CLE_FACULTATIFS_CHOISIS] if c != code])
    _set_reponse(session, session.section_courante, {"inclus": False, "retire_par_utilisateur": True})
    _advance_to_next_section(db, session)
    db.commit()
    db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Finalisation — assemblage du document final
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Version v2 (document_type="pacte_fondateurs_v2") de l'identification des
# parties -- voir decisions_articles.json, article "entete",
# cible="donnee_projet_dynamique". Contrairement à la v1 (une ligne générique
# par associé), distingue le patron personne physique / personne morale par
# associé, et sépare Associés Fondateurs / Associés Investisseurs comme le
# fait le vrai modèle Bpifrance. Ajoutée à côté de la fonction v1 plutôt qu'à
# sa place : le moteur reste générique et partagé entre v1/v2 (voir décision
# actée avec l'utilisateur, 21/09/2026), seule cette section a un rendu
# suffisamment différent entre les deux versions pour justifier une branche.
# ---------------------------------------------------------------------------


def _render_patron_associe_v2(a: ProjectAssociate) -> list[dict]:
    """Rend le patron d'identification d'UN associé (personne physique ou
    morale) en "runs" -- voir docstring de `_assemble_document_blocks` pour le
    pourquoi. "(prénom) (nom)" et "(représentant prénom) (représentant nom)"
    restent traités comme un seul run chacun (`project_associates` ne sépare
    pas prénom/nom pour l'associé lui-même, seulement pour son représentant
    le cas échéant -- voir docstring du modèle).

    Champ manquant -> placeholder textuel explicite ("(champ non renseigné)"),
    jamais une chaîne vide silencieuse -- même convention que
    `_resoudre_variables_auto`. Marqué `valeur_utilisateur=True` quand même :
    c'est la valeur réellement injectée dans le document, son caractère
    "manquant" est visible dans le texte du placeholder lui-même.
    """
    if a.type_personne == "personne_morale":
        representant = (
            f"{a.representant_prenom} {a.representant_nom}"
            if a.representant_prenom and a.representant_nom
            else "(représentant non renseigné)"
        )
        return [
            _val(a.denomination_sociale or "(dénomination sociale non renseignée)", "denomination_sociale"),
            _lit(", "),
            _val(a.type_societe or "(type de société non renseigné)", "type_societe"),
            _lit(" au capital de "),
            _val(
                str(a.capital_social) if a.capital_social is not None else "(capital social non renseigné)",
                "capital_social",
            ),
            _lit(" €, ayant son siège social à "),
            _val(a.siege_social or "(siège social non renseigné)", "siege_social"),
            _lit(", immatriculée au Registre du commerce et des sociétés de "),
            _val(a.lieu_immatriculation or "(lieu d'immatriculation non renseigné)", "lieu_immatriculation"),
            _lit(" sous le numéro "),
            _val(a.numero_siren or "(numéro Siren non renseigné)", "numero_siren"),
            _lit(", représentée par "),
            _val(representant, "representant"),
            _lit(", en sa qualité de "),
            _val(a.representant_qualite or "(qualité du représentant non renseignée)", "representant_qualite"),
        ]
    return [
        _val(a.nom_complet or "(nom non renseigné)", "nom_complet"),
        _lit(", né(e) le "),
        _val(
            a.date_naissance.strftime("%d/%m/%Y") if a.date_naissance else "(date de naissance non renseignée)",
            "date_naissance",
        ),
        _lit(", demeurant à "),
        _val(a.adresse or "(adresse non renseignée)", "adresse"),
    ]


def _joindre_runs(groupes: list[list[dict]], separateur: str) -> list[dict]:
    """Intercale `separateur` (run littéral) entre chaque groupe de runs --
    équivalent runs de `" et/ou\\n".join(...)`."""
    runs: list[dict] = []
    for i, groupe in enumerate(groupes):
        if i > 0:
            runs.append(_lit(separateur))
        runs.extend(groupe)
    return runs


def _render_identification_parties_v2(db: Session, project_id) -> list[dict]:
    associates = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == project_id, ProjectAssociate.est_partie_au_pacte_fondateurs.is_(True))
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    if not associates:
        raise InvalidAnswerError(
            "Aucun associé n'est marqué comme partie au pacte de fondateurs (project_associates."
            "est_partie_au_pacte_fondateurs) — impossible de générer la section des parties."
        )

    fondateurs = [a for a in associates if a.est_fondateur]
    investisseurs = [a for a in associates if not a.est_fondateur]

    bloc_fondateurs = (
        _joindre_runs([_render_patron_associe_v2(a) for a in fondateurs], " et/ou\n")
        if fondateurs
        else [_lit("(aucun associé fondateur)")]
    )

    runs: list[dict] = [_lit("Entre les soussignés,\n\n"), *bloc_fondateurs, _lit("\nci-après dénommés les « Associés Fondateurs »,\n")]

    if investisseurs:
        bloc_investisseurs = _joindre_runs([_render_patron_associe_v2(a) for a in investisseurs], " et/ou\n")
        runs.append(_lit("d'une part,\n\n"))
        runs.extend(bloc_investisseurs)
        runs.append(
            _lit(
                "\nci-après dénommés les « Associés Investisseurs »,\nd'autre part,\n\n"
                "le(s) Associé(s) Fondateur(s) et le(s) Associé(s) Investisseur(s) étant ci-après "
                "dénommés individuellement une « Partie » et collectivement les « Parties »,"
            )
        )
    else:
        runs.append(
            _lit(
                "\nétant ci-après dénommés individuellement une « Partie » et collectivement les « Parties »,"
            )
        )
    return runs


def _numero_ordinal_liste(n: int) -> str:
    """Numérotation "1°, 2°, 3°..." du patron d'en-tête des statuts SAS (voir
    decisions_articles_statuts_sas.json, article 'entete', note : "numérotés
    1o, 2o, ..."). Le "o" du texte de la décision est l'abréviation française
    de l'ordinal ; rendu ici par le caractère degré "°" plutôt que la lettre
    "o", ambiguë avec un zéro dans un rendu PDF."""
    return f"{n}°"


def _render_patron_associe_statuts(a: ProjectAssociate) -> list[dict]:
    """Rend le patron d'identification d'UN associé fondateur pour l'en-tête
    des statuts SAS -- distinct du patron pacte (`_render_patron_associe_v2`,
    voir sa docstring pour le principe général des "runs") : voir
    decisions_articles_statuts_sas.json, article 'entete',
    patron_personne_physique/patron_personne_morale (22/09/2026).

    Différences avec le patron pacte :
    - personne physique : ajoute lieu de naissance + situation et régime
      matrimonial (`project_associates.lieu_naissance`/
      `situation_et_regime_matrimonial`, colonnes propres aux statuts, absentes
      du patron pacte qui n'en a pas besoin).
    - personne morale : vocabulaire du modèle Bpifrance statuts ("forme",
      "n° [SIREN]", "es qualités de", "dûment habilité aux fins des présentes")
      différent de celui du pacte, mêmes champs source
      (`type_societe`/`lieu_immatriculation`/`numero_siren`/`representant_*`).

    Même convention que le pacte pour un champ manquant : placeholder textuel
    explicite ("(champ non renseigné)"), jamais un vide silencieux.
    """
    if a.type_personne == "personne_morale":
        representant = (
            f"{a.representant_prenom} {a.representant_nom}"
            if a.representant_prenom and a.representant_nom
            else "(représentant non renseigné)"
        )
        return [
            _val(a.denomination_sociale or "(dénomination sociale non renseignée)", "denomination_sociale"),
            _lit(", "),
            _val(a.type_societe or "(forme non renseignée)", "type_societe"),
            _lit(" au capital de "),
            _val(
                formater_montant(a.capital_social) if a.capital_social is not None else "(capital non renseigné)",
                "capital_social",
            ),
            _lit(" euros, ayant son siège social à "),
            _val(a.siege_social or "(siège social non renseigné)", "siege_social"),
            _lit(", immatriculée au Registre du commerce et des sociétés de "),
            _val(a.lieu_immatriculation or "(lieu d'immatriculation non renseigné)", "lieu_immatriculation"),
            _lit(" sous le n° "),
            _val(a.numero_siren or "(numéro Siren non renseigné)", "numero_siren"),
            _lit(" représentée par "),
            _val(representant, "representant_legal"),
            _lit(", es qualités de "),
            _val(a.representant_qualite or "(fonction non renseignée)", "fonction"),
            _lit(", dûment habilité aux fins des présentes"),
        ]
    return [
        _val(a.nom_complet or "(nom non renseigné)", "nom_complet"),
        _lit(", demeurant à "),
        _val(a.adresse or "(adresse non renseignée)", "adresse"),
        _lit(", né(e) le "),
        _val(
            a.date_naissance.strftime("%d/%m/%Y") if a.date_naissance else "(date de naissance non renseignée)",
            "date_naissance",
        ),
        _lit(" à "),
        _val(a.lieu_naissance or "(lieu de naissance non renseigné)", "lieu_naissance"),
        _lit(", "),
        _val(
            a.situation_et_regime_matrimonial or "(situation et régime matrimonial non renseignés)",
            "situation_et_regime_matrimonial",
        ),
    ]


def _render_identification_parties_statuts(db: Session, project_id) -> list[dict]:
    """Rend la page de garde + le bloc "Les soussignés" des statuts SAS --
    équivalent statuts de `_render_identification_parties_v2` (pacte). Voir
    decisions_articles_statuts_sas.json, article 'entete' (cible
    "donnee_projet_dynamique" -- jamais une clause ordinaire, voir sa note).

    AVANT cette fonction (23/09/2026) : `_assemble_document_blocks` appelait
    `_render_identification_parties_v2` (pacte) SANS condition sur
    `document_type` -- comme le générateur (`generate_statuts_sas_v2.py`,
    comme celui du pacte) n'émet volontairement AUCUNE section pour l'entête
    (`cible="donnee_projet_dynamique"` -- l'injection se fait en constante côté
    `seed_statuts_sas.py`, voir `_SECTION_IDENTIFICATION_PARTIES`), cette
    branche n'était simplement jamais atteinte pour un statuts : le document
    généré aurait commencé directement à l'Article 1, sans page de garde ni
    identification des fondateurs. Trou trouvé et corrigé ici.

    Différences avec le pacte, actées le 22/09/2026 :
    - Seuls les Associés FONDATEURS (`est_fondateur=True`) apparaissent -- les
      statuts constitutifs n'ont pas la notion d'Associés Investisseurs du
      pacte (elle n'existe qu'après signature d'un pacte séparé, postérieur).
    - Numérotation "1°, 2°, ..." (physiques, puis moraux à la suite), les
      associés d'un même groupe sont séparés par des virgules (modèle
      Bpifrance) -- "Et/Ou" ne sépare QUE le groupe physique du groupe moral,
      pas les associés entre eux (voir texte_assemblage de la décision).
    - Page de garde (dénomination, forme, capital, siège, "société en cours de
      constitution") avant "Les soussignés" -- absente du pacte, qui s'adresse
      à une société déjà immatriculée.
    """
    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project_id).first()
    )
    fondateurs = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == project_id, ProjectAssociate.est_fondateur.is_(True))
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    if not fondateurs:
        raise InvalidAnswerError(
            "Aucun associé n'est marqué comme fondateur (project_associates.est_fondateur) "
            "— impossible de générer l'identification des parties des statuts."
        )

    physiques = [a for a in fondateurs if a.type_personne != "personne_morale"]
    morales = [a for a in fondateurs if a.type_personne == "personne_morale"]

    def _bloc_numerote(associes: list[ProjectAssociate], depart: int) -> list[dict]:
        runs: list[dict] = []
        for i, a in enumerate(associes):
            if i > 0:
                runs.append(_lit(",\n"))
            runs.append(_lit(f"{_numero_ordinal_liste(depart + i)} "))
            runs.extend(_render_patron_associe_statuts(a))
        return runs

    runs: list[dict] = [
        _val(
            legal_profile.legal_name if legal_profile and legal_profile.legal_name else "(dénomination sociale non renseignée)",
            "denomination_sociale",
        ),
        _lit(",\nsociété par actions simplifiée\nau capital de "),
        _val(
            formater_montant(legal_profile.capital_social) if legal_profile and legal_profile.capital_social is not None else "(capital non renseigné)",
            "capital_social",
        ),
        _lit(" euros,\nSiège social : "),
        _val(
            _formater_siege_social(legal_profile.registered_address if legal_profile else None)
            or "(siège social non renseigné)",
            "siege_social",
        ),
        _lit("\nSociété en cours de constitution\n\nLes soussignés,\n\n"),
    ]
    runs.extend(_bloc_numerote(physiques, 1))
    if morales:
        if physiques:
            # Lot B : « Et/Ou » était une consigne du modèle (choisir le
            # patron PP ou PM), jamais un texte à imprimer.
            runs.append(_lit("\n"))
        runs.extend(_bloc_numerote(morales, len(physiques) + 1))
    runs.append(
        _lit(
            "\n\nOnt établi ainsi qu'il suit :\nles statuts de la société par actions simplifiée devant exister "
            "entre eux et toute autre personne qui viendrait ultérieurement à acquérir la qualité d'associé "
            "(la « Société »)."
        )
    )
    return runs






def _resoudre_variables_auto(variables: list[dict], legal_profile) -> dict:
    """Résout tous les types `auto_*` qui se lisent directement (ou après
    formatage simple) depuis `ProjectLegalProfile` du projet -- jamais posées
    à l'entrepreneur, résolues au moment d'assembler le document final.

    Reçoit l'objet `ProjectLegalProfile` complet (`None` si le projet n'en a
    pas encore) plutôt qu'un paramètre scalaire par champ : cette fonction
    gérait déjà `forme_juridique`/`nom_societe` en paramètres séparés, et
    l'inventaire des variables du Préambule (21/09/2026, service 1.1.13) en a
    ajouté 6 d'un coup -- une signature qui grossirait d'un paramètre à
    chaque nouveau champ ne passe pas à l'échelle. Chaque branche ci-dessous
    reste responsable de son propre champ/formatage, seule la façon d'accéder
    à la donnée source change.

    Types gérés :
    - `auto_forme_juridique` (cases 95-96, ex. Mandataire, Préambule
      "type de société") : `valeurs_par_forme_juridique` (dict sur la
      variable) associe la forme juridique exacte du projet à la formulation
      attendue -- plusieurs formes peuvent partager la même entrée.
    - `auto_nom_societe` (ex. Article 9.2 non-concurrence, Préambule
      "dénomination sociale") : passage direct de `legal_name`.
    - `auto_profil_juridique` (Préambule -- capital, lieu d'immatriculation,
      numéro Siren, activités, nombre d'actions, valeur nominale) : passage
      direct d'UN champ scalaire de `ProjectLegalProfile`, nommé par `champ`
      sur la variable (ex. `{"champ": "capital_social"}`) -- un seul type
      générique plutôt qu'un type dédié par champ, ces 6 variables n'ayant
      besoin d'aucun formatage ni table de correspondance.
    - `auto_siege_social` (Préambule) : `registered_address` (JSONB) formaté
      en une chaîne via `_formater_siege_social` -- seul cas qui a besoin
      d'un vrai formatage plutôt qu'un passage direct, garde son propre type.

    Dans tous les cas, si la donnée source du projet est absente/non
    renseignée, un placeholder textuel explicite est renvoyé
    (`f"({libelle} non renseigné)"`, même convention que
    `_render_patron_associe_v2`/`_render_patron_associe_statuts`) plutôt
    qu'un vide silencieux -- signal visible d'un problème de données, pas une
    erreur bloquante à ce stade de l'assemblage.

    CORRECTIF (23/09/2026) : avant, une donnée manquante laissait simplement
    la clé absente de `resolues` -- ce qui ne produisait un placeholder
    visible dans le document final que PAR ACCIDENT, quand le mécanisme de
    substitution ne trouvait de toute façon aucun `(...)` correspondant dans
    le texte (c'était le cas pour la quasi-totalité des variables statuts
    avant le correctif du bug de substitution nom/libelle -- voir
    `document_renderer_base.py`). Une fois la substitution corrigée, une clé
    absente produisait un texte vide invisible (`.get(nom, "")`) au lieu d'un
    signal -- exposé sur `activites_societe`/`duree` (type
    `auto_profil_juridique`, lisant `project_legal_profiles.objet_social`/
    `duree_societe`, colonnes qu'aucun écran de l'app ne remplit à ce jour,
    voir dette technique du récap 1.1.4). Corrigé ici en renvoyant toujours
    une valeur -- réelle ou un placeholder explicite -- jamais une absence.
    """
    resolues = {}
    forme_juridique = legal_profile.legal_form if legal_profile else None
    for var in variables:
        if var["type"] == "auto_forme_juridique":
            table = var.get("valeurs_par_forme_juridique", {})
            resolues[var["nom"]] = table.get(forme_juridique, f"({var['libelle']} non renseigné)")
        elif var["type"] == "auto_nom_societe":
            resolues[var["nom"]] = (
                legal_profile.legal_name if legal_profile and legal_profile.legal_name else f"({var['libelle']} non renseigné)"
            )
        elif var["type"] == "auto_profil_juridique":
            champ = var.get("champ")
            valeur = getattr(legal_profile, champ, None) if legal_profile and champ else None
            if valeur is None:
                resolues[var["nom"]] = f"({var['libelle']} non renseigné)"
            elif isinstance(valeur, date):
                # Lot 4 (24/09/2026) : date de signature des statuts -- format
                # français dans le document, jamais l'ISO "2026-10-01".
                resolues[var["nom"]] = valeur.strftime("%d/%m/%Y")
            elif isinstance(valeur, (Decimal, int)) and not isinstance(valeur, bool):
                # Capital, valeur nominale, nombre d'actions : « 20 000 », pas
                # « 20000.00 » (24/09/2026).
                resolues[var["nom"]] = formater_montant(valeur)
            else:
                resolues[var["nom"]] = str(valeur)
        elif var["type"] == "auto_siege_social":
            adresse = legal_profile.registered_address if legal_profile else None
            formatee = _formater_siege_social(adresse)
            resolues[var["nom"]] = formatee if formatee else f"({var['libelle']} non renseigné)"
    return resolues


def _resoudre_variables_associes(db: Session, variables: list[dict], project_id) -> dict:
    """Résout les variables `type='auto_repartition_associes'` et
    `type='auto_pourcentage_associes'` (Préambule, cases 2/3/13 du triage,
    corrigées le 21/09/2026 -- ces 3 cases étaient à tort modélisées comme
    saisies manuelles, alors que le triage du 20/09 les avait déjà classées
    SELECTION_ASSOCIES / AUTO_PROJET). Même principe que
    `_render_identification_parties_v2` (l'entrepreneur a déjà choisi, à l'étape
    "Équipe & capital", quels associés sont parties au pacte --
    `est_partie_au_pacte_fondateurs=true` -- rien à resaisir ici) mais résolu
    comme variable de clause plutôt que comme section "donnee_projet" entière :
    contrairement à l'entête, ici la donnée dynamique n'est que 1-2 lignes au
    milieu d'un préambule autrement statique, pas la totalité de la section.

    `auto_repartition_associes` (variable porte `groupe`: "fondateurs" ou
    "investisseurs") -- construit "Nom : X %" par associé du groupe, une
    ligne par associé, séparées par un retour à la ligne.
    `auto_pourcentage_associes` (variable porte `groupe`) -- somme des
    `pourcentage_capital` du groupe, formatée en nombre (ex. "100" ou "100.0"
    selon les valeurs réelles -- pas de règle d'arrondi imposée ici, les
    pourcentages saisis en amont sont réputés déjà corrects).

    Si aucun associé du groupe n'est trouvé, le placeholder reste tel quel
    (même choix que le reste du fichier -- signal visible plutôt que vide
    silencieux) plutôt que de lever une erreur bloquante comme
    `_render_identification_parties_v2` : contrairement à l'entête (où l'absence
    de Partie rend le pacte vide de sens), un préambule "sans Investisseurs"
    est un cas normal et déjà prévu par ailleurs (`preambule_sans_investisseurs`).
    """
    resolues: dict[str, str] = {}
    a_poids_participation = any(v["type"] == "auto_poids_participation" for v in variables)
    groupes_necessaires = {v["groupe"] for v in variables if v["type"] in ("auto_repartition_associes", "auto_pourcentage_associes")}
    if not groupes_necessaires and not a_poids_participation:
        return resolues

    associes_par_groupe: dict[str, list] = {"fondateurs": [], "investisseurs": []}
    associes = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == project_id, ProjectAssociate.est_partie_au_pacte_fondateurs.is_(True))
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    for a in associes:
        associes_par_groupe["fondateurs" if a.est_fondateur else "investisseurs"].append(a)

    for var in variables:
        groupe = var.get("groupe")
        membres = associes_par_groupe.get(groupe, [])
        if var["type"] == "auto_repartition_associes":
            if membres:
                resolues[var["nom"]] = "\n".join(f"{a.nom_complet} : {a.pourcentage_capital} %" for a in membres)
        elif var["type"] == "auto_pourcentage_associes":
            if membres:
                resolues[var["nom"]] = str(sum(a.pourcentage_capital for a in membres))

    if a_poids_participation:
        # Préambule ("la prise de participation (minoritaire/majoritaire) des
        # Associés Investisseurs") : décrit le poids des INVESTISSEURS dans le
        # capital, pas celui des Fondateurs -- calculé depuis leur pourcentage
        # cumulé plutôt que redemandé à l'entrepreneur (déjà une donnée
        # dérivée de `pourcentage_capital`, comme `auto_pourcentage_associes`).
        # Seuil à 50% pile : cas limite improbable en pratique (participation
        # d'investisseurs exactement à 50%) classé "majoritaire" par
        # convention (>=), pas d'ambiguïté cachée -- pas de note légale
        # attachée, ce n'est qu'une qualification descriptive du préambule.
        pourcentage_investisseurs = sum(a.pourcentage_capital for a in associes_par_groupe.get("investisseurs", []))
        poids = "majoritaire" if pourcentage_investisseurs >= 50 else "minoritaire"
        for var in variables:
            if var["type"] == "auto_poids_participation":
                resolues[var["nom"]] = poids

    return resolues


def _resoudre_variables_reference_croisee(variables: list[dict], reponses: dict) -> dict:
    """Résout les variables `type='reference_croisee'` (ex. "préemption/préférence"
    réutilisé dans cessions_libres, sortie_conjointe_totale_drag_along,
    sortie_conjointe_proportionnelle, sortie_forcee_reciproque -- le mot choisi à
    la section `preemption_preference` doit être repris tel quel dans ces 4
    clauses). AVANT cette fonction, ce type n'avait AUCUNE résolution codée nulle
    part -- seul un commentaire en décrivait l'intention (voir _validate_variables)
    -- un document généré aujourd'hui garderait le placeholder brut
    "(préemption/préférence)" dans le texte final. Trou trouvé et corrigé ici
    (service 1.1.13, 20/09/2026).

    `depend_de_section` (sur la variable) : le `code_section` de la section
    `variante_obligatoire` où le choix source a été fait. `valeurs_par_clause`
    (dict sur la variable) : associe le code de la variante CHOISIE À CE
    NIVEAU LÀ (pas la sous-variante -- voir ci-dessous) au mot à réinjecter.

    Pourquoi le code de la variante de premier niveau et pas la sous-variante :
    `submit_section` stocke `code_clause` = la clause RÉELLEMENT appliquée
    (donc une sous-variante type `..._totalite`/`..._partiel` quand il y en a
    -- voir Hyp3/Hyp7), mais stocke aussi `variante` = le code de premier
    niveau choisi (ajouté ci-dessous). En indexant `valeurs_par_clause` sur ce
    dernier, la table reste stable même si de nouvelles sous-variantes
    apparaissent plus tard (Hyp1/Hyp2) -- pas besoin de lister chaque
    sous-variante une par une.

    Si la section source n'a pas encore de réponse, ou si son code n'est pas
    dans la table, le placeholder reste tel quel (même choix que
    `_resoudre_variables_auto` : signal visible plutôt que vide silencieux).
    """
    resolues = {}
    for var in variables:
        if var["type"] != "reference_croisee":
            continue
        depend_de_section = var.get("depend_de_section")
        if depend_de_section is None:
            continue
        source_reponse = reponses.get(depend_de_section) or {}

        # Mode 2 (article 8, cas 61/62/64/65/66/69/70 du triage, 21/09/2026) :
        # `resout_depuis_variable` -- au lieu de retrouver quelle CLAUSE a été
        # choisie ailleurs (mode 1, `valeurs_par_clause`), va lire directement
        # la valeur d'une VARIABLE précise répondue dans une section qui n'est
        # PAS un `variante_obligatoire` (ex. le nom de l'organe de gouvernance,
        # choisi une seule fois via un `choix` simple en 8.2, réutilisé tel
        # quel en 8.3). Les 2 modes coexistent sur le même type `reference_croisee`
        # plutôt que d'en créer un nouveau -- seule la résolution diffère, le
        # reste (validation, rendu du texte) est identique.
        resout_depuis_variable = var.get("resout_depuis_variable")
        if resout_depuis_variable is not None:
            valeurs_source = source_reponse.get("valeurs") or {}
            if resout_depuis_variable in valeurs_source:
                resolues[var["nom"]] = valeurs_source[resout_depuis_variable]
            continue

        # Mode 1 (préexistant) : choix entre plusieurs clauses candidates
        # d'une section `variante_obligatoire` (ex. préemption/préférence).
        source_code = source_reponse.get("variante") or source_reponse.get("code_clause")
        table = var.get("valeurs_par_clause", {})
        if source_code in table:
            resolues[var["nom"]] = table[source_code]
        elif "valeur_par_defaut" in var:
            # Lot A (24/09/2026) : section source non applicable ou non
            # choisie (ex. Art. 7 « libérées » sans apport en numéraire) --
            # valeur de repli déclarée dans le clausier plutôt qu'un vide.
            resolues[var["nom"]] = var["valeur_par_defaut"]
    return resolues


def _placeholder_block(db: Session, section: DocumentTemplate) -> dict:
    """Bloc affiché pour `session.section_courante` -- la seule section dont
    l'applicabilité est certaine mais la saisie pas encore faite (état 2 du
    modèle à 3 états, voir docstring de `_assemble_document_blocks`). Même
    résolution de titre/explication que `get_current_section_state` (une seule
    clause -> son titre/description ; plusieurs candidats ou pas de clause ->
    `document_templates.titre_affiche`/`explication`)."""
    titre = section.titre_affiche
    explication = section.explication
    if section.comportement_section in ("mention_obligatoire", "clause_optionnelle"):
        clause = db.query(ContractClauseLibrary).filter(ContractClauseLibrary.id == section.reference_id).first()
        if clause is not None:
            titre = clause.titre_clause
            explication = clause.description_clause
    return {
        "code_section": section.code_section,
        "code_clause": None,
        "type": "placeholder",
        "titre": titre,
        "explication": explication,
        "runs": [],
    }


def _assemble_document_blocks(
    db: Session, session: DocumentGenerationSession, corrections_texte: list[dict] | None = None
) -> list[dict]:
    """Assemble le document en blocs typés -- remplace `_assemble_document_text`
    (texte plat) : chaque bloc `{code_section, code_clause, type, titre,
    explication, runs}` porte des "runs" au lieu d'une chaîne, pour que
    `render_document_as_pdf` puisse colorer en rouge toute valeur injectée et
    poser un signet PDF par article (`titre`).

    Appelable sur une session `en_cours` (pas seulement `complete`, contrairement
    à l'ancienne fonction) -- c'est ce qui permet la préview live pendant la
    rédaction (nouvelle route `.../preview`, streamée à la demande, jamais
    stockée -- décision actée avec l'utilisateur 21/09/2026).

    Modèle à 3 états pour la visibilité d'une section, validé avec l'utilisateur
    (21/09/2026, suite à un défaut relevé sur une première version "squelette
    complet dès le départ") :
    1. Connue non applicable (`reponse["applicable"] is False`) -- jamais
       affichée.
    2. Applicabilité certaine, section en cours de saisie
       (`section.code_section == session.section_courante`) -- bloc
       `placeholder` (titre + explication, sans contenu).
    3. Applicabilité pas encore résolue (section pas encore atteinte par
       `_advance_to_next_section`, ni dans `reponses` ni `section_courante`)
       -- rien du tout. Sans ce 3e état, une section conditionnée par un choix
       pas encore fait apparaîtrait comme "à venir" puis disparaîtrait
       silencieusement si le choix s'avère négatif -- confus pour l'entrepreneur.

    Exception volontaire : une `clause_optionnelle` refusée (`inclus=False`)
    disparaît aussi, mais ce n'est pas un cas caché du modèle à 3 états --
    c'est la conséquence DIRECTE de la propre réponse "non" de l'utilisateur à
    l'instant où il vient de la donner, pas un effet de bord d'une autre
    section.

    AJOUT 24/09/2026 (constaté par l'utilisateur sur un pacte généré, projet
    sans Associés Investisseurs) : les titres de chapitre ("Article 5 -
    Clauses de « sortie »...", section `titre_article_N`, texte_statique)
    étaient émis inconditionnellement, MÊME quand aucune section de cet
    article ne produit de contenu -- ex. un Article entièrement réservé aux
    Investisseurs (`necessite_investisseurs=True` sur toutes ses clauses)
    dans un pacte 100% Fondateurs, ou un article dont l'utilisateur a décliné
    toutes les clauses optionnelles. Le titre apparaissait seul, suivi
    directement du titre de l'article suivant -- ressemble à un document
    tronqué/cassé, alors que c'est un comportement légitime (rien à dire
    dans cet article POUR CE PROJET). Un titre `titre_article_N` est donc mis
    en attente (`titre_article_en_attente`) au lieu d'être ajouté tout de
    suite, et n'est réellement ajouté à `blocks` que juste avant le premier
    bloc de contenu réel qui suit (voir `_ajouter_bloc`) -- s'il n'y en a
    aucun avant le prochain titre_article_N (ou la fin du document), il est
    silencieusement abandonné, jamais affiché.
    """
    # Import local -- voir la docstring de module de `statuts_sas_resolvers.py`.
    from backend.entrepreneur.services.statuts_sas_resolvers import (
        _render_apports_industrie_statuts,
        _render_apports_nature_statuts,
        _render_apports_numeraire_statuts,
        _render_dispense_l225_8_1_statuts,
        _resoudre_references_articles,
        _resoudre_variables_apports_statuts,
        _resoudre_variables_officiers_pm_statuts,
        _resoudre_signatures_associes,
        _resoudre_variables_officiers_statuts,
        _resoudre_variables_selection_associe,
        _formater_dates_saisies,
        _formater_montants_saisis,
        _resoudre_exercice_social,
    )

    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()
    )

    blocks: list[dict] = []
    titre_article_en_attente: dict | None = None
    # Lot B : numéros affichés des articles (statuts uniquement, None sinon).
    numeros = _numeros_articles_statuts(db, session)

    def _ajouter_bloc(bloc: dict) -> None:
        nonlocal titre_article_en_attente
        if titre_article_en_attente is not None:
            blocks.append(titre_article_en_attente)
            titre_article_en_attente = None
        blocks.append(bloc)

    from backend.entrepreneur.services.statuts_sas_resolvers import SECTIONS_HORS_ARTICLE

    for section in _sections(db, session.document_type):
        reponse = session.reponses.get(section.code_section)

        # Lot C (24/09/2026) : une section hors article (clôture des statuts)
        # ferme l'article précédent -- un titre d'article resté en attente
        # (ex. Art. 44 non coché, sans contenu) ne doit pas être imprimé
        # au-dessus d'elle.
        if session.document_type == DOCUMENT_TYPE_STATUTS and section.code_section in SECTIONS_HORS_ARTICLE:
            titre_article_en_attente = None

        if reponse is None:
            if section.code_section != session.section_courante:
                continue
            _ajouter_bloc(_placeholder_block(db, section))
            continue

        if not reponse.get("applicable", True):
            continue

        # AJOUT (23/09/2026, service 1.1.4 statuts, Cas B résolu) -- section
        # 6.1 "Apports en numéraire" : reste `variante_obligatoire` normale au
        # niveau du squelette (la politique de libération est une réponse
        # UNIQUE), mais son RENDU est spécial-casé ici pour produire un
        # paragraphe par apporteur en numéraire plutôt qu'un seul -- voir
        # `_render_apports_numeraire_statuts` pour le détail et les limites
        # assumées.
        if section.code_section == "apports_numeraire_liberation":
            runs = _render_apports_numeraire_statuts(db, session)
            if runs:
                _ajouter_bloc(
                    {
                        "code_section": section.code_section,
                        "code_clause": reponse.get("code_clause"),
                        "type": "content",
                        "titre": section.titre_affiche,
                        "explication": None,
                        "runs": runs,
                    }
                )
            continue

        # AJOUT (23/09/2026, service 1.1.4 statuts, Cas B résolu) -- clause
        # dédiée `apport_nature_identite` (retouche du clausier, séparée de
        # l'en-tête statique "apports") : même principe que
        # `apports_numeraire_liberation` ci-dessus, un paragraphe par
        # apporteur en NATURE plutôt qu'un seul -- voir
        # `_render_apports_nature_statuts`.
        if section.code_section == "apport_nature_identite":
            runs = _render_apports_nature_statuts(db, session)
            if runs:
                _ajouter_bloc(
                    {
                        "code_section": section.code_section,
                        "code_clause": reponse.get("code_clause"),
                        "type": "content",
                        "titre": section.titre_affiche,
                        "explication": None,
                        "runs": runs,
                    }
                )
            continue

        # AJOUT (23/09/2026, service 1.1.4 statuts, limite résolue) -- section
        # `evaluation_apports_nature` (Article 6.2) a 4 variantes possibles
        # (voir clausier) ; seule `dispense_commissaire_apports_l225_8_1` est
        # spéciale-casée ici, un paragraphe par apporteur en nature -- les 3
        # autres variantes ne référencent aucune variable par-associé et
        # continuent le rendu générique normal ci-dessous (fallthrough, pas de
        # `continue` avant la vérification du code_clause choisi).
        if (
            section.code_section == "evaluation_apports_nature"
            and reponse.get("code_clause") == "dispense_commissaire_apports_l225_8_1"
        ):
            runs = _render_dispense_l225_8_1_statuts(db, session)
            if runs:
                _ajouter_bloc(
                    {
                        "code_section": section.code_section,
                        "code_clause": reponse.get("code_clause"),
                        "type": "content",
                        "titre": section.titre_affiche,
                        "explication": None,
                        "runs": runs,
                    }
                )
            continue

        # AJOUT (25/09/2026, audit complet du clausier, trou résolu) -- clause
        # optionnelle `apports_industrie` (art. 6.2 bis) : même principe que
        # `apport_nature_identite`, un paragraphe par associé
        # `type_apport='industrie'` (rare en pratique, mais pas déductible
        # d'une formule -- voir `_valeurs_apports_industrie_par_associe`).
        if section.code_section == "apports_industrie":
            runs = _render_apports_industrie_statuts(db, session)
            if runs:
                _ajouter_bloc(
                    {
                        "code_section": section.code_section,
                        "code_clause": reponse.get("code_clause"),
                        "type": "content",
                        "titre": section.titre_affiche,
                        "explication": None,
                        "runs": runs,
                    }
                )
            continue

        if section.comportement_section == "donnee_projet":
            if section.code_section == "identification_des_parties":
                # SIMPLIFIE (26/09/2026) : le v1 a ete supprime de la base (document_type
                # "pacte_fondateurs_v2" n'existe plus, tout est renomme en "pacte_fondateurs"),
                # donc cette condition sur session.document_type ne selectionnait plus jamais
                # la bonne branche. Appel direct a la version v2, seule utilisee desormais.
                # _render_identification_parties (v1) a ete supprimee (code mort, plus jamais
                # appelee) -- voir recap-service-1.1.13-pacte-fondateurs.md, nettoyage du
                # 22/09/2026.
                # AJOUT (23/09/2026, service 1.1.4 statuts) : cette branche appelait
                # `_render_identification_parties_v2` (pacte) inconditionnellement --
                # jamais atteinte pour un statuts (aucun bug visible AVANT que
                # document_type="statuts_sas" existe), voir docstring de
                # `_render_identification_parties_statuts` pour le trou trouvé/corrigé.
                # CORRECTIF (24/09/2026) : comparait à "statuts_sas", valeur
                # inexistante en base -- branche jamais prise (voir
                # DOCUMENT_TYPE_STATUTS dans statuts_sas_renderer.py).
                if session.document_type == DOCUMENT_TYPE_STATUTS:
                    runs = _render_identification_parties_statuts(db, session.project_id)
                else:
                    runs = _render_identification_parties_v2(db, session.project_id)
                _ajouter_bloc(
                    {
                        "code_section": section.code_section,
                        "code_clause": None,
                        "type": "content",
                        "titre": section.titre_affiche,
                        "explication": None,
                        "runs": runs,
                    }
                )
            continue

        if section.comportement_section == "texte_statique":
            bloc_titre = {
                "code_section": section.code_section,
                "code_clause": None,
                "type": "texte_statique",
                "titre": section.titre_affiche,
                "explication": None,
                "runs": [_lit(section.texte_statique or "")],
            }
            if section.code_section.startswith("titre_article_"):
                # En attente plutôt qu'ajouté tout de suite (voir docstring) --
                # remplace un éventuel titre déjà en attente non flushed (ne
                # devrait pas arriver, deux titres d'article ne se suivent
                # jamais sans contenu/section entre les deux dans le squelette,
                # mais garde le dernier plutôt que d'empiler par sécurité).
                titre_article_en_attente = bloc_titre
            else:
                _ajouter_bloc(bloc_titre)
            continue

        if not reponse.get("inclus"):
            continue

        clause = (
            db.query(ContractClauseLibrary)
            .filter(
                ContractClauseLibrary.document_type == session.document_type,
                ContractClauseLibrary.code_clause == reponse["code_clause"],
            )
            .first()
        )
        if clause is None:
            raise InvalidAnswerError(f"Clause '{reponse['code_clause']}' introuvable (donnée corrompue).")
        texte_clause = clause.texte_clause
        # Corrections de texte décidées par la vérification finale (tool
        # `correction_renvois`, 25/09/2026) : appliquées UNIQUEMENT au
        # document final (`finalize_session`), jamais pendant la rédaction.
        for correction in corrections_texte or []:
            if correction["code_section"] == section.code_section:
                texte_clause = texte_clause.replace(correction["remplace"], correction["par"])
        valeurs = dict(reponse.get("valeurs", {}))
        valeurs.update(_resoudre_variables_auto(clause.variables_requises, legal_profile))
        valeurs.update(_resoudre_variables_associes(db, clause.variables_requises, session.project_id))
        valeurs.update(_resoudre_variables_reference_croisee(clause.variables_requises, session.reponses))
        # Audit #13 (24/09/2026) : renvois d'article des statuts
        # (`resout_depuis_section`), jamais résolus avant -- sans effet pour
        # le pacte (aucune de ses variables ne porte ce champ).
        valeurs.update(_resoudre_references_articles(clause.variables_requises, numeros))
        valeurs.update(_resoudre_variables_apports_statuts(clause.variables_requises, db, session.project_id))
        valeurs.update(_resoudre_variables_officiers_statuts(clause.variables_requises, db, session.project_id))
        valeurs.update(_resoudre_variables_officiers_pm_statuts(clause.variables_requises, db, session.project_id))
        valeurs.update(_resoudre_signatures_associes(clause.variables_requises, db, session.project_id))
        if numeros is not None:
            valeurs.update(_formater_dates_saisies(clause.variables_requises, valeurs))
            valeurs.update(_formater_montants_saisis(clause.variables_requises, valeurs))
            valeurs.update(_resoudre_exercice_social(clause.variables_requises, valeurs))
        valeurs.update(_resoudre_variables_selection_associe(db, clause.variables_requises, session.project_id, valeurs))
        _ajouter_bloc(
            {
                "code_section": section.code_section,
                "code_clause": clause.code_clause,
                "type": "content",
                "titre": clause.titre_clause,
                "explication": clause.description_clause,
                # Dispatch par document_type (23/09/2026, correctif du bug de
                # substitution des statuts) -- voir document_renderer_base.py :
                # le clausier statuts utilise `(nom)` comme clé de placeholder,
                # le clausier pacte `(libelle)`. Seul ce choix de renderer
                # change ; le squelette de substitution appelé derrière est
                # identique pour les 2 (ClauseRendererBase.render_clause_texte).
                "runs": (
                    # CORRECTIF (24/09/2026) : comparait à "statuts_sas" (jamais
                    # vrai) -- les statuts passaient par le renderer du pacte.
                    statuts_clause_renderer
                    if session.document_type == DOCUMENT_TYPE_STATUTS
                    else pacte_clause_renderer
                ).render_clause_texte(texte_clause, valeurs, clause.variables_requises),
            }
        )

    if numeros is not None:
        # Lot B : titres « Article n – … », titres de clause retirés,
        # sous-titres « § » numérotés -- voir statuts_sas_numerotation.py.
        from backend.entrepreneur.services.statuts_sas_numerotation import numeroter_blocs

        blocks = numeroter_blocs(blocks, _sections(db, session.document_type), numeros)
    return blocks


def _collect_variable_values(db: Session, session: DocumentGenerationSession) -> list[dict]:
    """Reconstruit, à partir de `session.reponses`, les lignes à insérer dans
    `document_generation_variable_values` à la finalisation -- repart des
    réponses brutes plutôt que des runs du PDF (`_assemble_document_blocks`) :
    garde le `type` déclaré de chaque variable (`clause.variables_requises`),
    une information que les runs n'ont pas besoin de porter pour le rendu.

    Portée volontairement limitée aux variables de CLAUSE (mention_obligatoire/
    clause_optionnelle/variante_obligatoire) -- les données de
    `identification_des_parties` (donnee_projet) ne sont pas dupliquées ici :
    elles vivent déjà dans `project_associates`/`project_legal_profiles`, leur
    table source déjà éditable ; les recopier créerait une 2e source de vérité
    pour rien. Dette technique NON assumée ici, c'est un choix de conception :
    cette table sert à consulter/modifier les variables PROPRES au pacte
    (les blancs du texte Bpifrance), pas à recopier tout le projet.
    """
    # Import local -- voir la docstring de module de `statuts_sas_resolvers.py`.
    from backend.entrepreneur.services.statuts_sas_resolvers import (
        _resoudre_references_articles,
        _resoudre_variables_apports_statuts,
        _resoudre_variables_officiers_pm_statuts,
        _resoudre_signatures_associes,
        _resoudre_exercice_social,
        _resoudre_variables_officiers_statuts,
        _resoudre_variables_selection_associe,
        _valeurs_apports_industrie_par_associe,
        _valeurs_apports_nature_par_associe,
        _valeurs_apports_numeraire_par_associe,
        _valeurs_dispense_l225_8_1_par_associe,
    )

    # Lot B : numéros affichés calculés UNE fois (pas une requête par clause).
    numeros = _numeros_articles_statuts(db, session)
    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()
    )
    rows: list[dict] = []
    for section in _sections(db, session.document_type):
        reponse = session.reponses.get(section.code_section) or {}
        if not reponse.get("applicable", True):
            continue
        if section.comportement_section in ("texte_statique", "donnee_projet"):
            continue
        if not reponse.get("inclus", True):
            continue

        # AJOUT (23/09/2026, service 1.1.4 statuts, Cas B résolu) -- section
        # répétée par apporteur (voir `_render_apports_numeraire_statuts`) :
        # une ligne de traçabilité par (apporteur, variable), `nom_variable`
        # suffixé de son rang ("#1", "#2"...) pour rester unique -- le schéma
        # `document_generation_variable_values` (une ligne par variable de
        # clause) suppose une seule occurrence par variable, jamais N.
        if section.code_section == "apports_numeraire_liberation":
            resultat = _valeurs_apports_numeraire_par_associe(db, session)
            if resultat is not None:
                clause, par_associe = resultat
                valeurs_partagees_saisies = reponse.get("valeurs", {})
                for i, (_associe, valeurs_associe) in enumerate(par_associe, start=1):
                    for var in clause.variables_requises:
                        nom = var["nom"]
                        if nom not in valeurs_associe:
                            continue
                        rows.append(
                            {
                                "code_section": section.code_section,
                                "code_clause": clause.code_clause,
                                "nom_variable": f"{nom}#{i}",
                                "type_variable": var["type"],
                                "valeur": str(valeurs_associe[nom]),
                                # Seuls les champs PARTAGÉS (ex. fraction_libérée)
                                # peuvent être "saisis" -- identité/somme/actions
                                # sont toujours auto-résolus, jamais dans
                                # reponse["valeurs"] (voir docstring de
                                # `_valeurs_apports_numeraire_par_associe`).
                                "saisie_manuellement": nom in valeurs_partagees_saisies,
                            }
                        )
            continue

        # AJOUT (23/09/2026, service 1.1.4 statuts, Cas B résolu) -- même
        # principe que `apports_numeraire_liberation` ci-dessus, pour la
        # clause dédiée `apport_nature_identite`. `designation_bien_apporte`
        # (texte_par_associe) est bien "saisie_manuellement=True" pour chaque
        # apporteur -- contrairement à `identite_apporteur_nature`, résolu
        # automatiquement.
        if section.code_section == "apport_nature_identite":
            resultat = _valeurs_apports_nature_par_associe(db, session)
            if resultat is not None:
                clause, par_associe = resultat
                for i, (_associe, valeurs_associe) in enumerate(par_associe, start=1):
                    for var in clause.variables_requises:
                        nom = var["nom"]
                        if nom not in valeurs_associe:
                            continue
                        rows.append(
                            {
                                "code_section": section.code_section,
                                "code_clause": clause.code_clause,
                                "nom_variable": f"{nom}#{i}",
                                "type_variable": var["type"],
                                "valeur": str(valeurs_associe[nom]),
                                "saisie_manuellement": var["type"] == "texte_par_associe",
                            }
                        )
            continue

        # AJOUT (23/09/2026, service 1.1.4 statuts, limite résolue) -- même
        # principe, pour la variante `dispense_commissaire_apports_l225_8_1`
        # de la section `evaluation_apports_nature` (Article 6.2). Les 3
        # autres variantes de cette section n'ont aucune variable par-associé
        # et continuent le rendu générique ci-dessous (fallthrough). Toutes
        # les variables sont ici `saisie_manuellement=False` : entièrement
        # auto-résolues (voir `_CLAUSES_ENTIEREMENT_AUTO_RESOLUES`), y compris
        # `nature_biens`, qui recopie `designation_bien_apporte` déjà saisi
        # dans `apport_nature_identite` plutôt que de le redemander.
        if (
            section.code_section == "evaluation_apports_nature"
            and reponse.get("code_clause") == "dispense_commissaire_apports_l225_8_1"
        ):
            resultat = _valeurs_dispense_l225_8_1_par_associe(db, session)
            if resultat is not None:
                clause, par_associe = resultat
                for i, (_associe, valeurs_associe) in enumerate(par_associe, start=1):
                    for var in clause.variables_requises:
                        nom = var["nom"]
                        if nom not in valeurs_associe:
                            continue
                        rows.append(
                            {
                                "code_section": section.code_section,
                                "code_clause": clause.code_clause,
                                "nom_variable": f"{nom}#{i}",
                                "type_variable": var["type"],
                                "valeur": str(valeurs_associe[nom]),
                                "saisie_manuellement": False,
                            }
                        )
            continue

        # AJOUT (25/09/2026, audit complet du clausier, trou résolu) -- même
        # principe, pour la clause optionnelle `apports_industrie`
        # (art. 6.2 bis). Contrairement à `dispense_commissaire_apports_l225_8_1`,
        # RIEN n'est ici déductible d'une formule -- seule l'identité est
        # `saisie_manuellement=False`, les 4 autres champs
        # (`texte_par_associe`/`nombre_par_associe`) sont bien des saisies de
        # l'entrepreneur, juste réparties par associé plutôt qu'une seule fois.
        if section.code_section == "apports_industrie":
            resultat = _valeurs_apports_industrie_par_associe(db, session)
            if resultat is not None:
                clause, par_associe = resultat
                for i, (_associe, valeurs_associe) in enumerate(par_associe, start=1):
                    for var in clause.variables_requises:
                        nom = var["nom"]
                        if nom not in valeurs_associe:
                            continue
                        rows.append(
                            {
                                "code_section": section.code_section,
                                "code_clause": clause.code_clause,
                                "nom_variable": f"{nom}#{i}",
                                "type_variable": var["type"],
                                "valeur": str(valeurs_associe[nom]),
                                "saisie_manuellement": var["type"] in ("texte_par_associe", "nombre_par_associe"),
                            }
                        )
            continue

        code_clause = reponse.get("code_clause")
        if not code_clause:
            continue
        clause = (
            db.query(ContractClauseLibrary)
            .filter(
                ContractClauseLibrary.document_type == session.document_type,
                ContractClauseLibrary.code_clause == code_clause,
            )
            .first()
        )
        if clause is None:
            continue
        valeurs_saisies = dict(reponse.get("valeurs", {}))
        valeurs_toutes = {
            **valeurs_saisies,
            **_resoudre_variables_auto(clause.variables_requises, legal_profile),
            **_resoudre_variables_associes(db, clause.variables_requises, session.project_id),
            **_resoudre_variables_reference_croisee(clause.variables_requises, session.reponses),
            **_resoudre_references_articles(clause.variables_requises, numeros),
            **_resoudre_variables_apports_statuts(clause.variables_requises, db, session.project_id),
            **_resoudre_variables_officiers_statuts(clause.variables_requises, db, session.project_id),
            **_resoudre_variables_officiers_pm_statuts(clause.variables_requises, db, session.project_id),
            **_resoudre_signatures_associes(clause.variables_requises, db, session.project_id),
            **_resoudre_variables_selection_associe(db, clause.variables_requises, session.project_id, valeurs_saisies),
            **_resoudre_exercice_social(clause.variables_requises, valeurs_saisies),
        }
        for var in clause.variables_requises:
            nom = var["nom"]
            if nom not in valeurs_toutes:
                continue
            rows.append(
                {
                    "code_section": section.code_section,
                    "code_clause": code_clause,
                    "nom_variable": nom,
                    "type_variable": var["type"],
                    "valeur": str(valeurs_toutes[nom]),
                    "saisie_manuellement": nom in valeurs_saisies,
                }
            )
    return rows


def finalize_session(db: Session, user: User, project_id, document_type: str) -> Document:
    project = get_owned_project(db, user, project_id)
    session = get_or_create_session(db, user, project_id, document_type)
    if session.statut != "complete":
        raise InvalidAnswerError(
            f"Session pas encore terminée (section courante : '{session.section_courante}')."
        )
    if session.document_genere_id is not None:
        raise SessionAlreadyCompleteError("Un document a déjà été généré pour cette session.")

    # Validation globale (24/09/2026) : refus côté serveur tant qu'un problème
    # bloquant reste, même si le frontend est contourné. Import local : le
    # service de validation importe ce module. Dette assumée : le document
    # est assemblé deux fois (validation + rendu) -- simple, et la
    # génération finale n'a lieu qu'une fois.
    from backend.entrepreneur.services.document_generation_validation_service import valider_session

    resultat_validation = valider_session(db, session)
    if not resultat_validation["pret"]:
        raise ValidationFinaleError(resultat_validation)

    blocks = _assemble_document_blocks(db, session, resultat_validation.get("corrections_texte"))
    # Statuts : titre « Statuts » en tête du document (retour utilisateur
    # 24/09/2026 : le PDF n'avait plus de titre). Le « Statuts » en texte
    # simple de l'en-tête a été retiré à la place (plus de doublon).
    titre_document = "Statuts" if document_type == DOCUMENT_TYPE_STATUTS else document_type.replace("_", " ").title()
    pdf_bytes = render_document_as_pdf(blocks, titre=titre_document)
    filename = f"{document_type}_{project.id}.pdf"
    upload = cloudinary_service.upload_raw_file(
        pdf_bytes, folder="wink/documents_generes", filename=filename
    )

    # documents.document_type garde un CHECK fermé (migration d2e3f4a5b6c7,
    # ck_documents_document_type) qui n'inclut QUE "pacte_fondateurs"/"statuts"/...
    # DEVENU SANS OBJET (26/09/2026) : la normalisation "pacte_fondateurs_v2" ->
    # "pacte_fondateurs" ne sert plus a rien, cette valeur n'existe plus en base
    # (v1 supprime, plus qu'une seule valeur "pacte_fondateurs"). Gardee en no-op
    # explicite plutot que supprimee : si un futur document_type versionne a
    # nouveau (ex. "statuts_v2"), le meme point de normalisation sera reutilise ici.
    document_type_stocke = document_type
    document = Document(owner_user_id=user.id, project_id=project.id, document_type=document_type_stocke)
    db.add(document)
    db.flush()

    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        original_filename=filename,
        cloudinary_public_id=upload["public_id"],
        secure_url=upload["secure_url"],
        mime_type="application/pdf",
        size_bytes=len(pdf_bytes),
    )
    db.add(version)
    db.flush()

    for row in _collect_variable_values(db, session):
        db.add(DocumentGenerationVariableValue(document_version_id=version.id, **row))

    document.current_version_id = version.id
    session.document_genere_id = document.id

    db.commit()
    db.refresh(document)
    return document


def get_document_preview_pdf(db: Session, user: User, project_id, document_type: str) -> bytes:
    """Preview PDF de la session en cours -- streamée à la demande à chaque
    appel (option B tranchée avec l'utilisateur, 21/09/2026), jamais stockée
    sur Cloudinary : évite une écriture à chaque validation de section (coût,
    et des dizaines de fichiers orphelins pour un seul document jamais
    finalisé). Ne fait AUCUNE vérification `statut='complete'` (contrairement
    à `finalize_session`) -- c'est tout l'intérêt : afficher le document tel
    qu'il avance, y compris `en_cours`.
    """
    get_owned_project(db, user, project_id)
    session = get_or_create_session(db, user, project_id, document_type)
    blocks = _assemble_document_blocks(db, session)
    # Statuts : titre « Statuts » en tête du document (retour utilisateur
    # 24/09/2026 : le PDF n'avait plus de titre). Le « Statuts » en texte
    # simple de l'en-tête a été retiré à la place (plus de doublon).
    titre_document = "Statuts" if document_type == DOCUMENT_TYPE_STATUTS else document_type.replace("_", " ").title()
    return render_document_as_pdf(blocks, titre=titre_document)
