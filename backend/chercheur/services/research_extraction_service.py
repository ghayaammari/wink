"""Service — extraction automatique de contenu, pour 2 déclencheurs :
1) HAL/OpenAlex, à la fin de l'onboarding si extraction_preference != 'deposer'
2) Dépôt manuel d'un fichier (service 0.0.2) — le texte du PDF est extrait
   localement (pypdf), puis analysé par LLM (Qwen via Groq, voir
   paper_llm_service.py) pour en tirer les champs directs et les champs
   reformulés.

⚠️ Tourne en tâche de fond (FastAPI BackgroundTasks), donc APRÈS que la
réponse HTTP soit renvoyée. La session SQLAlchemy de la requête d'origine est
déjà fermée à ce moment — ce module ouvre donc SA PROPRE session
(`SessionLocal()`). Ne jamais lui passer le `db` d'une requête FastAPI.

Dette technique assumée pour l'I0 (à inscrire dans DECISIONS.md) :
- BackgroundTasks s'exécute dans le même process que l'API, sans persistance
  de la tâche elle-même. Si le serveur redémarre pendant l'extraction, le job
  est perdu.
- Pour le dépôt manuel c'est plus impactant que pour HAL/OpenAlex : aucune
  ligne research_works n'existe tant que l'extraction n'a pas fini (décision
  actée : pas de colonne de statut par travail). En cas d'échec (LLM,
  parsing PDF...), rien n'est persisté, le chercheur voit juste sa card
  "en cours" ne jamais aboutir côté frontend (timeout local de 90s).
- HAL/OpenAlex : si une des deux sources échoue (timeout, erreur HTTP), on
  continue avec l'autre plutôt que de faire échouer toute l'extraction — voir
  _safe_fetch. Si les DEUX échouent, sync_status passe quand même à
  'completed' avec zéro travail trouvé, indiscernable d'un chercheur sans
  publication. Pas de statut "extraction partielle/échouée" dédié pour
  l'instant — à améliorer si ça devient un problème réel en usage.
- Chaque travail extrait est commité individuellement dès qu'il est prêt
  (voir run_extraction) plutôt qu'en un seul commit à la fin du lot — un
  chercheur avec beaucoup de publications voit apparaître les premiers
  travaux au fur et à mesure, sans attendre que les N appels LLM (en série,
  avec pause anti rate-limit) soient tous terminés. Contrepartie assumée :
  en cas d'échec partiel, le chercheur peut se retrouver avec certains
  travaux traités et d'autres non, sans liste explicite de ce qui a échoué
  au-delà des logs serveur — acceptable en I0 tant que le rattrapage manuel
  (bouton "Extraire" à nouveau, régénération d'analyse par travail) reste
  disponible.
- À durcir si le volume augmente : queue avec persistance + retry, et un
  vrai statut par travail plutôt qu'un silence en cas d'échec.
- Décision actée : les champs factuels d'un travail (titre, résumé, auteurs,
  revue, doi, type de publication) sont soumis au cycle de validation
  researcher_field_values (confirm/reject/edit), en plus d'être écrits
  directement sur research_works à la création pour un affichage immédiat
  sans attendre une confirmation. S'applique désormais UNIFORMÉMENT aux deux
  flux (extrait_hal_openalex ET depot_manuel) — y compris les champs générés
  par LLM (paper_summary, methodology, key_findings, application_domains)
  pour les travaux extraits, qui n'étaient plus générés du tout dans une
  version intermédiaire de ce fichier (voir _generate_and_store_analysis).
  Limitation connue : un rejet ne réinitialise pas la colonne correspondante
  sur research_works — aucun mécanisme de "retour à vide" pour l'instant.
  La valeur initialement extraite reste affichée même après rejet ; le
  chercheur peut toujours la corriger via Modifier.
  ⚠️ Conséquence à trancher séparément : research_works.validation_status
  (validation globale du travail entier, gérée via ResearchWorkValidationUpdate)
  devient fonctionnellement redondant maintenant que chaque champ se valide
  individuellement — un travail extrait_hal_openalex reste indéfiniment
  "pending_confirmation" au niveau global si rien ne le fait plus jamais
  passer à "confirmed". Pas traité dans ce fichier, à décider : soit retirer
  ce statut global pour extrait_hal_openalex, soit le dériver automatiquement
  (confirmed une fois tous les champs confirmés).
- Déduplication locale dans _store_direct_fields_as_pending /
  _store_reformulated_fields : les sources externes (HAL notamment) peuvent
  renvoyer des doublons dans une même liste (ex: authFullName_s avec un nom
  répété — affiliation mal parsée comme auteur, doublon côté source). Deux
  valeurs identiques dans le MÊME lot d'insertion violent la contrainte
  UNIQUE au flush, même si rien n'existait en base avant — ce n'est pas
  rattrapé par la logique de réactivation d'add_value (qui compare contre ce
  qui est déjà commit, pas contre le lot en cours de construction). D'où un
  set() local dans chaque boucle d'insertion.
- Pause anti rate-limit Groq ajoutée dans run_extraction (voir time.sleep
  ci-dessous) : valeur fixe (2s), pas un vrai backoff adaptatif basé sur les
  headers de rate limit renvoyés par Groq — suffisant pour le volume de
  travaux attendu en I0, à revoir si ça devient limitant.
"""
import io
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from pypdf import PdfReader

from backend.chercheur.models.researcher_field_value import ResearcherFieldValue
from backend.chercheur.models.researcher_profile import ResearcherProfile
from backend.chercheur.models.research_work import ResearchWork
from backend.chercheur.services import paper_llm_service, researcher_field_value_service
from backend.chercheur.services.paper_llm_service import LLMExtractionError
from backend.chercheur.services.researcher_field_value_service import SINGLE_VALUE_FIELDS
from backend.shared.database import SessionLocal

logger = logging.getLogger(__name__)

HAL_DOCTYPE_TO_PUBLICATION_TYPE = {
    "ART": "article",
    "COMM": "communication",
    "THESE": "these",
    "REPORT": "rapport",
    "PATENT": "brevet",
}

OPENALEX_TYPE_TO_PUBLICATION_TYPE = {
    "article": "article",
    "proceedings-article": "communication",
    "dissertation": "these",
    "report": "rapport",
    "patent": "brevet",
}

# Champs factuels d'un dépôt manuel soumis au cycle de validation par champ.
# authors est géré séparément (multi-valeur, une ligne par auteur).
DIRECT_FIELD_NAMES = ("title", "abstract", "venue", "doi", "publication_type")

# Pause entre chaque appel LLM d'analyse (_generate_and_store_analysis),
# un par travail extrait — tier gratuit Groq limité à 7000 tokens/minute en
# entrée (ITPM). Sans pause, une extraction avec plusieurs dizaines de
# travaux déclenche autant d'appels en quelques secondes, dont la somme
# dépasse la limite (413 Payload Too Large observé le 05/09/2026 avec un
# volume de travaux plus faible mais des abstracts complets envoyés d'un
# coup dans un autre appel — même cause racine : trop de tokens/minute).
LLM_CALL_PAUSE_SECONDS = 2


def run_extraction(researcher_profile_id: uuid.UUID, orcid_id: str) -> None:
    """HAL/OpenAlex — voir _fetch_from_hal_openalex.

    Chaque travail est commité individuellement dès qu'il est entièrement
    traité (champs directs + analyse LLM), PAS dans un commit unique à la
    fin du lot. Deux raisons :
    1) Un chercheur avec beaucoup de publications attendait sinon plusieurs
       minutes (N appels LLM en série + pause anti rate-limit à chaque fois)
       avant de voir apparaître le moindre travail, alors que le premier
       pouvait être prêt en quelques secondes. Le frontend peut maintenant
       afficher chaque travail dès qu'il est prêt (voir ResearchWorksPage,
       polling sur profile.sync_status plutôt que sur l'apparition d'UN
       nouveau travail).
    2) Un échec sur UN travail (exception inattendue — pas LLMExtractionError,
       déjà géré dans _generate_and_store_analysis) ne fait plus perdre tout
       le travail déjà accompli sur les précédents : il est loggé et ignoré,
       l'extraction continue avec le suivant.
    """
    db = SessionLocal()
    try:
        profile = db.get(ResearcherProfile, researcher_profile_id)
        if profile is None:
            return  # profil supprimé entre le déclenchement et l'exécution

        profile.sync_status = "in_progress"
        db.commit()

        works_data = _fetch_from_hal_openalex(orcid_id)

        for work_data in works_data:
            try:
                work = ResearchWork(
                    researcher_profile_id=profile.id,
                    title=work_data["title"],
                    abstract=work_data.get("abstract"),
                    authors=work_data.get("authors"),
                    venue=work_data.get("venue"),
                    doi=work_data.get("doi"),
                    external_url=work_data.get("external_url"),
                    publication_type=work_data.get("publication_type"),
                    source_type="extrait_hal_openalex",
                    validation_status="pending_confirmation",
                    visibility="private_matching_only",
                )
                db.add(work)
                db.flush()  # attribue work.id, nécessaire pour les field_values liés

                _store_direct_fields_as_pending(db, work.id, work_data)
                _generate_and_store_analysis(db, work.id, work_data)

                db.commit()  # ce travail est visible côté frontend dès maintenant, indépendamment des suivants
            except Exception:
                db.rollback()
                logger.exception(
                    "Échec du traitement du travail extrait '%s' — travail ignoré, extraction poursuivie.",
                    work_data.get("title"),
                )
            finally:
                # Pause placée en finally : s'applique aussi après un échec,
                # pour ne pas accélérer artificiellement la boucle sur les
                # travaux qui échouent (un échec précoce, ex: parsing, ne
                # doit pas donner un rythme d'appels plus rapide que la
                # normale sur le reste du lot).
                time.sleep(LLM_CALL_PAUSE_SECONDS)

        for domain in _extract_domains(works_data):
            try:
                researcher_field_value_service.add_value(
                    db,
                    entity_type="researcher_profile",
                    entity_id=profile.id,
                    field_name="research_domains",
                    field_value=domain,
                    source="extracted_from_papers",
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Échec de l'ajout du domaine '%s'.", domain)

        profile.sync_status = "completed"
        profile.last_synced_at = datetime.now(timezone.utc)
        db.commit()

    except Exception:
        db.rollback()
        profile = db.get(ResearcherProfile, researcher_profile_id)
        if profile is not None:
            profile.sync_status = "failed"
            db.commit()
        raise
    finally:
        db.close()


def _generate_and_store_analysis(db, work_id: uuid.UUID, work_data: dict) -> None:
    """Génère paper_summary/methodology/key_findings/application_domains à
    partir de l'abstract seul (pas de PDF pour un travail extrait HAL/
    OpenAlex, contrairement au dépôt manuel qui a le texte complet). Skip si
    pas d'abstract exploitable : mieux vaut un travail sans champs
    analytiques qu'un LLM qui invente à partir de rien.

    Un échec LLM (rate limit Groq, timeout, réponse invalide) sur CE travail
    est loggé puis avalé plutôt que propagé — ne doit pas faire échouer toute
    l'extraction alors que les autres travaux et les champs factuels de
    celui-ci ont déjà réussi. Rattrapage manuel possible ensuite via
    POST /chercheur/travaux/{work_id}/regenerer-analyse."""
    abstract = work_data.get("abstract")
    if not abstract or not abstract.strip():
        return

    try:
        reformulated = paper_llm_service.generate_reformulated_fields(
            abstract, {"title": work_data.get("title")}
        )
    except LLMExtractionError as exc:
        logger.warning(
            "Génération d'analyse LLM échouée pour le travail '%s' (work_id=%s) : %s — "
            "aucun champ généré, régénération manuelle possible.",
            work_data.get("title"),
            work_id,
            exc,
        )
        return

    _store_reformulated_fields(db, work_id, reformulated)


def run_manual_deposit_extraction(researcher_profile_id: uuid.UUID, file_url: str, file_bytes: bytes) -> None:
    """Dépôt manuel (service 0.0.2). file_bytes est transmis directement par
    le router (déjà en mémoire au moment de l'upload) — pas de retélé-
    chargement depuis file_url, qui pointe vers Cloudinary et ajouterait un
    aller-retour réseau inutile alors qu'on a déjà les données en main.

    Contrairement à run_extraction, la ligne research_works n'existe pas
    avant la fin du traitement — elle est créée ici, une fois les champs
    directs extraits par le LLM. Ces champs directs sont écrits sur les
    colonnes ET soumis en parallèle au cycle de validation par champ
    (voir _store_direct_fields_as_pending) — affichage immédiat, correction
    possible via le mode "Consulter les champs à confirmer" côté frontend."""
    db = SessionLocal()
    try:
        raw_text = _extract_text_from_pdf(file_bytes)

        if not raw_text.strip():
            # PDF scanné ou vide (pas de couche texte) — aucune extraction
            # possible avec l'approche actuelle (pas d'OCR/VLM branché).
            # On abandonne proprement plutôt que d'envoyer du vide au LLM,
            # qui inventerait un contenu à partir de rien.
            return

        direct_fields = paper_llm_service.extract_direct_fields(raw_text)

        work = ResearchWork(
            researcher_profile_id=researcher_profile_id,
            title=direct_fields["title"],
            abstract=direct_fields.get("abstract"),
            authors=direct_fields.get("authors"),
            venue=direct_fields.get("venue"),
            doi=direct_fields.get("doi"),
            publication_type=direct_fields.get("publication_type"),
            source_type="depot_manuel",
            file_url=file_url,
            validation_status="confirmed",  # validation globale du dépôt — distincte de la validation par champ ci-dessous
            visibility="private_matching_only",
        )
        db.add(work)
        db.flush()  # nécessaire pour obtenir work.id avant de créer les field_values liés

        _store_direct_fields_as_pending(db, work.id, direct_fields)

        reformulated = paper_llm_service.generate_reformulated_fields(raw_text, direct_fields)
        _store_reformulated_fields(db, work.id, reformulated)

        db.commit()

    except Exception:
        db.rollback()
        raise  # pas de trace persistée possible ici (voir dette technique en tête de fichier)
    finally:
        db.close()


def regenerate_analysis(work_id: uuid.UUID, abstract: str, title: str | None) -> None:
    """Rattrapage manuel — relance UNE analyse LLM (paper_summary,
    methodology...) pour un travail déjà existant en base, quand l'appel
    initial a échoué (rate limit Groq typiquement — voir
    _generate_and_store_analysis / l'absence de try/except autour de
    generate_reformulated_fields dans run_manual_deposit_extraction, où un
    échec LLM fait actuellement échouer toute la création du travail).

    Ne touche jamais aux champs factuels (titre, auteurs, DOI...), déjà en
    base — uniquement les champs analytiques via researcher_field_values.
    Appelée par POST /chercheur/travaux/{work_id}/regenerer-analyse."""
    db = SessionLocal()
    try:
        try:
            reformulated = paper_llm_service.generate_reformulated_fields(abstract, {"title": title})
        except LLMExtractionError as exc:
            logger.warning("Régénération d'analyse toujours en échec pour work_id=%s : %s", work_id, exc)
            return
        _store_reformulated_fields(db, work_id, reformulated)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _store_direct_fields_as_pending(db, work_id: uuid.UUID, direct_fields: dict) -> None:
    """Crée une ligne pending_confirmation pour chaque champ factuel déjà
    écrit sur les colonnes de research_works (voir run_manual_deposit_extraction) —
    permet au chercheur de confirmer/corriger/rejeter titre, résumé, auteurs,
    revue, doi et type de publication via le même mécanisme que les champs
    générés, plutôt que de les considérer comme fiables par défaut.

    Cas limite géré ici : les sources externes (HAL notamment) renvoient
    parfois des doublons dans authFullName_s (affiliation mal parsée comme
    auteur, doublon côté source). Sans le set() ci-dessous, deux valeurs
    identiques dans le même lot d'insertion violent la contrainte UNIQUE au
    flush, même si rien n'existait en base avant."""
    for field_name in DIRECT_FIELD_NAMES:
        value = direct_fields.get(field_name)
        if not value:
            continue  # champ introuvable par le LLM — rien à soumettre à validation
        db.add(
            ResearcherFieldValue(
                entity_type="research_work",
                entity_id=work_id,
                field_name=field_name,
                field_value=str(value),
                source="extracted_from_papers",
                validation_status="pending_confirmation",
            )
        )

    seen_authors: set[str] = set()
    for author in direct_fields.get("authors") or []:
        if not author or author in seen_authors:
            continue
        seen_authors.add(author)
        db.add(
            ResearcherFieldValue(
                entity_type="research_work",
                entity_id=work_id,
                field_name="authors",
                field_value=author,
                source="extracted_from_papers",
                validation_status="pending_confirmation",
            )
        )


def _store_reformulated_fields(db, work_id: uuid.UUID, reformulated: dict) -> None:
    """Transforme le dict renvoyé par paper_llm_service en lignes
    researcher_field_values. application_domains est multi-valeur (une ligne
    par élément de la liste) — les autres champs (methodology, key_findings,
    paper_summary) sont à valeur unique (une seule ligne).

    Réutilise SINGLE_VALUE_FIELDS de researcher_field_value_service plutôt
    que de redéfinir ici quels champs sont multi-valeur : un seul point de
    vérité, sinon un champ qui change de catégorie un jour désynchronise
    silencieusement ce fichier et researcher_field_value_service.py.

    Même garde-fou de déduplication que _store_direct_fields_as_pending :
    le LLM peut répéter une valeur quasi-identique dans une liste multi-
    valeur (application_domains), ce qui violerait la contrainte UNIQUE au
    flush si on ne filtrait pas les doublons dans le même lot."""
    for field_name, field_value in reformulated.items():
        if not field_value:
            continue  # champ introuvable par le LLM (null/vide) — rien à valider

        if field_name in SINGLE_VALUE_FIELDS:
            values = [field_value]
        elif isinstance(field_value, list):
            values = field_value
        else:
            # cas limite : le LLM peut renvoyer une string au lieu d'une
            # liste pour un champ multi-valeur malgré la consigne — sans ce
            # garde-fou, `for v in field_value` itérerait caractère par
            # caractère sur la string.
            values = [field_value]

        seen: set[str] = set()
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            db.add(
                ResearcherFieldValue(
                    entity_type="research_work",
                    entity_id=work_id,
                    field_name=field_name,
                    field_value=value,
                    source="llm_generated",
                    validation_status="pending_confirmation",
                )
            )


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extraction réelle du texte via pypdf — suffisant pour la plupart des
    papiers académiques (couche texte native). Un PDF scanné (uniquement des
    pages image) renvoie une chaîne vide ici, géré par l'appelant."""
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# ---------------------------------------------------------------------------
# HAL / OpenAlex — extraction à l'onboarding, à partir de l'ORCID
# ---------------------------------------------------------------------------

def _fetch_from_hal_openalex(orcid_id: str) -> list[dict]:
    """Interroge HAL et OpenAlex, dédoublonne par DOI (HAL prioritaire en cas
    de doublon — décision produit : le projet est centré sur l'écosystème
    français). Les travaux sans DOI des deux sources sont tous conservés
    (pas de dédoublonnage par titre pour l'I0 — trop de faux positifs/négatifs
    possibles sans une comparaison floue, hors scope pour l'instant)."""
    hal_works = _safe_fetch(_fetch_from_hal, orcid_id)
    openalex_works = _safe_fetch(_fetch_from_openalex, orcid_id)

    by_doi: dict[str, dict] = {}
    without_doi: list[dict] = []

    for work in hal_works:
        doi = _normalize_doi(work.get("doi"))
        if doi:
            by_doi[doi] = work
        else:
            without_doi.append(work)

    for work in openalex_works:
        doi = _normalize_doi(work.get("doi"))
        if doi:
            by_doi.setdefault(doi, work)  # HAL déjà présent au même DOI → gardé, OpenAlex ignoré
        else:
            without_doi.append(work)

    return list(by_doi.values()) + without_doi


def _safe_fetch(fetch_fn, orcid_id: str) -> list[dict]:
    """Une source indisponible (timeout, erreur HTTP, changement d'API) ne
    doit pas faire échouer toute l'extraction si l'autre source répond — on
    renvoie une liste vide plutôt que de propager l'exception."""
    try:
        return fetch_fn(orcid_id)
    except httpx.HTTPError:
        return []


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def _first(value) -> str | None:
    """HAL renvoie des listes même pour des champs à valeur unique (title_s,
    abstract_s...) — prend le premier élément, None si absent/vide."""
    if isinstance(value, list) and value:
        return value[0]
    return None


def _fetch_from_hal(orcid_id: str) -> list[dict]:
    params = {
        "q": f'authORCIDIdExt_s:"{orcid_id}"',
        "fl": "title_s,abstract_s,authFullName_s,journalTitle_s,conferenceTitle_s,doiId_s,docType_s,uri_s,keyword_s",
        "wt": "json",
        "rows": 100,
    }
    response = httpx.get("https://api.archives-ouvertes.fr/search/", params=params, timeout=15)
    response.raise_for_status()
    docs = response.json().get("response", {}).get("docs", [])

    works = []
    for doc in docs:
        title = _first(doc.get("title_s"))
        if not title:
            continue  # research_works.title est NOT NULL — un doc sans titre exploitable est ignoré
        works.append(
            {
                "title": title,
                "abstract": _first(doc.get("abstract_s")),
                "authors": doc.get("authFullName_s") or None,
                "venue": _first(doc.get("journalTitle_s")) or _first(doc.get("conferenceTitle_s")),
                "doi": doc.get("doiId_s"),
                "external_url": doc.get("uri_s"),
                "publication_type": HAL_DOCTYPE_TO_PUBLICATION_TYPE.get(doc.get("docType_s")),
                "_domain_hints": doc.get("keyword_s") or [],
            }
        )
    return works


def _fetch_from_openalex(orcid_id: str) -> list[dict]:
    orcid_url = orcid_id if orcid_id.startswith("http") else f"https://orcid.org/{orcid_id}"
    params = {"filter": f"author.orcid:{orcid_url}", "per-page": 100}
    response = httpx.get("https://api.openalex.org/works", params=params, timeout=15)
    response.raise_for_status()
    results = response.json().get("results", [])

    works = []
    for item in results:
        title = item.get("title")
        if not title:
            continue  # research_works.title est NOT NULL
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        concepts = item.get("concepts") or []
        top_concepts = [c["display_name"] for c in concepts if c.get("score", 0) >= 0.3]

        works.append(
            {
                "title": title,
                "abstract": _reconstruct_abstract(item.get("abstract_inverted_index")),
                "authors": [
                    a["author"]["display_name"] for a in item.get("authorships", []) if a.get("author")
                ]
                or None,
                "venue": source.get("display_name"),
                "doi": item.get("doi"),
                "external_url": primary_location.get("landing_page_url") or item.get("id"),
                "publication_type": OPENALEX_TYPE_TO_PUBLICATION_TYPE.get(item.get("type")),
                "_domain_hints": top_concepts,
            }
        )
    return works


def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """OpenAlex ne fournit pas l'abstract en texte brut mais sous forme
    d'index inversé (mot -> positions), pour des raisons de droits d'usage —
    reconstruction en texte lisible à partir des positions."""
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions[idx] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def _extract_domains(works_data: list[dict]) -> list[str]:
    """Domaines dérivés des indices bruts renvoyés par les sources (mots-clés
    HAL, concepts OpenAlex — voir _domain_hints attaché par _fetch_from_hal /
    _fetch_from_openalex), dédoublonnés (insensible à la casse). Pas de LLM
    ici : ces métadonnées sont déjà structurées côté source, un passage LLM
    ajouterait un coût et une latence sans gain clair pour l'I0."""
    seen: set[str] = set()
    domains: list[str] = []
    for work in works_data:
        for hint in work.get("_domain_hints", []):
            normalized = hint.strip()
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                domains.append(normalized)
    return domains