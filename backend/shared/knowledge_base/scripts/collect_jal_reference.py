"""Collecte annuelle du référentiel des journaux habilités (service 1.1.5)
-> `jal_reference`.

Lancement : `python -m backend.shared.knowledge_base.scripts.collect_jal_reference`
depuis `wink/`. À relancer chaque année (les habilitations sont annuelles,
arrêtés préfectoraux publiés en fin d'année).

Étapes :
1. pages de liste A→Z du registre actulegales.fr (`scrapers/jal_reference/`) ;
2. noms de départements -> codes (`backend/shared/utils/departements.py`) ;
   un nom inconnu est signalé, jamais deviné ;
3. upsert par fiche du journal, en `extrait_automatique` ;
4. SEULEMENT si les 27 pages ont été lues sans erreur : les journaux absents
   passent `actif=False` (une panne réseau ne doit pas désactiver la moitié
   du référentiel).

Transaction unique : tout ou rien. Ensuite : relecture humaine
(`/knowledge-base/jal-reference/...`) — seules les lignes `valide_humain` et
`actif` sont proposées aux entrepreneurs.
"""
import sys

from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.jal_reference_service import desactiver_absents, upsert_jal
from backend.shared.utils.departements import code_depuis_nom
from scrapers.jal_reference.actulegales_client import LETTRES, ActulegalesError, recuperer_journaux


def run() -> None:
    db = SessionLocal()
    urls_vues: set[str] = set()
    pages_en_erreur: list[str] = []
    noms_inconnus: set[str] = set()
    compteurs = {"crees": 0, "mis_a_jour": 0, "sans_departement": 0}
    try:
        for lettre in LETTRES:
            try:
                journaux = recuperer_journaux(lettre)
            except ActulegalesError as exc:
                print(f"  [ERREUR] lettre {lettre!r} : {exc}")
                pages_en_erreur.append(lettre)
                continue
            print(f"Lettre {lettre!r} : {len(journaux)} journal(aux).")
            for j in journaux:
                codes = []
                for nom in j.departements_noms:
                    code = code_depuis_nom(nom)
                    if code is None:
                        noms_inconnus.add(nom)
                    elif code not in codes:
                        codes.append(code)
                if not codes:
                    compteurs["sans_departement"] += 1
                    continue
                _, cree = upsert_jal(
                    db,
                    nom_journal=j.nom,
                    type_support=j.type_support,
                    departements_couverts=codes,
                    lien_site=j.lien_fiche,
                    source_url=j.lien_fiche,
                )
                urls_vues.add(j.lien_fiche)
                compteurs["crees" if cree else "mis_a_jour"] += 1

        if not urls_vues:
            raise RuntimeError(
                "Aucun journal extrait : la structure de la source a probablement changé — "
                "vérifier parser_page_liste (scrapers/jal_reference/actulegales_client.py)."
            )
        if pages_en_erreur:
            print(f"Désactivation des absents IGNORÉE : {len(pages_en_erreur)} page(s) en erreur {pages_en_erreur}.")
        else:
            print(f"{desactiver_absents(db, urls_vues)} journal(aux) absent(s) passé(s) actif=False.")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if noms_inconnus:
        print(f"⚠️ Noms de départements non reconnus (à ajouter aux alias de departements.py) : {sorted(noms_inconnus)}")
    print(f"Terminé — {compteurs}. Relecture humaine avant affichage aux entrepreneurs.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — rien n'a été écrit en base (transaction unique) : {exc}", file=sys.stderr)
        sys.exit(1)
