"""URLs de depart ANSSI (cyber.gouv.fr) pour la collecte du referentiel

SecNumCloud (service 3.3.11) — meme principe que `cnil/pages_rgpd.py` :
curation manuelle stricte, pas de crawling (`max_liens_a_suivre=0` partout).
SecNumCloud n'est pas sectoriel (contrairement au volet assurance pour
lequel PageSeed a ete concu) : `secteurs_cibles` laisse vide, meme
justification que pour CNIL/RGPD (voir docstring de ce fichier).

Seule certification des 3 visees a terme (ISO 27001, SOC 2, SecNumCloud)
dont le referentiel est entierement public et redistribuable (ANSSI,
administration francaise) — voir discussion produit du 21/09/2026, raison
du choix de commencer par celle-ci plutot qu'ISO 27001/SOC 2.

Verifie via WebFetch le 21/09/2026 :
- Le PDF du referentiel repond en 200 (redirection vers un lien S3 signe,
  transparente pour `requests` qui suit les redirections par defaut) et
  contient bien le referentiel d'exigences SecNumCloud v3.2.
- La page FAQ qualification contient du contenu reel sur le processus (durée
  de validite 3 ans, audits annuels de surveillance, discussion du cout selon
  l'approche retenue) meme si elle ne donne pas de chiffre delai/cout unique
  et absolu -- coherent avec le choix de stocker une FOURCHETTE (voir
  ProjectCertificationEstimation) plutot qu'un chiffre exact invente.

CORRECTIF du 22/09/2026 — le PDF vendeurs a l'URL
`.../document/SecNumCloud_fournisseurs_service_cloud.pdf` renvoie desormais
un 404 (repere lors d'une collecte reelle qui l'a marque "inaccessible",
confirme par `requests.get` direct : status 404, pas un probleme robots.txt
ni timeout) -- document deplace/retire lors d'une refonte du site ANSSI.
Remplace par la page HTML `secnumcloud-pour-les-fournisseurs-de-services-cloud`
(verifiee en 200 le meme jour), qui semble etre le remplacement de ce
contenu. `fetch_page()` gere PDF et HTML de facon generique, aucun
changement necessaire cote scraper pour ce changement de type de source.
Ecartee "non pertinente" par le LLM apres collecte reelle -- probablement
un vrai rejet (page de presentation cote fournisseurs, contenu qui recoupe
le referentiel/la FAQ deja en base) plutot qu'un faux negatif comme pour le
referentiel (voir _extrait_representatif). Laissee dans PAGES : idempotente,
cout nul de la garder meme rejetee, et permet de reconsiderer facilement si
son contenu change.

CORRECTIF du 22/09/2026 (2) — 4e source testee puis retiree : la page
"prestataires-de-services-dinformatique-en-nuage-secnumcloud" (verifiee en
200, 43 163 octets) s'est averee etre un ANNUAIRE des prestataires en cours
de qualification (noms d'entreprises, adresses, sites web) -- confirme par
lecture directe de l'extrait envoye au LLM, pas juste sa justification.
Rejet "non pertinent" legitime, pas un faux negatif comme le referentiel
(voir _extrait_representatif) : structurellement un annuaire, ne deviendra
jamais pertinent pour ce corpus. Retiree de PAGES plutot que laissee pour
rien a chaque future collecte.

CONCLUSION (22/09/2026) : 2 sources (referentiel + FAQ) suffisent pour la
V1 -- elles couvrent a elles seules les 4 sous-themes definis dans
legal_text_structuring_service_secnumcloud.py. Le "peu de lignes" observe
dans legal_texts ne reflete pas le volume reel du corpus (le referentiel
seul, 55 pages, sera decoupe en dizaines de chunks a l'embedding).
"""
from scrapers.shared.page_seed import PageSeed

NOM_SOURCE = "ANSSI"

PAGES: list[PageSeed] = [
    # --- Référentiel d'exigences (le document normatif lui-même) ---
    PageSeed(
        url="https://cyber.gouv.fr/sites/default/files/document/secnumcloud-referentiel-exigences-v3.2.pdf",
        max_liens_a_suivre=0,
    ),
    # --- Processus de qualification (délai/coût/étapes, tels que documentés) ---
    PageSeed(
        url="https://cyber.gouv.fr/enjeux-technologiques/cloud/faq-qualification-secnumcloud/",
        max_liens_a_suivre=0,
    ),
    # --- Remplace l'ancien PDF vendeurs (404 depuis une refonte du site, voir CORRECTIF ci-dessus) ---
    PageSeed(
        url="https://cyber.gouv.fr/secnumcloud-pour-les-fournisseurs-de-services-cloud",
        max_liens_a_suivre=0,
    ),
]
