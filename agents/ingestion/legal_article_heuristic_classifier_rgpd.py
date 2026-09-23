"""Filtrage/classification des articles de loi RGPD SANS appel LLM (service
3.3.1, partie Legifrance uniquement) — remplace l'usage de
legal_text_structuring_service_rgpd.py pour collect_rgpd_articles.py.

Pourquoi une heuristique ici et pas pour collect_rgpd_guides.py (qui garde
le LLM, voir legal_text_structuring_service_rgpd.py) : les articles traites
ici viennent de textes Legifrance choisis a la main parce qu'ils parlent
deja de protection des donnees (voir scrapers/legifrance/texte_loi_rgpd.py,
TEXTES_RGPD) — la question "cet article est-il pertinent pour le RGPD ?"
a une reponse quasi toujours vraie AVANT meme d'interroger un LLM, sauf pour
les articles purement procoduraux (entree en vigueur, abrogation). A
l'inverse, les pages CNIL (guides/FAQ) sont un contenu editorial heterogene
ou un LLM apporte une vraie valeur de jugement — l'heuristique n'y serait
pas fiable, donc pas appliquee la-bas.

Dette technique assumee : le `sous_theme` heuristique (mots-cles) est moins
fin qu'une classification LLM qui comprend le contexte — une phrase
ambigue ou un theme non couvert par la liste de mots-cles tombera dans
"bases_legales" (categorie generique par defaut) plutot que d'etre
correctement categorisee. Acceptable ici car `sous_theme` sert a
indexer/filtrer la recherche, pas a generer du contenu affiche a
l'utilisateur (contrairement a l'AIPD) — impact d'une erreur de
classification nettement plus faible. A revoir si des recherches par
sous_theme s'averent peu pertinentes en pratique.

Ajoute le 18/09/2026 suite a l'epuisement recurrent du quota Groq (TPD)
par cette seule etape de collecte — voir discussion, decision actee :
supprimer l'usage LLM ici plutot que de tourner en rond sur le quota,
puisque les sources sont deja curees et que la valeur ajoutee du LLM y
etait marginale.
"""
from agents.ingestion.legal_text_structuring_service_rgpd import (
    ClassificationResult,
    RelevanceResult,
    SousThemeRGPD,
)

# Articles purement procoduraux (pas de fond RGPD) : entree en vigueur,
# abrogation, renumerotation. Si le texte de l'article ne contient QUE ce
# type de mention (et rien d'autre de substantiel), il est ecarte.
_MOTIFS_NON_PERTINENTS = (
    "entre en vigueur",
    "entrent en vigueur",
    "est abrogé",
    "est abrogée",
    "sont abrogés",
    "sont abrogées",
)

# Longueur en-dessous de laquelle un article ne peut raisonnablement
# contenir de disposition de fond (seuil empirique, pas une science exacte).
_LONGUEUR_MIN_PERTINENT = 40

_MOTS_CLES_PAR_SOUS_THEME: dict[SousThemeRGPD, tuple[str, ...]] = {
    "aipd": ("analyse d'impact", "analyse d'impact relative à la protection des données", "aipd"),
    "dpo": ("délégué à la protection des données", "délégué à la protection", " dpo "),
    "registre_traitements": ("registre des activités de traitement", "registre de traitement"),
    "transferts_hors_ue": (
        "hors de l'union européenne",
        "hors union européenne",
        "pays tiers",
        "transfert de données",
    ),
    "droits_personnes": (
        "droit d'accès",
        "droit de rectification",
        "droit à l'effacement",
        "droit d'opposition",
        "droit à la portabilité",
        "consentement de la personne",
        "personne concernée",
    ),
    "securite_donnees": (
        "sécurité des données",
        "violation de données",
        "mesures techniques et organisationnelles",
        "confidentialité des données",
    ),
}

# Categorie par defaut si aucun mot-cle ne correspond — voir dette technique
# documentee dans le docstring du module.
_SOUS_THEME_PAR_DEFAUT: SousThemeRGPD = "bases_legales"

# Au-dela de cette longueur, on suppose que l'article contient plusieurs
# dispositions distinctes (alineas) qui beneficient d'un chunking separe.
_LONGUEUR_SEUIL_PAR_ALINEA = 800
_MARQUEURS_ALINEA = ("\n1°", "\n2°", "\nI.-", "\nII.-", "\na)", "\nb)")


def filter_article_relevance_heuristique(texte_brut: str) -> RelevanceResult:
    """Remplace filter_article_relevance() (LLM) pour les articles Legifrance

    deja pre-filtres par construction — voir docstring du module.
    """
    texte_normalise = texte_brut.strip().lower()

    if len(texte_normalise) < _LONGUEUR_MIN_PERTINENT:
        return RelevanceResult(
            pertinent=False, justification="Article trop court pour contenir une disposition de fond."
        )

    if any(motif in texte_normalise for motif in _MOTIFS_NON_PERTINENTS) and len(texte_normalise) < 200:
        return RelevanceResult(
            pertinent=False, justification="Article purement procédural (entrée en vigueur / abrogation)."
        )

    return RelevanceResult(pertinent=True, justification="Article issu d'un texte Legifrance pré-sélectionné RGPD.")


def classify_article_heuristique(texte_brut: str) -> ClassificationResult:
    """Remplace classify_article() (LLM) pour les articles Legifrance — voir

    docstring du module pour le compromis assume (moins fin qu'un LLM, mais
    suffisant pour de l'indexation, pas de generation de contenu affiche).
    """
    texte_normalise = texte_brut.lower()

    sous_theme = _SOUS_THEME_PAR_DEFAUT
    for candidat, mots_cles in _MOTS_CLES_PAR_SOUS_THEME.items():
        if any(mot_cle in texte_normalise for mot_cle in mots_cles):
            sous_theme = candidat
            break

    contient_marqueur_alinea = any(marqueur in texte_brut for marqueur in _MARQUEURS_ALINEA)
    chunking_suggere = (
        "par_alinea" if len(texte_brut) > _LONGUEUR_SEUIL_PAR_ALINEA or contient_marqueur_alinea else "aucun"
    )

    return ClassificationResult(sous_theme=sous_theme, chunking_suggere=chunking_suggere)
