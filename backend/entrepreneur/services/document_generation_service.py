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
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_generation_session import DocumentGenerationSession
from backend.entrepreneur.models.document_generation_variable_value import DocumentGenerationVariableValue
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.services.pdf_rendering_service import render_document_as_pdf
from backend.entrepreneur.services.project_service import get_owned_project
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
    return True


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

    for section in _sections(db, session.document_type):
        if section.code_section in session.reponses:
            continue
        if not _applicable(section, forme_juridique, a_des_investisseurs, session.reponses):
            _set_reponse(session, section.code_section, {"applicable": False})
            continue
        if section.comportement_section in ("texte_statique", "donnee_projet"):
            _set_reponse(session, section.code_section, {"traite_automatiquement": True})
            continue
        session.section_courante = section.code_section
        db.flush()
        return

    session.section_courante = None
    session.statut = "complete"
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


def _nom_article_courant(db: Session, document_type: str, ordre_section: float) -> str | None:
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
    return row.titre_affiche if row else None


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
        "nom_article": _nom_article_courant(db, document_type, section.ordre),
        "position": position,
        "total_sections_estime": total,
    }

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

    sections = _sections(db, document_type)
    ordre_par_section = {s.code_section: s.ordre for s in sections}

    candidats_retour = [
        s
        for s in sections
        if s.comportement_section in _SECTIONS_INTERACTIVES
        and s.code_section in session.reponses
        and session.reponses[s.code_section].get("applicable", True) is not False
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


def _validate_variables(clause: ContractClauseLibrary | None, valeurs: dict) -> None:
    if clause is None:
        # Ne devrait jamais arriver : section.reference_id pointe vers une clause
        # supprimée depuis, ou le seed n'a pas encore tourné — signale une
        # incohérence de données, pas une erreur de saisie utilisateur.
        raise InvalidAnswerError("Clause de référence introuvable pour cette section (squelette incohérent).")

    variables_applicables = [v for v in clause.variables_requises if _variable_applicable(v, valeurs)]

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
        )
    ]

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
) -> DocumentGenerationSession:
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
        _validate_variables(clause, valeurs)
        reponse = {"inclus": True, "code_clause": clause.code_clause, "valeurs": valeurs}

    elif section.comportement_section == "clause_optionnelle":
        if inclus is None:
            raise InvalidAnswerError("'inclus' est requis pour une section facultative.")
        if not inclus:
            reponse = {"inclus": False}
        else:
            clause = db.query(ContractClauseLibrary).filter(ContractClauseLibrary.id == section.reference_id).first()
            _validate_variables(clause, valeurs)
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
            _validate_variables(clause, valeurs)
            # `variante` (en plus de `code_clause`) : conservé séparément pour que
            # `_resoudre_variables_reference_croisee` puisse retrouver le choix de
            # premier niveau même quand `code_clause` finit par pointer vers une
            # sous-variante (Hyp3/Hyp7) -- voir docstring de cette fonction.
            reponse = {"inclus": True, "code_clause": clause.code_clause, "variante": variante, "valeurs": valeurs}

    else:
        # texte_statique/donnee_projet ne devraient jamais arriver ici : traitées
        # automatiquement par _advance_to_next_section avant de devenir "courante".
        raise InvalidAnswerError(f"La section '{code_section}' ({section.comportement_section}) ne prend pas de réponse.")

    _set_reponse(session, section.code_section, reponse)

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


def _lit(texte: str) -> dict:
    return {"texte": texte, "valeur_utilisateur": False, "nom_variable": None}


def _val(texte: str, nom_variable: str) -> dict:
    return {"texte": texte, "valeur_utilisateur": True, "nom_variable": nom_variable}


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


def _formater_siege_social(adresse: dict | None) -> str | None:
    """Formate `ProjectLegalProfile.registered_address` (JSONB libre) en une
    chaîne unique pour le Préambule ("ayant son siège social à (siège
    social)"). Champs attendus, tous optionnels : `ligne1`, `ligne2`,
    `code_postal`, `ville`. Pas de format d'adresse strict imposé ailleurs
    dans le repo à ce jour (JSONB libre) -- reconstruction best-effort, jointe
    par des virgules, en sautant les champs absents plutôt que d'écrire des
    virgules vides ou "None"."""
    if not adresse:
        return None
    parts = [adresse.get("ligne1"), adresse.get("ligne2")]
    ville = " ".join(p for p in (adresse.get("code_postal"), adresse.get("ville")) if p)
    if ville:
        parts.append(ville)
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


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
    renseignée, le placeholder reste tel quel dans le texte plutôt que de
    générer un document avec un vide silencieux -- signal visible d'un
    problème de données, pas une erreur bloquante à ce stade de l'assemblage.
    """
    resolues = {}
    forme_juridique = legal_profile.legal_form if legal_profile else None
    for var in variables:
        if var["type"] == "auto_forme_juridique":
            table = var.get("valeurs_par_forme_juridique", {})
            if forme_juridique in table:
                resolues[var["nom"]] = table[forme_juridique]
        elif var["type"] == "auto_nom_societe":
            if legal_profile and legal_profile.legal_name:
                resolues[var["nom"]] = legal_profile.legal_name
        elif var["type"] == "auto_profil_juridique":
            champ = var.get("champ")
            valeur = getattr(legal_profile, champ, None) if legal_profile and champ else None
            if valeur is not None:
                resolues[var["nom"]] = str(valeur)
        elif var["type"] == "auto_siege_social":
            adresse = legal_profile.registered_address if legal_profile else None
            formatee = _formater_siege_social(adresse)
            if formatee:
                resolues[var["nom"]] = formatee
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
    return resolues


def _render_clause_texte(clause_texte: str, valeurs: dict, variables: list[dict]) -> list[dict]:
    """Remplace chaque placeholder brut (`libelle`, tel qu'apparu dans le texte
    Bpifrance, ex. "(nombre)") par la valeur saisie par l'utilisateur pour la
    variable correspondante -- retourne des "runs" (liste de segments
    `{texte, valeur_utilisateur, nom_variable}`) plutôt qu'une chaîne assemblée :
    `render_document_as_pdf` colore en rouge tout run `valeur_utilisateur=True`
    (exigence utilisateur, 21/09/2026 -- TOUTE valeur injectée, saisie ou
    auto-résolue). Remplacement littéral, pas de moteur de templating : le
    texte source contient les parenthèses telles quelles, on les retire au
    passage plutôt que de les garder dans le document final signé.

    Implémentation : chaque placeholder est d'abord remplacé par un marqueur
    sentinelle unique portant le nom de variable + la valeur (`\\x00nom\\x00valeur\\x00`),
    avec les mêmes règles `.replace()` que l'ancienne version (donc les mêmes
    limites assumées : un placeholder identique répété dans le texte source
    donnerait plusieurs runs avec le même `nom_variable`, aucun cas réel
    aujourd'hui). Le texte final est ensuite découpé sur ces marqueurs pour
    produire la liste de runs, sans jamais risquer qu'un `\\x00` apparaisse
    dans une vraie valeur saisie (caractère non imprimable, absent de toute
    saisie utilisateur normale).

    `valeurs_par_choix` (dict sur une variable `type='choix'`, ex.
    "(l'intégralité/au moins X %)" à l'article 7.5) : certains blancs Bpifrance
    représentent en réalité 2 saisies distinctes -- un choix (`regle_distribution`
    ici) + un nombre qui ne s'applique que pour UNE des options
    (`seuil_pourcentage`, actif seulement si `regle_distribution="pourcentage
    minimum"`, via le mécanisme `depend_de_variable`/`depend_de_valeurs` déjà
    utilisé pour la validation -- voir `_variable_applicable`). `valeurs_par_choix`
    associe l'option choisie à un gabarit qui peut référencer `{nom_autre_variable}`
    -- résolu ici plutôt que par un remplacement séquentiel, pour ne substituer la
    variable dépendante (`seuil_pourcentage`) qu'À L'INTÉRIEUR du gabarit de
    l'option qui la rend applicable, jamais comme un 2e placeholder autonome dans
    le texte (elle n'apparaît nulle part telle quelle dans le texte source).
    """
    valeurs_resolues = dict(valeurs)
    for var in variables:
        gabarits = var.get("valeurs_par_choix")
        if not gabarits or var["type"] != "choix":
            continue
        choix_fait = valeurs.get(var["nom"])
        gabarit = gabarits.get(choix_fait)
        if gabarit is None:
            continue
        try:
            valeurs_resolues[var["nom"]] = gabarit.format(**valeurs)
        except KeyError:
            # variable référencée par le gabarit pas encore renseignée --
            # signal visible (placeholder du gabarit laissé tel quel), même
            # choix que le reste de cette fonction plutôt qu'un vide silencieux.
            valeurs_resolues[var["nom"]] = gabarit

    marque = clause_texte
    for var in variables:
        placeholder = f"({var['libelle']})"
        value = str(valeurs_resolues.get(var["nom"], "")).strip()
        marque = marque.replace(placeholder, f"\x00{var['nom']}\x00{value}\x00")

    segments = re.split(r"\x00([^\x00]+)\x00([^\x00]*)\x00", marque)
    runs: list[dict] = []
    if segments[0]:
        runs.append(_lit(segments[0]))
    i = 1
    while i < len(segments):
        runs.append(_val(segments[i + 1], segments[i]))
        texte_suivant = segments[i + 2] if i + 2 < len(segments) else ""
        if texte_suivant:
            runs.append(_lit(texte_suivant))
        i += 3
    return runs


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


def _assemble_document_blocks(db: Session, session: DocumentGenerationSession) -> list[dict]:
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
    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()
    )

    blocks: list[dict] = []
    titre_article_en_attente: dict | None = None

    def _ajouter_bloc(bloc: dict) -> None:
        nonlocal titre_article_en_attente
        if titre_article_en_attente is not None:
            blocks.append(titre_article_en_attente)
            titre_article_en_attente = None
        blocks.append(bloc)

    for section in _sections(db, session.document_type):
        reponse = session.reponses.get(section.code_section)

        if reponse is None:
            if section.code_section != session.section_courante:
                continue
            _ajouter_bloc(_placeholder_block(db, section))
            continue

        if not reponse.get("applicable", True):
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
        valeurs = dict(reponse.get("valeurs", {}))
        valeurs.update(_resoudre_variables_auto(clause.variables_requises, legal_profile))
        valeurs.update(_resoudre_variables_associes(db, clause.variables_requises, session.project_id))
        valeurs.update(_resoudre_variables_reference_croisee(clause.variables_requises, session.reponses))
        _ajouter_bloc(
            {
                "code_section": section.code_section,
                "code_clause": clause.code_clause,
                "type": "content",
                "titre": clause.titre_clause,
                "explication": clause.description_clause,
                "runs": _render_clause_texte(clause.texte_clause, valeurs, clause.variables_requises),
            }
        )

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

    blocks = _assemble_document_blocks(db, session)
    titre_document = document_type.replace("_", " ").title()
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
    titre_document = document_type.replace("_", " ").title()
    return render_document_as_pdf(blocks, titre=titre_document)
