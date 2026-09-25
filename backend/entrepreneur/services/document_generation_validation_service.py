"""Validation globale avant la génération finale — partie base de données
(service 1.1.4, 24/09/2026).

Construit le contexte de l'agent `agents/document_generation_validation`
(qui, lui, ne lit jamais la base) en lisant tout UNE seule fois, puis
l'appelle. Utilisé par la route `…/validation-finale` (écran de fin) et par
`finalize_session` (blocage côté serveur : la génération est refusée tant
qu'un problème bloquant reste, même si le frontend est contourné).

Fichier séparé de `document_generation_service.py` (déjà > 2 000 lignes) :
une responsabilité claire, « préparer et lancer la validation ».
"""
from sqlalchemy.orm import Session

from agents.document_generation_validation.contexte import (
    AssocieContexte,
    BlocContexte,
    ClauseContexte,
    ContexteValidation,
    DirigeantContexte,
    SectionContexte,
)
from agents.document_generation_validation.document_generation_validation import TOOLS_PAR_DOCUMENT, valider
from agents.document_generation_validation.tools.commun.controle_juridique_attente import CLE_EN_ATTENTE
from backend.entrepreneur.models.company_officer import CompanyOfficer
from backend.entrepreneur.models.document_generation_session import DocumentGenerationSession
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.services.document_generation_service import (
    _SECTIONS_INTERACTIVES,
    InvalidAnswerError,
    _assemble_document_blocks,
    _numeros_articles_statuts,
    _sections,
    get_or_create_session,
)
from backend.entrepreneur.services.statuts_sas_regles_validite import critere_verifiable_par_code
from backend.shared.knowledge_base.models.contract_clause_library import ContractClauseLibrary
from backend.shared.knowledge_base.services.clause_validity_criteria_service import list_for_clause
from backend.shared.models.user import User

# Réponses calculées par le moteur (jamais saisies) : une telle section ne se
# « corrige » pas en la rouvrant.
_MARQUEURS_CALCULES = ("derivee", "auto_genere", "traite_automatiquement")


def _saisie_utilisateur(section, reponse: dict) -> bool:
    return (
        section.comportement_section in _SECTIONS_INTERACTIVES
        and reponse.get("applicable", True) is not False
        and not any(reponse.get(m) for m in _MARQUEURS_CALCULES)
    )


def _libelles_sections(sections, reponses: dict, clauses: dict, numeros: dict | None) -> dict[str, str]:
    """{code_section: « Article 6 – Apports · Dépôt des fonds »}, calculé en
    mémoire (pas une requête par section)."""
    hors_article: dict = {}
    if numeros is not None:
        from backend.entrepreneur.services.statuts_sas_numerotation import PREFIXE_TITRE_ARTICLE, libelle_article
        from backend.entrepreneur.services.statuts_sas_resolvers import SECTIONS_HORS_ARTICLE

        hors_article = SECTIONS_HORS_ARTICLE
    libelles: dict[str, str] = {}
    article: str | None = None
    for s in sections:
        if s.code_section.startswith("titre_article_"):
            article = (
                libelle_article(numeros.get(s.code_section[len(PREFIXE_TITRE_ARTICLE):]), s.titre_affiche)
                if numeros is not None
                else s.titre_affiche
            )
            continue
        clause = clauses.get((reponses.get(s.code_section) or {}).get("code_clause"))
        titre = clause.titre_clause if clause else (s.titre_affiche or s.code_section)
        parent = "Clôture des statuts" if s.code_section in hors_article else article
        libelles[s.code_section] = f"{parent} · {titre}" if parent and parent != titre else titre
    return libelles


def construire_contexte(db: Session, session: DocumentGenerationSession) -> ContexteValidation:
    sections = _sections(db, session.document_type)
    reponses = session.reponses or {}

    codes_clause = {r.get("code_clause") for r in reponses.values() if isinstance(r, dict) and r.get("code_clause")}
    lignes_clauses = (
        db.query(ContractClauseLibrary)
        .filter(
            ContractClauseLibrary.document_type == session.document_type,
            ContractClauseLibrary.code_clause.in_(codes_clause),
        )
        .all()
        if codes_clause
        else []
    )
    # Critères réservés au LLM : seulement pour les clauses qui ont des champs
    # encore à vérifier (évite une requête par clause pour rien).
    a_verifier = {
        r.get("code_clause") for r in reponses.values() if isinstance(r, dict) and r.get(CLE_EN_ATTENTE)
    }
    clauses = {
        c.code_clause: ClauseContexte(
            code_clause=c.code_clause,
            titre_clause=c.titre_clause,
            texte_clause=c.texte_clause,
            variables_requises=c.variables_requises or [],
            criteres_llm=[
                {"description_critere": k.description_critere, "base_legale": k.base_legale, "valeur_limite": k.valeur_limite}
                for k in list_for_clause(db, clause_library_id=c.id)
                if not critere_verifiable_par_code({"valeur_limite": k.valeur_limite})
            ]
            if c.code_clause in a_verifier
            else [],
        )
        for c in lignes_clauses
    }

    numeros = _numeros_articles_statuts(db, session)
    libelles = _libelles_sections(sections, reponses, clauses, numeros)
    sections_ctx = [
        SectionContexte(
            code_section=s.code_section,
            libelle=libelles.get(s.code_section, s.code_section),
            reponse=reponses[s.code_section],
            saisie_utilisateur=_saisie_utilisateur(s, reponses[s.code_section]),
        )
        for s in sections
        if isinstance(reponses.get(s.code_section), dict)
    ]

    associes = [
        AssocieContexte(
            id=str(a.id),
            nom=(a.denomination_sociale if a.type_personne == "personne_morale" and a.denomination_sociale else a.nom_complet),
            type_apport=a.type_apport,
            pourcentage_capital=a.pourcentage_capital,
        )
        for a in db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == session.project_id)
        .order_by(ProjectAssociate.created_at)
    ]
    noms_par_associe = {a.id: a.nom for a in associes}
    dirigeants = [
        DirigeantContexte(
            role=o.role,
            # Dirigeant associé : son identité vit sur la fiche associé.
            nom=o.denomination_sociale or o.nom_complet or noms_par_associe.get(str(o.associate_id), ""),
            duree_fonctions=o.duree_fonctions,
        )
        # Ordre de création : le « premier » de chaque rôle est celui imprimé.
        for o in db.query(CompanyOfficer)
        .filter(CompanyOfficer.project_id == session.project_id)
        .order_by(CompanyOfficer.created_at)
    ]
    profil = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()

    blocs = [
        BlocContexte(code_section=b.get("code_section"), texte="".join(r.get("texte", "") for r in b.get("runs", [])))
        for b in _assemble_document_blocks(db, session)
    ]
    return ContexteValidation(
        document_type=session.document_type,
        sections=sections_ctx,
        clauses=clauses,
        associes=associes,
        dirigeants=dirigeants,
        capital_social=profil.capital_social if profil else None,
        blocs=blocs,
        articles_presents=set(numeros) if numeros is not None else None,
    )


def valider_session(db: Session, session: DocumentGenerationSession) -> dict:
    """{pret, etapes, problemes} -- voir agents/document_generation_validation.
    Document sans vérification définie (pacte aujourd'hui) : prêt, sans
    construire le contexte pour rien."""
    if session.document_type not in TOOLS_PAR_DOCUMENT:
        return {"pret": True, "etapes": [], "problemes": [], "corrections_texte": []}
    return valider(session.document_type, construire_contexte(db, session))


def valider_document(db: Session, user: User, project_id, document_type: str) -> dict:
    """GET …/validation-finale. Seulement une fois le parcours terminé : avant,
    le document assemblé est incomplet par nature (le filet signalerait tout)."""
    session = get_or_create_session(db, user, project_id, document_type)
    if session.statut != "complete":
        raise InvalidAnswerError("La vérification finale n'est possible qu'une fois toutes les sections rédigées.")
    return valider_session(db, session)

