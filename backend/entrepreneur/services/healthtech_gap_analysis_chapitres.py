"""Registre des chapitres du diagnostic d'écart HealthTech (service 3.3.6) —
pure donnée, aucune logique, même séparation que sector_roadmap_service.py
(services/) pour "quels chapitres existent" vs "comment calculer leur statut".

Pas de table dédiée : liste fixe et connue au moment de l'écriture, 3
chapitres seulement — une table catalogue serait sur-ingénierie tant qu'aucun
besoin d'édition dynamique n'apparaît (même raisonnement que le rejet de
roadmap_nodes pour le parcours sectoriel top-niveau, voir SectorDiagnosticPage.tsx).

`requete_semantique` : texte utilisé pour la recherche vectorielle dans
`content_embeddings` (domaine='secteur_healthtech') — pas de tag `chapitre`
sur les articles collectés eux-mêmes (contrairement à `sous_theme`, qui vient
de la classification LLM générique côté collecte, pas du découpage en
chapitres de ce diagnostic). Le chapitre est donc retrouvé par similarité
sémantique au moment de la génération, pas par un filtre exact — même
principe que le RAG déjà utilisé pour RGPD/AI Act (recherche vectorielle,
jamais un filtre de colonne).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ChapitreGapAnalysisHealthtech:
    cle: str
    titre: str
    requete_semantique: str


# ORDRE SIGNIFICATIF : reflète le cycle de vie réglementaire MDR (obligations
# du fabricant avant mise sur le marché -> évaluation clinique -> surveillance
# après commercialisation) — utilisé tel quel pour le déblocage séquentiel
# (voir project_healthtech_gap_analysis_service.py).
CHAPITRES_GAP_ANALYSIS_HEALTHTECH: list[ChapitreGapAnalysisHealthtech] = [
    ChapitreGapAnalysisHealthtech(
        "obligations_fabricant",
        "Obligations du fabricant",
        "obligations générales des fabricants de dispositifs médicaux avant mise sur le marché",
    ),
    ChapitreGapAnalysisHealthtech(
        "evaluation_clinique",
        "Évaluation clinique",
        "évaluation clinique et données cliniques requises pour un dispositif médical",
    ),
    ChapitreGapAnalysisHealthtech(
        "surveillance_post_commercialisation",
        "Surveillance post-commercialisation",
        "surveillance après commercialisation et vigilance pour un dispositif médical",
    ),
]
