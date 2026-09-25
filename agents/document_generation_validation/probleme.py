"""Format commun d'un problème et d'une étape de la validation globale
(agents/document_generation_validation, 24/09/2026).

Un problème dit (retour utilisateur 25/09/2026 : « pas seulement une notice ») :
- OÙ : `cible_libelle` (article / clause), `cible_type` = "section" (à
  rouvrir, `cible` = code_section) ou "page" (`cible` = informations_legales
  | equipe_capital | dirigeants) ;
- QUOI : `champ` et `valeur_actuelle` ;
- COMMENT corriger : `correction_proposee` (texte), et `valeur_a_appliquer`
  ({variable, valeur}) quand la bonne valeur est CERTAINE (bouton
  « Appliquer ») ;
- POURQUOI : `message` (+ `base_legale`), affiché sous « Pourquoi ? ».
`message_court` reste le titre d'une ligne de la carte.
"""
from dataclasses import asdict, dataclass

GRAVITE_BLOQUANT = "bloquant"
GRAVITE_AVERTISSEMENT = "avertissement"

CIBLE_SECTION = "section"
CIBLE_PAGE = "page"

PAGE_INFORMATIONS_LEGALES = "informations_legales"
PAGE_EQUIPE_CAPITAL = "equipe_capital"
PAGE_DIRIGEANTS = "dirigeants"

STATUT_OK = "ok"
STATUT_PROBLEMES = "problemes"
STATUT_ERREUR = "erreur"


@dataclass
class Probleme:
    code: str
    message_court: str
    message: str
    gravite: str = GRAVITE_BLOQUANT
    cible_type: str | None = None
    cible: str | None = None
    # Libellé lisible de la cible (« Article 6 – Apports · Dépôt des fonds »).
    cible_libelle: str | None = None
    base_legale: str | None = None
    reformulation_proposee: str | None = None
    champ: str | None = None
    valeur_actuelle: str | None = None
    correction_proposee: str | None = None
    # {"variable": nom, "valeur": valeur brute à enregistrer} -- seulement si
    # la correction est certaine (ex. somme déposée calculée).
    valeur_a_appliquer: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Etape:
    tool: str
    libelle: str
    statut: str
    duree_ms: int
    nb_problemes: int

    def to_dict(self) -> dict:
        return asdict(self)
