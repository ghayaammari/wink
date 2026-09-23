"""URLs de depart CNIL pour la collecte du RGPD (service 3.3.1) — meme
principe que cci_paris_idf/pages_assurance.py, mais un seul dossier `cnil`
suffit ici (pas de decoupage par organisme, une seule source).

CURATION MANUELLE STRICTE, pas de crawling (`max_liens_a_suivre=0` partout) —
correction du 16/09/2026 : une premiere version utilisait une page hub avec
crawling active (discover_links, profondeur 1), mais `discover_links` ne fait
aucun tri thematique, il suit TOUS les liens du meme domaine (actualites,
autres reglementations, page carrieres...) — memes contredit le principe deja
applique dans cci_paris_idf/pages_assurance.py ("Fixe par curation humaine ...
jamais devine"). Le perimetre elargi (au-dela des 3 obligations trackees) est
donc couvert en ajoutant des pages precises par theme ci-dessous, pas en
laissant un crawler decider.

`secteurs_cibles` sur PageSeed ne s'applique pas vraiment au RGPD (le RGPD
concerne tous les secteurs, pas un secteur precis comme le volet assurance
pour lequel PageSeed a ete concu) — laisse vide plutot que de forcer une
valeur qui n'a pas de sens ici. Le champ reste dans la dataclass partagee
(pas duplique) puisqu'il ne genere aucun probleme laisse vide, juste inutilise
pour cette source ; a reconsiderer seulement si ce decalage se reproduit sur
une 2e source non sectorielle (regle de 3, meme logique que la dette assumee
sur _call_llm dans legal_text_structuring_service.py).

`type_source` (colonne a ajouter sur legal_texts, voir decision du 15/09) :
- guide_pratique pour toutes les pages HTML ci-dessous
- pdf pour le guide DPO et le guide securite (2 PDF)
Pas encode ici (PageSeed n'a pas ce champ) : c'est le script de collecte
(collect_rgpd_guides.py, a ecrire) qui determine type_source a l'insertion,
selon que fetch_page() renvoie une page HTML ou un PDF (voir FetchedPage.html_brut
vide pour un PDF, deja le signal utilise par web_fetch.py lui-meme).

Verifie via recherche le 16/09/2026 (URLs officielles cnil.fr trouvees, pages
non ouvertes une a une en detail). Non verifie : la page FAQ CNIL specifique
RGPD (non trouvee a une URL stable unique - a chercher separement).
"""
from scrapers.shared.page_seed import PageSeed

NOM_SOURCE = "CNIL"

PAGES: list[PageSeed] = [
    # --- Registre des traitements (Art. 30) ---
    PageSeed(url="https://www.cnil.fr/fr/le-registre-rgpd-de-la-cnil", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/RGPD-le-registre-des-activites-de-traitement", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/documenter-la-conformite", max_liens_a_suivre=0),

    # --- AIPD (Art. 36) ---
    PageSeed(url="https://www.cnil.fr/fr/RGPD-analyse-impact-protection-des-donnees-aipd", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/ce-quil-faut-savoir-sur-lanalyse-dimpact-relative-la-protection-des-donnees-aipd", max_liens_a_suivre=0),

    # --- DPO (Art. 37) ---
    PageSeed(url="https://www.cnil.fr/fr/designation-dpo", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/passer-laction/le-delegue-la-protection-des-donnees-dpo", max_liens_a_suivre=0),
    PageSeed(
        url="https://www.cnil.fr/sites/cnil/files/atoms/files/guide_pratique_rgpd_-_delegues_a_la_protection_des_donnees.pdf",
        max_liens_a_suivre=0,
    ),

    # --- Bases légales / licéité (questions frequentes hors des 3 obligations) ---
    PageSeed(url="https://www.cnil.fr/fr/les-bases-legales/liceite-essentiel-sur-les-bases-legales", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/les-bases-legales/choisir-base-legale", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/les-bases-legales/consentement", max_liens_a_suivre=0),

    # --- Droits des personnes ---
    PageSeed(url="https://www.cnil.fr/fr/preparer-lexercice-des-droits-des-personnes", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/repondre-une-demande-de-droit-dacces", max_liens_a_suivre=0),

    # --- Sécurité des données / violations ---
    PageSeed(url="https://www.cnil.fr/fr/les-violations-de-donnees-personnelles", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/notifier-une-violation-de-donnees-personnelles", max_liens_a_suivre=0),
    PageSeed(
        url="https://www.cnil.fr/sites/cnil/files/2023-04/cnil_guide_securite_des_donnees_personnelles-2023.pdf",
        max_liens_a_suivre=0,
    ),

    # --- Transferts hors UE ---
    PageSeed(url="https://www.cnil.fr/fr/transferts-de-donnees-hors-ue-le-cadre-general-prevu-par-le-rgpd", max_liens_a_suivre=0),
    PageSeed(url="https://www.cnil.fr/fr/les-outils-de-la-conformite/transferer-des-donnees-hors-de-lue", max_liens_a_suivre=0),
]
