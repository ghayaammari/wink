"""Golden set de test de l'agent de matching chercheur (agents/matching_agent/
chercheur_matching_service.py, service 7.7.2) -- même principe que
evaluate_retrieval_langsmith.py pour le RAG, mais adapté à un problème de
classement à pertinence graduée (fort/moyen/faible) plutôt qu'à une seule
bonne réponse : la métrique est donc le nDCG (Normalized Discounted
Cumulative Gain), pas Recall@k/MRR.

2 besoins réels (research_needs en base de dev, projet "Écoute") x 4 profils
chercheurs réels -- jugement de référence posé à la main ci-dessous, en
lisant le contenu réel des profils (résumés, domaines), jamais deviné.

Le dict `besoin` reproduit exactement celui construit par
chercheur_matching_orchestration_service.run_matching -- même format que ce
que l'agent reçoit en production. Les tools sont les vrais tools construits
sur la vraie base (build_matching_agent_tools), pas de mock : l'agent voit
les 4 mêmes profils qu'en production.

Usage: python evaluate_matching_chercheur.py
"""
import math

from backend.matching.services.chercheur_matching_tools_service import build_matching_agent_tools
from backend.shared.database import SessionLocal
from agents.matching_agent.chercheur_matching_service import match_chercheurs

PROJET_ECOUTE = {
    "secteur": "Intelligence artificielle conversationnelle",
    "description": (
        "Écoute développe un agent conversationnel vocal pour lutter contre l'isolement des "
        "personnes âgées. Le produit combine un modèle de dialogue empathique et une détection "
        "des signaux faibles de détresse émotionnelle ou de dégradation de l'état général dans "
        "la façon de parler, pas seulement dans le contenu des phrases."
    ),
    "technologies": [
        "traitement automatique du langage",
        "reconnaissance vocale et analyse de la prosodie",
        "apprentissage automatique",
    ],
    "value_proposition": (
        "Écoute est un compagnon vocal conversationnel destiné aux personnes âgées isolées : au "
        "fil des appels quotidiens, il analyse la voix (prosodie, hésitations, changements de "
        "ton) pour détecter une fatigue, une détresse ou un isolement croissant, et alerte un "
        "aidant si besoin -- sans jamais remplacer un contact humain."
    ),
}

# Jugement de référence : 2 = fort, 1 = moyen, 0 = non pertinent / absent = 0.
# Posé en lisant le contenu réel des 4 profils (voir inventaire du 26/09) :
# - f21e456d : reconnaissance d'émotion vocale, HRI, robotique assistive pour
#   personnes âgées, centres d'appel d'urgence -- correspond directement au
#   besoin 1, aucun rapport avec la méthode scattering du besoin 2.
# - 59669b1a : ondelettes/scattering appliqués aux sons environnementaux
#   (méthode exacte demandée par le besoin 2) + expérience de conseil pour
#   des fonds d'investissement deep tech (2e partie du besoin 2, seulement
#   dans le texte du résumé, jamais dans un champ structuré) -- pertinence
#   "moyen" seulement pour le besoin 1 (signal processing générique, pas
#   spécifique à l'émotion vocale).
# - 60fbe605 : bioinformatique/phylogénétique, hors sujet pour les deux.
# - dd76a2d3 : profil vide, ne doit jamais être proposé.
GOLDEN_SET = [
    {
        "id": "besoin_emotion_voix",
        "besoin": {
            "type_besoin": "probleme",
            "titre": "Fiabiliser la détection d'émotion et de détresse dans la voix",
            "description": (
                "Nous développons un compagnon vocal conversationnel pour des personnes âgées "
                "isolées. Il analyse en continu la prosodie de la voix (hésitations, changements "
                "de ton, débit) pour repérer des signaux faibles de fatigue, de détresse "
                "émotionnelle ou d'isolement croissant, en complément du contenu des phrases. "
                "Avant tout déploiement pilote en EHPAD, nous devons valider scientifiquement la "
                "fiabilité de cette détection et nous assurer que l'interaction reste acceptable "
                "et éthique pour des utilisateurs âgés et potentiellement vulnérables. Nous "
                "cherchons un chercheur pouvant apporter une expertise en traitement du signal "
                "vocal / apprentissage automatique appliqué à la reconnaissance d'émotion, et/ou "
                "en interaction humain-machine et IA affective, pour challenger notre approche "
                "et nous aider à la rendre robuste."
            ),
            "projet": PROJET_ECOUTE,
        },
        "jugement": {
            "f21e456d-ca9e-4086-b655-6fa9ab785b5c": 2,
            "59669b1a-c898-49cd-8144-76c9b79e8934": 1,
        },
    },
    {
        "id": "besoin_scattering_sons",
        "besoin": {
            "type_besoin": "probleme",
            "titre": (
                "Chercheur ayant publié sur la classification de sons environnementaux par "
                "transformée en scattering"
            ),
            "description": (
                "Nous voulons valider notre approche de détection d'émotion vocale en nous "
                "appuyant sur des techniques de classification audio par transformée en "
                "scattering (ondelettes), une méthode précise et spécifique -- pas juste "
                "\"traitement du signal\" en général. Nous cherchons un chercheur ayant "
                "réellement publié un travail sur la classification de sons environnementaux "
                "avec cette méthode : merci de vérifier le contenu exact d'un tel travail "
                "(méthodologie, domaines d'application) avant de le proposer, un titre ou un "
                "domaine de recherche approximatif ne suffit pas. Nous voulons aussi savoir si "
                "ce chercheur a déjà été sollicité par un fonds d'investissement ou une "
                "structure de financement deep tech pour évaluer des projets similaires au "
                "nôtre -- cette information ne figure pas forcément dans son résumé de profil."
            ),
            "projet": PROJET_ECOUTE,
        },
        "jugement": {
            "59669b1a-c898-49cd-8144-76c9b79e8934": 2,
            # f21e456d volontairement absent (= 0) : c'est le piège du set --
            # aussi "audio", mais pas la bonne sous-discipline. Un agent qui
            # généralise trop sur "audio" au lieu de lire le contenu exact
            # doit le proposer à tort ici.
        },
    },
]


def dcg(relevances: list[int]) -> float:
    return sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg(ranked_ids: list[str], jugement: dict[str, int]) -> float:
    relevances = [jugement.get(rid, 0) for rid in ranked_ids]
    ideal = sorted(jugement.values(), reverse=True)
    idcg = dcg(ideal)
    return dcg(relevances) / idcg if idcg > 0 else 0.0


def main():
    db = SessionLocal()
    scores = []

    for cas in GOLDEN_SET:
        seen_researcher_ids: list[str] = []
        tools = build_matching_agent_tools(db, seen_researcher_ids)
        result = match_chercheurs(tools, cas["besoin"])

        # Même filtre anti-hallucination qu'en production (voir
        # chercheur_matching_orchestration_service.run_matching).
        matches_valides = [m for m in result.matches if m.researcher_profile_id in seen_researcher_ids]
        n_hallucines = len(result.matches) - len(matches_valides)

        matches_tries = sorted(matches_valides, key=lambda m: m.rang)
        ranked_ids = [m.researcher_profile_id for m in matches_tries]
        score = ndcg(ranked_ids, cas["jugement"])
        scores.append(score)

        print(f"\n=== {cas['id']} -- nDCG = {score:.3f} ===")
        if n_hallucines:
            print(f"  /!\\ {n_hallucines} match(es) halluciné(s) filtré(s) (id jamais vu via les tools)")
        for m in matches_tries:
            attendu = cas["jugement"].get(m.researcher_profile_id, 0)
            print(f"  rang {m.rang} | {m.researcher_profile_id[:8]}... | agent={m.niveau_pertinence} | attendu={attendu} | {m.explication[:100]}")

    print(f"\n=== nDCG moyen sur {len(GOLDEN_SET)} besoins : {sum(scores)/len(scores):.3f} ===")
    db.close()


if __name__ == "__main__":
    main()
