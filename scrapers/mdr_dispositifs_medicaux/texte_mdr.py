"""Texte source EUR-Lex a collecter en entier pour le MDR (service 3.3.6,
volet HealthTech du diagnostic sectoriel 3.3.5).

Meme situation que texte_ai_act.py : le reglement (UE) 2017/745 est publie
sur EUR-Lex sous forme d'UN SEUL document HTML continu (pas d'endpoint par
article) — voir mdr_client.py pour le decoupage local par parsing HTML.

CELEX de la version de base utilisee : 32017R0745 (pas de suffixe de
consolidation type "-20260727" comme pour l'AI Act : a verifier si une version
consolidee plus recente existe sur EUR-Lex avant la collecte reelle — le MDR a
ete amende plusieurs fois depuis 2017 (dates d'application etalees par
dispositif/classe), une consolidation existe probablement mais son CELEX exact
n'a pas ete confirme au moment de l'ecriture, 19/09/2026).

Pure donnee, aucune logique — meme separation que texte_ai_act.py.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TexteEurLexMDR:
    code_source: str
    description: str
    source_url: str
    domaine_reglementaire: str = "secteur_healthtech"


TEXTES_MDR: list[TexteEurLexMDR] = [
    TexteEurLexMDR(
        "Règlement (UE) 2017/745",
        "Texte de base entier (MDR, dispositifs médicaux) — CELEX 32017R0745, "
        "version consolidée la plus récente à vérifier avant collecte",
        "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX%3A32017R0745",
    ),
]
