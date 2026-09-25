"""Orchestrateur collecte AI Act — EUR-Lex (service 3.3.12).
Lancement : `python -m backend.shared.knowledge_base.scripts.collect_ai_act_articles`
depuis `wink/` (même convention que collect_rgpd_articles.py). Peut être
relancé plusieurs fois sans risque (voir REPRISE ci-dessous).

HISTORIQUE (dans l'ordre où les problèmes réels sont apparus) :
1. Version initiale : classification 100% LLM (choix explicite de
   l'utilisatrice — les catégories de risque AI Act sont nuancées).
   Classifier les 119 articles un par un aurait fait ~238 appels Groq ->
   regroupés par lots dès le départ.
2. 1er run réel : 413 "tokens per minute (TPM) : Limit 8000" — un lot de
   taille FIXE (10 articles) ne borne pas le nombre de tokens (certains
   articles, ex. art. 9, sont bien plus longs que d'autres). Corrigé par
   `_lots_par_budget()` : découpage par budget de tokens estimé, pas par
   nombre d'articles.
3. 2e et 3e run réels : 429 "tokens per day (TPD) : Limit 200000" — le quota
   quotidien (partagé avec le reste de l'app) s'épuise EN COURS DE COLLECTE
   avant même de classifier tous les articles. Corrigé par la REPRISE
   ci-dessous (commit par lot + saut des articles déjà collectés).
4. Toujours bloqué après le correctif de reprise (quota déjà à ~99% avant
   même de commencer) : la classification 100% LLM reste structurellement
   trop coûteuse pour ce quota partagé, quel que soit le découpage en lots.
   CORRECTIF FINAL : contrairement au RGPD (sous-thèmes dispersés sans
   structure exploitable), la catégorie de risque AI Act EST la structure
   officielle du règlement — chaque Titre correspond exactement à un niveau
   de risque (voir legal_article_heuristic_classifier_ai_act.py). La
   catégorie de risque est donc assignée par HEURISTIQUE (plage de numéros
   d'article), zéro appel LLM, pour TOUS les articles. Le LLM n'est conservé
   que pour la question qui reste un vrai jugement : la PERTINENCE des
   articles de gouvernance/sanctions/dispositions finales (à partir de
   l'article 57) qu'un simple mot-clé ne suffit pas à trancher — un
   sous-ensemble restreint, pas les 119 articles.

REPRISE (ajoutée au correctif 3, toujours active) :
  1. `list_article_numeros()` récupère les articles déjà présents en base
     pour cette source AVANT tout traitement, et les exclut — un article
     déjà upserté ne consomme plus jamais de quota (ni même de traitement).
  2. Commit après le traitement heuristique, puis après CHAQUE lot LLM — si
     le quota tombe en cours de route, le travail déjà fait reste acquis.
Conséquence : relancer ce script après un 429/413 est le comportement
normal attendu, pas un échec à corriger autrement.

Note : le TPM (tokens par minute) et le TPD (tokens par jour) sont deux
limites Groq INDÉPENDANTES — voir correctifs 2 et 3 ci-dessus, l'un ne
protège pas de l'autre.

FICHIERS DU PIPELINE :
  scrapers/eu_ai_act/texte_ai_act.py                              — texte source (page EUR-Lex)
  scrapers/eu_ai_act/eu_ai_act_client.py                          — fetch_articles_in_text()
  agents/ingestion/legal_article_heuristic_classifier_ai_act.py   — catégorie de risque (heuristique, toujours) + pertinence (heuristique, sauf zone ambiguë)
  agents/ingestion/legal_text_structuring_service_ai_act.py       — filtre + classification LLM (résiduel, zone ambiguë uniquement, par lots)
  backend/shared/knowledge_base/models/legal_texts.py
  backend/shared/knowledge_base/services/legal_texts_service.py
  backend/.env (GROQ_API_KEY)

Aucune migration préalable requise pour legal_texts (domaine_reglementaire et
sous_theme sont des colonnes String libres, sans CheckConstraint) — seule
content_embeddings.domaine (vérifiée au moment de l'embedding, voir
chunk_and_embed_legal_texts.py) nécessite 'ai_act' dans sa CheckConstraint,
déjà ajouté dans le modèle (voir content_embeddings.py) ; la migration
Alembic correspondante reste À ÉCRIRE avant de lancer
chunk_and_embed_legal_texts.py sur ce domaine (voir tâche en attente,
distincte de ce script qui n'écrit que dans legal_texts).
"""
import sys

from agents.ingestion.legal_article_heuristic_classifier_ai_act import (
    ChunkingSuggere,
    chunking_suggere_heuristique,
    classify_categorie_risque_heuristique,
    evaluer_pertinence_heuristique,
)
from agents.ingestion.legal_text_structuring_service_ai_act import classify_articles_batch
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.legal_texts_service import list_article_numeros, upsert_legal_text
from scrapers.eu_ai_act.eu_ai_act_client import fetch_articles_in_text
from scrapers.eu_ai_act.texte_ai_act import TEXTES_AI_ACT

# Estimation grossiere (pas de tokenizer exact disponible ici) : ~4 caracteres
# par token, suffisant pour rester prudent sous la limite TPM. Volontairement
# conservateur (marge pour le prompt/schema fixes et la reponse JSON du LLM,
# qui comptent aussi dans le TPM). Ne s'applique plus qu'au residu ambigu
# (voir docstring module), donc peu de lots desormais.
_CARACTERES_PAR_TOKEN_ESTIME = 4
_BUDGET_TOKENS_PAR_LOT = 1500


def _lots_par_budget(articles: list[dict], budget_tokens: int = _BUDGET_TOKENS_PAR_LOT):
    lot: list[dict] = []
    tokens_lot = 0
    for article in articles:
        tokens_article = max(1, len(article["texte_brut"]) // _CARACTERES_PAR_TOKEN_ESTIME)
        if lot and tokens_lot + tokens_article > budget_tokens:
            yield lot
            lot = []
            tokens_lot = 0
        lot.append(article)
        tokens_lot += tokens_article
    if lot:
        yield lot


def _upserer(db, texte, article: dict, categorie_risque, chunking_suggere: ChunkingSuggere, compteurs: dict) -> None:
    upsert_legal_text(
        db,
        domaine_reglementaire=texte.domaine_reglementaire,
        code_source=texte.code_source,
        article_numero=article["article_numero"],
        texte_brut=article["texte_brut"],
        sous_theme=categorie_risque,
        chunking_suggere=chunking_suggere,
        type_source="article_loi",
        source_url=texte.source_url,
    )
    compteurs["insere"] += 1


def _traiter_lot_llm(db, texte, lot: list[dict], compteurs: dict) -> None:
    """Verifie la PERTINENCE (seule question retenue du LLM, voir docstring
    module) d'un lot d'articles de la zone ambigue. La categorie_risque
    reste TOUJOURS celle de l'heuristique, jamais celle que le LLM
    proposerait — c'est un fait structurel, pas une opinion a lui demander.
    Si classify_articles_batch() leve (429/413/autre), aucune ecriture n'a
    ete faite pour ce lot : les lots precedents restent commités."""
    resultats = classify_articles_batch(lot)
    pertinence_par_numero = {resultat.article_numero: resultat.pertinent for resultat in resultats}

    for article in lot:
        pertinent = pertinence_par_numero.get(article["article_numero"])
        if not pertinent:
            # None (LLM n'a pas repondu pour cet article) ou False : on
            # n'upserte pas, l'article sera retente au prochain run (pas
            # dans list_article_numeros tant qu'il n'est pas upserte).
            compteurs["ignore_non_pertinent"] += 1
            continue
        _upserer(
            db,
            texte,
            article,
            classify_categorie_risque_heuristique(article["article_numero"]),
            chunking_suggere_heuristique(article["texte_brut"]),
            compteurs,
        )
    db.commit()


def run() -> None:
    compteurs = {
        "insere": 0,
        "ignore_non_pertinent": 0,
        "ignore_texte_vide": 0,
        "deja_collectes": 0,
    }

    for texte in TEXTES_AI_ACT:
        articles = fetch_articles_in_text(texte.source_url)
        articles_valides = [a for a in articles if a["texte_brut"]]
        compteurs["ignore_texte_vide"] += len(articles) - len(articles_valides)

        db = SessionLocal()
        try:
            deja_collectes = list_article_numeros(db, code_source=texte.code_source)
            a_traiter = [a for a in articles_valides if a["article_numero"] not in deja_collectes]
            compteurs["deja_collectes"] += len(articles_valides) - len(a_traiter)

            articles_ambigus: list[dict] = []
            for article in a_traiter:
                pertinence = evaluer_pertinence_heuristique(article["article_numero"], article["texte_brut"])
                if pertinence == "non_pertinent":
                    compteurs["ignore_non_pertinent"] += 1
                    continue
                if pertinence == "ambigu":
                    articles_ambigus.append(article)
                    continue
                # "pertinent" tranché par heuristique seule — aucun appel LLM.
                _upserer(
                    db,
                    texte,
                    article,
                    classify_categorie_risque_heuristique(article["article_numero"]),
                    chunking_suggere_heuristique(article["texte_brut"]),
                    compteurs,
                )
            db.commit()

            for lot in _lots_par_budget(articles_ambigus):
                _traiter_lot_llm(db, texte, lot, compteurs)

            print(
                f"Texte '{texte.description}' — OK ({len(a_traiter)} articles traités ce run, "
                f"{len(articles_ambigus)} envoyés au LLM pour pertinence, "
                f"{compteurs['deja_collectes']} déjà collectés lors d'un run précédent)."
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    print(
        f"Terminé — {compteurs['insere']} articles insérés/mis à jour en 'extrait_automatique', "
        f"{compteurs['ignore_non_pertinent']} écartés (non pertinents ou non classifiés), "
        f"{compteurs['ignore_texte_vide']} écartés (texte vide), "
        f"{compteurs['deja_collectes']} déjà collectés (sautés)."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(
            f"Erreur — arrêt de la collecte (les lots déjà traités avant cette erreur restent commités, "
            f"relancer le script reprendra où il s'est arrêté) : {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
