"""Evaluation du retrieval multi-domaines (Recall@k, MRR) via LangSmith --
distinct du tracing (LANGSMITH_TRACING=true dans backend/.env, deja actif
automatiquement sur run_react_agent/run_react_agent_conversation, aucun code a
ecrire pour ca).

Ici on mesure la qualite de search_similar_chunks() elle-meme (pas l'agent) :
pour chaque question du GOLDEN_SET, le bon chunk (source_id) est-il retrouve
dans le top_k du MEME domaine que la question, et a quel rang ? Aucun appel
Groq -- juste embed_texts (BGE-M3, local) + une requete pgvector -- donc pas de
risque de 429, relancable a volonte.

Domaines couverts (voir list_domaines_disponibles.py pour le volume reel de
chunks par domaine -- seuls les domaines avec un volume suffisant ont ete
retenus ici, un domaine a quelques chunks rendrait le Recall@k mecaniquement
gonfle et non representatif) : rgpd, ai_act, secteur_healthtech,
forme_juridique, certification_secnumcloud.

Mode d'emploi (2 passages) :
1er passage -- les chunk_id_attendu ci-dessous sont a None : le script tourne
en mode "decouverte", affiche juste les candidats trouves pour chaque question
(recherche restreinte au domaine de la question) sans calculer de score. Vous
lisez les resultats, vous identifiez le bon source_id pour chaque question et
vous le collez dans GOLDEN_SET ci-dessous.

2e passage -- une fois tous les chunk_id_attendu remplis, le script bascule en
mode evaluation : il calcule Recall@k et MRR globalement ET par domaine
(un domaine plus faible ne doit pas etre noye dans la moyenne generale), cree
(ou reutilise) un dataset LangSmith "wink-retrieval-multi-domaines", et
affiche aussi un resume en local (au cas ou la partie LangSmith echoue -- le
calcul du score ne doit pas en dependre).

Lancement : depuis wink/, venv actif : python evaluate_retrieval_langsmith.py
"""
import random

from dotenv import load_dotenv
load_dotenv("backend/.env")

from agents.ingestion.embedding_service import embed_texts
from agents.shared.reranking.reranking_service import rerank_indices
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.content_embeddings_service import search_similar_chunks

TOP_K = 8

# Bascule pour mesurer l'effet du reranking avec ce meme script, avant/apres
# (voir claude/Wink_rag_retrieval_eval_baseline.md) : True = chunks reordonnes
# par le cross-encoder (comportement de production) ; False = comportement
# d'avant reranking, pour comparer. Ne change jamais TOP_K ni les candidats
# recuperes, seulement leur ordre.
USE_RERANKING = False

# A completer : mettez le source_id attendu pour chaque question apres le
# premier passage en mode decouverte (voir docstring ci-dessus). Chaque
# question porte son propre domaine -- la recherche est restreinte a ce
# domaine, jamais tous domaines confondus (meme regle que search_similar_chunks
# en production, voir content_embeddings_service.py).
GOLDEN_SET = [
    # --- rgpd (800 chunks) ---
    {"domaine": "rgpd", "question": "Quelles sont les obligations en cas de profilage automatise des utilisateurs ?", "chunk_id_attendu": "ea6ab098-c2b0-43c7-a688-fd619aa6fd82"},
    {"domaine": "rgpd", "question": "Faut-il un contrat de sous-traitance pour partager des donnees avec un prestataire ?", "chunk_id_attendu": "ee8e3a7a-0fcf-4631-8d1a-9e50aa31ed5d"},
    {"domaine": "rgpd", "question": "Quelles regles s'appliquent au transfert de donnees hors Union europeenne ?", "chunk_id_attendu": "10ca8673-8f81-484f-9a63-1da06d673283"},
    {"domaine": "rgpd", "question": "Quel est le delai pour notifier une violation de donnees a la CNIL ?", "chunk_id_attendu": "3ab50ef6-d7f8-4776-bcf5-fde2ee7baf17"},
    {"domaine": "rgpd", "question": "Quelles sont les bases legales qui permettent de traiter des donnees personnelles ?", "chunk_id_attendu": "930cd323-b395-48c0-854e-ba245742e9e3"},
    {"domaine": "rgpd", "question": "Un utilisateur peut-il demander la suppression de ses donnees a tout moment ?", "chunk_id_attendu": "19e2a5a4-76c9-4c8d-9741-b61a5543fcbd"},
    {"domaine": "rgpd", "question": "Quelles sont les conditions de validite du consentement au traitement des donnees ?", "chunk_id_attendu": "b32b2d31-cebd-4694-8342-995f822198aa"},
    {"domaine": "rgpd", "question": "Comment un utilisateur peut-il exercer son droit d'acces a ses donnees personnelles ?", "chunk_id_attendu": "15cfd72c-e717-4839-8f48-d66f0cae9998"},
    {"domaine": "rgpd", "question": "Qu'est-ce que le droit a la portabilite des donnees ?", "chunk_id_attendu": "306a9dc6-2635-44f6-9cb8-aeb712992238"},
    {"domaine": "rgpd", "question": "Quelles regles specifiques s'appliquent au traitement des donnees des mineurs ?", "chunk_id_attendu": "d6c253b9-157d-4b80-ba88-1a8e93810d83"},
    {"domaine": "rgpd", "question": "Dans quels cas une analyse d'impact relative a la protection des donnees (AIPD) est-elle obligatoire ?", "chunk_id_attendu": "a56c709a-9dde-4258-96a1-2ef9322c9878"},
    {"domaine": "rgpd", "question": "Combien de temps peut-on conserver des donnees personnelles ?", "chunk_id_attendu": "bb57f128-1321-4ea0-b830-e2308f977e7c"},
    {"domaine": "rgpd", "question": "Faut-il le consentement de l'utilisateur pour deposer des cookies ?", "chunk_id_attendu": "b32b2d31-cebd-4694-8342-995f822198aa"},
    {"domaine": "rgpd", "question": "Quelles sont les sanctions possibles en cas de non-conformite au RGPD ?", "chunk_id_attendu": "79667956-1f61-4f97-99e9-57a0d968fdcc"},
    {"domaine": "rgpd", "question": "Quelles informations doivent figurer dans le registre des activites de traitement ?", "chunk_id_attendu": "de9f4021-7495-4f34-abaa-16baf3383982"},
    {"domaine": "rgpd", "question": "Quelles mesures de securite un responsable de traitement doit-il mettre en place ?", "chunk_id_attendu": "1d29cce2-e4a4-4b08-8250-1201b4e18698"},
    {"domaine": "rgpd", "question": "Dans quels cas la designation d'un delegue a la protection des donnees (DPO) est-elle obligatoire ?", "chunk_id_attendu": "de91180b-cefb-444b-accb-7de7537c2f28"},
    {"domaine": "rgpd", "question": "Quelles informations doivent etre fournies aux personnes avant la collecte de leurs donnees ?", "chunk_id_attendu": "c88fe775-c123-43a1-9e2f-df4364fbcdf6"},
    {"domaine": "rgpd", "question": "Qu'est-ce que la pseudonymisation des donnees personnelles ?", "chunk_id_attendu": "fafafa81-9f08-49ea-b94a-8a886ea86b26"},
    {"domaine": "rgpd", "question": "Un utilisateur peut-il s'opposer au traitement de ses donnees ?", "chunk_id_attendu": "c71feeb4-8e66-488f-8b5e-ecd363b7f2b9"},
    {"domaine": "rgpd", "question": "Comment un utilisateur peut-il deposer une reclamation aupres de la CNIL ?", "chunk_id_attendu": "de91180b-cefb-444b-accb-7de7537c2f28"},
    {"domaine": "rgpd", "question": "Le consentement au traitement des donnees peut-il etre retire a tout moment ?", "chunk_id_attendu": "b32b2d31-cebd-4694-8342-995f822198aa"},
    # --- ai_act (258 chunks) ---
    {"domaine": "ai_act", "question": "Comment un systeme d'IA est-il classe comme etant a haut risque ?", "chunk_id_attendu": "7be5d3f9-942e-4233-90a9-f4af58ca612a"},
    {"domaine": "ai_act", "question": "Quelles pratiques d'intelligence artificielle sont totalement interdites par l'AI Act ?", "chunk_id_attendu": "1e94d549-1048-45fc-9b1a-e0d1a9b3f0da"},
    {"domaine": "ai_act", "question": "Quelles obligations de transparence s'appliquent aux systemes d'IA generative ?", "chunk_id_attendu": "0b8b9c4b-d2e4-4d55-baa1-0f50e95308f5"},
    {"domaine": "ai_act", "question": "Qu'est-ce qu'une evaluation de conformite pour un systeme d'IA a haut risque ?", "chunk_id_attendu": "9a8981e3-212e-4587-a655-1c30d01266a3"},
    {"domaine": "ai_act", "question": "Quelles sont les obligations d'un fournisseur de modele d'IA a usage general ?", "chunk_id_attendu": "d402fdf6-07e9-401e-b0f3-d61962592232"},
    {"domaine": "ai_act", "question": "Quelles sont les obligations de surveillance post-commercialisation pour un systeme d'IA a haut risque ?", "chunk_id_attendu": "75bdde93-5b70-4357-9958-e6691bf9437b"},
    {"domaine": "ai_act", "question": "Qu'est-ce que le marquage CE pour un systeme d'IA a haut risque ?", "chunk_id_attendu": "f25d8b65-b190-4768-a6eb-ed5dc7a6bc52"},
    {"domaine": "ai_act", "question": "Quelles sont les sanctions et amendes prevues par l'AI Act en cas de non-conformite ?", "chunk_id_attendu": "35c74e15-cbb2-4dd1-b04d-f8c52caaeffe"},
    {"domaine": "ai_act", "question": "Quel est le role du Bureau de l'IA institue par le reglement europeen ?", "chunk_id_attendu": "7b30c872-a724-42e2-a64a-d53fc44fcec5"},
    {"domaine": "ai_act", "question": "Quelles obligations incombent aux deployeurs de systemes d'IA a haut risque ?", "chunk_id_attendu": "0023144f-80bf-4131-accb-6028afa93025"},
    {"domaine": "ai_act", "question": "Comment un systeme d'IA a haut risque doit-il etre concu pour permettre une supervision humaine ?", "chunk_id_attendu": "093bee66-6c54-46fe-b1a6-1e454278ec68"},
    # --- secteur_healthtech (159 chunks) ---
    {"domaine": "secteur_healthtech", "question": "Quelles regles s'appliquent a l'hebergement de donnees de sante (certification HDS) ?", "chunk_id_attendu": "7e045008-c508-44e1-8559-c2837aaeee8f"},
    {"domaine": "secteur_healthtech", "question": "Comment un dispositif medical logiciel est-il classe reglementairement ?", "chunk_id_attendu": "d5b83630-6e82-41b7-9600-a9d0cabcccc0"},
    {"domaine": "secteur_healthtech", "question": "Quelles autorisations sont necessaires pour mener un essai clinique ?", "chunk_id_attendu": "3bbfc5e5-e06d-457a-b879-a54266bb0f7c"},
    {"domaine": "secteur_healthtech", "question": "Quelles sont les obligations d'interoperabilite pour les logiciels de sante ?", "chunk_id_attendu": "c1308bdc-0409-45f3-8494-d791eb3f5784"},
    {"domaine": "secteur_healthtech", "question": "Quelles obligations de vigilance incombent aux fabricants apres la mise sur le marche d'un dispositif medical ?", "chunk_id_attendu": "5ef80b36-d22e-4870-97dd-d442fa3534f6"},
    {"domaine": "secteur_healthtech", "question": "Qu'est-ce qu'un organisme notifie et quel est son role dans la certification des dispositifs medicaux ?", "chunk_id_attendu": "92bd99d3-4851-4dbd-8884-edb0502387b7"},
    {"domaine": "secteur_healthtech", "question": "Quelles sont les obligations du mandataire d'un fabricant de dispositifs medicaux etabli hors UE ?", "chunk_id_attendu": "c9e40c07-17b3-4e40-b0cd-d1f6cab260b5"},
    {"domaine": "secteur_healthtech", "question": "Comment un dispositif medical est-il identifie et trace (systeme IUD) ?", "chunk_id_attendu": "edc4e260-716b-49e9-908c-a4ac0a21da2b"},
    {"domaine": "secteur_healthtech", "question": "Quelles informations doivent figurer sur l'etiquetage d'un dispositif medical ?", "chunk_id_attendu": "880dc6e8-8fc7-4eea-8b63-712c2c55e515"},
    {"domaine": "secteur_healthtech", "question": "Quelles sont les conditions de consentement eclaire pour un participant a une investigation clinique ?", "chunk_id_attendu": "b2eb704d-d310-4cce-b798-a7b8293b9c61"},
    {"domaine": "secteur_healthtech", "question": "Quelles obligations incombent aux importateurs de dispositifs medicaux ?", "chunk_id_attendu": "3b05d4f2-b328-4ed8-851b-8d3b43c71d28"},
    # --- forme_juridique (113 chunks) ---
    {"domaine": "forme_juridique", "question": "Quelle est la difference entre une SAS et une SARL ?", "chunk_id_attendu": "08648670-478d-48c5-9139-9bf90cbcb12a"},
    {"domaine": "forme_juridique", "question": "Quel est le capital social minimum pour creer une SAS ?", "chunk_id_attendu": "1215dd30-d0df-4611-8bc1-b410e7abdb41"},
    {"domaine": "forme_juridique", "question": "Comment la responsabilite des associes est-elle limitee selon la forme juridique choisie ?", "chunk_id_attendu": "1215dd30-d0df-4611-8bc1-b410e7abdb41"},
    {"domaine": "forme_juridique", "question": "Quelles formalites sont necessaires pour immatriculer une societe ?", "chunk_id_attendu": "d7125ead-8217-4385-ae30-9363b981a104"},
    {"domaine": "forme_juridique", "question": "Comment sont prises les decisions collectives des associes dans une SARL ?", "chunk_id_attendu": "cad02867-e1d7-4f90-80ff-a479e3f19e5d"},
    {"domaine": "forme_juridique", "question": "Quelles sont les conditions de nomination et de revocation du gerant d'une SARL ?", "chunk_id_attendu": "5a9262f4-0da4-427e-a07a-8a5da4f3738d"},
    {"domaine": "forme_juridique", "question": "Comment se deroule la cession de parts sociales dans une SARL ?", "chunk_id_attendu": "5b782e55-27e2-4d4d-a68f-ddfb8981e370"},
    {"domaine": "forme_juridique", "question": "Quelles sont les regles de majorite pour modifier les statuts d'une societe ?", "chunk_id_attendu": "dc2c9b12-c6b3-4675-b9ac-f36523273eac"},
    {"domaine": "forme_juridique", "question": "Qu'est-ce qu'un associe unique et quelles regles particulieres s'appliquent ?", "chunk_id_attendu": "08648670-478d-48c5-9139-9bf90cbcb12a"},
    {"domaine": "forme_juridique", "question": "Comment fonctionne la direction d'une societe par actions simplifiee (SAS) ?", "chunk_id_attendu": "1215dd30-d0df-4611-8bc1-b410e7abdb41"},
    {"domaine": "forme_juridique", "question": "Quelles sont les conditions de transformation d'une SARL en une autre forme sociale ?", "chunk_id_attendu": "304b0d3e-4115-4b19-a019-6bf24172bc5b"},
    {"domaine": "forme_juridique", "question": "Quelles clauses statutaires peuvent limiter la cession d'actions dans une SAS ?", "chunk_id_attendu": "c94f9874-2db3-4461-9c9d-4794dd1f45fe"},
    # --- certification_secnumcloud (112 chunks) ---
    {"domaine": "certification_secnumcloud", "question": "Quels sont les criteres de souverainete exiges par la certification SecNumCloud ?", "chunk_id_attendu": "4bd594c8-2205-4dcb-9542-e19efae4823e"},
    {"domaine": "certification_secnumcloud", "question": "Quelles exigences de securite s'appliquent a un hebergeur cloud certifie SecNumCloud ?", "chunk_id_attendu": "4bd594c8-2205-4dcb-9542-e19efae4823e"},
    {"domaine": "certification_secnumcloud", "question": "Qui delivre la certification SecNumCloud et selon quel referentiel ?", "chunk_id_attendu": "4bd594c8-2205-4dcb-9542-e19efae4823e"},
]


def _rechercher(db, domaine: str, question: str) -> list[str]:
    """source_ids retournes par le retrieval reel, dans l'ordre (meilleur
    d'abord) -- meme appel que celui utilise en production (compliance_agent),
    restreint au domaine de la question (jamais tous domaines confondus)."""
    embedding = embed_texts([question])[0]
    chunks = search_similar_chunks(db, domaine=domaine, query_embedding=embedding, top_k=TOP_K)
    if USE_RERANKING and chunks:
        ordre = rerank_indices(question, [c.chunk_texte for c in chunks])
        chunks = [chunks[i] for i in ordre]
    return [c.source_id for c in chunks]


def _mode_decouverte(db) -> None:
    print(f"=== Mode decouverte -- top {TOP_K} candidats par question ===")
    print("Identifiez le bon source_id pour chaque question et remplissez GOLDEN_SET.\n")
    for item in GOLDEN_SET:
        if item["chunk_id_attendu"] is not None:
            continue
        print(f"[{item['domaine']}] Question : {item['question']}")
        embedding = embed_texts([item["question"]])[0]
        chunks = search_similar_chunks(db, domaine=item["domaine"], query_embedding=embedding, top_k=TOP_K)
        if not chunks:
            print("  Aucun chunk trouve.")
        for rang, chunk in enumerate(chunks, start=1):
            print(f"  {rang}. [{chunk.source_id}] {chunk.chunk_texte[:150]}...")
        print()


def _reciprocal_rank(source_ids_retournes: list[str], attendu: str) -> float:
    """1/rang si le chunk attendu est trouve (rang 1-indexe), 0.0 sinon --
    definition standard du MRR : penalise un bon chunk trouve tard plus qu'un
    chunk trouve en 1ere position, contrairement au Recall@k qui traite tout
    rang <= k de la meme facon."""
    if attendu in source_ids_retournes:
        return 1.0 / (source_ids_retournes.index(attendu) + 1)
    return 0.0


def _mode_evaluation(db) -> None:
    # Ordre mélangé (mais deterministe -- seed fixe) pour eviter tout biais
    # d'ordre pendant la relecture manuelle des resultats par domaine.
    questions = list(GOLDEN_SET)
    random.Random(42).shuffle(questions)

    resultats = []
    for item in questions:
        source_ids = _rechercher(db, item["domaine"], item["question"])
        attendu = item["chunk_id_attendu"]
        resultats.append(
            {
                "domaine": item["domaine"],
                "question": item["question"],
                "attendu": attendu,
                "trouve": attendu in source_ids,
                "rr": _reciprocal_rank(source_ids, attendu),
            }
        )

    print(f"=== Resume local -- Recall@{TOP_K} et MRR ===\n")
    for r in resultats:
        statut = "OK" if r["trouve"] else "RATE"
        print(f"[{statut}] (rr={r['rr']:.2f}) [{r['domaine']}] {r['question']}")

    print(f"\n--- Par domaine ---")
    domaines = sorted({r["domaine"] for r in resultats})
    for domaine in domaines:
        sous_ensemble = [r for r in resultats if r["domaine"] == domaine]
        recall_d = sum(r["trouve"] for r in sous_ensemble) / len(sous_ensemble)
        mrr_d = sum(r["rr"] for r in sous_ensemble) / len(sous_ensemble)
        print(f"  {domaine:<28} Recall@{TOP_K} = {recall_d:.0%}   MRR = {mrr_d:.3f}   (n={len(sous_ensemble)})")

    recall = sum(r["trouve"] for r in resultats) / len(resultats)
    mrr = sum(r["rr"] for r in resultats) / len(resultats)
    print(f"\n--- Global ---\nRecall@{TOP_K} = {recall:.2%}   MRR = {mrr:.3f}   (n={len(resultats)} questions, {len(domaines)} domaines)\n")

    # Partie LangSmith -- optionnelle, echoue proprement si LANGSMITH_API_KEY
    # n'est pas encore renseignee/valide dans backend/.env (le resume local
    # ci-dessus reste dans tous les cas la source de verite immediate).
    try:
        from langsmith import Client

        client = Client()
        dataset_name = "wink-retrieval-multi-domaines"
        if not client.has_dataset(dataset_name=dataset_name):
            dataset = client.create_dataset(dataset_name=dataset_name)
            client.create_examples(
                inputs=[{"domaine": item["domaine"], "question": item["question"]} for item in GOLDEN_SET],
                outputs=[{"chunk_id_attendu": item["chunk_id_attendu"]} for item in GOLDEN_SET],
                dataset_id=dataset.id,
            )
            print(f"Dataset '{dataset_name}' cree sur LangSmith avec {len(GOLDEN_SET)} exemples.")

        def target(inputs: dict) -> dict:
            return {"chunk_ids_retournes": _rechercher(db, inputs["domaine"], inputs["question"])}

        def recall_evaluator(run, example) -> dict:
            attendu = example.outputs["chunk_id_attendu"]
            trouves = run.outputs["chunk_ids_retournes"]
            return {"key": f"recall@{TOP_K}", "score": 1.0 if attendu in trouves else 0.0}

        def mrr_evaluator(run, example) -> dict:
            attendu = example.outputs["chunk_id_attendu"]
            trouves = run.outputs["chunk_ids_retournes"]
            return {"key": "mrr", "score": _reciprocal_rank(trouves, attendu)}

        client.evaluate(target, data=dataset_name, evaluators=[recall_evaluator, mrr_evaluator])
        print(f"Evaluation envoyee sur LangSmith -- voir smith.langchain.com/projects (dataset '{dataset_name}').")
    except Exception as exc:
        print(f"(LangSmith non disponible ou non configure -- resume local ci-dessus uniquement. Detail : {exc})")


if __name__ == "__main__":
    db = SessionLocal()
    if any(item["chunk_id_attendu"] is None for item in GOLDEN_SET):
        _mode_decouverte(db)
    else:
        _mode_evaluation(db)
    db.close()
