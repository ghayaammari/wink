"""Logique de classification `project_healthtech_classification` — service

3.3.5 (HealthTech). Contient à la fois le calcul déterministe (`classify()`,
arbre de décision MDR 2017/745 fermé sur 4 booléens — voir docstring du
modèle pour le raisonnement) ET le get-or-create/upsert : contrairement à
l'AI Act, il n'y a pas de LLM ni de recherche vectorielle à orchestrer, donc
pas de fichier `*_diagnostic_service.py` séparé ici — `upsert_from_profile`
est appelé directement à chaque PATCH du profil
(`healthtech_data_profile_service.update_profile`), pas via un bouton
explicite côté frontend. C'est un choix délibéré différent de l'AI Act/RGPD :
là-bas le recalcul est manuel car chaque appel coûte un appel LLM (Groq) ;
ici le calcul est un simple arbre de décision Python, gratuit et instantané,
donc l'auto-recalcul évite un clic inutile sans aucun inconvénient.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.healthtech_data_profile import HealthtechDataProfile
from backend.entrepreneur.models.project_healthtech_classification import ProjectHealthtechClassification
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def classify(profile: HealthtechDataProfile) -> tuple[str | None, str]:
    """Retourne (classe_risque, justification). `classe_risque=None` tant que

    la chaîne de questions n'est pas assez répondue pour conclure (voir
    docstring `healthtech_data_profile.py` pour l'ordre des portes) — un champ
    `None` n'est jamais traité comme `False`.
    """
    if profile.est_dispositif_medical is None:
        return None, "En attente de reponse : le projet est-il un dispositif medical ?"

    if profile.est_dispositif_medical is False:
        return "non_dispositif_medical", (
            "Le projet n'est pas declare comme dispositif medical au sens du reglement (UE) "
            "2017/745 (MDR) : aucune classe de risque MDR ne s'applique."
        )

    if profile.fournit_aide_decision_diagnostique_ou_therapeutique is None:
        return None, (
            "En attente de reponse : le dispositif fournit-il une aide a la decision "
            "diagnostique ou therapeutique ?"
        )

    if profile.fournit_aide_decision_diagnostique_ou_therapeutique is False:
        return "I", (
            "Dispositif medical que ne fournit pas d'aide a la decision diagnostique ou "
            "therapeutique : classe I (risque le plus faible) par defaut, reglement (UE) "
            "2017/745 (MDR)."
        )

    if profile.risque_deces_ou_deterioration_irreversible is True:
        return "III", (
            "Dispositif medical fournissant une aide a la decision diagnostique ou "
            "therapeutique, dont une erreur peut entrainer un deces ou une deterioration "
            "irreversible de l'etat de sante du patient : classe III (risque le plus eleve), "
            "regle 11 de l'annexe VIII du reglement (UE) 2017/745."
        )

    if profile.risque_intervention_chirurgicale_ou_deterioration_grave is True:
        return "IIb", (
            "Dispositif medical fournissant une aide a la decision diagnostique ou "
            "therapeutique, dont une erreur peut necessiter une intervention chirurgicale ou "
            "entrainer une deterioration grave de l'etat de sante du patient : classe IIb, "
            "regle 11 de l'annexe VIII du reglement (UE) 2017/745."
        )

    if (
        profile.risque_deces_ou_deterioration_irreversible is None
        or profile.risque_intervention_chirurgicale_ou_deterioration_grave is None
    ):
        return None, "En attente de reponse pour determiner precisement la gravite du risque."

    return "IIa", (
        "Dispositif medical fournissant une aide a la decision diagnostique ou therapeutique, "
        "sans risque de deces, de deterioration irreversible ou grave identifie : classe IIa "
        "par defaut, regle 11 de l'annexe VIII du reglement (UE) 2017/745."
    )


def get_or_create_classification(db: Session, user: User, project_id: UUID) -> ProjectHealthtechClassification:
    project = get_owned_project(db, user, project_id)

    classification = (
        db.query(ProjectHealthtechClassification)
        .filter(ProjectHealthtechClassification.project_id == project.id)
        .first()
    )
    if classification is None:
        classification = ProjectHealthtechClassification(project_id=project.id)
        db.add(classification)
        db.commit()
        db.refresh(classification)
    return classification


def upsert_from_profile(
    db: Session, project_id: UUID, profile: HealthtechDataProfile
) -> ProjectHealthtechClassification:
    """Appelé côté serveur par `healthtech_data_profile_service.update_profile

    aà chaque PATCH, `project_id` déjà validé en amont — pas de
    `get_owned_project` ici (même convention que `upsert_classification`,
    `project_ai_act_classification_service.py`)."""
    classe_risque, justification = classify(profile)

    classification = (
        db.query(ProjectHealthtechClassification)
        .filter(ProjectHealthtechClassification.project_id == project_id)
        .first()
    )
    if classification is None:
        classification = ProjectHealthtechClassification(project_id=project_id)
        db.add(classification)

    classification.classe_risque = classe_risque
    classification.justification = justification
    db.commit()
    db.refresh(classification)
    return classification
