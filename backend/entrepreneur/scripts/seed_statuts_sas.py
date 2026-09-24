"""Seed idempotent du contenu v2 des statuts SAS (service 1.1.4, Phase 5,
23/09/2026).

Charge les 3 fichiers de sortie du générateur statuts SAS
(`shared/knowledge_base/scripts/statuts_sas/generate_statuts_sas_v2.py`, qui
produit `statuts_sas_clauses.json`, `statuts_sas_document_templates.json` et
`statuts_sas_validity_criteria.json` à partir du clausier
`decisions_articles_statuts_sas.json` -- jamais tapés à la main, voir le
docstring de ce générateur) dans les MÊMES tables que le pipeline pacte v2
(`contract_clauses_library`, `document_templates`, `clause_validity_criteria`,
`content_embeddings`), sous `document_type="statuts"`.

Pourquoi réutiliser les mêmes tables : `document_type` est une colonne libre
sans contrainte CHECK (voir `contract_clauses_library.py`) et le moteur de
session (`document_generation_service.py`/`document_generation_router.py`) est
déjà générique par `document_type` -- rien à dupliquer. Un document pacte déjà
généré pour un projet reste intact : les deux contenus vivent sous des
`document_type` distincts, l'upsert est par `(document_type, code_clause)`
(voir `contract_clause_library_service.py`).

Pourquoi `"statuts"` et pas `"statuts_sas"` : la table `documents` porte une
liste fermée `ck_documents_document_type` (migration d2e3f4a5b6c7) qui
n'accepte QUE 'entrepreneur_idea', 'other', 'pacte_fondateurs' et 'statuts',
et `document_schemas.py` la reflète (`DocumentType = Literal[...]`). Même
précédent que le pacte : le contenu réutilise la valeur déjà autorisée au lieu
d'étendre la contrainte par migration (une seule source de vérité côté Python,
le module `document_schemas.py`, n'est pas touchée ici).

Adaptations par rapport à `seed_pacte_fondateurs_v2.py` (le modèle) :

1. Convention de placeholder : le texte des clauses statuts SAS porte `(nom)`
   de variable (ex. "(capital_social)"), pas le `libelle` ("montant du capital
   social" reste le libellé humain). Le contrôle d'occurrence du seed vérifie
   donc la présence de `(nom)` dans `texte_clause`, au lieu de `(libelle)`.
2. Groupes de variantes sans titre : le pacte exige `titre_affiche` +
   `explication` sur chaque `variante_obligatoire`. En SAS, un groupe peut être
   un simple contenant (ex. `motifs_revocation_president`) dont les candidats
   portent chacun leur propre titre/trigger (convention supposée par le frontend
   `PacteSectionFormV2` : "chaque titre de candidat porte son propre trigger").
   La validation exige donc titre+explication UNIQUEMENT pour `donnee_projet`.
3. Section `identification_des_parties` (`donnee_projet`) : aucune entrée du
   clausier ne l'émet (l'entête est `cible="donnee_projet_dynamique"`, ignorée
   par le générateur) -- elle est injectée ici en constante, comme pour le
   pacte. `ordre=0` (décimal) la place avant les titres d'articles (0.5, 1.5, ...).
4. `valeur_limite` des critères est un dict structuré (`{"unite": ..., "max": ...}`)
   -- passé tel quel à `upsert_criterion`, comme pour le pacte.

Lancement : `python -m backend.entrepreneur.scripts.seed_statuts_sas` depuis
`wink/`.
"""
import json
import sys
from pathlib import Path

from agents.ingestion.embedding_service import embed_texts
from agents.config.loader import get_llm_config
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.clause_validity_criteria_service import upsert_criterion
from backend.shared.knowledge_base.services.contract_clause_library_service import upsert_clause
from backend.shared.knowledge_base.services.content_embeddings_service import delete_for_source, upsert_embedding
from backend.shared.knowledge_base.services.contract_clause_library_service import list_hors_liste
from backend.shared.knowledge_base.services.document_template_service import delete_hors_liste, upsert_section

_DATA_DIR = Path(__file__).parent / "data"
# "statuts_sas" n'existe pas dans la liste fermée de `documents.document_type`
# (voir docstring de module) -- la valeur v1 "statuts" est réutilisée telle
# quelle, comme le pacte avec "pacte_fondateurs".
_DOCUMENT_TYPE = "statuts"
# Le domaine content_embeddings a une liste fermée (voir ce modèle) : "statuts"
# (schéma I1, dépôt des statuts) est déjà autorisée, contrairement à
# "statuts_sas". Réutilisée pour le routage copilot sans migration.
_DOMAINE = "statuts"
_CHUNK_METHOD = "aucun"
_SOURCE_MODELE = "Bpifrance Création"

_CHUNK_INDEX_DESCRIPTION_CLAUSE = 0
_CHUNK_INDEX_TEXTE_CLAUSE = 1

# Section `donnee_projet` injectée (clausier : entête `identification_des_parties`,
# `cible="donnee_projet_dynamique"` -- le générateur n'émet rien pour elle, comme
# le pacte). `ordre=0` la place avant les titres d'articles (ordres 0.5, 1.5, ...).
_SECTION_IDENTIFICATION_PARTIES = {
    "code_section": "identification_des_parties",
    "comportement_section": "donnee_projet",
    "ordre": 0,
    "obligatoire": True,
    "reference_code_clause": None,
    "variantes_candidates": None,
    "texte_statique": None,
    "formes_juridiques_concernees": ["SAS"],
    "necessite_investisseurs": False,
    "necessite_absence_investisseurs": False,
    "depend_de_section": None,
    "depend_de_variantes": None,
    "titre_affiche": "Identification des parties",
    "explication": (
        "Qui constitue la Société : les Associés (dénomination sociale, capital, "
        "siège social, identité de chaque associé). Ces informations sont reprises "
        "automatiquement depuis la liste des associés de ton projet."
    ),
}


class SeedError(Exception):
    """Erreur de validation des JSON source, avant toute écriture en base."""


def _load_json(name: str):
    with open(_DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _validate(clauses: list[dict], sections: list[dict]) -> None:
    codes_clauses = {c["code_clause"] for c in clauses}
    if len(codes_clauses) != len(clauses):
        seen, dupes = set(), set()
        for c in clauses:
            if c["code_clause"] in seen:
                dupes.add(c["code_clause"])
            seen.add(c["code_clause"])
        raise SeedError(f"Codes de clause en doublon dans le JSON source : {sorted(dupes)}")

    codes_sections = {s["code_section"] for s in sections}
    if len(codes_sections) != len(sections):
        raise SeedError("Codes de section en doublon dans le JSON source (ou avec la section injectée).")

    for section in sections:
        referenced = (
            [section["reference_code_clause"]] if section.get("reference_code_clause") else []
        ) + (section.get("variantes_candidates") or [])
        missing = [s for s in referenced if s not in codes_clauses]
        if missing:
            raise SeedError(f"Section '{section['code_section']}' référence un code_clause inconnu : {missing}")
        if section["comportement_section"] == "variante_obligatoire" and not section.get("variantes_candidates"):
            raise SeedError(f"Section '{section['code_section']}' est variante_obligatoire sans variantes_candidates.")
        if section["comportement_section"] in ("mention_obligatoire", "clause_optionnelle") and not section.get(
            "reference_code_clause"
        ):
            raise SeedError(
                f"Section '{section['code_section']}' ({section['comportement_section']}) sans reference_code_clause."
            )
        # Point 2 du docstring de module : contrairement au pacte, un groupe
        # `variante_obligatoire` SAS PEUT être un simple contenant sans
        # titre/explication (les candidats portent leur propre titre). Seule la
        # section `donnee_projet` (identification injectée ci-dessus) l'exige.
        if section["comportement_section"] == "donnee_projet" and not (
            section.get("titre_affiche") and section.get("explication")
        ):
            raise SeedError(
                f"Section '{section['code_section']}' (donnee_projet) sans titre_affiche/explication."
            )

    # Contrôle d'occurrence des variables : chaque variable "de premier niveau"
    # doit apparaître littéralement "(nom)" dans le texte de sa clause, au moins
    # une fois (point 1 du docstring de module -- le placeholder SAS est le
    # `nom`, pas le `libelle`). Le moteur remplace TOUTES les occurrences via
    # `str.replace`, donc une répétition légitime de la même variable dans une
    # clause n'est pas un bug.
    #
    # Exclusion : les variables avec `depend_de_variable` (un seul cas : la
    # majorité renforcée sous condition, dans modalites_decisions_collectives)
    # sont des sous-variables conditionnelles substituées dans le gabarit de
    # leur variable parente (`choix`) -- voir `_resoudre_variables_choix` dans
    # document_generation_service.py -- elles n'apparaissent jamais elles-mêmes
    # comme "(nom)" dans texte_clause ; leur `libelle` vaut `None` là aussi.
    for clause in clauses:
        for var in clause["variables_requises"]:
            if var.get("depend_de_variable"):
                continue
            if var.get("libelle") is None:
                raise SeedError(
                    f"Clause '{clause['code_clause']}' : variable '{var['nom']}' sans libelle "
                    "(et sans depend_de_variable -- ne peut pas être une sous-variable de gabarit)."
                )
            placeholder = f"({var['nom']})"
            if clause["texte_clause"].count(placeholder) < 1:
                raise SeedError(
                    f"Clause '{clause['code_clause']}' : placeholder {placeholder!r} absent de texte_clause."
                )


def _seed_clauses(db, clauses: list[dict]) -> dict[str, object]:
    by_code = {}
    for clause in clauses:
        row = upsert_clause(
            db,
            document_type=_DOCUMENT_TYPE,
            code_clause=clause["code_clause"],
            description_clause=clause["description_clause"],
            titre_clause=clause["titre_clause"],
            texte_clause=clause["texte_clause"],
            variables_requises=clause["variables_requises"],
            source_modele=_SOURCE_MODELE,
            verifie_par_professionnel=False,
            forme_juridique_concernee="SAS",
        )
        by_code[clause["code_clause"]] = row
    db.flush()
    for code_clause, row in by_code.items():
        if row.id is None:
            db.refresh(row)
    return by_code


def _seed_sections(db, sections: list[dict], clauses_by_code: dict[str, object]) -> None:
    for section in sections:
        reference_id = None
        reference_type = None
        if section["comportement_section"] in ("mention_obligatoire", "clause_optionnelle"):
            reference_id = clauses_by_code[section["reference_code_clause"]].id
            reference_type = "contract_clauses_library"

        upsert_section(
            db,
            document_type=_DOCUMENT_TYPE,
            code_section=section["code_section"],
            ordre=section["ordre"],
            comportement_section=section["comportement_section"],
            obligatoire=section["obligatoire"],
            reference_type=reference_type,
            reference_id=reference_id,
            variantes_candidates=section.get("variantes_candidates"),
            texte_statique=section.get("texte_statique"),
            formes_juridiques_concernees=section.get("formes_juridiques_concernees"),
            necessite_investisseurs=section.get("necessite_investisseurs", False),
            necessite_absence_investisseurs=section.get("necessite_absence_investisseurs", False),
            depend_de_section=section.get("depend_de_section"),
            depend_de_variantes=section.get("depend_de_variantes"),
            titre_affiche=section.get("titre_affiche"),
            explication=section.get("explication"),
        )


def _seed_criteria(db, criteria: list[dict], clauses_by_code: dict[str, object]) -> None:
    for critere in criteria:
        clause = clauses_by_code.get(critere["code_clause"])
        if clause is None:
            raise SeedError(f"Critère de validité référence un code_clause inconnu : {critere['code_clause']}")
        upsert_criterion(
            db,
            clause_library_id=clause.id,
            type_critere=critere["type_critere"],
            description_critere=critere["description_critere"],
            base_legale=critere["base_legale"],
            valeur_limite=critere.get("valeur_limite"),
        )


def _compute_embeddings(clauses: list[dict]) -> dict[str, dict[int, tuple[str, str, list[float]]]]:
    textes, meta = [], []
    for clause in clauses:
        textes.append(clause["description_clause"])
        meta.append((clause["code_clause"], _CHUNK_INDEX_DESCRIPTION_CLAUSE, "description_clause"))
        textes.append(clause["texte_clause"])
        meta.append((clause["code_clause"], _CHUNK_INDEX_TEXTE_CLAUSE, "texte_clause"))

    vecteurs = embed_texts(textes)

    par_code: dict[str, dict[int, tuple[str, str, list[float]]]] = {}
    for (code_clause, chunk_index, champ_source), texte, vecteur in zip(meta, textes, vecteurs):
        par_code.setdefault(code_clause, {})[chunk_index] = (champ_source, texte, vecteur)
    return par_code


def _seed_embeddings(
    db,
    clauses_by_code: dict[str, object],
    vecteurs_by_code: dict[str, dict[int, tuple[str, str, list[float]]]],
) -> None:
    modele_utilise = get_llm_config()["embedding"]["model"]

    for code_clause, row in clauses_by_code.items():
        for chunk_index, (champ_source, chunk_texte, vecteur) in vecteurs_by_code[code_clause].items():
            upsert_embedding(
                db,
                source_type="contract_clauses_library",
                source_id=str(row.id),
                chunk_index=chunk_index,
                chunk_texte=chunk_texte,
                chunk_method=_CHUNK_METHOD,
                embedding=vecteur,
                modele_utilise=modele_utilise,
                champ_source=champ_source,
                domaine=_DOMAINE,
            )


def _purger_obsoletes(db, sections: list[dict], clauses: list[dict]) -> None:
    """Supprime ce qui n'existe plus dans les JSON générés (24/09/2026) :
    sections aux positions en trop, clauses retirées ou exclues (articles hors
    périmètre, actions de préférence…), avec leurs embeddings — leurs critères
    de validité partent en cascade (FK ondelete=CASCADE). Systématique, pas
    une option : un squelette qui rétrécit sans purge laisserait des sections
    fantômes posées à l'utilisateur. La liste supprimée est affichée.

    Cas limite : une session statuts en cours dont une réponse pointe vers une
    section supprimée garde cette réponse, simplement ignorée (le moteur ne
    parcourt que les sections existantes) — faire « Recommencer » pour repartir
    proprement."""
    sections_supprimees = delete_hors_liste(
        db, document_type=_DOCUMENT_TYPE, ordres_gardes={s["ordre"] for s in sections}
    )
    clauses_obsoletes = list_hors_liste(
        db, document_type=_DOCUMENT_TYPE, codes_gardes={c["code_clause"] for c in clauses}
    )
    embeddings_supprimes = 0
    for clause in clauses_obsoletes:
        embeddings_supprimes += delete_for_source(db, source_type="contract_clauses_library", source_id=str(clause.id))
        db.delete(clause)
    db.flush()
    print(f"Purge — {len(sections_supprimees)} section(s) : {sections_supprimees}")
    print(
        f"Purge — {len(clauses_obsoletes)} clause(s) : {sorted(c.code_clause for c in clauses_obsoletes)} "
        f"({embeddings_supprimes} embedding(s), critères supprimés en cascade)"
    )


def run() -> None:
    clauses = _load_json("statuts_sas_clauses.json")
    sections = [_SECTION_IDENTIFICATION_PARTIES] + _load_json("statuts_sas_document_templates.json")
    criteria = _load_json("statuts_sas_validity_criteria.json")
    _validate(clauses, sections)

    vecteurs_by_code = _compute_embeddings(clauses)

    db = SessionLocal()
    try:
        clauses_by_code = _seed_clauses(db, clauses)
        _seed_sections(db, sections, clauses_by_code)
        _seed_criteria(db, criteria, clauses_by_code)
        _seed_embeddings(db, clauses_by_code, vecteurs_by_code)
        _purger_obsoletes(db, sections, clauses)
        db.commit()
        print(
            f"OK — {len(clauses)} clauses, {len(sections)} sections, {len(criteria)} critère(s) "
            f"upsertés, {len(clauses) * 2} embeddings upsertés (document_type='{_DOCUMENT_TYPE}')."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        run()
    except SeedError as exc:
        print(f"Erreur de validation des données source — rien n'a été écrit en base : {exc}", file=sys.stderr)
        sys.exit(1)