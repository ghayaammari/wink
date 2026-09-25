"""Extraction brute (Phase 0 — préparation), service 1.1.4 générateur de statuts
guidé (SAS uniquement, v1 — décision actée avec l'utilisateur le 22/09/2026).

Source : "Modèle gratuit de statuts de SAS" — Bpifrance Création
(https://bpifrance-creation.fr/boiteaoutils/modele-gratuit-statuts-sas), même
éditeur que le modèle de pacte de fondateurs déjà utilisé pour 1.1.13. À la
différence du pacte, Bpifrance ne propose ce modèle qu'en **PDF**, pas en
`.docx` (vérifié le 22/09/2026) — ce script utilise donc `pypdf`, pas
`python-docx`. Dépendance déjà présente dans `requirements.txt`
(`backend/chercheur/services/research_extraction_service.py`,
`scrapers/shared/web_fetch.py`), réutilisée à l'identique (`PdfReader` +
`page.extract_text()`) plutôt que d'introduire une lib supplémentaire.

Lancement (une fois), depuis `wink/` :

    python -m backend.shared.knowledge_base.scripts.extract_statuts_sas_raw \
        --source "<chemin vers le .pdf Modèle de statuts de SAS Bpifrance>" \
        --label modele_sas

DIFFÉRENCE STRUCTURELLE IMPORTANTE avec `extract_pacte_fondateurs_raw.py`
(donc DETTE TECHNIQUE ASSUMÉE, pas cachée, pour la suite du pipeline) :
`python-docx` donne un paragraphe logique par entrée (une phrase complète
même si elle prend 3 lignes à l'écran). `pypdf.extract_text()` ne rend que
des LIGNES VISUELLES : une phrase qui prend 2 lignes dans le PDF ressort en 2
entrées séparées, sans blanc ni marqueur qui dise "ceci est la suite de la
phrase précédente". Reconstruire le paragraphe logique ici, par heuristique
(ex. "une ligne qui ne finit pas par un point continue sur la suivante"),
serait deviner silencieusement — exactement l'erreur qui a coûté une reprise
complète sur le pacte de fondateurs (voir recap 1.1.13, 20/09/2026). Donc :
une ligne pypdf = une entrée `paragraphes`, point final. La Phase 1
(segmentation par `Article <n>` / `›` / `+` / `Ou`, prochaine étape) n'a de
toute façon besoin que du DÉBUT de chaque ligne pour détecter ses marqueurs —
elle fonctionne très bien sur des lignes plus fines que des paragraphes
complets. Recoller les lignes en phrases, si nécessaire, sera une décision à prendre
EN RELISANT le résultat réel (Phase 1b, comme pour le pacte), pas devinée ici.

FILTRAGE DU BRUIT DE MISE EN PAGE : chaque page du PDF répète un même bloc
en-tête/pied de page (mention légale + numéro de page). Détecté PAR
FRÉQUENCE : toute ligne identique (après strip) présente sur au moins 80 %
des pages est classée comme répétition de mise en page, PAS supprimée mais
sortie dans `lignes_repetees_exclues` (séparé de `paragraphes`) — vérifiable,
jamais un filtrage silencieux. Volontairement pas un motif codé en dur sur le
texte français exact (fragile si Bpifrance change la formulation) : la
détection par fréquence generalise à n'importe quel document paginé de même
structure. Une ligne "numéro de page seul" (`^\\d+/\\d+$`) est filtrée par le
même mécanisme, elle finit de toute façon dans le lot des lignes répétées
(le numérateur change, mais `/35` est commun — en réalité chaque ligne
"N/35" est UNIQUE par page donc ne passe PAS le seuil de fréquence : filtrée
séparément, explicitement, par un second motif dédié).

N'écrit RIEN en base — voir la docstring de `extract_pacte_fondateurs_raw.py`
pour le raisonnement complet (fidélité vérifiable avant tout découpage).
"""
import argparse
import io
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

_OUTPUT_DIR = Path(__file__).parent / "data" / "statuts_sas_raw"
_PAGE_NUMBER_RE = re.compile(r"^\d+\s*/\s*\d+$")
_REPETITION_THRESHOLD = 0.8  # une ligne présente sur >= 80% des pages = bruit de mise en page


def extract_raw(source_path: str, label: str) -> Path:
    with open(source_path, "rb") as f:
        reader = PdfReader(io.BytesIO(f.read()))

    # Passe 1 — lire chaque page, ligne par ligne, sans rien filtrer encore.
    lignes_brutes: list[dict] = []  # {index, page, texte}
    index = 0
    for page_num, page in enumerate(reader.pages, start=1):
        texte_page = page.extract_text() or ""
        for ligne in texte_page.split("\n"):
            stripped = ligne.strip()
            if stripped == "":
                # Ligne blanche = artefact de mise en page pypdf, aucun contenu —
                # même raisonnement que les paragraphes vides filtrés côté docx.
                index += 1
                continue
            lignes_brutes.append({"index": index, "page": page_num, "texte": stripped})
            index += 1

    # Passe 2 — détecter les lignes répétées sur la quasi-totalité des pages
    # (en-tête/pied de page), par fréquence, pas par motif codé en dur.
    nb_pages = len(reader.pages)
    occurrences_par_page: dict[str, set[int]] = {}
    for ligne in lignes_brutes:
        occurrences_par_page.setdefault(ligne["texte"], set()).add(ligne["page"])
    textes_repetes = {
        texte
        for texte, pages in occurrences_par_page.items()
        if len(pages) / nb_pages >= _REPETITION_THRESHOLD
    }

    paragraphes = []
    lignes_repetees_exclues = []
    for ligne in lignes_brutes:
        est_numero_page = bool(_PAGE_NUMBER_RE.match(ligne["texte"]))
        est_repetition = ligne["texte"] in textes_repetes
        if est_numero_page or est_repetition:
            lignes_repetees_exclues.append({**ligne, "motif": "numero_page" if est_numero_page else "repetition_frequente"})
        else:
            paragraphes.append(ligne)

    # pypdf n'expose aucune table structurée comparable à python-docx —
    # non extrait ici (dette technique assumée) : le seul tableau visible
    # dans ce modèle (récapitulatif des apports, Article 6.3) est court et
    # sera saisi/vérifié à la main en Phase 1b si besoin, pas une table de
    # données répétitive comme pourrait l'être une répartition du capital.
    tables: list = []

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outpath = _OUTPUT_DIR / f"raw_{label}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "source_file": label,
                "nb_pages": nb_pages,
                "paragraphes": paragraphes,
                "lignes_repetees_exclues": lignes_repetees_exclues,
                "tables": tables,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return outpath


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Chemin vers le fichier .pdf source.")
    parser.add_argument(
        "--label",
        required=True,
        help="Nom court identifiant la source (ex: modele_sas) — "
        "détermine le nom du fichier de sortie raw_<label>.json.",
    )
    args = parser.parse_args()

    outpath = extract_raw(args.source, args.label)
    with open(outpath, encoding="utf-8") as f:
        data = json.load(f)
    print(
        f"OK — {data['nb_pages']} page(s), {len(data['paragraphes'])} ligne(s) de contenu, "
        f"{len(data['lignes_repetees_exclues'])} ligne(s) de mise en page exclue(s) -> {outpath}"
    )


if __name__ == "__main__":
    main()
