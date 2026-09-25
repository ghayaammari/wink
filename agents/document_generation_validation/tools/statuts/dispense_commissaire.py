"""Tool ④ (statuts) — la dispense de commissaire aux apports (L. 227-1)
est-elle permise ?

Conditions cumulatives (art. L. 227-1 al. 4 et D. 227-3 du Code de
commerce) : décision unanime (écrite dans la clause), aucun apport en
nature de plus de 30 000 €, et total des apports en nature non évalués ≤
moitié du capital. Les montants viennent d'« Équipe & capital ».
"""
from decimal import Decimal

from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.outils import euros, probleme_section
from agents.document_generation_validation.probleme import Probleme

NOM = "dispense_commissaire"
LIBELLE = "Dispense de commissaire aux apports"

CLAUSE_DISPENSE = "dispense_commissaire_apports_l227_1"
SEUIL_PAR_APPORT = Decimal(30000)
BASE_LEGALE = "Art. L. 227-1 al. 4 et D. 227-3 du Code de commerce"


def executer(contexte: ContexteValidation, precedents: list[Probleme]) -> list[Probleme]:
    section = contexte.section_de_clause(CLAUSE_DISPENSE)
    if section is None or contexte.capital_social is None:
        return []
    apports = [(a, contexte.montant_apport(a)) for a in contexte.associes if a.type_apport == "nature"]
    apports = [(a, m) for a, m in apports if m is not None]
    problemes: list[Probleme] = []

    trop_eleves = [(a, m) for a, m in apports if m > SEUIL_PAR_APPORT]
    if trop_eleves:
        detail = ", ".join(f"{a.nom} : {euros(m)}" for a, m in trop_eleves)
        problemes.append(
            probleme_section(
                section,
                code="dispense_apport_superieur_seuil",
                message_court="Dispense de commissaire impossible",
                champ="Évaluation des apports en nature",
                valeur_actuelle="Dispense de commissaire aux apports (L. 227-1)",
                correction_proposee="Choisissez la désignation d'un commissaire aux apports (à l'unanimité ou par ordonnance).",
                message=f"La dispense n'est possible que si aucun apport en nature ne dépasse 30 000 €. Ici : {detail}.",
                base_legale=BASE_LEGALE,
            )
        )

    total = sum((m for _, m in apports), Decimal(0))
    moitie = contexte.capital_social / 2
    if total > moitie:
        problemes.append(
            probleme_section(
                section,
                code="dispense_total_superieur_moitie",
                message_court="Dispense de commissaire impossible",
                champ="Évaluation des apports en nature",
                valeur_actuelle="Dispense de commissaire aux apports (L. 227-1)",
                correction_proposee="Choisissez la désignation d'un commissaire aux apports (à l'unanimité ou par ordonnance).",
                message=(
                    f"Total des apports en nature : {euros(total)}, pour un capital de {euros(contexte.capital_social)}. "
                    f"La dispense exige que ce total ne dépasse pas la moitié du capital ({euros(moitie)})."
                ),
                base_legale=BASE_LEGALE,
            )
        )
    return problemes
