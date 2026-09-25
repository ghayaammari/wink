"""Classification heuristique (ZÉRO appel LLM) des articles MDR (service

3.3.6, volet HealthTech) — décision actée le 20/09/2026 : collecte du texte
MDR entier (potentiellement 100+ articles, même ordre de grandeur que l'AI
Act, voir historique de quota dans collect_ai_act_articles.py).

Contrairement à l'AI Act, ce fichier NE PROPOSE PAS de catégorie_risque par
plage d'articles : la découpe exacte des chapitres du MDR (Titre/Chapitre ->
articles) n'a pas été vérifiée sur le texte réel (voir texte_mdr.py, CELEX
non confirmé) — inventer des bornes numériques non vérifiées serait une
fausse affirmation réglementaire, contraire à la règle du projet ("aucune
réponse réglementaire sans source vérifiable"). Ce risque n'existe pas pour
l'AI Act, où les bornes de Titres avaient déjà été vérifiées et validées
avec l'utilisatrice. De toute façon, la classe de risque MDR d'un projet est
déjà calculée ailleurs par un arbre de décision déterministe (voir
project_healthtech_classification_service.classify) à partir du
questionnaire entrepreneur, pas depuis le texte réglementaire lui-même —
`sous_theme` n'a donc aucun usage aval ici (ni filtre, ni chunking, ni
affichage) et reste `None` pour chaque article MDR (colonne libre, sans
CheckConstraint, voir legal_texts.py).

`evaluer_pertinence_heuristique` : mêmes marqueurs de boilerplate procédural
que legal_article_heuristic_classifier_ai_act.py (entrée en vigueur,
abrogation, délais de transposition...) — génériques à tout texte
réglementaire européen/français, pas spécifiques à l'AI Act, donc valides
ici sans adaptation. Contrairement à l'AI Act, AUCUNE zone n'est renvoyée en
vérification LLM ("ambigu" n'existe pas ici) : un article non écarté par ces
marqueurs est toujours traité "pertinent" — même choix que le correctif du
19/09/2026 sur l'AI Act (zone Titres VI+, déjà traitée "pertinent" par
défaut en pratique), généralisé ici dès le départ plutôt que de construire
une infrastructure de lots LLM qui finirait, comme pour l'AI Act, par ne
plus être appelée. Conséquence assumée : la collecte MDR entière ne
consomme aucun appel Groq, donc aucun risque de quota (TPM/TPD) — seul le
volume de lignes insérées augmente, pas leur coût.

`chunking_suggere_heuristique` : dupliqué depuis
legal_article_heuristic_classifier_ai_act.py (logique générique — longueur +
marqueurs d'alinéas, aucune connaissance du fond MDR) — même règle des 3
occurrences avant de factoriser que mdr_client.py/eu_ai_act_client.py (2
occurrences seulement pour l'instant, pas encore factorisé).
"""
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


def evaluer_pertinence_heuristique(texte_brut: str) -> bool:
    texte_normalise = texte_brut.strip().lower()
    if len(texte_normalise) < _LONGUEUR_MIN_PERTINENT:
        return False
    return not any(motif in texte_normalise for motif in _MOTIFS_NON_PERTINENTS)


_LONGUEUR_SEUIL_PAR_ALINEA = 800
_MARQUEURS_ALINEA = ("\n1°", "\n2°", "\nI.-", "\nII.-", "\na)", "\nb)", " a) ", " b) ")


def chunking_suggere_heuristique(texte_brut: str) -> str:
    contient_marqueur = any(marqueur in texte_brut for marqueur in _MARQUEURS_ALINEA)
    return "par_alinea" if len(texte_brut) > _LONGUEUR_SEUIL_PAR_ALINEA or contient_marqueur else "aucun"
