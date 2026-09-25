"""Logique métier du service 1.1.5 — annonce légale de constitution (SAS).

Responsabilités (orchestration seulement) :
- lire les données du projet et des statuts finalisés (`_lire`) ;
- déléguer la pré-validation (`legal_announcement_prevalidation.py`, pur) et
  la rédaction (`legal_announcement_text_builder.py`, pur) ;
- gérer le cycle de statut : `genere` -> `valide_utilisateur` -> `attestation_deposee` ;
- lister les journaux habilités du département du siège (`jal_reference`) ;
- enregistrer l'attestation de parution déposée par l'entrepreneur.

Sources des données (spec 1.1.5, §4) :
- profil juridique, associés, dirigeants : tables du projet (source unique,
  « option 2 » — avertissement si modifiées après les statuts) ;
- date et lieu de l'acte : variables de clôture de la version FINALISÉE des
  statuts (`lieu_signature`/`date_signature`), PAS les colonnes
  `date_signature_statuts`/`lieu_signature_statuts` (sans usage, dette 1.1.4) ;
- agrément / cession libre : réponses de la session statuts.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.company_officer import CompanyOfficer
from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_generation_session import DocumentGenerationSession
from backend.entrepreneur.models.document_generation_variable_value import DocumentGenerationVariableValue
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.legal_announcement import LegalAnnouncement
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.services.legal_announcement_prevalidation import (
    ContexteAnnonce,
    IdentiteLue,
    avertissements_annonce,
    prevalider_annonce,
)
from backend.entrepreneur.services.legal_announcement_text_builder import (
    AGREMENT,
    CESSION_LIBRE,
    RESTRICTIONS_SANS_AGREMENT,
    DirigeantAnnonce,
    DonneesAnnonce,
    generer_texte_annonce,
)
from backend.entrepreneur.services.project_service import get_owned_project
from backend.entrepreneur.services.statuts_sas_prevalidation import PAGE_DIRIGEANTS, PAGE_EQUIPE_CAPITAL
from backend.entrepreneur.services.statuts_sas_renderer import DOCUMENT_TYPE_STATUTS
from backend.shared.knowledge_base.models.jal_reference import JalReference
from backend.shared.models.user import User
from backend.shared.services import cloudinary_service
from backend.shared.utils.departements import DEPARTEMENTS, departement_depuis_code_postal
from backend.shared.utils.formatting import formater_siege_social

# Fiche Service-Public « Rechercher un support habilité par département »
# (renvoie vers le registre actulegales.fr) — filet si notre référentiel est
# incomplet pour un département.
LIEN_RECHERCHE_OFFICIELLE = "https://entreprendre.service-public.gouv.fr/vosdroits/R44934"
DOCUMENT_TYPE_ATTESTATION = "attestation_annonce_legale"
TYPES_FICHIER_ACCEPTES = frozenset({"application/pdf", "image/png", "image/jpeg"})
TAILLE_MAX_ATTESTATION = 10 * 1024 * 1024  # 10 Mo

_VARIABLES_CLOTURE = ("lieu_signature", "date_signature")


class AnnonceError(Exception):
    """Erreur métier générique — 400 par défaut côté route."""


class AnnonceIntrouvableError(AnnonceError):
    """Aucune annonce générée pour ce projet — 404."""


class AnnonceStatutError(AnnonceError):
    """Action impossible dans le statut actuel de l'annonce — 409."""


class AnnoncePrevalidationError(AnnonceError):
    """Données manquantes avant génération — 422, avec la liste des problèmes."""

    def __init__(self, problemes: list[dict]):
        super().__init__("Des informations manquent pour générer l'annonce légale.")
        self.problemes = problemes


class AnnonceStockageError(AnnonceError):
    """Échec de l'upload de l'attestation (Cloudinary) — 503."""


# ---------------------------------------------------------------- lecture


def _identite_dirigeant(db: Session, officer: CompanyOfficer) -> tuple[DirigeantAnnonce | None, IdentiteLue]:
    """Identité d'un dirigeant, depuis `project_associates` s'il est associé
    (source de vérité, anti-redondance de `company_officers`), sinon depuis
    ses propres champs. Même règle que les statuts (`_identite_officier`),
    réécrite ici plutôt qu'importée : c'est une fonction privée du module
    statuts, qui renvoie des placeholders textuels inadaptés à une annonce."""
    if officer.associate_id is not None:
        a = db.get(ProjectAssociate, officer.associate_id)
        if a is None:
            return None, IdentiteLue(nom=None, adresse=None, page=PAGE_DIRIGEANTS)
        if a.type_personne == "personne_morale":
            representant = " ".join(p for p in (a.representant_prenom, a.representant_nom) if p) or None
            dirigeant = DirigeantAnnonce(
                nom=a.denomination_sociale or "",
                adresse=a.siege_social,
                est_personne_morale=True,
                forme_juridique=a.type_societe,
                capital_social=a.capital_social,
                lieu_immatriculation=a.lieu_immatriculation,
                siren=a.numero_siren,
                representant=representant,
            )
            return dirigeant, IdentiteLue(a.denomination_sociale, a.siege_social, PAGE_EQUIPE_CAPITAL)
        return (
            DirigeantAnnonce(nom=a.nom_complet or "", adresse=a.adresse),
            IdentiteLue(a.nom_complet, a.adresse, PAGE_EQUIPE_CAPITAL),
        )

    if officer.type_personne == "personne_morale":
        representant = " ".join(p for p in (officer.representant_prenom, officer.representant_nom) if p) or None
        dirigeant = DirigeantAnnonce(
            nom=officer.denomination_sociale or "",
            adresse=officer.siege_social,
            est_personne_morale=True,
            forme_juridique=officer.forme_juridique,
            capital_social=officer.capital_social,
            lieu_immatriculation=officer.lieu_immatriculation,
            siren=officer.siren,
            representant=representant,
        )
        return dirigeant, IdentiteLue(officer.denomination_sociale, officer.siege_social, PAGE_DIRIGEANTS)
    return (
        DirigeantAnnonce(nom=officer.nom_complet or "", adresse=officer.adresse),
        IdentiteLue(officer.nom_complet, officer.adresse, PAGE_DIRIGEANTS),
    )


def _premier_officier(officers: list[CompanyOfficer], role: str) -> CompanyOfficer | None:
    # Même convention que les statuts : le premier créé pour ce rôle.
    return next((o for o in officers if o.role == role), None)


def _transmission_actions(reponses: dict) -> tuple[str | None, str | None]:
    """Modalité de cession déduite des réponses de la session statuts :
    agrément inclus (Art. 17) > sinon variante retenue à l'Art. 14."""
    if (reponses.get("agrement") or {}).get("inclus"):
        exceptions = reponses.get("agrement_exceptions") or {}
        texte = (exceptions.get("valeurs") or {}).get("exceptions_agrement") if exceptions.get("inclus") else None
        return AGREMENT, texte
    transmission = reponses.get("transmission_actions") or {}
    code = transmission.get("code_clause") or transmission.get("variante")
    if code == "cession_actions_libre":
        return CESSION_LIBRE, None
    if code == "cession_actions_restrictions":
        return RESTRICTIONS_SANS_AGREMENT, None
    return None, None


def _valeurs_cloture(db: Session, document: Document | None) -> dict[str, str]:
    if document is None or document.current_version_id is None:
        return {}
    lignes = (
        db.query(DocumentGenerationVariableValue)
        .filter(
            DocumentGenerationVariableValue.document_version_id == document.current_version_id,
            DocumentGenerationVariableValue.nom_variable.in_(_VARIABLES_CLOTURE),
        )
        .all()
    )
    return {ligne.nom_variable: ligne.valeur for ligne in lignes if ligne.valeur}


def _lire(db: Session, project_id: UUID) -> tuple[ContexteAnnonce, DonneesAnnonce | None, LegalAnnouncement | None]:
    """Lit tout ce qu'il faut (5 requêtes, aucune par ligne : pas de N+1 sur
    les dirigeants, au plus 2 `db.get` pour Président/DG)."""
    profil = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project_id).first()
    associes = db.query(ProjectAssociate).filter(ProjectAssociate.project_id == project_id).all()
    officers = (
        db.query(CompanyOfficer)
        .filter(CompanyOfficer.project_id == project_id)
        .order_by(CompanyOfficer.created_at)
        .all()
    )
    session_statuts = (
        db.query(DocumentGenerationSession)
        .filter(
            DocumentGenerationSession.project_id == project_id,
            DocumentGenerationSession.document_type == DOCUMENT_TYPE_STATUTS,
            DocumentGenerationSession.document_genere_id.isnot(None),
        )
        .first()
    )
    annonce = db.query(LegalAnnouncement).filter(LegalAnnouncement.project_id == project_id).first()

    document_statuts = db.get(Document, session_statuts.document_genere_id) if session_statuts else None
    cloture = _valeurs_cloture(db, document_statuts)
    transmission, exceptions = _transmission_actions(session_statuts.reponses or {}) if session_statuts else (None, None)

    president_officer = _premier_officier(officers, "president")
    dg_officer = _premier_officier(officers, "directeur_general")
    president, president_lu = _identite_dirigeant(db, president_officer) if president_officer else (None, None)
    dg, dg_lu = _identite_dirigeant(db, dg_officer) if dg_officer else (None, None)

    adresse = profil.registered_address if profil else None
    siege = formater_siege_social(adresse)
    departement = departement_depuis_code_postal((adresse or {}).get("code_postal"))
    dates_modif = [r.updated_at for r in [profil, *associes, *officers] if r is not None and r.updated_at]

    ctx = ContexteAnnonce(
        statuts_finalises_le=document_statuts.created_at if document_statuts else None,
        forme_juridique=profil.legal_form if profil else None,
        denomination=profil.legal_name if profil else None,
        objet_social=profil.objet_social if profil else None,
        duree_societe=profil.duree_societe if profil else None,
        capital_social=profil.capital_social if profil else None,
        greffe=profil.lieu_immatriculation if profil else None,
        siege_formate=siege,
        departement=departement,
        date_acte=cloture.get("date_signature"),
        lieu_acte=cloture.get("lieu_signature"),
        transmission_actions=transmission,
        president=president_lu,
        directeur_general=dg_lu,
        donnees_modifiees_le=max(dates_modif) if dates_modif else None,
        annonce_generee_le=annonce.date_generation if annonce else None,
    )

    donnees = None
    if not prevalider_annonce(ctx):
        donnees = DonneesAnnonce(
            date_acte=ctx.date_acte,
            lieu_acte=ctx.lieu_acte,
            denomination=ctx.denomination,
            sigle=profil.sigle,
            # SASU : un seul associé (même forme juridique « SAS » dans le projet).
            unipersonnelle=len(associes) == 1,
            siege=siege,
            objet_social=ctx.objet_social,
            duree_annees=int(ctx.duree_societe),
            capital_social=Decimal(ctx.capital_social),
            greffe=ctx.greffe,
            transmission_actions=transmission,
            exceptions_agrement=exceptions,
            president=president,
            directeur_general=dg,
        )
    return ctx, donnees, annonce


def _annonce_existante(db: Session, project_id: UUID) -> LegalAnnouncement:
    annonce = db.query(LegalAnnouncement).filter(LegalAnnouncement.project_id == project_id).first()
    if annonce is None:
        raise AnnonceIntrouvableError("Aucune annonce légale n'a encore été générée pour ce projet.")
    return annonce


# ---------------------------------------------------------------- actions


def get_etat_annonce(db: Session, user: User, project_id: UUID) -> dict:
    project = get_owned_project(db, user, project_id)
    ctx, _, annonce = _lire(db, project.id)
    problemes = prevalider_annonce(ctx)
    return {
        "annonce": annonce,
        "pret_a_generer": not problemes,
        "problemes": problemes,
        "avertissements": avertissements_annonce(ctx),
        "departement": ctx.departement,
        "departement_nom": DEPARTEMENTS.get(ctx.departement) if ctx.departement else None,
    }


def generer_annonce(db: Session, user: User, project_id: UUID) -> LegalAnnouncement:
    """Génère (ou régénère) le texte. Régénérer ÉCRASE les corrections faites
    à la relecture : le frontend doit demander confirmation."""
    project = get_owned_project(db, user, project_id)
    ctx, donnees, annonce = _lire(db, project.id)
    problemes = prevalider_annonce(ctx)
    if problemes:
        raise AnnoncePrevalidationError(problemes)
    if annonce is not None and annonce.statut == "attestation_deposee":
        raise AnnonceStatutError(
            "L'annonce est déjà publiée (attestation déposée) : elle ne peut plus être régénérée. "
            "Une correction passe par une annonce rectificative."
        )

    texte = generer_texte_annonce(donnees)
    maintenant = datetime.now(timezone.utc)
    if annonce is None:
        annonce = LegalAnnouncement(project_id=project.id, texte_annonce=texte, statut="genere", date_generation=maintenant)
        db.add(annonce)
    else:
        annonce.texte_annonce = texte
        annonce.statut = "genere"
        annonce.date_generation = maintenant
        annonce.date_validation_utilisateur = None
    db.commit()
    db.refresh(annonce)
    return annonce


def modifier_texte(db: Session, user: User, project_id: UUID, texte: str) -> LegalAnnouncement:
    """Correction à la relecture. Possible aussi après validation (tant que
    rien n'est publié) : l'annonce repasse alors en `genere`, à revalider."""
    project = get_owned_project(db, user, project_id)
    annonce = _annonce_existante(db, project.id)
    if annonce.statut == "attestation_deposee":
        raise AnnonceStatutError("L'annonce est déjà publiée : son texte ne peut plus être modifié.")
    annonce.texte_annonce = texte
    annonce.statut = "genere"
    annonce.date_validation_utilisateur = None
    db.commit()
    db.refresh(annonce)
    return annonce


def valider_annonce(db: Session, user: User, project_id: UUID) -> LegalAnnouncement:
    project = get_owned_project(db, user, project_id)
    annonce = _annonce_existante(db, project.id)
    if annonce.statut != "genere":
        raise AnnonceStatutError(f"L'annonce ne peut pas être validée dans son état actuel ({annonce.statut}).")
    annonce.statut = "valide_utilisateur"
    annonce.date_validation_utilisateur = datetime.now(timezone.utc)
    db.commit()
    db.refresh(annonce)
    return annonce


def lister_journaux(db: Session, user: User, project_id: UUID) -> dict:
    """Journaux habilités du département du siège : seulement les lignes
    relues (`valide_humain`) et encore habilitées (`actif`)."""
    project = get_owned_project(db, user, project_id)
    profil = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()
    adresse = (profil.registered_address if profil else None) or {}
    departement = departement_depuis_code_postal(adresse.get("code_postal"))
    journaux = []
    if departement is not None:
        journaux = (
            db.query(JalReference)
            .filter(
                JalReference.statut_contenu == "valide_humain",
                JalReference.actif.is_(True),
                JalReference.departements_couverts.any(departement),
            )
            .order_by(JalReference.type_support, JalReference.nom_journal)
            .all()
        )
    return {
        "departement": departement,
        "departement_nom": DEPARTEMENTS.get(departement) if departement else None,
        "journaux": journaux,
        "lien_recherche_officielle": LIEN_RECHERCHE_OFFICIELLE,
    }


def deposer_attestation(
    db: Session,
    user: User,
    project_id: UUID,
    *,
    file_bytes: bytes,
    filename: str | None,
    content_type: str | None,
    journal_utilise: str,
    date_publication: date,
) -> LegalAnnouncement:
    project = get_owned_project(db, user, project_id)
    annonce = _annonce_existante(db, project.id)
    if annonce.statut == "genere":
        raise AnnonceStatutError("Validez d'abord le texte de l'annonce avant de déposer l'attestation.")
    if annonce.statut == "attestation_deposee":
        raise AnnonceStatutError("Une attestation a déjà été déposée pour cette annonce.")

    if not file_bytes:
        raise AnnonceError("Le fichier de l'attestation est vide.")
    if len(file_bytes) > TAILLE_MAX_ATTESTATION:
        raise AnnonceError("Le fichier dépasse 10 Mo.")
    if content_type not in TYPES_FICHIER_ACCEPTES:
        raise AnnonceError("Format non accepté : déposez un PDF, un PNG ou un JPEG.")
    if not journal_utilise or not journal_utilise.strip():
        raise AnnonceError("Indiquez le journal dans lequel l'annonce a été publiée.")
    if date_publication > date.today():
        raise AnnonceError("La date de parution ne peut pas être dans le futur.")

    nom_fichier = filename or "attestation_annonce_legale.pdf"
    try:
        upload = cloudinary_service.upload_raw_file(
            file_bytes, folder="wink/attestations_annonce_legale", filename=nom_fichier
        )
    except cloudinary_service.CloudinaryError as exc:
        raise AnnonceStockageError(str(exc)) from exc

    # Même structure que les documents générés (finalize_session) : un
    # Document + sa version 1 ; l'attestation apparaît donc aussi dans le
    # coffre-fort documentaire (1.1.17) sans code en plus.
    document = Document(owner_user_id=user.id, project_id=project.id, document_type=DOCUMENT_TYPE_ATTESTATION)
    db.add(document)
    db.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        original_filename=nom_fichier,
        cloudinary_public_id=upload["public_id"],
        secure_url=upload["secure_url"],
        mime_type=content_type,
        size_bytes=len(file_bytes),
    )
    db.add(version)
    db.flush()
    document.current_version_id = version.id

    annonce.attestation_document_id = document.id
    annonce.journal_utilise = journal_utilise.strip()
    annonce.date_publication = date_publication
    annonce.statut = "attestation_deposee"
    db.commit()
    db.refresh(annonce)
    return annonce
