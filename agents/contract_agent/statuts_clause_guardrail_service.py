"""Garde-fou juridique LLM des STATUTS SAS (service 1.1.4, niveau B du
garde-fou — 24/09/2026).

Pourquoi un module distinct de `legal_clause_guardrail_service.py` (pacte) :
- le prompt du pacte parle de « pacte d'associés » et juge chaque champ
  isolément, sans le texte de la clause : il bloquait des saisies correctes
  (ex. une adresse jugée contre « somme > 0 ») ;
- ici, le LLM ne reçoit QUE les champs marqués `controle_juridique` dans le
  clausier (texte libre à portée juridique : exceptions, motifs, majorités…),
  avec le texte de la clause, le libellé de chaque champ et les autres
  valeurs de la section ;
- les critères déjà vérifiés par code (niveau A, statuts_sas_regles_validite)
  ne lui sont pas donnés : le code est gratuit et toujours exact ;
- UN appel pour toute la section (pas un par champ), résultat mis en cache.

Le pacte garde son garde-fou actuel (hors périmètre, pas touché).

Réutilise `_get_client` et `_create_completion_with_backoff` du garde-fou du
pacte plutôt que de les recopier une 5e fois (voir la dette « retries Groq
dupliqués » dans sa docstring). Module sans accès base : le router lui passe
tout ce qu'il faut.
"""
import hashlib
import json
from collections import OrderedDict

from pydantic import BaseModel, Field, ValidationError

from agents.config.loader import get_llm_config, get_prompts
from agents.contract_agent.legal_clause_guardrail_service import (
    LegalClauseGuardrailError,
    _create_completion_with_backoff,
    _get_client,
)

# Cache mémoire des résultats (clé = empreinte du prompt complet). Évite de
# repayer un appel quand l'utilisateur renvoie la même section (retour
# arrière, erreur de niveau A corrigée sur un autre champ…). Borné : le
# plus ancien est retiré au-delà de la limite. Perdu au redémarrage : sans
# conséquence (simple ré-appel).
_CACHE_MAX = 512
_cache: "OrderedDict[str, dict[str, ChampResultat]]" = OrderedDict()


class ChampResultat(BaseModel):
    variable: str
    autorise: bool
    motif: str = Field(description="Une phrase simple, compréhensible par un non-juriste.")
    # Ligne affichée sous le champ (le motif complet est dans « Détails »).
    motif_court: str | None = Field(default=None, description="8 mots maximum.")
    article_cite: str | None = None
    reformulation_proposee: str | None = None


class SectionResultat(BaseModel):
    resultats: list[ChampResultat]


def construire_champs(
    variables_requises: list[dict], valeurs: dict, noms_associes: dict[str, str]
) -> tuple[list[dict], dict[str, tuple[str, str, str | None]]]:
    """Champs `controle_juridique` non vides d'une saisie, au format attendu
    par `check_statuts_section`, + {nom envoyé au LLM: (variable, libellé
    affiché, id associé)} pour rattacher chaque résultat à son champ.

    Une saisie par associé ({id: texte}) donne un champ par associé
    (`prestations_industrie[<id>]`). Partagé par le garde-fou à la saisie
    (router) et par la validation globale (agents/document_generation_validation)
    -- une seule façon de construire la demande au LLM."""
    cibles: dict[str, tuple[str, str, str | None]] = {}
    champs: list[dict] = []
    for v in variables_requises:
        if not v.get("controle_juridique"):
            continue
        valeur, libelle = valeurs.get(v["nom"]), v.get("libelle", v["nom"])
        entrees = (
            [
                (f"{v['nom']}[{cle}]", f"{libelle} — {noms_associes.get(str(cle), 'associé')}", t, str(cle))
                for cle, t in valeur.items()
            ]
            if isinstance(valeur, dict)
            else [(v["nom"], libelle, valeur, None)]
        )
        for nom_llm, libelle_affiche, texte, associe_id in entrees:
            if texte is not None and str(texte).strip():
                cibles[nom_llm] = (v["nom"], libelle_affiche, associe_id)
                champs.append({"nom": nom_llm, "libelle": libelle_affiche, "valeur": str(texte).strip()})
    return champs, cibles


def construire_autres_valeurs(variables_requises: list[dict], valeurs: dict) -> list[dict]:
    """Valeurs simples de la section hors champs contrôlés (contexte du LLM)."""
    controles = {v["nom"] for v in variables_requises if v.get("controle_juridique")}
    libelles = {v["nom"]: v.get("libelle", v["nom"]) for v in variables_requises}
    return [
        {"libelle": libelles.get(nom, nom), "valeur": val}
        for nom, val in valeurs.items()
        if nom not in controles and val not in (None, "") and not isinstance(val, (dict, list))
    ]


def _format_champs(champs: list[dict]) -> str:
    return "\n".join(f"- `{c['nom']}` ({c['libelle']}) : {c['valeur']}" for c in champs)


def _format_autres_valeurs(autres: list[dict]) -> str:
    if not autres:
        return "(aucune)"
    return "\n".join(f"- {a['libelle']} : {a['valeur']}" for a in autres)


def _format_criteres(criteres: list[dict]) -> str:
    if not criteres:
        return "(aucun critère particulier : applique le droit français des SAS)"
    return "\n".join(
        f"- {c['description_critere']}" + (f" — base légale : {c['base_legale']}" if c.get("base_legale") else "")
        for c in criteres
    )


def check_statuts_section(
    *,
    titre_clause: str,
    texte_clause: str,
    champs: list[dict],
    autres_valeurs: list[dict] | None = None,
    criteres: list[dict] | None = None,
) -> dict[str, ChampResultat]:
    """Vérifie en UN appel les champs à contrôler d'une section des statuts.

    `champs` : [{nom, libelle, valeur}] -- valeurs non vides uniquement (pour
    une saisie par associé, un nom distinct par associé, ex.
    `prestations_industrie[Alice]`) ; `autres_valeurs` : [{libelle, valeur}]
    du reste de la section, pour le contexte ; `criteres` : critères NON
    vérifiables par code. Renvoie {nom: résultat}. Un champ absent de la
    réponse du LLM est considéré autorisé (doute -> on ne bloque pas).

    Lève LegalClauseGuardrailError si le LLM est indisponible ou ne répond
    pas en JSON valide : l'appelant décide (statuts : ne pas bloquer)."""
    champs = [c for c in champs if str(c.get("valeur") or "").strip()]
    if not champs:
        return {}

    config = get_llm_config()["contract_agent"]["statuts_clause_guardrail"]
    prompt = get_prompts()["contract_agent"]["statuts_clause_guardrail"].format(
        titre_clause=titre_clause,
        texte_clause=texte_clause,
        champs=_format_champs(champs),
        autres_valeurs=_format_autres_valeurs(autres_valeurs or []),
        criteres=_format_criteres(criteres or []),
        schema_json=json.dumps(SectionResultat.model_json_schema()),
    )
    cle = hashlib.sha256(f"{config['model']}|{prompt}".encode()).hexdigest()
    if cle in _cache:
        _cache.move_to_end(cle)
        return _cache[cle]

    client = _get_client()
    last_error: Exception | None = None
    for _ in range(config["max_retries"]):
        try:
            response = _create_completion_with_backoff(
                client,
                model=config["model"],
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=config["temperature"],
            )
        except Exception as exc:
            raise LegalClauseGuardrailError(f"Échec de l'appel au LLM (Groq, garde-fou statuts) : {exc}") from exc
        try:
            resultat = SectionResultat.model_validate_json(response.choices[0].message.content or "{}")
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
        noms = {c["nom"] for c in champs}
        par_champ = {r.variable: r for r in resultat.resultats if r.variable in noms}
        _cache[cle] = par_champ
        if len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
        return par_champ

    raise LegalClauseGuardrailError(
        f"Le LLM n'a pas produit de JSON valide (garde-fou statuts) après {config['max_retries']} tentatives : {last_error}"
    )
