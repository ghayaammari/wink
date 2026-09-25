"""Les blocs de l'arborescence légale à collecter pour le service 3.3.6
(diagnostic d'écart FinTech, volet du diagnostic sectoriel 3.3.5). Pure
donnée, aucune logique — même séparation que blocs_formes_juridiques.py :
"quels blocs on collecte" vs "comment parler à l'API" (legifrance_client.py).

Bloc unique pour l'instant : le Chapitre II entier du Code monétaire et
financier, "Les établissements de paiement" (L522-1 à L522-20) — pas
seulement la Sous-section 1 "Agrément" (L522-6 à L522-11-1, LEGISCTA
000020862304) qui couvre uniquement le seuil déjà utilisé par
project_fintech_classification_service.classify() (article L522-11-1). Le
diagnostic d'écart doit expliquer des obligations concrètes (documentation,
procédures, exigences prudentielles), pas seulement le critère de
classification — d'où le chapitre entier plutôt que la sous-section, même
logique que le choix du Code de commerce entier pour SAS/SASU (23 articles)
plutôt qu'un sous-découpage plus fin.

`legifrance_source_id` : LEGITEXT du Code monétaire et financier entier,
récupéré via `consult/legiPart` (fonds="LEGI", défaut de
fetch_articles_in_block) — même texte source que toute autre collecte future
sur ce Code, mis en cache par (fonds, legifrance_source_id) dans
legifrance_client.py, un seul appel réseau même si d'autres blocs FinTech
s'ajoutent plus tard.

`legifrance_section_id` : LEGISCTA identifié via les URLs officielles
legifrance.gouv.fr (même méthode que blocs_formes_juridiques.py) — PAS ENCORE
vérifié par un vrai appel `consult/legiPart` au moment de l'écriture
(19/09/2026), contrairement au bloc SAS/SASU qui lui a été testé. Si
`fetch_articles_in_block(_CODE_MONETAIRE_FINANCIER, "LEGISCTA000020862288")`
renvoie une liste vide ou une erreur "section introuvable", vérifier ici en
premier que l'identifiant est toujours valide (Légifrance peut renuméroter).
"""
from dataclasses import dataclass

_CODE_MONETAIRE_FINANCIER = "LEGITEXT000006072026"


@dataclass(frozen=True)
class BlocLegifrance:
    code_source: str
    description: str
    legifrance_source_id: str
    legifrance_section_id: str
    domaine_reglementaire: str


BLOCS_SECTEUR_FINTECH: list[BlocLegifrance] = [
    BlocLegifrance(
        "Code monétaire et financier",
        "Livre V, Titre II, Chapitre II — Les établissements de paiement (L522-1 à L522-20)",
        _CODE_MONETAIRE_FINANCIER,
        "LEGISCTA000020862288",
        "secteur_fintech",
    ),
]
