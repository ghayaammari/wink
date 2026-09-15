"""Logique métier du nouveau service "Vérification croisée SIREN/SIRET" (pas
encore numéroté officiellement — 1.1.18 provisoire dans le plan, Groupe 4).

Confirme le SIREN déjà saisi/sauvegardé sur `project_legal_profiles` auprès de
l'API Recherche d'Entreprises, et met à jour les 3 statuts de vérification.
Déclenché uniquement par un appel explicite (bouton "Mettre à jour" côté Mon
Projet, Parcours B) — jamais pendant l'onboarding, qui ne fait que le contrôle
de format (Luhn, côté frontend, voir entrepreneur/utils/luhn.ts).

Fichier séparé de project_service.py : cette logique dépend d'un appel externe
avec ses propres échecs (503 si l'API est indisponible), même séparation que
name_availability_service.py pour 1.1.2.

Cœur destiné à être réutilisé tel quel par le futur service 1.1.9 (Parcours A,
job périodique une fois le SIREN attribué) — seul le déclenchement changera
(script relancé manuellement plutôt que ce bouton), voir
docs/documentation-implementation.md.
"""
from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User
from scrapers.recherche_entreprises.client import RechercheEntreprisesApiError, get_by_siren
from scrapers.shared.text_normalize import fold


class LegalVerificationError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class LegalVerificationUpstreamError(LegalVerificationError):
    """Échec de l'appel à l'API Recherche d'Entreprises — traduite en 503 : ce
    n'est pas une erreur de saisie de l'utilisateur, et ses données restent
    enregistrées telles quelles (la sauvegarde, via update_legal_profile, est
    un appel séparé qui a déjà réussi avant celui-ci — voir project_router.py).
    """


class LegalVerificationMissingSirenError(LegalVerificationError):
    """Pas de SIREN enregistré sur le profil légal — rien à vérifier. Ne
    devrait pas arriver en usage normal (le frontend ne propose l'action que
    si un SIREN est déjà saisi), gardé comme garde-fou explicite plutôt qu'un
    appel API avec `siren=None`.
    """


def verify_legal_profile(db: Session, user: User, project_id) -> ProjectLegalProfile:
    project = get_owned_project(db, user, project_id)

    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()
    )
    if legal_profile is None or not legal_profile.siren:
        raise LegalVerificationMissingSirenError("Aucun SIREN enregistré sur ce profil — rien à vérifier.")

    try:
        result = get_by_siren(legal_profile.siren)
    except RechercheEntreprisesApiError as exc:
        raise LegalVerificationUpstreamError(f"Vérification indisponible pour le moment : {exc}") from exc

    if result is None:
        # Format valide (Luhn passé à la saisie) mais SIREN introuvable/inactif
        # auprès de la source officielle — pas une panne, juste un fait à
        # refléter. Les 3 statuts restent `non_verifie` (voir "Déclencheur 1",
        # page Notion "Wink — Schémas Incrément 1 v3").
        legal_profile.denomination_verification_status = "non_verifie"
        legal_profile.immatriculation_verification_status = "non_verifie"
        legal_profile.kbis_verification_status = "non_verifie"
        db.commit()
        db.refresh(legal_profile)
        return legal_profile

    # SIREN trouvé et actif : au minimum "verifie" pour l'immatriculation. Si un
    # SIRET a été saisi, on le compare en plus au SIRET du siège renvoyé par
    # l'API (confirmé par appel réel : `result["siege"]["siret"]`) — un SIRET
    # manifestement faux ne doit pas passer inaperçu derrière un SIREN correct
    # (bug réel rencontré : le badge affichait "Vérifié" avec un SIRET bidon,
    # jamais comparé à rien). Aucun SIRET saisi → pas de comparaison possible,
    # "verifie" reste basé sur le SIREN seul, comme avant.
    siret_api = (result.get("siege") or {}).get("siret")
    siret_saisi = legal_profile.siret
    if siret_saisi and siret_api and siret_saisi != siret_api:
        legal_profile.immatriculation_verification_status = "incoherent"
    else:
        legal_profile.immatriculation_verification_status = "verifie"

    # Un seul appel confirme immatriculation ET Kbis en même temps (même instant,
    # même source) — voir "Récapitulatif — Décisions Entrepreneur (Groupe 4)".
    # Le Kbis suit le même statut que l'immatriculation (y compris "incoherent"
    # en cas de SIRET faux) : la logique "un seul appel confirme les deux" reste
    # valable, il n'y a pas de vérification séparée du document Kbis lui-même.
    legal_profile.kbis_verification_status = legal_profile.immatriculation_verification_status

    nom_api = result.get("nom_complet") or result.get("nom_raison_sociale") or ""
    nom_saisi = legal_profile.legal_name or ""
    # "incoherent" (pas "non_verifie") : on a une réponse de la source officielle,
    # elle contredit juste ce que l'utilisateur a saisi — distinction utile pour
    # l'affichage (voir VerificationStatusBadge côté frontend).
    legal_profile.denomination_verification_status = (
        "verifie" if nom_saisi and fold(nom_saisi) == fold(nom_api) else "incoherent"
    )

    db.commit()
    db.refresh(legal_profile)
    return legal_profile
