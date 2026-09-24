"""Pré-validation des statuts SAS au démarrage (service 1.1.4, 24/09/2026).

Décision utilisateur : aucune donnée automatique n'est contrôlée PENDANT le
parcours (les sections sans saisie sont générées directement). À la place,
deux contrôles bloquants :
1. **ici, au démarrage** : les données du projet que les statuts reprennent
   automatiquement (Informations légales, Équipe & capital, Dirigeants) ;
2. une validation globale avant la génération finale (à venir) : les données
   qui dépendent des choix faits pendant le parcours (DG si l'article DG est
   coché…) et le filet « aucun (… non renseigné) dans le document ».

Chaque problème porte la page où le corriger (`page`), pour un lien direct
côté frontend. Fonction pure sur la base (lecture seule), sans effet de bord.

Règle de maintenance : un champ lu par une clause `auto_*` ou par l'en-tête
(`_render_identification_parties_statuts`) doit être contrôlé ici. Sinon il
peut sortir en « (… non renseigné) » dans le PDF sans que rien ne bloque.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.entrepreneur.models.company_officer import CompanyOfficer
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile

PAGE_INFORMATIONS_LEGALES = "informations_legales"
PAGE_EQUIPE_CAPITAL = "equipe_capital"
PAGE_DIRIGEANTS = "dirigeants"

# Forme juridique attendue EXACTEMENT : les sections du clausier portent
# `formes_juridiques_concernees = ["SAS"]` et le moteur compare la valeur
# telle quelle (`_applicable`) -- « sas » ou « Société par actions
# simplifiée » rendraient toutes les sections non applicables (statuts vides).
FORME_JURIDIQUE_ATTENDUE = "SAS"


def _probleme(code: str, message: str, page: str) -> dict:
    return {"code": code, "message": message, "page": page}


def _vide(valeur) -> bool:
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def _verifier_profil_juridique(profil: ProjectLegalProfile | None, siege_formate: str | None) -> list[dict]:
    if profil is None:
        return [_probleme("profil_absent", "Les informations légales du projet ne sont pas renseignées.", PAGE_INFORMATIONS_LEGALES)]

    problemes = []
    champs = (
        ("legal_name", "la dénomination sociale (nom légal)"),
        ("objet_social", "l'objet social"),
        ("duree_societe", "la durée de la société"),
        ("capital_social", "le capital social"),
        ("nombre_actions", "le nombre d'actions"),
        ("valeur_nominale", "la valeur d'une action"),
        ("lieu_immatriculation", "la ville du greffe (RCS)"),
    )
    for champ, libelle in champs:
        if _vide(getattr(profil, champ)):
            problemes.append(_probleme(f"profil_{champ}", f"Renseignez {libelle}.", PAGE_INFORMATIONS_LEGALES))

    forme = (profil.legal_form or "").strip()
    if forme != FORME_JURIDIQUE_ATTENDUE:
        actuelle = f" (actuellement : « {forme} »)" if forme else ""
        problemes.append(
            _probleme(
                "profil_legal_form",
                f"La forme juridique doit être exactement « {FORME_JURIDIQUE_ATTENDUE} »{actuelle} : ce générateur ne rédige que des statuts de SAS.",
                PAGE_INFORMATIONS_LEGALES,
            )
        )

    if not siege_formate:
        problemes.append(_probleme("profil_siege", "Renseignez l'adresse du siège social.", PAGE_INFORMATIONS_LEGALES))

    # Données saisies avant le contrôle de cohérence (lot 1) : revérifié ici.
    if None not in (profil.capital_social, profil.nombre_actions, profil.valeur_nominale):
        if Decimal(profil.nombre_actions) * Decimal(profil.valeur_nominale) != Decimal(profil.capital_social):
            problemes.append(
                _probleme(
                    "profil_capital_incoherent",
                    "Le capital social doit être égal au nombre d'actions multiplié par la valeur d'une action.",
                    PAGE_INFORMATIONS_LEGALES,
                )
            )
    return problemes


def _verifier_associe(a: ProjectAssociate) -> list[dict]:
    """Champs imprimés dans l'en-tête des statuts pour cet associé."""
    nom = a.nom_complet or "un associé sans nom"
    if a.type_personne == "personne_morale":
        champs = (
            ("denomination_sociale", "la dénomination"),
            ("type_societe", "la forme juridique"),
            ("capital_social", "le capital"),
            ("siege_social", "le siège social"),
            ("lieu_immatriculation", "la ville du greffe"),
            ("numero_siren", "le numéro SIREN"),
            ("representant_prenom", "le prénom du représentant"),
            ("representant_nom", "le nom du représentant"),
            ("representant_qualite", "la qualité du représentant"),
        )
    else:
        champs = (
            ("adresse", "l'adresse"),
            ("date_naissance", "la date de naissance"),
            ("lieu_naissance", "le lieu de naissance"),
            ("situation_et_regime_matrimonial", "la situation et le régime matrimonial"),
        )
    manquants = [libelle for champ, libelle in champs if _vide(getattr(a, champ))]
    problemes = []
    if manquants:
        problemes.append(
            _probleme(f"associe_{a.id}_identite", f"{nom} : renseignez {', '.join(manquants)}.", PAGE_EQUIPE_CAPITAL)
        )
    if a.type_apport == "nature" and _vide(a.description_apport_nature):
        problemes.append(
            _probleme(f"associe_{a.id}_apport_nature", f"{nom} : décrivez le bien apporté en nature.", PAGE_EQUIPE_CAPITAL)
        )
    return problemes


def _verifier_associes(associes: list[ProjectAssociate]) -> list[dict]:
    if not associes:
        return [_probleme("associes_absents", "Ajoutez au moins un associé.", PAGE_EQUIPE_CAPITAL)]
    problemes = []
    total = sum((a.pourcentage_capital or Decimal(0)) for a in associes)
    if total != Decimal(100):
        problemes.append(
            _probleme(
                "associes_total_capital",
                f"La répartition du capital doit totaliser 100 % (actuellement : {total} %).",
                PAGE_EQUIPE_CAPITAL,
            )
        )
    for a in associes:
        problemes.extend(_verifier_associe(a))
    return problemes


def prevalider_statuts(db: Session, project_id, siege_formate: str | None) -> list[dict]:
    """Liste des problèmes bloquants (vide = on peut commencer).

    `siege_formate` : adresse du siège déjà mise en forme par l'appelant
    (`_formater_siege_social` du moteur) -- passée en paramètre pour ne pas
    dupliquer cette mise en forme ni créer une dépendance circulaire."""
    profil = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project_id).first()
    associes = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == project_id)
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    president = (
        db.query(CompanyOfficer)
        .filter(CompanyOfficer.project_id == project_id, CompanyOfficer.role == "president")
        .order_by(CompanyOfficer.created_at)
        .first()
    )

    problemes = _verifier_profil_juridique(profil, siege_formate)
    problemes += _verifier_associes(associes)
    if president is None:
        problemes.append(_probleme("dirigeant_president", "Désignez le Président de la société.", PAGE_DIRIGEANTS))
    elif _vide(president.duree_fonctions):
        # Imprimée dans la nomination du premier Président (25/09/2026).
        problemes.append(
            _probleme("dirigeant_president_duree", "Renseignez la durée des fonctions du Président.", PAGE_DIRIGEANTS)
        )
    return problemes
