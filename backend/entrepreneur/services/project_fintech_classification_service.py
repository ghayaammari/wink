"""Logique de classification `project_fintech_classification` — service 3.3.5

(FinTech). Même rôle et même choix d'architecture que
`project_healthtech_classification_service.py` (calcul déterministe +
get-or-create/upsert dans le même fichier, auto-recalcul à chaque PATCH — voir
cette docstring pour le "pourquoi" détaillé, non répété ici).

`classify()` implémente un arbre de décision simplifié sur les seuils ACPR /
Code monétaire et financier pour les établissements de paiement — voir la
docstring de `project_fintech_classification.py` pour la simplification
assumée (pas de valeur "exemption" faute de seuil exploitable).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.fintech_data_profile import FintechDataProfile
from backend.entrepreneur.models.project_fintech_classification import ProjectFintechClassification
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def classify(profile: FintechDataProfile) -> tuple[str | None, str]:
    """Retourne (type_agrement, justification). `type_agrement=None` tant que

    la chaîne de questions n'est pas assez répondue pour conclure — un champ
    `None` n'est jamais traité comme `False`.
    """
    if profile.gere_fonds_ou_paiements_clients is None:
        return None, "En attente de reponse : le projet gere-t-il des fonds ou paiements clients ?"

    if profile.gere_fonds_ou_paiements_clients is False:
        return "aucun", (
            "Le projet ne detient, ne gere et ne transmet aucun fonds ni paiement pour le "
            "compte de ses clients : aucun agrement au sens du Code monetaire et financier ne "
            "s'applique."
        )

    if profile.gere_investissement_ou_actifs is True:
        return "agrement_classique", (
            "Le projet gere de l'investissement ou des actifs pour le compte de ses clients "
            "(conseil en investissement, gestion de portefeuille, actifs numeriques) : un "
            "agrement classique est requis (CIF, PSI ou PSAN selon l'activite exacte, Code "
            "monetaire et financier)."
        )

    if profile.volume_mensuel_depasse_3_millions is True:
        return "agrement_classique", (
            "Le volume mensuel des paiements traites depasse 3 millions d'euros : le seuil de "
            "l'agrement simplifie (article L522-11-1 du Code monetaire et financier) est "
            "depasse, un agrement classique d'etablissement de paiement est requis."
        )

    if (
        profile.propose_transmission_de_fonds is None
        or profile.volume_mensuel_depasse_3_millions is None
        or profile.gere_investissement_ou_actifs is None
    ):
        return None, "En attente de reponse pour determiner precisement le type d'agrement."

    return "agrement_simplifie", (
        "Le projet gere des fonds ou paiements clients sous le seuil de 3 millions d'euros par "
        "mois, sans gestion d'investissement ni d'actifs : un agrement simplifie "
        "d'etablissement de paiement suffit (article L522-11-1 du Code monetaire et "
        "financier)."
    )


def get_or_create_classification(db: Session, user: User, project_id: UUID) -> ProjectFintechClassification:
    project = get_owned_project(db, user, project_id)

    classification = (
        db.query(ProjectFintechClassification).filter(ProjectFintechClassification.project_id == project.id).first()
    )
    if classification is None:
        classification = ProjectFintechClassification(project_id=project.id)
        db.add(classification)
        db.commit()
        db.refresh(classification)
    return classification


def upsert_from_profile(db: Session, project_id: UUID, profile: FintechDataProfile) -> ProjectFintechClassification:
    """Appelé côté serveur par `fintech_data_profile_service.update_profile

    aà chaque PATCH, `project_id` déjà validé en amont — même convention que
    `project_healthtech_classification_service.upsert_from_profile`."""
    type_agrement, justification = classify(profile)

    classification = (
        db.query(ProjectFintechClassification).filter(ProjectFintechClassification.project_id == project_id).first()
    )
    if classification is None:
        classification = ProjectFintechClassification(project_id=project_id)
        db.add(classification)

    classification.type_agrement = type_agrement
    classification.justification = justification
    db.commit()
    db.refresh(classification)
    return classification
