"""Script 0 (correction méthodologique, service 1.1.13, 21/09/2026) : regroupe
les segments de `segmented_modele_principal.json` par ARTICLE RÉEL, au lieu de
les laisser fragmentés.

Pourquoi ce script existe : `segment_pacte_fondateurs_articles.py` (script
précédent) découpe en segments à chaque changement de type de paragraphe
détecté (titre d'article vs note explicative Bpifrance) -- résultat, un même
article peut apparaître dans PLUSIEURS segments non contigus quand des notes
explicatives ("annotation") s'intercalent au milieu de son texte (cas de
l'Article 3 : 10 segments `titre_article=3` séparés par des `annotation`).
Aucun fichier existant ne recolle ces morceaux en un texte d'article continu
-- ce script le fait, mécaniquement, sans interpréter le contenu.

Règle de regroupement (déterministe, pas de devinette sur le sens) :
  - on parcourt les segments dans leur ORDRE D'ORIGINE dans le .docx ;
  - un segment `titre_article` : ses paragraphes s'ajoutent à la liste de
    l'article `article_numero` correspondant (créée si besoin) ;
  - un segment `annotation` : ses paragraphes s'ajoutent à la liste
    `annotations` du DERNIER article rencontré (les notes Bpifrance suivent
    toujours immédiatement le texte qu'elles commentent) -- gardées à part,
    jamais mélangées au texte opérant, pour qu'on ne les recopie jamais par
    erreur dans une clause finale ;
  - le premier segment (`hors_marqueur`, avant tout article numéroté) mélange
    3 choses distinctes : titre + avertissement Bpifrance, identification des
    parties (déjà gérée ailleurs dans l'appli, pas à reprendre ici), et le
    vrai Préambule. Séparé ici au paragraphe qui commence par "Préambule" --
    seul point de ce script qui repose sur un repère textuel plutôt que
    purement structurel, signalé explicitement en sortie (voir "cesure_manuelle").

Sortie : `articles_consolides_modele_principal.json`, une entrée par article
(clé `"entete"` pour la partie ignorée, `"preambule"`, puis `1` à `10`), avec
tous ses paragraphes dans l'ordre d'origine + ses annotations séparées.
Rien n'est perdu : nb paragraphes en sortie == nb paragraphes en entrée
(vérifié en fin de script).
"""
import json
from pathlib import Path

SRC = Path("backend/shared/knowledge_base/scripts/data/pacte_fondateurs/segmented_modele_principal.json")
DST = Path("backend/shared/knowledge_base/scripts/data/pacte_fondateurs/articles_consolides_modele_principal.json")


def split_hors_marqueur(paragraphes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Sépare le segment hors_marqueur en (entete, preambule) au paragraphe
    qui commence le vrai Préambule. Seul repère textuel du script, isolé ici
    pour rester visible et auditable plutôt que noyé dans la boucle générale.
    """
    for i, p in enumerate(paragraphes):
        if p["texte"].strip().lower().startswith("préambule"):
            return paragraphes[:i], paragraphes[i:]
    print("ATTENTION : paragraphe 'Préambule' introuvable dans le segment hors_marqueur -- vérifier manuellement.")
    return paragraphes, []


def main() -> None:
    with SRC.open(encoding="utf-8") as f:
        data = json.load(f)
    segments = data["segments"]

    articles: dict = {}

    def get_article(key):
        if key not in articles:
            articles[key] = {"article": key, "paragraphes": [], "annotations": []}
        return articles[key]

    current_key = None
    nb_paragraphes_source = 0

    for seg in segments:
        nb_paragraphes_source += len(seg["paragraphes"])

        if seg["type"] == "hors_marqueur":
            entete, preambule = split_hors_marqueur(seg["paragraphes"])
            get_article("entete")["paragraphes"].extend(entete)
            get_article("preambule")["paragraphes"].extend(preambule)
            current_key = "preambule"
            continue

        if seg["type"] == "titre_article":
            key = seg["article_numero"]
            get_article(key)["paragraphes"].extend(seg["paragraphes"])
            current_key = key
            continue

        if seg["type"] == "annotation":
            if current_key is None:
                print("ATTENTION : annotation rencontrée avant le premier article -- ignorée, à vérifier.")
                continue
            get_article(current_key)["annotations"].extend(seg["paragraphes"])
            continue

        print(f"ATTENTION : type de segment inconnu '{seg['type']}' -- ignoré, à vérifier.")

    ordre = ["entete", "preambule"] + list(range(1, 11))
    result = {
        "source_file": data.get("source_file"),
        "articles": [articles[k] for k in ordre if k in articles],
    }

    nb_paragraphes_sortie = sum(
        len(a["paragraphes"]) + len(a["annotations"]) for a in result["articles"]
    )
    assert nb_paragraphes_sortie == nb_paragraphes_source, (
        f"Incohérence : {nb_paragraphes_source} paragraphes en entrée, {nb_paragraphes_sortie} en sortie."
    )

    DST.parent.mkdir(parents=True, exist_ok=True)
    with DST.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"OK -- {len(result['articles'])} entrées, {nb_paragraphes_sortie} paragraphes au total (vérifié).")
    for a in result["articles"]:
        print(f"  - {a['article']}: {len(a['paragraphes'])} paragraphes opérants, {len(a['annotations'])} annotations")


if __name__ == "__main__":
    main()
