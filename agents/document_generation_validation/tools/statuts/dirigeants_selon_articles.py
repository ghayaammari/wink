"""Tool ① (statuts) — les dirigeants exigés par les articles inclus sont-ils
désignés sur la page Dirigeants, avec les informations imprimées (durée des
fonctions) ?

Pourquoi ici et pas seulement à la pré-validation : la pré-validation ne
connaît pas encore les choix du parcours (article DG, comité, mandat de
l'Art. 44), et un dirigeant peut avoir été modifié ou supprimé depuis.
"""
from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.outils import nombre
from agents.document_generation_validation.probleme import (
    CIBLE_PAGE,
    GRAVITE_AVERTISSEMENT,
    PAGE_DIRIGEANTS,
    Probleme,
)

NOM = "dirigeants_selon_articles"
LIBELLE = "Dirigeants exigés par les articles"

# Section de nomination -> rôle exigé (même table que `_NOMINATIONS_PAR_ROLE`
# du backend ; testée contre le clausier).
ROLE_PAR_NOMINATION = {
    "nomination_premier_president": "president",
    "nomination_premier_directeur_general": "directeur_general",
    "nomination_premiers_membres_comite": "membre_comite",
}
LIBELLES_ROLE = {
    "president": "Président",
    "directeur_general": "Directeur Général",
    "membre_comite": "Membres du Comité de Direction",
    "mandataire": "Associé mandataire (actes pendant la formation)",
}
# Avec article, pour les phrases (« Désignez le Président »).
DESIGNATION = {
    "president": "le Président",
    "directeur_general": "le Directeur Général",
    "membre_comite": "les membres du Comité de Direction",
    "mandataire": "l'associé mandataire",
}
# Clauses qui impriment l'identité du mandataire.
CLAUSES_MANDATAIRE = ("mandat_actes_societe_en_formation", "cloture_annexe_mandat")
CLAUSE_COMITE = "comite_direction"


def _page(**kwargs) -> Probleme:
    return Probleme(cible_type=CIBLE_PAGE, cible=PAGE_DIRIGEANTS, cible_libelle="Dirigeants", **kwargs)


def _manquant(role: str, libelle_article: str) -> Probleme:
    return _page(
        code=f"dirigeant_{role}_absent",
        message_court=f"{LIBELLES_ROLE[role]} non désigné",
        champ=LIBELLES_ROLE[role],
        valeur_actuelle="Non désigné",
        correction_proposee=f"Désignez {DESIGNATION[role]} sur la page Dirigeants.",
        message=(
            f"L'article « {libelle_article} » est inclus dans vos statuts et nomme {DESIGNATION[role]}. "
            "Sans désignation, les statuts afficheraient « non désigné »."
        ),
    )


def executer(contexte: ContexteValidation, precedents: list[Probleme]) -> list[Probleme]:
    roles = contexte.roles_designes()
    problemes: list[Probleme] = []

    for code_section, role in ROLE_PAR_NOMINATION.items():
        section = contexte.section(code_section)
        inclus = contexte.reponse_incluse(code_section) is not None
        if inclus and not roles.get(role):
            problemes.append(_manquant(role, section.libelle))
        elif inclus:
            premier = contexte.premier_dirigeant(role)
            if premier is not None and not (premier.duree_fonctions or "").strip():
                problemes.append(
                    _page(
                        code=f"dirigeant_{role}_duree",
                        message_court=f"Durée des fonctions : {LIBELLES_ROLE[role]}",
                        champ=f"Durée des fonctions — {premier.nom or LIBELLES_ROLE[role]}",
                        valeur_actuelle="Non renseignée",
                        correction_proposee="Renseignez la durée sur la page Dirigeants (ex. « une durée indéterminée », « 3 ans »).",
                        message=(
                            f"L'article « {section.libelle} » indique pour quelle durée {DESIGNATION[role]} "
                            "sont nommés. Sans cette information, les statuts afficheraient « durée non renseignée »."
                            if role == "membre_comite"
                            else f"L'article « {section.libelle} » indique pour quelle durée {DESIGNATION[role]} "
                            "est nommé. Sans cette information, les statuts afficheraient « durée non renseignée »."
                        ),
                    )
                )
        elif roles.get(role) and role != "president":
            problemes.append(
                _page(
                    code=f"dirigeant_{role}_sans_article",
                    message_court="Dirigeant désigné mais article absent",
                    champ=LIBELLES_ROLE[role],
                    valeur_actuelle="Désigné sur la page Dirigeants",
                    correction_proposee="Incluez l'article correspondant, ou retirez ce dirigeant de la page Dirigeants.",
                    message="Ce dirigeant est désigné, mais l'article qui le nomme n'est pas dans vos statuts : il n'y apparaîtra pas.",
                    gravite=GRAVITE_AVERTISSEMENT,
                )
            )

    mandat = contexte.section_de_clause(*CLAUSES_MANDATAIRE)
    if mandat is not None and not roles.get("mandataire"):
        problemes.append(_manquant("mandataire", mandat.libelle))

    valeurs_comite = contexte.valeurs_de_clause(CLAUSE_COMITE)
    if valeurs_comite is not None and roles.get("membre_comite"):
        minimum = nombre(valeurs_comite.get("nombre_membres_comite"))
        # Le Président fait partie du comité (« dont le Président »).
        effectif = roles.get("membre_comite", 0) + (1 if roles.get("president") else 0)
        if minimum is not None and effectif < minimum:
            problemes.append(
                _page(
                    code="dirigeant_comite_incomplet",
                    message_court="Comité de Direction incomplet",
                    champ="Membres du Comité de Direction (Président compris)",
                    valeur_actuelle=f"{effectif} désigné(s)",
                    correction_proposee=(
                        f"Ajoutez {int(minimum - effectif)} membre(s) sur la page Dirigeants, "
                        "ou baissez le nombre minimum dans l'article du Comité."
                    ),
                    message=f"Vos statuts prévoient un Comité d'au moins {minimum} membres, dont le Président.",
                )
            )
    return problemes
