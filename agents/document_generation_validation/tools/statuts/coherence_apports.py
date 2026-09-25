"""Tool ② (statuts) — la somme déposée correspond-elle au numéraire libéré ?

Le montant de chaque apport vient d'« Équipe & capital » (capital ×
pourcentage), la fraction libérée de l'Art. 6, la somme déposée et le
surplus de la section « Dépôt des fonds » : trois sources, aucune règle de
section ne peut les croiser. La bonne valeur est CERTAINE (calculée) : elle
est proposée avec « Appliquer ».
"""
from decimal import Decimal

from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.outils import euros, nombre, probleme_section
from agents.document_generation_validation.probleme import Probleme

NOM = "coherence_apports"
LIBELLE = "Cohérence des apports en numéraire"

CLAUSE_LIBERES = "apport_numeraire_liberes"
CLAUSE_NON_LIBERES = "apport_numeraire_non_liberes"
CLAUSES_DEPOT = ("depot_fonds_numeraire", "depot_fonds_surplus")
CLAUSE_SURPLUS = "depot_fonds_surplus"
_TOLERANCE = Decimal("0.01")


def _brut(v: Decimal) -> str:
    """Valeur enregistrée (format du formulaire) : « 5000 », « 1250.50 »."""
    v = v.quantize(Decimal("0.01"))
    return str(v.to_integral()) if v == v.to_integral() else str(v)


def executer(contexte: ContexteValidation, precedents: list[Probleme]) -> list[Probleme]:
    apporteurs = [a for a in contexte.associes if a.type_apport == "numeraire"]
    montants = [contexte.montant_apport(a) for a in apporteurs]
    if not apporteurs or any(m is None for m in montants):
        return []  # rien à comparer (capital ou pourcentages absents : pré-validation)
    total = sum(montants, Decimal(0))

    liberation = contexte.section_de_clause(CLAUSE_LIBERES, CLAUSE_NON_LIBERES)
    if liberation is None:
        return []
    if liberation.reponse.get("code_clause") == CLAUSE_LIBERES:
        libere, comment = total, "actions entièrement libérées"
    else:
        fraction = nombre((liberation.reponse.get("valeurs") or {}).get("fraction_libérée"))
        if fraction is None:
            return []
        libere, comment = total * fraction / 100, f"libération à {fraction.normalize()} %"

    detail = f"{euros(total)} souscrits en numéraire par {len(apporteurs)} associé(s), {comment}"
    problemes: list[Probleme] = []
    for depot in [s for s in contexte.sections if contexte.reponse_incluse(s.code_section)]:
        if depot.reponse.get("code_clause") not in CLAUSES_DEPOT:
            continue
        valeurs = depot.reponse.get("valeurs") or {}
        somme_depot = nombre(valeurs.get("somme_depot"))
        if somme_depot is not None and abs(somme_depot - libere) > _TOLERANCE:
            problemes.append(
                probleme_section(
                    depot,
                    code="apports_somme_deposee",
                    message_court="Somme déposée incorrecte",
                    champ="Somme déposée (euros)",
                    valeur_actuelle=euros(somme_depot),
                    correction_proposee=euros(libere),
                    valeur_a_appliquer={"variable": "somme_depot", "valeur": _brut(libere)},
                    message=(
                        f"La somme déposée doit être exactement la somme libérée à la constitution : {detail}, "
                        f"soit {euros(libere)}. C'est ce montant que le certificat du dépositaire atteste."
                    ),
                )
            )
        if depot.reponse.get("code_clause") == CLAUSE_SURPLUS:
            surplus = nombre(valeurs.get("somme_surplus"))
            attendu = total - libere
            if surplus is not None and abs(surplus - attendu) > _TOLERANCE:
                problemes.append(
                    probleme_section(
                        depot,
                        code="apports_surplus",
                        message_court="Somme restant à libérer incorrecte",
                        champ="Somme restant à libérer (euros)",
                        valeur_actuelle=euros(surplus),
                        correction_proposee=euros(attendu),
                        valeur_a_appliquer={"variable": "somme_surplus", "valeur": _brut(attendu)},
                        message=(
                            f"Reste à libérer = numéraire souscrit − somme libérée : {euros(total)} − {euros(libere)} "
                            f"= {euros(attendu)}."
                        ),
                    )
                )
    return problemes
