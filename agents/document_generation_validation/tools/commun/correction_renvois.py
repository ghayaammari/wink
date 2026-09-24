"""Tool (commun, lancé EN PREMIER) — corrige le texte des clauses qui
renvoient à un article absent des statuts (25/09/2026).

Décision utilisateur : ce problème vient de notre clausier, pas de
l'utilisateur -> rien ne lui est montré. Le tool :
- adapte le texte quand le clausier prévoit un remplacement exact
  (`si_article_absent` mode « texte » : `remplace` -> `par`, texte relu,
  sans LLM) ;
- ne supprime JAMAIS une clause ni un article ;
- sinon, laisse le texte tel quel.
Les corrections sont appliquées par le backend au document FINAL
uniquement (`finalize_session`), jamais pendant la rédaction.

Seul tool qui écrit dans le contexte (`corrections_texte`) ; il ne renvoie
aucun problème.
"""
from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.probleme import Probleme

NOM = "correction_renvois"
LIBELLE = "Correction des renvois d'articles"


def executer(contexte: ContexteValidation, precedents: list[Probleme]) -> list[Probleme]:
    if contexte.articles_presents is None:
        return []
    for section in contexte.sections:
        if contexte.reponse_incluse(section.code_section) is None:
            continue
        clause = contexte.clauses.get(section.reponse.get("code_clause"))
        if clause is None:
            continue
        for v in clause.variables_requises:
            regle = v.get("si_article_absent") or {}
            article = v.get("article_cible")
            if regle.get("mode") != "texte" or article is None or str(article) in contexte.articles_presents:
                continue
            if regle.get("remplace") and regle["remplace"] in clause.texte_clause:
                contexte.corrections_texte.append(
                    {"code_section": section.code_section, "remplace": regle["remplace"], "par": regle.get("par", "")}
                )
    return []
