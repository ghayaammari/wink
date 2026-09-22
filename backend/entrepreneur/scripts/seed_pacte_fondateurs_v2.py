"""Seed idempotent du contenu v2 du pacte de fondateurs (service 1.1.13,
Groupe 5, étape 1 de la ré-implémentation v2, 21/09/2026).

Charge les 3 fichiers `_v2.json` (générés par
`shared/knowledge_base/scripts/pacte_fondateurs/generate_pacte_fondateurs_v2.py` à partir de
`decisions_articles.json` -- jamais tapés à la main, voir le docstring de ce
générateur) dans les MÊMES tables que le pipeline v1
(`contract_clauses_library`, `document_templates`, `clause_validity_criteria`,
`content_embeddings`), sous un `document_type` différent :
`"pacte_fondateurs_v2"` au lieu de `"pacte_fondateurs"`.

Pourquoi réutiliser les mêmes tables plutôt que d'en créer de nouvelles :
`document_type` est déjà une colonne libre sans contrainte CHECK (voir
`contract_clauses_library.py`), et le moteur de session
(`document_generation_service.py`/`document_generation_router.py`) est déjà
générique par `document_type` -- aucune des deux tables ni du moteur n'a
besoin d'être dupliqué pour faire coexister v1 et v2. Un document v1 déjà
généré pour un projet reste intact : le v2 vit sous un `document_type`
distinct, aucune collision de clé (upsert par `(document_type, code_clause)`,
voir `contract_clause_library_service.py`).

Adaptations nécessaires par rapport à `seed_pacte_fondateurs.py` (v1), la
source `_v2.json` ayant un schéma différent (généré, pas recopié du v1) :

1. Les clauses v2 ne portent pas `document_type`/`source_modele`/
   `verifie_par_professionnel`/`forme_juridique_concernee` -- fournis en
   constantes ici plutôt que lus du JSON (`source_modele` reste "Bpifrance
   Création" : même modèle juridique source, seule la méthode d'extraction a
   changé -- via `decisions_articles.json` au lieu du .docx brut).
2. Les sections v2 ne portent pas `document_type` -- même traitement.
3. Contrairement à la validation v1, une section `mention_obligatoire` PEUT
   porter son propre `titre_affiche` en v2 (ex. "Préambule", commun aux deux
   variantes avec/sans investisseurs) -- la règle v1 qui l'interdisait est
   retirée ici, elle ne correspond pas au schéma réellement produit par le
   générateur v2.
4. `decisions_articles.json` ne couvre que les clauses -- il n'y a pas
   d'entrée pour la section `identification_des_parties`
   (`comportement_section="donnee_projet"`, gérée par
   `_render_identification_parties_v2()` dans le moteur, PAS par une clause).
   Cette section est injectée ici en constante (`_SECTION_IDENTIFICATION_PARTIES`)
   plutôt qu'ajoutée à la main dans le JSON généré -- elle est identique à la
   version v1, universelle, non dépendante d'une décision d'article.

Lancement : `python -m backend.entrepreneur.scripts.seed_pacte_fondateurs_v2`
depuis `wink/`.
"""
import json
import sys
from pathlib import Path

from agents.ingestion.embedding_service import embed_texts
from agents.config.loader import get_llm_config
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.clause_validity_criteria_service import upsert_criterion
from backend.shared.knowledge_base.services.contract_clause_library_service import upsert_clause
from backend.shared.knowledge_base.services.content_embeddings_service import upsert_embedding
from backend.shared.knowledge_base.services.document_template_service import upsert_section

_DATA_DIR = Path(__file__).parent / "data"
_DOCUMENT_TYPE = "pacte_fondateurs"  # RENOMME (26/09/2026) : etait "pacte_fondateurs_v2". Le pipeline v1 (fichiers, donnees DB, seed) a ete entierement supprime -- une seule version du pacte existe desormais, "_v2" n'a plus de sens comme suffixe distinctif. Docstring du module pas entierement mise a jour (garde l'historique de la coexistence v1/v2), seule cette constante et son usage runtime comptent.
# "pacte_fondateurs_v2" n'existe pas dans la contrainte CHECK de content_embeddings.domaine (liste fermee, voir ce modele) -- reutilise la valeur v1, deja autorisee : ce champ designe le domaine reglementaire pour le routage du copilot, pas la version du pipeline de donnees, et l'unicite des lignes est deja garantie par source_id (id de la clause), pas par domaine.
_DOMAINE = "pacte_fondateurs"
_CHUNK_METHOD = "aucun"
_SOURCE_MODELE = "Bpifrance Création"

_CHUNK_INDEX_DESCRIPTION_CLAUSE = 0
_CHUNK_INDEX_TEXTE_CLAUSE = 1

# Voir point 4 du docstring de module -- section universelle, pas issue de
# decisions_articles.json, injectée avant les sections générées. `ordre=0` la
# place avant le préambule (ordre 1/2 dans le JSON généré).
_SECTION_IDENTIFICATION_PARTIES = {
    "code_section": "identification_des_parties",
    "comportement_section": "donnee_projet",
    "ordre": 0,
    "obligatoire": True,
    "reference_code_clause": None,
    "variantes_candidates": None,
    "texte_statique": None,
    "formes_juridiques_concernees": None,
    "necessite_investisseurs": False,
    "necessite_absence_investisseurs": False,
    "depend_de_section": None,
    "depend_de_variantes": None,
    "titre_affiche": "Identification des parties",
    "explication": (
        "Qui signe ce pacte : les Associés Fondateurs et les Associés "
        "Investisseurs. Ces informations sont reprises automatiquement "
        "depuis la liste des associés de ton projet."
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
        # Point 3 du docstring de module : contrairement à v1, une
        # mention_obligatoire/clause_optionnelle PEUT avoir son propre
        # titre_affiche en v2 (ex. "Préambule" commun aux 2 variantes) --
        # seule l'obligation pour variante_obligatoire/donnee_projet est
        # vérifiée ici, pas d'interdiction pour les autres.
        needs_own_label = section["comportement_section"] in ("variante_obligatoire", "donnee_projet")
        if needs_own_label and not (section.get("titre_affiche") and section.get("explication")):
            raise SeedError(
                f"Section '{section['code_section']}' ({section['comportement_section']}) sans titre_affiche/explication."
            )

    # Vérification anti-répétition du bug v1 (préambule) : chaque libelle de
    # variable "de premier niveau" doit apparaître littéralement "(libelle)"
    # dans le texte de sa clause, au moins une fois (le moteur remplace TOUTES
    # les occurrences via `str.replace`, donc une répétition légitime du même
    # sens n'est pas un bug -- vérifié manuellement sur les 8 cas trouvés ici,
    # toujours la même valeur répétée, ex. "(organe compétent pour la
    # gouvernance)" cité 2-3 fois dans une même clause pour désigner le même
    # organe).
    #
    # Exclusion : les variables avec `depend_de_variable` (ex. seuil_pourcentage
    # dans repartition_benefices) sont des sous-variables conditionnelles,
    # substituées via `{nom}`.format() DANS le gabarit `valeurs_par_choix` de
    # leur variable parente (type "choix") -- voir `_resoudre_variables_choix`
    # dans document_generation_service.py -- elles n'apparaissent donc jamais
    # elles-mêmes comme "(libelle)" dans texte_clause, et leur `libelle` vaut
    # `None` par construction. Un `(None)` trouvé ici serait un vrai bug ;
    # l'absence pure et simple de placeholder pour ces variables est normale.
    for clause in clauses:
        for var in clause["variables_requises"]:
            if var.get("depend_de_variable"):
                continue
            if var.get("libelle") is None:
                raise SeedError(
                    f"Clause '{clause['code_clause']}' : variable '{var['nom']}' sans libelle "
                    "(et sans depend_de_variable -- ne peut pas être une sous-variable de gabarit)."
                )
            placeholder = f"({var['libelle']})"
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
            forme_juridique_concernee=None,
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


def run() -> None:
    clauses = _load_json("pacte_fondateurs_bpifrance_clauses_v2.json")
    sections = [_SECTION_IDENTIFICATION_PARTIES] + _load_json("pacte_fondateurs_document_templates_v2.json")
    criteria = _load_json("pacte_fondateurs_validity_criteria_v2.json")
    _validate(clauses, sections)

    vecteurs_by_code = _compute_embeddings(clauses)

    db = SessionLocal()
    try:
        clauses_by_code = _seed_clauses(db, clauses)
        _seed_sections(db, sections, clauses_by_code)
        _seed_criteria(db, criteria, clauses_by_code)
        _seed_embeddings(db, clauses_by_code, vecteurs_by_code)
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
