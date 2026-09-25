"""SCRIPT JETABLE (25/09/2026) — à supprimer après exécution.

Met à jour UNIQUEMENT la colonne `variables_requises` des clauses des statuts
en base, depuis `data/statuts_sas_clauses.json` (régénéré), SANS relancer le
seed ni recalculer les embeddings.

Pourquoi c'est sûr : les embeddings sont calculés sur le TEXTE des clauses
(`texte_clause`), pas sur leurs variables. Le script refuse donc toute clause
dont le texte, le titre ou la description en base diffère du JSON : dans ce
cas, l'embedding serait périmé et il faudrait le vrai seed.

Contexte : ajout de `si_article_absent` sur les 14 renvois d'article
(service 1.1.4) — aucun texte modifié.

Usage (depuis wink/) :
    python -m backend.entrepreneur.scripts.jetable_maj_variables_statuts          # aperçu, rien n'est écrit
    python -m backend.entrepreneur.scripts.jetable_maj_variables_statuts --ecrire # applique
"""
import json
import sys
from pathlib import Path

from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.models.contract_clause_library import ContractClauseLibrary

DOCUMENT_TYPE = "statuts"
CLAUSES_JSON = Path(__file__).parent / "data" / "statuts_sas_clauses.json"


def main() -> None:
    ecrire = "--ecrire" in sys.argv
    clauses = json.loads(CLAUSES_JSON.read_text(encoding="utf-8"))
    db = SessionLocal()
    a_jour, refusees, absentes, inchangees = [], [], [], 0
    try:
        for c in clauses:
            ligne = (
                db.query(ContractClauseLibrary)
                .filter(
                    ContractClauseLibrary.document_type == DOCUMENT_TYPE,
                    ContractClauseLibrary.code_clause == c["code_clause"],
                )
                .first()
            )
            if ligne is None:
                absentes.append(c["code_clause"])
                continue
            if (ligne.texte_clause, ligne.titre_clause) != (c["texte_clause"], c["titre_clause"]):
                refusees.append(c["code_clause"])
                continue
            if ligne.variables_requises == c["variables_requises"]:
                inchangees += 1
                continue
            a_jour.append(c["code_clause"])
            if ecrire:
                ligne.variables_requises = c["variables_requises"]
        if ecrire and not refusees and not absentes:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()

    print(f"Inchangées : {inchangees}")
    print(f"À mettre à jour ({len(a_jour)}) : {', '.join(a_jour) or '-'}")
    if refusees:
        print(f"REFUSÉ -- texte/titre différent en base (seed complet nécessaire) : {', '.join(refusees)}")
    if absentes:
        print(f"REFUSÉ -- absentes en base (seed complet nécessaire) : {', '.join(absentes)}")
    if refusees or absentes:
        print("Rien n'a été écrit.")
    elif ecrire:
        print("Écrit en base.")
    else:
        print("Aperçu seulement : relancez avec --ecrire pour appliquer.")


if __name__ == "__main__":
    main()
