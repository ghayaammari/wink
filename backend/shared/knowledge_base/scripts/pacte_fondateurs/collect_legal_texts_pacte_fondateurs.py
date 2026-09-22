"""Orchestrateur Phase 1 (collecte) -- service 1.1.13, categorie 3 (agent
conversationnel pacte de fondateurs). Meme role que
`collect_legal_texts_formes_juridiques.py` pour le domaine `forme_juridique`,
mais SANS les 2 appels LLM de filtre/classification (Etapes 1.3/1.4 de ce
dernier) : la liste des sources est deja curatee a la main (voir
articles_cites_pacte_fondateurs.py / requetes_pacte_fondateurs.py /
pages_pacte_fondateurs.py), un appel LLM de "pertinence" serait un cout sans
valeur sur une liste deja triee -- decision explicite (rester sobre).

Lancement : `python -m backend.shared.knowledge_base.scripts.pacte_fondateurs.collect_legal_texts_pacte_fondateurs`
depuis `wink/` (meme convention que collect_legal_texts_formes_juridiques.py).

3 SOURCES, dans l'ordre, chacune sa propre transaction (meme raison que
"commit par bloc" du script forme_juridique : un echec sur une source garde
les precedentes deja commitees) :
  1. Legifrance -- articles de loi cites dans clause_validity_criteria
     (scrapers/legifrance/articles_cites_pacte_fondateurs.py). L227-13 EST
     UN CAS PARTICULIER (voir garde-fou _collecter_l227_13 ci-dessous).
  2. Judilibre -- jurisprudence sur les clauses les plus contestees
     (scrapers/judilibre/requetes_pacte_fondateurs.py).
  3. Bpifrance Creation -- pages d'encyclopedie pedagogiques
     (scrapers/bpifrance_encyclopedie/pages_pacte_fondateurs.py).

Toutes les lignes sont inserees en `statut_contenu='extrait_automatique'`
(jamais directement en `valide_humain`) -- meme regle que le pipeline
forme_juridique : la relecture humaine passe par le dashboard existant
(GET/PATCH /knowledge-base/legal-texts/..., deja generique par domaine, voir
legal_texts_validation_router.py) AVANT tout chunking/embedding. Ce script
ne chunke ni n'embedde rien -- voir chunk_and_embed_legal_texts.py (Phase 2+3,
deja generique par domaine, reutilise TEL QUEL, aucune modification requise :
'pacte_fondateurs' est deja accepte par ck_content_embeddings_domaine).

Prealables .env : LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET (deja
utilises par le pipeline forme_juridique) + JUDILIBRE_API_KEY (nouveau, voir
scrapers/judilibre/judilibre_client.py).
"""
import sys

from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import get_legal_text, upsert_legal_text
from scrapers.bpifrance_encyclopedie.bpifrance_encyclopedie_client import fetch_page_text
from scrapers.bpifrance_encyclopedie.pages_pacte_fondateurs import PAGES_PACTE_FONDATEURS
from scrapers.judilibre.judilibre_client import search_decisions
from scrapers.judilibre.requetes_pacte_fondateurs import REQUETES_PACTE_FONDATEURS
from scrapers.legifrance.articles_cites_pacte_fondateurs import (
    ARTICLES_CITES_PACTE_FONDATEURS,
    CODE_ARTICLE_L227_13,
)
from scrapers.legifrance.blocs_formes_juridiques import BLOCS_FORMES_JURIDIQUES
from scrapers.legifrance.legifrance_client import fetch_articles_in_block, fetch_single_article_by_id

_DOMAINE = "pacte_fondateurs"  # deja accepte par ck_content_embeddings_domaine (voir seed_pacte_fondateurs_v2.py)
_CODE_SOURCE_JUDILIBRE = "Judilibre - Cour de cassation"
_CODE_SOURCE_BPIFRANCE = "Bpifrance Création - Encyclopédie"


def _collecter_l227_13(db) -> str:
    """CAS PARTICULIER (voir docstring articles_cites_pacte_fondateurs.py) :
    L227-13 est deja collecte par le pipeline forme_juridique, sous
    domaine_reglementaire='forme_juridique'. `legal_texts` n'a qu'UN domaine
    par ligne (UniqueConstraint globale sur (code_source, article_numero),
    pas par domaine) -- upsert_legal_text() ECRASERAIT ce domaine existant
    si on l'appelait ici sans precaution. Garde-fou : si la ligne existe deja
    avec un domaine DIFFERENT, on ne touche RIEN et on le signale -- decision
    de savoir si on la re-tague ou si on accepte qu'elle reste invisible pour
    l'agent pacte_fondateurs laissee a l'utilisateur (voir conversation),
    jamais tranchee silencieusement ici.
    """
    existante = get_legal_text(db, code_source="Code de commerce", article_numero=CODE_ARTICLE_L227_13)
    if existante is not None:
        if existante.domaine_reglementaire != _DOMAINE:
            return (
                f"ignore_deja_present_autre_domaine (domaine actuel={existante.domaine_reglementaire!r}, "
                "voir docstring _collecter_l227_13 -- rien modifie)"
            )
        return "deja_present_bon_domaine"

    # Pas encore en base sous aucun domaine (pipeline forme_juridique pas
    # encore lance, ou echoue avant ce bloc) -- on va le chercher nous-memes
    # via le bloc SAS/SASU deja verifie, plutot que d'appeler getArticle
    # (endpoint jamais teste, voir legifrance_client.py) pour un article
    # qu'un bloc existant et deja verifie sait deja retrouver.
    bloc_sas = next(b for b in BLOCS_FORMES_JURIDIQUES if "SAS/SASU" in b.description)
    articles = fetch_articles_in_block(bloc_sas.legifrance_source_id, bloc_sas.legifrance_section_id)
    cible = next(
        (a for a in articles if (a.get("article_numero") or "").replace(" ", "").replace(".", "") == "L227-13"),
        None,
    )
    if cible is None:
        return "erreur_l227_13_introuvable_dans_bloc_sas"

    upsert_legal_text(
        db,
        domaine_reglementaire=_DOMAINE,
        code_source="Code de commerce",
        article_numero=CODE_ARTICLE_L227_13,
        texte_brut=cible["texte_brut"],
        sous_theme="inalienabilite_actions",
        chunking_suggere="aucun",
        date_effet=cible.get("date_effet"),
    )
    return "insere"


def _collecter_legifrance(db) -> dict[str, int]:
    compteurs = {"insere": 0, "ignore": 0}
    for article_ref in ARTICLES_CITES_PACTE_FONDATEURS:
        donnees = fetch_single_article_by_id(article_ref.legifrance_article_id)
        if not donnees["texte_brut"]:
            compteurs["ignore"] += 1
            continue
        upsert_legal_text(
            db,
            domaine_reglementaire=_DOMAINE,
            code_source=article_ref.code_source,
            article_numero=donnees.get("article_numero") or article_ref.code_article,
            texte_brut=donnees["texte_brut"],
            sous_theme=article_ref.sous_theme,
            chunking_suggere=article_ref.chunking_suggere,
            date_effet=donnees.get("date_effet"),
        )
        compteurs["insere"] += 1

    resultat_l227_13 = _collecter_l227_13(db)
    print(f"  L227-13 : {resultat_l227_13}")
    if resultat_l227_13 == "insere":
        compteurs["insere"] += 1
    return compteurs


def _collecter_judilibre(db) -> dict[str, int]:
    compteurs = {"insere": 0, "ignore": 0}
    for requete in REQUETES_PACTE_FONDATEURS:
        decisions = search_decisions(requete.query, taille=requete.taille, chamber=requete.chamber)
        for decision in decisions:
            if not decision["texte_brut"]:
                compteurs["ignore"] += 1
                continue
            upsert_legal_text(
                db,
                domaine_reglementaire=_DOMAINE,
                code_source=_CODE_SOURCE_JUDILIBRE,
                article_numero=decision["numero_decision"],
                texte_brut=decision["texte_brut"],
                sous_theme=requete.sous_theme,
                chunking_suggere="par_alinea",  # decisions longues, multi-paragraphes -- voir chunk_texte_brut
                source_url=decision.get("url"),
            )
            compteurs["insere"] += 1
    return compteurs


def _collecter_bpifrance(db) -> dict[str, int]:
    compteurs = {"insere": 0, "ignore": 0}
    for page in PAGES_PACTE_FONDATEURS:
        texte = fetch_page_text(page.url)
        upsert_legal_text(
            db,
            domaine_reglementaire=_DOMAINE,
            code_source=_CODE_SOURCE_BPIFRANCE,
            article_numero=page.titre,
            texte_brut=texte,
            sous_theme=page.sous_theme,
            chunking_suggere="par_alinea",  # pages longues, plusieurs sujets par page
            source_url=page.url,
        )
        compteurs["insere"] += 1
    return compteurs


def run() -> None:
    for nom, fonction in (
        ("Légifrance (articles de loi)", _collecter_legifrance),
        ("Judilibre (jurisprudence)", _collecter_judilibre),
        ("Bpifrance Création (encyclopédie)", _collecter_bpifrance),
    ):
        db = SessionLocal()
        try:
            compteurs = fonction(db)
            db.commit()
            print(f"Source '{nom}' — OK ({compteurs}).")
        except Exception:
            db.rollback()
            print(f"Source '{nom}' — ÉCHEC, transaction annulée (les sources précédentes restent commitées).")
            raise
        finally:
            db.close()

    print(
        "Terminé — toutes les lignes sont en 'extrait_automatique'. "
        "Relecture humaine obligatoire avant embedding : voir dashboard "
        "GET/PATCH /knowledge-base/legal-texts/... (legal_texts_validation_router.py), "
        "puis python -m backend.shared.knowledge_base.scripts.chunk_and_embed_legal_texts."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — arrêt de la collecte (les sources déjà commitées restent en base) : {exc}", file=sys.stderr)
        sys.exit(1)
