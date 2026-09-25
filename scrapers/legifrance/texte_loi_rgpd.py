"""Texte Légifrance à collecter en entier pour le RGPD (service 3.3.1) —
remplace l'approche initiale par articles isolés (articles_rgpd.py, supprimé
le 16/09/2026) : le copilot conformité doit pouvoir répondre à des questions
RGPD au-delà des 3 obligations trackées (registre/AIPD/DPO) — bases légales,
droits des personnes, sécurité, transferts hors UE, sanctions, etc. Plutôt que
de deviner et lister article par article tout ce qui pourrait servir un jour,
on collecte la Loi n°78-17 en entier via fetch_articles_in_text() (voir
legifrance_client.py) — texte de taille raisonnable (une loi, pas un code),
donc pas de risque de volume excessif comme sur le Code de commerce.

Pure donnée, aucune logique — même séparation que blocs_formes_juridiques.py.

`legifrance_source_id` : LEGITEXT de la Loi n°78-17 du 6 janvier 1978,
version consolidée (intègre les modifications RGPD/loi du 20/06/2018) —
legifrance.gouv.fr/loda/id/LEGITEXT000006068624/.

CORRECTIF du 17/09/2026 : la valeur précédente (JORFTEXT000000886460) était
l'id de la publication originale au Journal officiel de 1978 (texte non
consolidé), pas l'id consolidé — consult/legiPart exige un LEGITEXT et
rejetait cet appel en 403. Erreur découverte seulement maintenant car
l'id n'avait jamais été testé par un vrai appel API avant (compte PISTE
verrouillé au moment de l'écriture initiale, voir échange du 16/09/2026).

HORS PÉRIMÈTRE de ce fichier (à traiter séparément si besoin confirmé) : le
texte du Règlement UE 2016/679 (RGPD) lui-même est un texte européen, publié
sur EUR-Lex, pas sur Légifrance — `scrapers/legifrance/` ne peut pas le
collecter tel quel. La loi n°78-17 ci-dessous est le texte français qui
transpose/applique le RGPD et contient les pouvoirs de la CNIL — c'est ce qui
couvre le besoin réel (obligations françaises), mais si le copilot doit un
jour citer un article du règlement UE directement, ce sera un nouveau dossier
`scrapers/eurlex/`, pas un ajout ici.
"""
from dataclasses import dataclass

_LOI_INFORMATIQUE_ET_LIBERTES = "LEGITEXT000006068624"


@dataclass(frozen=True)
class TexteLegifranceRGPD:
    code_source: str
    description: str
    legifrance_source_id: str
    domaine_reglementaire: str
    # "LEGI" (Codes, ex: Code de commerce) ou "LODA" (Lois/Ordonnances/
    # Décrets/Arrêtés) — détermine l'endpoint PISTE appelé par
    # fetch_articles_in_text(), voir correctif du 17/09/2026 dans
    # legifrance_client.py. Une Loi comme celle-ci est TOUJOURS "LODA",
    # jamais "LEGI" même si son id partage le préfixe LEGITEXT avec les Codes.
    fonds: str = "LODA"


TEXTES_RGPD: list[TexteLegifranceRGPD] = [
    TexteLegifranceRGPD(
        "Loi n°78-17 du 6 janvier 1978",
        "Texte consolidé entier (informatique, fichiers et libertés)",
        _LOI_INFORMATIQUE_ET_LIBERTES,
        "rgpd",
    ),
]
