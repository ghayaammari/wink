"""Explications des articles facultatifs des statuts — génération par LLM puis
relecture humaine (service 1.1.4, étape 5 de la refonte du parcours,
24/09/2026). Les textes validés remplacent, sur l'écran de choix des
facultatifs, les textes provisoires de `FACULTATIFS_STATUTS`.

Trois commandes (à lancer depuis `wink/`, après `alembic upgrade head`) :

  python -m backend.entrepreneur.scripts.generate_statuts_article_explanations generer
      Génère une explication pour chacun des 11 choix de l'écran (ou un seul
      avec --code) et l'enregistre en `extrait_automatique`. N'écrase JAMAIS
      une explication déjà validée, sauf --ecraser-validees. Puis écrit le
      fichier à relire (commande `exporter`).

  python -m backend.entrepreneur.scripts.generate_statuts_article_explanations exporter
      (Ré)écrit `scripts/data/statuts_article_explications_a_relire.md` :
      chaque explication avec son statut, pour relecture.

  python -m backend.entrepreneur.scripts.generate_statuts_article_explanations valider CODE [CODE ...] [--fichier texte.txt]
  python -m backend.entrepreneur.scripts.generate_statuts_article_explanations importer [CODE ...]
      -> relecture faite directement dans le `.md` : valide ses textes (tous
      par défaut). À lancer AVANT `valider`/`generer`, qui réécrivent le `.md`.
      Marque les explications comme validées (affichées à l'utilisateur).
      Avec --fichier (un seul CODE) : remplace d'abord le texte par votre
      version corrigée.

Le texte de chaque article vient des JSON générés (`statuts_sas_clauses.json`,
`statuts_sas_document_templates.json`) — la même source que le seed. Un commit
par explication : un échec LLM sur un article ne perd pas les autres.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from agents.contract_agent.article_explanation_service import ArticleExplanationError, explain_article
from backend.entrepreneur.services.statuts_sas_renderer import DOCUMENT_TYPE_STATUTS
from backend.entrepreneur.services.statuts_sas_resolvers import FACULTATIFS_STATUTS
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services import article_explication_service as service

_DATA_DIR = Path(__file__).parent / "data"
_FICHIER_A_RELIRE = _DATA_DIR / "statuts_article_explications_a_relire.md"


def _texte_du_choix(facultatif: dict, sections: list[dict], clauses: dict[str, dict]) -> str:
    """Texte de toutes les clauses des articles du choix, dans l'ordre du
    document, avec leur titre — c'est ce que le LLM explique."""
    articles = {str(a) for a in facultatif["articles"]}
    morceaux = []
    for section in sorted(sections, key=lambda s: s["ordre"]):
        if str(section["article"]) not in articles:
            continue
        codes = section.get("variantes_candidates") or [section.get("reference_code_clause")]
        for code in codes:
            clause = clauses.get(code or "")
            if clause:
                morceaux.append(f"[{clause['titre_clause']}]\n{clause['texte_clause']}")
    return "\n\n".join(morceaux)


def _charger_json(nom: str):
    return json.loads((_DATA_DIR / nom).read_text(encoding="utf-8"))


def generer(code: str | None, ecraser_validees: bool) -> int:
    sections = _charger_json("statuts_sas_document_templates.json")
    clauses = {c["code_clause"]: c for c in _charger_json("statuts_sas_clauses.json")}
    a_traiter = [f for f in FACULTATIFS_STATUTS if code is None or f["code"] == code]
    if not a_traiter:
        print(f"Code inconnu : {code}. Codes possibles : {', '.join(f['code'] for f in FACULTATIFS_STATUTS)}")
        return 1

    echecs = 0
    db = SessionLocal()
    try:
        for f in a_traiter:
            texte_article = _texte_du_choix(f, sections, clauses)
            titre = f"{f['titre']} (Art. {' et '.join(f['articles'])})"
            try:
                explication = explain_article(DOCUMENT_TYPE_STATUTS, titre, texte_article)
            except ArticleExplanationError as exc:
                echecs += 1
                print(f"  ÉCHEC  {f['code']} : {exc}")
                continue
            _, ecrite = service.upsert_generee(
                db,
                document_type=DOCUMENT_TYPE_STATUTS,
                code_facultatif=f["code"],
                texte=explication,
                ecraser_validee=ecraser_validees,
            )
            db.commit()
            print(f"  {'généré ' if ecrite else 'conservé'} {f['code']}" + ("" if ecrite else " (déjà validé)"))
    finally:
        db.close()
    exporter()
    return 1 if echecs else 0


def exporter() -> int:
    db = SessionLocal()
    try:
        par_code = {e.code_facultatif: e for e in service.list_all(db, document_type=DOCUMENT_TYPE_STATUTS)}
    finally:
        db.close()
    lignes = [
        "# Explications des articles facultatifs — à relire",
        "",
        "Valider : `python -m backend.entrepreneur.scripts.generate_statuts_article_explanations valider CODE`",
        "Corriger puis valider : corriger le texte ici, puis `importer` (tous) ou `importer CODE…` — AVANT tout `valider`/`generer`, qui réécrivent ce fichier",
        "",
    ]
    for f in FACULTATIFS_STATUTS:
        e = par_code.get(f["code"])
        statut = e.statut_contenu if e else "absent (à générer)"
        lignes += [f"## {f['titre']} — Art. {' et '.join(f['articles'])}", f"Code : `{f['code']}` — statut : **{statut}**", ""]
        lignes += [e.texte if e else "_(pas encore généré — l'écran affiche le texte provisoire)_", ""]
    _FICHIER_A_RELIRE.write_text("\n".join(lignes), encoding="utf-8")
    print(f"Fichier à relire : {_FICHIER_A_RELIRE}")
    return 0


def valider(codes: list[str], fichier: str | None) -> int:
    if fichier and len(codes) != 1:
        print("--fichier ne s'utilise qu'avec un seul CODE.")
        return 1
    texte_corrige = Path(fichier).read_text(encoding="utf-8") if fichier else None
    db = SessionLocal()
    try:
        for code in codes:
            try:
                service.valider(db, document_type=DOCUMENT_TYPE_STATUTS, code_facultatif=code, texte_corrige=texte_corrige)
            except LookupError as exc:
                db.rollback()
                print(f"  {exc}")
                return 1
            print(f"  validé {code}")
        db.commit()
    finally:
        db.close()
    exporter()
    return 0


_MOTIF_SECTION_MD = re.compile(r"^Code : `([a-z_]+)` — statut : .*?\n\n(.*?)(?=\n+## |\Z)", re.S | re.M)


def _textes_du_fichier_relu() -> dict[str, str]:
    """{code_facultatif: texte} lus dans le fichier `.md` relu (sections
    produites par `exporter`). Les sections encore vides (placeholder) sont
    ignorées."""
    contenu = _FICHIER_A_RELIRE.read_text(encoding="utf-8")
    return {
        code: texte.strip()
        for code, texte in _MOTIF_SECTION_MD.findall(contenu)
        if texte.strip() and not texte.strip().startswith("_(")
    }


def importer(codes: list[str]) -> int:
    """Relecture faite directement dans le `.md` : enregistre chaque texte du
    fichier comme validé (tous les codes du fichier, ou seulement `codes`).
    Tout ou rien : une erreur annule l'ensemble. À lancer AVANT tout
    `valider`/`generer`, qui réécrivent le `.md` depuis la base."""
    textes = _textes_du_fichier_relu()
    inconnus = [c for c in codes if c not in textes]
    if inconnus:
        print(f"Absents du fichier relu : {', '.join(inconnus)}")
        return 1
    a_importer = {c: textes[c] for c in (codes or textes)}
    db = SessionLocal()
    try:
        for code, texte in a_importer.items():
            try:
                service.valider(db, document_type=DOCUMENT_TYPE_STATUTS, code_facultatif=code, texte_corrige=texte)
            except LookupError as exc:
                db.rollback()
                print(f"  {exc} — rien n'a été enregistré.")
                return 1
            print(f"  validé {code}")
        db.commit()
    finally:
        db.close()
    exporter()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = parser.add_subparsers(dest="commande", required=True)
    p_gen = sous.add_parser("generer")
    p_gen.add_argument("--code", help="un seul choix (ex. droit_preemption)")
    p_gen.add_argument("--ecraser-validees", action="store_true", help="régénère aussi les explications déjà validées")
    sous.add_parser("exporter")
    p_val = sous.add_parser("valider")
    p_val.add_argument("codes", nargs="+")
    p_val.add_argument("--fichier", help="texte corrigé (un seul CODE)")
    p_imp = sous.add_parser("importer", help="valide les textes corrigés directement dans le .md relu")
    p_imp.add_argument("codes", nargs="*", help="par défaut : tous les codes du fichier")
    args = parser.parse_args()

    if args.commande == "generer":
        return generer(args.code, args.ecraser_validees)
    if args.commande == "exporter":
        return exporter()
    if args.commande == "importer":
        return importer(args.codes)
    return valider(args.codes, args.fichier)


if __name__ == "__main__":
    sys.exit(main())
