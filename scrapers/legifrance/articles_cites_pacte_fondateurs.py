"""Articles de loi precis a collecter pour le service 1.1.13, categorie 3
(agent conversationnel pacte de fondateurs) -- pure donnee, meme separation
que `blocs_formes_juridiques.py` : "quels articles on collecte" ici,
"comment parler a l'API" dans `legifrance_client.py`.

Contrairement a `blocs_formes_juridiques.py` (collecte tout un bloc/section,
filtre par LLM ensuite), ici la liste est deja curatee a la main : ce sont
EXACTEMENT les articles cites en `base_legale` dans
`pacte_fondateurs_validity_criteria_v2.json`, plus l'article 1195 (renonce
expressement dans le preambule du pacte, voir Notice explicative Bpifrance).
Pas de filtre LLM de pertinence ici (Etape 1.3 de `collect_legal_texts_
formes_juridiques.py`) : la pertinence est deja connue, un appel LLM
supplementaire serait un cout sans valeur (voir instruction projet
"rester sobre").

`legifrance_article_id` : identifiants LEGIARTI trouves par recherche web le
25/09/2026 (voir conversation), PAS verifies par un vrai appel API --
premiere execution reelle a confirmer (voir fetch_single_article_by_id).

`L227-13` fait EXCEPTION : deja couvert par le bloc SAS/SASU de
`blocs_formes_juridiques.py` (domaine_reglementaire='forme_juridique') --
collect_legal_texts_pacte_fondateurs.py le retrouve via ce bloc existant
plutot que de rappeler l'API pour un article deja en base, et NE RE-TAGUE
JAMAIS silencieusement son domaine_reglementaire existant (voir le
garde-fou dans ce script) : `legal_texts` n'a qu'un domaine par ligne
(UniqueConstraint globale sur (code_source, article_numero), pas par
domaine) -- un meme article ne peut donc pas appartenir "a la fois" a
forme_juridique et pacte_fondateurs dans le schema actuel. Signale
explicitement dans le script, pas resolu silencieusement ici.
"""
from dataclasses import dataclass

_CODE_CIVIL = "LEGITEXT000006070721"


@dataclass(frozen=True)
class ArticleLegifrance:
    code_source: str
    code_article: str          # tel qu'affiche a l'utilisateur (ex: "1591")
    legifrance_article_id: str  # identifiant LEGIARTI
    sous_theme: str
    cite_par_code_clause: list[str]
    chunking_suggere: str = "aucun"  # tous ces articles sont courts, un seul sujet


ARTICLES_CITES_PACTE_FONDATEURS: list[ArticleLegifrance] = [
    ArticleLegifrance(
        code_source="Code civil",
        code_article="1591",
        legifrance_article_id="LEGIARTI000006441332",
        sous_theme="prix_determinable",
        cite_par_code_clause=[
            "retrait_sans_condition_investisseurs",
            "retrait_conditionnel_investisseurs",
            "sortie_alternative_shotgun",
        ],
    ),
    ArticleLegifrance(
        code_source="Code civil",
        code_article="1843-4",
        legifrance_article_id="LEGIARTI000038790979",
        sous_theme="prix_determinable",
        cite_par_code_clause=[
            "retrait_sans_condition_investisseurs",
            "retrait_conditionnel_investisseurs",
            "sortie_alternative_shotgun",
        ],
    ),
    ArticleLegifrance(
        code_source="Code civil",
        code_article="1195",
        legifrance_article_id="LEGIARTI000032041302",
        sous_theme="imprevision_renoncee_preambule",
        cite_par_code_clause=[],  # non cite dans clause_validity_criteria, voir docstring module
    ),
]

# L227-13 (inalienabilite 10 ans, C. com.) : PAS dans cette liste -- deja
# couvert par le bloc SAS/SASU de blocs_formes_juridiques.py, voir docstring
# module et le garde-fou dans collect_legal_texts_pacte_fondateurs.py.
CODE_ARTICLE_L227_13 = "L227-13"
CODE_CLAUSES_CITANT_L227_13 = ["inalienabilite_fondateurs_partielle_plafond"]
