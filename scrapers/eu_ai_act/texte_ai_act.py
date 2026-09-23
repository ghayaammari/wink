"""Texte source EUR-Lex a collecter en entier pour l'AI Act (service 3.3.12).

Contrairement a scrapers/legifrance/ (API PISTE, un id par texte + endpoint
article), l'AI Act n'a pas d'equivalent : le reglement (UE) 2024/1689 est
publie sur EUR-Lex sous forme d'UN SEUL document HTML continu (pas d'endpoint
par article) — voir eu_ai_act_client.py pour le decoupage local par parsing
HTML. Deux pistes d'API existantes verifiees le 18/09/2026 et ecartees comme
impraticables :
- EUR-Lex Webservice (SOAP) : necessite un enregistrement + approbation
  humaine par un administrateur UE, delai non maitrisable pour ce projet.
- CELLAR REST : accessible publiquement mais necessite un UUID CELLAR deja
  connu, lui-meme uniquement obtenable via le webservice SOAP ci-dessus.
On recupere donc directement la page HTML publique (pas d'auth necessaire),
comme n'importe quel navigateur.

CELEX de la version consolidee utilisee : 02024R1689-20260727 — version en
vigueur au 27/07/2026, la plus recente au moment de l'ecriture (18/09/2026).
Cette consolidation est susceptible d'evoluer : un "AI Digital Omnibus"
amende deja ce reglement au moment de l'ecriture. A verifier periodiquement
si le CELEX consolide change (EUR-Lex republie la derniere consolidation
sous un nouveau CELEX quand une modification est actee).

Pure donnee, aucune logique — meme separation que texte_loi_rgpd.py.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TexteEurLexAIAct:
    code_source: str
    description: str
    source_url: str
    domaine_reglementaire: str = "ai_act"


TEXTES_AI_ACT: list[TexteEurLexAIAct] = [
    TexteEurLexAIAct(
        "Règlement (UE) 2024/1689",
        "Texte consolidé entier (AI Act) — version en vigueur au 27/07/2026",
        "https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX%3A02024R1689-20260727",
    ),
]
