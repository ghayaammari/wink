"""Phase 2 (chunking) + Phase 3 (embedding) du service 1.1.1 — un seul script :
le chunking (Étape 2.2) ne persiste rien à part, un chunk n'existe qu'au
moment de son insertion dans `content_embeddings` (Étape 3.2). Même
convention que `backend/entrepreneur/scripts/seed_roadmap_nodes.py` (Groupe 1) :
un seul appel groupé à `embed_texts()`.

Depuis le CORRECTIF du 22/09/2026 (voir `run()`) : DEUX sessions DB courtes
(lecture, puis ecriture), pas une seule tenue ouverte pendant tout le script
-- une session unique qui traverse le calcul d'embeddings (CPU, lent) se
faisait couper par le pooler Supabase (mode transaction, port 6543). La
transaction d'ECRITURE reste atomique (un seul commit a la fin de la
phase 2) ; c'est seulement la lecture qui est desormais une transaction
distincte, fermee avant le calcul.

Lancement : `python -m backend.shared.knowledge_base.scripts.chunk_and_embed_legal_texts`
depuis `wink/`. Préalable obligatoire : migration 6f1a2c9d3e5b appliquée
(`alembic upgrade head`) — sans elle, la CheckConstraint sur
content_embeddings.domaine rejette 'forme_juridique'/'statuts_societe'.

Étape 2.1 : ne traite QUE les lignes `statut_contenu = 'valide_humain'" —
aucune redécision de `chunking_suggere`, déjà confirmé par le dashboard
(Phase 1.5). Idempotent par construction : `upsert_embedding` remplace par
(source_type, source_id, chunk_index), donc relancer ce script après une
correction de texte_brut ne crée jamais de doublon — mais attention, ça
signifie aussi qu'un article qui passait de 3 à 2 chunks laisserait un
chunk_index=2 orphelin en base (aucun mécanisme de suppression ici, pas
rencontré en pratique tant que chunking_suggere ne change pas après
validation — voir dashboard, qui repasse en extrait_automatique si le texte
change, donc hors de la liste traitée par ce script tant que non revalidé).

CORRECTIF du 11/09/2026 — skip des articles déjà à jour : relancer ce script
(ex: après une collecte partielle sur un autre domaine, comme le volet
assurance du service 1.1.10 qui partage cette même table) réembeddait
inutilement TOUS les articles déjà `valide_humain`, y compris ceux jamais
touchés — coût API (embedding) et temps gaspillés pour rien. Désormais, pour
chaque article, on recalcule les chunks localement (fonction pure, gratuite,
voir `chunk_texte_brut`) et on les compare aux chunks déjà en base
(`get_embedded_chunks`) : si le texte de chaque chunk ET le modèle utilisé
sont identiques, l'article est sauté — sinon (texte modifié, nombre de
chunks différent, ou changement du modèle d'embedding configuré), il repasse
par l'appel `embed_texts()`. Comparer le texte réel des chunks (pas juste
« une ligne existe déjà ») est nécessaire : un article revalidé après
correction retombe dans la liste `valide_humain` à traiter, et doit être
réembeddé, pas sauté à tort.

CORRECTIF du 11/09/2026 (2) — domaine assurance trop fin pour content_embeddings :
`legal_texts.domaine_reglementaire` du volet assurance (service 1.1.10) utilise
des valeurs fines par type d'obligation (ex: 'assurance_rc_pro', 'assurance_fintech',
voir `scrapers/legifrance/blocs_secteurs_assurance.py`), absentes de la
CheckConstraint `ck_content_embeddings_domaine` (qui n'connait que
'assurance_sectorielle', générique, partagé avec le volet 2 non-légal).
Passer `row.domaine_reglementaire` tel quel provoquait un CheckViolation à
l'insertion. Décision (11/09/2026, discussion pros/cons) : ne PAS étendre la
CheckConstraint avec les 7 domaines fins — le filtrage réel par secteur pour
l'orchestrateur nécessite de toute façon une jointure vers
`sector_insurance_recommendations.secteurs` (`content_embeddings` n'a pas de
colonne secteurs, et un domaine comme 'assurance_rc_pro' couvre a lui seul 11
secteurs — le découpage fin n'apporte donc pas le filtrage recherché, juste
une migration a rouvrir a chaque nouveau bloc Legifrance). `domaine_reglementaire`
reste fin sur `legal_texts` (métadonnée utile, colonne sans contrainte) ; seul
le domaine écrit dans `content_embeddings` est ramené au générique
'assurance_sectorielle' via `_domaine_embedding()` ci-dessous.
"""
import sys

# CORRECTIF du 16/09/2026 — chunk_texte_brut() produisait 1 seul chunk geant
# par page CNIL (jusqu'a 111 656 caracteres, voir chunk_texte_guide() pour le
# detail) : les guides/PDF (type_source != 'article_loi') passent desormais
# par chunk_texte_guide() (decoupage par paragraphes groupes), les articles de
# loi restent inchanges sur chunk_texte_brut(). Voir la boucle dans run().
from agents.config.loader import get_llm_config
from agents.ingestion.embedding_service import embed_texts
from agents.ingestion.legal_text_chunking_service import chunk_si_trop_long, chunk_texte_brut, chunk_texte_guide
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.content_embeddings_service import (
    get_embedded_chunks,
    upsert_embedding,
)
from backend.shared.knowledge_base.services.legal_texts_service import list_valide_humain

_CHAMP_SOURCE = "texte_brut"

# Domaines fins de legal_texts.domaine_reglementaire propres au volet assurance
# (service 1.1.10) — collapse vers 'assurance_sectorielle', seule valeur
# assurance acceptee par la CheckConstraint de content_embeddings.domaine.
# Voir CORRECTIF du 11/09/2026 (2) ci-dessus.
_DOMAINES_ASSURANCE_FINS = {
    "assurance_rc_pro",
    "assurance_decennale",
    "assurance_auto",
    "assurance_sante",
    "assurance_fintech",
    "assurance_environnement",
    "assurance_rc_produit",
}


def _domaine_embedding(domaine_reglementaire: str) -> str:
    if domaine_reglementaire in _DOMAINES_ASSURANCE_FINS:
        return "assurance_sectorielle"
    return domaine_reglementaire


def run() -> None:
    modele_utilise = get_llm_config()["embedding"]["model"]

    # CORRECTIF du 22/09/2026 — session unique tenue ouverte pendant tout le
    # calcul d'embeddings (chargement du modele CPU + calcul de N chunks,
    # potentiellement plusieurs dizaines de secondes) : sur le pooler Supabase
    # en mode transaction (port 6543, voir database.py), une connexion tenue
    # "idle in transaction" aussi longtemps se fait couper par le pooler
    # (`psycopg.OperationalError: server closed the connection unexpectedly`),
    # constate en pratique des le premier vrai run avec plusieurs domaines en
    # attente. `pool_pre_ping=True` ne protege pas ce cas : il revalide une
    # connexion recuperee DEPUIS le pool, jamais une connexion deja en cours
    # d'utilisation. Fix : lecture (phase 1, sa propre session, fermee avant
    # le calcul) puis calcul (aucune activite DB) puis ecriture (phase 2, une
    # session neuve, ouverte seulement une fois les vecteurs deja en main) --
    # la session d'ecriture n'est jamais idle plus que le temps des upserts.
    db_lecture = SessionLocal()
    try:
        rows = list_valide_humain(db_lecture)
        if not rows:
            print("Aucune ligne 'valide_humain' à traiter — rien à faire (voir dashboard Phase 1.5).")
            return
        print(f"{len(rows)} article(s) 'valide_humain' trouvé(s) — vérification des chunks déjà à jour...")

        # Chunking (Étape 2.2) : construit la liste plate de tous les chunks à
        # (re)embedder, pour un seul appel groupé à embed_texts() ensuite
        # (même raison que seed_roadmap_nodes.py : coût réseau/CPU négligeable,
        # mais reste la bonne pratique par défaut plutôt qu'un appel par chunk).
        # Skip (voir CORRECTIF du 11/09/2026 ci-dessus) : chunk_texte_brut est
        # une fonction pure (aucun coût), donc on peut toujours recalculer les
        # chunks pour comparaison — seul embed_texts() (API payante) est evite.
        # Chaque entree du plan ne garde que des valeurs primitives (pas l'objet
        # `row` ORM) : `db_lecture` est fermee avant le calcul des embeddings,
        # un objet ORM detache exposerait ses attributs deja charges mais autant
        # eviter toute ambiguite ici.
        plan: list[tuple] = []  # (row_id, domaine_reglementaire, chunking_suggere, chunk_index, chunk_texte)
        skipped = 0
        for row in rows:
            # type_source='article_loi' (defaut) : decoupage existant, inchange
            # (fonctionne bien sur un article de loi court). Tout le reste
            # (guide_pratique, pdf, faq) : chunk_texte_guide, voir sa docstring
            # — correctif du 16/09/2026, chunk_texte_brut produisait 1 seul
            # chunk geant par page CNIL, inutilisable pour la recherche
            # vectorielle (jusqu'a 111 656 caracteres dans un seul vecteur).
            if row.type_source == "article_loi":
                chunks_bruts = chunk_texte_brut(row.texte_brut, row.chunking_suggere)
                # Garde-fou (decision du 19/09/2026, voir docstring de
                # chunk_si_trop_long) : un article dont chunking_suggere n'a
                # rien pu decouper (texte source aplati sans saut de ligne,
                # constate sur l'AI Act) resterait sinon un chunk geant -
                # meme risque que les guides CNIL corriges le 16/09/2026,
                # ici rattrape au niveau article plutot qu'au niveau type_source.
                chunks = [c2 for c in chunks_bruts for c2 in chunk_si_trop_long(c)]
            else:
                # CORRECTIF du 22/09/2026 -- chunk_si_trop_long() manquait ici
                # (present seulement sur la branche article_loi ci-dessus,
                # meme garde-fou pourtant deja construit le 19/09/2026 contre
                # ce risque precis). chunk_texte_guide() decoupe sur `\n`, mais
                # un PDF extrait via pypdf (ex: referentiel SecNumCloud, voir
                # scrapers/anssi/) a souvent tres peu de vrais retours a la
                # ligne -- son garde-fou interne ("un paragraphe seul plus
                # long que max_chars reste un chunk entier") laissait alors
                # passer des chunks de plusieurs milliers de caracteres,
                # cause du 413 "Request too large" (Groq, 8000 TPM) du
                # sous-agent SecNumCloud des le premier appel a l'agent.
                chunks_bruts = chunk_texte_guide(row.texte_brut)
                chunks = [c2 for c in chunks_bruts for c2 in chunk_si_trop_long(c)]
            existants = get_embedded_chunks(db_lecture, source_type="legal_texts", source_id=str(row.id))
            deja_a_jour = (
                len(existants) == len(chunks)
                and all(e.chunk_texte == c for e, c in zip(existants, chunks))
                and all(e.modele_utilise == modele_utilise for e in existants)
            )
            if deja_a_jour:
                skipped += 1
                continue
            for index, chunk_texte in enumerate(chunks):
                plan.append((row.id, row.domaine_reglementaire, row.chunking_suggere, index, chunk_texte))
    finally:
        db_lecture.close()

    if not plan:
        print(f"Rien à réembedder — {skipped} article(s) déjà à jour.")
        return
    print(
        f"{len(plan)} chunk(s) à (ré)embedder ({skipped} article(s) déjà à jour ignoré(s)) — "
        "démarrage du calcul des embeddings (voir logs du modèle ci-dessous)..."
    )

    # Aucune activite DB pendant ce calcul (voir CORRECTIF ci-dessus) : c'est
    # precisement le segment qui faisait expirer la connexion avant.
    textes = [chunk_texte for _, _, _, _, chunk_texte in plan]
    vecteurs = embed_texts(textes)

    db_ecriture = SessionLocal()
    try:
        for (row_id, domaine_reglementaire, chunking_suggere, chunk_index, chunk_texte), vecteur in zip(
            plan, vecteurs
        ):
            upsert_embedding(
                db_ecriture,
                source_type="legal_texts",
                source_id=str(row_id),
                chunk_index=chunk_index,
                chunk_texte=chunk_texte,
                chunk_method=chunking_suggere,
                embedding=vecteur,
                modele_utilise=modele_utilise,
                champ_source=_CHAMP_SOURCE,
                domaine=_domaine_embedding(domaine_reglementaire),
            )

        db_ecriture.commit()
        nb_articles_traites = len({row_id for row_id, _, _, _, _ in plan})
        print(
            f"OK — {nb_articles_traites} article(s) réembeddé(s) "
            f"({len(plan)} chunks), {skipped} déjà à jour ignoré(s)."
        )
    except Exception:
        db_ecriture.rollback()
        raise
    finally:
        db_ecriture.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"Erreur — rien n'a été écrit en base (transaction d'écriture atomique, voir docstring) : {exc}", file=sys.stderr)
        sys.exit(1)
