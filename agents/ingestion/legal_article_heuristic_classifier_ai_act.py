"""Classification heuristique (sans LLM, sauf residu ambigu renvoye au LLM
existant) des articles AI Act (service 3.3.12) — CORRECTIF du 19/09/2026
suite a 3 echecs reels de quota Groq (TPD) en tentant de classifier les 119
articles entierement par LLM (voir historique complet dans
collect_ai_act_articles.py et legal_text_structuring_service_ai_act.py).

Contrairement au RGPD (sous-themes disperses sans structure exploitable,
d'ou le besoin reel d'une heuristique par mots-cles ou d'un LLM), la
categorie de risque AI Act EST LA STRUCTURE OFFICIELLE DU REGLEMENT : chaque
Titre du texte correspond exactement a un des niveaux de risque cherches.
La categorie_risque est donc un FAIT STRUCTUREL deductible du numero
d'article, jamais une deduction semantique — un LLM n'y ajoute aucune valeur
et peut au contraire se tromper la ou le texte lui-meme ne laisse aucun
doute. Plages utilisees (deja presentees et non contestees dans les echanges
avec l'utilisatrice, structure officielle du reglement (UE) 2024/1689) :
  Titre II  (art. 5)      -> interdit (pratiques interdites)
  Titre III (art. 6-49)   -> haut_risque (systemes a haut risque)
  Titre IV  (art. 50)     -> risque_limite (transparence)
  Titre V   (art. 51-56)  -> gouvernance_gpai (modeles a usage general)
  Tout le reste (Titres I, VI a XII, art. 1-4 et 57+) -> minimal — regroupe
  dispositions generales/definitions ET gouvernance/sanctions/dispositions
  finales : aucune de ces sections n'appartient a un regime de risque
  specifique, donc pas besoin de connaitre le decoupage exact des Titres VI
  a XII un par un pour rester correct.

Seule la PERTINENCE (utile ou non a un entrepreneur) reste une vraie
question de jugement pour les articles a partir de _DEBUT_ZONE_AMBIGUE
(gouvernance/marche/sanctions/dispositions finales) : certains sont tres
pertinents (ex: sanctions/amendes), d'autres purement administratifs
(composition d'un comite, modele de notification, date d'entree en
vigueur). Ceux non tranches par le filtre de mots-cles ci-dessous partent en
verification LLM PAR LOT (voir collect_ai_act_articles.py) — pas les 119
articles, seulement ce sous-ensemble restreint. La categorie_risque n'est
JAMAIS demandee au LLM pour ces articles : elle reste "minimal" quoi que le
LLM reponde, puisque c'est un fait structurel, pas une opinion — seul son
jugement sur "pertinent" est retenu.
"""
import re
from typing import Literal

from agents.ingestion.legal_text_structuring_service_ai_act import CategorieRisqueAIAct

# Bornes utilisees (voir docstring module) — (debut, fin_inclus, categorie).
# Toute plage non listee (57 et au-dela, y compris "bis"/lettres) -> minimal.
_PLAGES_CATEGORIE_RISQUE: list[tuple[int, int, CategorieRisqueAIAct]] = [
    (5, 5, "interdit"),
    (6, 49, "haut_risque"),
    (50, 50, "risque_limite"),
    (51, 56, "gouvernance_gpai"),
]

_NUMERO_BASE_RE = re.compile(r"^(\d+)")


def _numero_de_base(article_numero: str) -> int | None:
    """"50" -> 50, "4 bis" -> 4 (rattache au Titre de l'article de base, pas
    un Titre a part : un article insere par amendement prolonge la section
    qui le contient, il ne cree pas une nouvelle categorie)."""
    match = _NUMERO_BASE_RE.match(article_numero.strip())
    return int(match.group(1)) if match else None


def classify_categorie_risque_heuristique(article_numero: str) -> CategorieRisqueAIAct:
    numero = _numero_de_base(article_numero)
    if numero is not None:
        for debut, fin, categorie in _PLAGES_CATEGORIE_RISQUE:
            if debut <= numero <= fin:
                return categorie
    return "minimal"


# Articles purement procoduraux/administratifs (pas de fond utile a un
# entrepreneur) : entree en vigueur, abrogation, delais de transposition,
# clauses de reexamen. Meme logique que legal_article_heuristic_classifier_rgpd.py.
_MOTIFS_NON_PERTINENTS = (
    "entre en vigueur",
    "entrent en vigueur",
    "est abrogé",
    "est abrogée",
    "sont abrogés",
    "sont abrogées",
    "au plus tard le",
    "la commission réexamine",
    "la commission évalue et fait rapport",
    "notifient à la commission",
)

_LONGUEUR_MIN_PERTINENT = 40

# A partir de ce numero (Titres VI a XII : gouvernance, marche, sanctions,
# dispositions finales), un article "minimal" non tranche par les mots-cles
# ci-dessus part en verification LLM plutot que d'etre suppose pertinent par
# defaut — voir docstring module, seule vraie zone de jugement restante.
_DEBUT_ZONE_AMBIGUE = 57


def evaluer_pertinence_heuristique(
    article_numero: str, texte_brut: str
) -> Literal["pertinent", "non_pertinent", "ambigu"]:
    texte_normalise = texte_brut.strip().lower()

    if len(texte_normalise) < _LONGUEUR_MIN_PERTINENT:
        return "non_pertinent"
    if any(motif in texte_normalise for motif in _MOTIFS_NON_PERTINENTS):
        return "non_pertinent"

    numero = _numero_de_base(article_numero)
    if numero is not None and numero < _DEBUT_ZONE_AMBIGUE:
        # Titres I a V : toujours substantiel (definitions, interdictions,
        # exigences haut risque, transparence, GPAI) — jamais purement
        # administratif, pas besoin d'un appel LLM.
        return "pertinent"

    # CORRECTIF du 19/09/2026 (suite a un test reel sur le texte complet) :
    # cette zone (Titre VI et au-dela, non tranchee par les mots-cles
    # ci-dessus) represente 54 des 119 articles — trop pour router au LLM
    # sans retomber dans la meme crise de quota Groq (voir historique dans
    # collect_ai_act_articles.py). Traitee "pertinent" par defaut plutot que
    # "ambigu" : le risque d'erreur ici est d'inclure un article purement
    # administratif dans le corpus RAG (un chunk de plus, sans consequence
    # juridique), pas d'affirmer un fait faux — contrairement a
    # categorie_risque qui, elle, reste garantie exacte par la structure du
    # texte quel que soit ce choix. Le code de verification LLM
    # (classify_articles_batch, voir collect_ai_act_articles.py) reste en
    # place mais n'est plus appele sur ce chemin — reactivable en repassant
    # cette branche a "ambigu" si un besoin de filtrage plus fin se confirme
    # une fois le quota Groq disponible sans contrainte.
    return "pertinent"


_LONGUEUR_SEUIL_PAR_ALINEA = 800
_MARQUEURS_ALINEA = ("\n1°", "\n2°", "\nI.-", "\nII.-", "\na)", "\nb)", " a) ", " b) ")

ChunkingSuggere = Literal["aucun", "par_alinea"]


def chunking_suggere_heuristique(texte_brut: str) -> ChunkingSuggere:
    contient_marqueur = any(marqueur in texte_brut for marqueur in _MARQUEURS_ALINEA)
    return "par_alinea" if len(texte_brut) > _LONGUEUR_SEUIL_PAR_ALINEA or contient_marqueur else "aucun"
