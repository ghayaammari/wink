"""Tool ③ (statuts) — les dates saisies dans différentes sections sont-elles
dans le bon ordre par rapport à la date de signature ?

Les statuts constatent des faits déjà accomplis (dépôt des fonds,
certificat du dépositaire, rapport du commissaire aux apports) : ils ne
peuvent pas être datés après la signature. Le 1er exercice, lui, se clôt
forcément après.
"""
from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.outils import date_iso, jj_mm_aaaa, probleme_section
from agents.document_generation_validation.probleme import Probleme

NOM = "chronologie_dates"
LIBELLE = "Chronologie des dates"

CLAUSE_SIGNATURE = "cloture_fait_a_signature"
# (clauses, variable, libellé) : dates qui doivent précéder la signature.
AVANT_SIGNATURE = (
    (("depot_fonds_numeraire", "depot_fonds_surplus"), "date_depot", "Date du dépôt des fonds"),
    (("apport_numeraire_non_liberes",), "date_certificat", "Date du certificat du dépositaire"),
    (("commissaire_apports_unanimite", "commissaire_apports_ordonnance"), "date_rapport", "Date du rapport du commissaire aux apports"),
    (("commissaire_apports_unanimite",), "date_designation", "Date de désignation du commissaire aux apports"),
    (("commissaire_apports_ordonnance",), "date_ordonnance", "Date de l'ordonnance de désignation du commissaire"),
)
CLAUSE_EXERCICE = "exercice_hors_annee_civile"


def executer(contexte: ContexteValidation, precedents: list[Probleme]) -> list[Probleme]:
    valeurs_signature = contexte.valeurs_de_clause(CLAUSE_SIGNATURE)
    signature = date_iso((valeurs_signature or {}).get("date_signature"))
    if signature is None:
        return []
    problemes: list[Probleme] = []

    for clauses, variable, libelle in AVANT_SIGNATURE:
        for section in contexte.sections:
            if not contexte.reponse_incluse(section.code_section) or section.reponse.get("code_clause") not in clauses:
                continue
            d = date_iso((section.reponse.get("valeurs") or {}).get(variable))
            if d is not None and d > signature:
                problemes.append(
                    probleme_section(
                        section,
                        code=f"chronologie_{variable}",
                        message_court=f"{libelle} postérieure à la signature",
                        champ=libelle,
                        valeur_actuelle=jj_mm_aaaa(d),
                        correction_proposee=(
                            f"Une date au plus tard le {jj_mm_aaaa(signature)} (date de signature), "
                            "ou repoussez la date de signature dans la clôture des statuts."
                        ),
                        message=(
                            "Les statuts constatent un fait déjà accompli au moment où ils sont signés : "
                            "cette date ne peut pas être après la signature."
                        ),
                    )
                )

    exercice = contexte.section_de_clause(CLAUSE_EXERCICE)
    if exercice is not None:
        cloture = date_iso((exercice.reponse.get("valeurs") or {}).get("date_cloture_premier_exercice"))
        if cloture is not None and cloture <= signature:
            problemes.append(
                probleme_section(
                    exercice,
                    code="chronologie_premier_exercice",
                    message_court="Clôture du 1er exercice avant la signature",
                    champ="Date de clôture du premier exercice",
                    valeur_actuelle=jj_mm_aaaa(cloture),
                    correction_proposee=(
                        f"Une date après le {jj_mm_aaaa(signature)} (date de signature), "
                        f"par exemple le 31/12/{signature.year + 1}."
                    ),
                    message=(
                        "Le premier exercice commence à l'immatriculation de la société, après la signature des "
                        "statuts : il ne peut pas se terminer avant, ni le jour même."
                    ),
                )
            )
    return problemes
