"""Tool ⑤ (commun) — revérifie les champs que le garde-fou juridique LLM n'a
pas pu contrôler pendant la saisie (LLM en panne : saisie acceptée, champs
notés `controle_juridique_en_attente` dans la réponse de section).

Toujours lancé (décision utilisateur), mais n'appelle le LLM que s'il reste
des champs en attente : sinon instantané. Un appel par section concernée,
avec le cache du garde-fou. LLM encore en panne -> avertissement « non
vérifié » (une panne externe ne bloque pas la génération indéfiniment).
"""
from agents.contract_agent.legal_clause_guardrail_service import LegalClauseGuardrailError
from agents.contract_agent.statuts_clause_guardrail_service import (
    check_statuts_section,
    construire_autres_valeurs,
    construire_champs,
)
from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.outils import probleme_section
from agents.document_generation_validation.probleme import GRAVITE_AVERTISSEMENT, Probleme

NOM = "controle_juridique_attente"
LIBELLE = "Contrôle juridique des champs non vérifiés"

# Garde-fou LLM par type de document. Seuls les statuts en ont un propre
# aujourd'hui ; un document absent d'ici n'a rien à revérifier.
_VERIFICATEURS = {"statuts": check_statuts_section}
CLE_EN_ATTENTE = "controle_juridique_en_attente"


def executer(contexte: ContexteValidation, precedents: list[Probleme]) -> list[Probleme]:
    verifier = _VERIFICATEURS.get(contexte.document_type)
    if verifier is None:
        return []
    noms_associes = {a.id: a.nom for a in contexte.associes}
    problemes: list[Probleme] = []

    for section in contexte.sections:
        en_attente = set(section.reponse.get(CLE_EN_ATTENTE) or [])
        if not en_attente or not contexte.reponse_incluse(section.code_section):
            continue
        clause = contexte.clauses.get(section.reponse.get("code_clause"))
        if clause is None:
            continue
        valeurs = section.reponse.get("valeurs") or {}
        variables = [v for v in clause.variables_requises if v["nom"] in en_attente or not v.get("controle_juridique")]
        champs, cibles = construire_champs(variables, valeurs, noms_associes)
        if not champs:
            continue
        try:
            resultats = verifier(
                titre_clause=clause.titre_clause,
                texte_clause=clause.texte_clause,
                champs=champs,
                autres_valeurs=construire_autres_valeurs(clause.variables_requises, valeurs),
                criteres=clause.criteres_llm,
            )
        except LegalClauseGuardrailError:
            problemes.append(
                probleme_section(
                    section,
                    code="controle_juridique_indisponible",
                    message_court="Contrôle juridique non effectué",
                    message=(
                        "Le contrôle juridique de vos formulations n'a pas pu être fait (service indisponible). "
                        "Vous pouvez réessayer plus tard, ou générer quand même et faire relire ces passages."
                    ),
                    gravite=GRAVITE_AVERTISSEMENT,
                )
            )
            continue
        valeurs_envoyees = {c["nom"]: c["valeur"] for c in champs}
        for nom, r in resultats.items():
            if r.autorise:
                continue
            _, libelle, _ = cibles[nom]
            problemes.append(
                probleme_section(
                    section,
                    code="controle_juridique_refus",
                    message_court=r.motif_court or "Formulation à revoir",
                    champ=libelle[:1].upper() + libelle[1:],
                    valeur_actuelle=valeurs_envoyees.get(nom),
                    correction_proposee=r.reformulation_proposee,
                    message=r.motif,
                    base_legale=r.article_cite,
                )
            )
    return problemes
