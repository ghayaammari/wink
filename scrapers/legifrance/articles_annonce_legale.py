"""Articles de loi à collecter pour le copilot de l'annonce légale (service
1.1.5) — pure donnée, même séparation que `blocs_formes_juridiques.py` :
« quels articles » ici, « comment parler à l'API » dans `legifrance_client.py`.

Liste curatée (pas de filtre LLM de pertinence, comme
`articles_cites_pacte_fondateurs.py`) : les articles déjà identifiés dans la
conception Groupe 5 pour l'annonce légale :
- R210-3 : obligation de publier un avis dans un support habilité ;
- R210-4 : contenu obligatoire de l'avis de constitution ;
- R210-16 : support habilité du département du siège (section « Des
  formalités de publicité »).

Récupération par SECTION (`fetch_articles_in_block`, endpoint déjà vérifié)
puis filtre sur le numéro d'article — plutôt que par identifiant LEGIARTI
(`fetch_single_article_by_id`, endpoint jamais vérifié, et un LEGIARTI désigne
une VERSION d'article : risque de collecter une version abrogée).

⚠️ Identifiants LEGISCTA trouvés via les URLs publiques legifrance.gouv.fr
(25/09/2026), PAS vérifiés par un vrai appel (voir l'avertissement de
`blocs_secteurs_assurance.py` : des LEGISCTA devinés s'y sont révélés faux).
Si une section est introuvable, `fetch_articles_in_block` lève une erreur
explicite : corriger l'identifiant ici, ne pas deviner.
"""
from dataclasses import dataclass

_CODE_DE_COMMERCE = "LEGITEXT000005634379"


@dataclass(frozen=True)
class SectionAnnonceLegale:
    code_source: str
    description: str
    legifrance_source_id: str
    legifrance_section_id: str
    # Numéros d'articles à garder dans la section (les autres sont ignorés),
    # avec leur sous-thème — fixé ici, jamais deviné par un LLM.
    articles: dict[str, str]


SECTIONS_ANNONCE_LEGALE: list[SectionAnnonceLegale] = [
    SectionAnnonceLegale(
        "Code de commerce",
        "Partie réglementaire, Livre II, Titre Ier, Sous-section 1 — De la constitution de la société (R210-1 à R210-8)",
        _CODE_DE_COMMERCE,
        "LEGISCTA000006161463",
        {"R210-3": "obligation_publication", "R210-4": "contenu_obligatoire"},
    ),
    SectionAnnonceLegale(
        "Code de commerce",
        "Partie réglementaire, Livre II, Titre Ier, Section 3 — Des formalités de publicité (R210-16 à R210-20)",
        _CODE_DE_COMMERCE,
        "LEGISCTA000006146225",
        {"R210-16": "support_habilite"},
    ),
]
