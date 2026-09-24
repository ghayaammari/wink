"""Validation globale d'un document généré, avant sa génération finale
(agent `document_generation_validation`, service 1.1.4 — 24/09/2026).

Point d'entrée : `valider(document_type, contexte)`. Chaque vérification est
un « tool » (un fichier dans `tools/`) exposant `NOM`, `LIBELLE` et
`executer(contexte, precedents) -> list[Probleme]`. Les tools du document
sont lancés dans l'ordre de `TOOLS_PAR_DOCUMENT`, toujours tous (pas
d'arrêt au premier problème : l'utilisateur voit tout d'un coup).

Pourquoi un ordre fixe décidé par le code, pas un LLM qui choisit ses
tools : une validation qui BLOQUE la génération doit donner le même
résultat à chaque appel ; un LLM pourrait sauter une vérification sans que
personne ne le voie. Seul le tool ⑤ appelle un LLM, pour ce qu'il sait
faire (juger une formulation juridique).

Ajouter une vérification = un fichier tool + une ligne dans la liste du
document. Un document sans liste est « prêt » (rien à vérifier).

Aucun accès base : le contexte est construit par le backend. Seul le tool
`correction_renvois` écrit dans le contexte (`corrections_texte`)
(`document_generation_validation_service.py`).

Écart d'architecture assumé (décision utilisateur, 24/09/2026) : `agents/`
est défini comme « l'IA générative », or 5 tools sur 6 sont du code sans
LLM. Regroupés ici pour garder l'agent de validation d'un seul tenant.
"""
import logging
import time

from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.probleme import (
    GRAVITE_AVERTISSEMENT,
    GRAVITE_BLOQUANT,
    STATUT_ERREUR,
    STATUT_OK,
    STATUT_PROBLEMES,
    Etape,
    Probleme,
)
from agents.document_generation_validation.tools.commun import (
    controle_juridique_attente,
    correction_renvois,
    filet_placeholders,
)
from agents.document_generation_validation.tools.statuts import (
    chronologie_dates,
    coherence_apports,
    dirigeants_selon_articles,
    dispense_commissaire,
)

logger = logging.getLogger(__name__)

TOOLS_PAR_DOCUMENT = {
    "statuts": [
        correction_renvois,  # en premier : corrige le texte (document final), ne signale rien
        dirigeants_selon_articles,
        coherence_apports,
        chronologie_dates,
        dispense_commissaire,
        controle_juridique_attente,
        filet_placeholders,  # toujours en dernier : filet de ce que les autres ont raté
    ],
}


def valider(document_type: str, contexte: ContexteValidation) -> dict:
    """{pret, etapes, problemes, corrections_texte}. `pret` = aucun problème
    bloquant (des avertissements seuls n'empêchent pas de générer).
    `corrections_texte` : à appliquer au document final (tool
    `correction_renvois`), jamais affichées."""
    etapes: list[Etape] = []
    problemes: list[Probleme] = []
    for tool in TOOLS_PAR_DOCUMENT.get(document_type, []):
        debut = time.perf_counter()
        try:
            trouves = tool.executer(contexte, list(problemes))
            statut = STATUT_PROBLEMES if trouves else STATUT_OK
        except Exception:
            # Un tool en échec n'arrête pas les autres : il devient un
            # avertissement visible, jamais un blocage silencieux.
            logger.exception("Tool de validation %s en échec", tool.NOM)
            trouves = [
                Probleme(
                    code=f"{tool.NOM}_indisponible",
                    message_court="Vérification non effectuée",
                    message=f"La vérification « {tool.LIBELLE} » n'a pas pu être faite (erreur interne).",
                    gravite=GRAVITE_AVERTISSEMENT,
                )
            ]
            statut = STATUT_ERREUR
        problemes.extend(trouves)
        etapes.append(
            Etape(
                tool=tool.NOM,
                libelle=tool.LIBELLE,
                statut=statut,
                duree_ms=round((time.perf_counter() - debut) * 1000),
                nb_problemes=len(trouves),
            )
        )
    return {
        "pret": not any(p.gravite == GRAVITE_BLOQUANT for p in problemes),
        "etapes": [e.to_dict() for e in etapes],
        "problemes": [p.to_dict() for p in problemes],
        "corrections_texte": list(contexte.corrections_texte),
    }
