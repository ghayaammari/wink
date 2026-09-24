"""Pages Service-Public Entreprendre sur l'annonce légale (service 1.1.5,
copilot). Pure donnée — le contenu est récupéré par
`scrapers/shared/web_fetch.py::fetch_page()`.

Vérifié le 25/09/2026 : la page existe (mise à jour au 01/01/2026) ; couvre
le moment de la publication, le support habilité du département, le contenu
obligatoire, l'attestation de parution et les tarifs forfaitaires.
"""
from scrapers.shared.guide_page import GuidePage

NOM_SOURCE = "Service-Public Entreprendre"

PAGES: list[GuidePage] = [
    GuidePage(
        url="https://entreprendre.service-public.gouv.fr/vosdroits/F35957",
        sous_theme="general",
    ),
]
