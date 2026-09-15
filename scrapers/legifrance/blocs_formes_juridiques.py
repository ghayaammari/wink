"""Les blocs de l'arborescence légale à collecter pour le service 1.1.1
(forme juridique) — Étape 1.1 du plan Notion "Collecte, puis Chunking/Embedding
des formes juridiques (4)". Pure donnée, aucune logique — séparé de
`legifrance_client.py` pour ne pas mélanger "quels blocs on collecte" et
"comment parler à l'API".

RECENTRÉ (Notion, page (4)) : après un premier blocage sur le quota Groq, la
collecte est restreinte aux formes réellement proposées par la roadmap
(nœud `e1` : SAS ou SARL uniquement), plus leurs variantes à associé unique
(SASU, EURL). Les autres formes (SNC, SCS, SA, SCA, SCOP, SCI, association,
EI/micro-entreprise) sont hors périmètre réel du produit actuel — écartées,
pas supprimées : conservées plus bas en commentaire pour référence future, si
un besoin utilisateur confirmé apparaît. Volume estimé ~66 articles, contre
plus de 400 dans la version initiale à 14 blocs.

`forme_juridique_concernee` : FIXE par bloc, plus jamais devinée par le LLM
article par article (décision Notion, Étape 1.4 — "Corrigé"). Chaque bloc
collecté correspond déjà à une ou plusieurs formes connues à l'avance, comme
`code_source` — filet de sécurité : si un article contenait une exception
explicite pour une forme précise, la relecture humaine (Étape 1.6, dashboard)
la corrige à ce moment, pas besoin que le LLM la devine en amont.

`legifrance_source_id` : LEGITEXT du texte ENTIER (ici, toujours le Code de
commerce) à récupérer via `consult/legiPart` — un seul appel, même si
plusieurs blocs en dépendent (voir legifrance_client.py, qui met en cache le
texte entier et en extrait la section localement). VÉRIFIÉ par un vrai appel
le 10/09/2026 : `consult/legiPart` ignore un identifiant de section en
`textId` et renvoie toujours le texte entier.

`legifrance_section_id` : identifiant (LEGISCTA) de la section précise à
extraire dans la réponse. VÉRIFIÉ pour SAS/SASU via un vrai appel (23 articles
trouvés, L227-1 à L227-20-1, conforme) ; les 2 autres LEGISCTA ci-dessous
viennent des URLs officielles legifrance.gouv.fr (même méthode) mais n'ont pas
chacun été testés individuellement par un vrai appel.
"""
from dataclasses import dataclass

_CODE_DE_COMMERCE = "LEGITEXT000005634379"


@dataclass(frozen=True)
class BlocLegifrance:
    code_source: str
    description: str
    legifrance_source_id: str
    legifrance_section_id: str
    domaine_reglementaire: str
    forme_juridique_concernee: list[str]


BLOCS_FORMES_JURIDIQUES: list[BlocLegifrance] = [
    BlocLegifrance(
        "Code de commerce",
        "Livre II, Titre I (L.210-1 à L.210-12)",
        _CODE_DE_COMMERCE,
        "LEGISCTA000006133175",
        "statuts_societe",
        ["SAS", "SASU", "SARL", "EURL"],  # socle commun aux 4 formes collectées
    ),
    BlocLegifrance(
        "Code de commerce",
        "Livre II, Titre II, Chapitre III — SARL/EURL (L.223-1 à L.223-43)",
        _CODE_DE_COMMERCE,
        "LEGISCTA000006146044",
        "forme_juridique",
        ["SARL", "EURL"],
    ),
    BlocLegifrance(
        "Code de commerce",
        "Livre II, Titre II, Chapitre VII — SAS/SASU (L.227-1 à L.227-20)",
        _CODE_DE_COMMERCE,
        "LEGISCTA000006146048",
        "forme_juridique",
        ["SAS", "SASU"],
    ),
]

# Blocs écartés (hors périmètre réel du produit actuel) — conservés ici pour
# référence future si un besoin utilisateur confirmé apparaît (voir Notion,
# page (4)). Identifiants LEGISCTA déjà trouvés lors de la 1ère version à 14
# blocs, gardés au cas où :
#
# - Chapitre I — SNC (L.221-1 à L.221-17) : LEGISCTA000006146042
# - Chapitre II — SCS (L.222-1 à L.222-12) : LEGISCTA000006146043
# - Chapitre IV — Sociétés par actions, dispositions générales (L.224-1 à L.224-3) : LEGISCTA000006146045
# - Chapitre V — SA (L.225-1 à L.225-270) : LEGISCTA000006146046
# - Chapitre VI — SCA (L.226-1 à L.226-14) : LEGISCTA000006146047
# - Code de commerce, Livre V, Titre II, Chapitre VI, Section 3 — EI (L.526-22 et suivants) : LEGISCTA000045168637
# - Code civil, Livre III, Titre IX, Chapitre I (1832-1844) : LEGISCTA000006136390 (source LEGITEXT000006070721)
# - Code civil, Chapitre II — SCI (1845 à 1870-1) : LEGISCTA000006136391 (source LEGITEXT000006070721)
# - Loi n°78-763 du 19/07/1978 — SCOP : JORFTEXT000000339242 (pas de LEGITEXT trouvé, non testé)
# - Loi du 1er juillet 1901 — Association : LEGITEXT000006069570
# - CGI, Articles 50-0, 102 ter, 293 B — Micro-entreprise : non résolu, articles non
#   contigus, nécessiterait un traitement à part (pas un simple bloc legiPart)
