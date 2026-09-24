"""Données fournies à la validation globale (agents/document_generation_validation).

L'agent ne lit JAMAIS la base : le backend
(`backend/entrepreneur/services/document_generation_validation_service.py`)
charge tout une seule fois et construit ce contexte. Même séparation que le
reste de `agents/` (le garde-fou LLM ne touche pas la base non plus) :
chaque tool se teste avec un contexte fabriqué à la main, et un autre
service pourra valider un document en fournissant son propre contexte.
"""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class SectionContexte:
    code_section: str
    # Libellé pour les messages : « Article 6 – Apports · Dépôt des fonds ».
    libelle: str
    reponse: dict
    # Vrai si l'utilisateur a répondu lui-même (section réouvrable) ; faux
    # pour une section déduite, générée automatiquement ou non applicable.
    saisie_utilisateur: bool


@dataclass
class ClauseContexte:
    code_clause: str
    titre_clause: str
    texte_clause: str
    variables_requises: list[dict]
    # Critères que le code ne vérifie pas (réservés au contrôle LLM).
    criteres_llm: list[dict] = field(default_factory=list)


@dataclass
class AssocieContexte:
    id: str
    nom: str
    type_apport: str | None
    pourcentage_capital: Decimal | None


@dataclass
class DirigeantContexte:
    role: str
    nom: str
    # Durée des fonctions (imprimée dans la nomination) ; None si vide.
    duree_fonctions: str | None = None


@dataclass
class BlocContexte:
    """Un bloc du document assemblé, en texte brut."""

    code_section: str | None
    texte: str


@dataclass
class ContexteValidation:
    document_type: str
    sections: list[SectionContexte]
    clauses: dict[str, ClauseContexte]
    associes: list[AssocieContexte]
    dirigeants: list[DirigeantContexte]
    capital_social: Decimal | None
    blocs: list[BlocContexte]
    # Numéros LOGIQUES (clausier) des articles présents dans le document ;
    # None pour un document sans numérotation calculée (pacte).
    articles_presents: set[str] | None = None
    # Seule sortie écrite par un tool : les corrections de texte décidées par
    # `correction_renvois` ({code_section, remplace, par}), appliquées par le
    # backend au document FINAL uniquement.
    corrections_texte: list[dict] = field(default_factory=list)

    def section(self, code_section: str) -> SectionContexte | None:
        return next((s for s in self.sections if s.code_section == code_section), None)

    def reponse_incluse(self, code_section: str) -> dict | None:
        """Réponse de la section si elle produit du contenu, None sinon."""
        s = self.section(code_section)
        if s is None or s.reponse.get("applicable", True) is False or not s.reponse.get("inclus"):
            return None
        return s.reponse

    def section_de_clause(self, *codes_clause: str) -> SectionContexte | None:
        """Première section incluse dont la clause retenue est l'une de `codes_clause`."""
        for s in self.sections:
            if self.reponse_incluse(s.code_section) and s.reponse.get("code_clause") in codes_clause:
                return s
        return None

    def valeurs_de_clause(self, *codes_clause: str) -> dict | None:
        s = self.section_de_clause(*codes_clause)
        return dict(s.reponse.get("valeurs") or {}) if s else None

    def premier_dirigeant(self, role: str) -> DirigeantContexte | None:
        """Premier dirigeant du rôle (liste dans l'ordre de création) : c'est
        lui que les statuts impriment (convention « premier » du backend)."""
        return next((d for d in self.dirigeants if d.role == role), None)

    def roles_designes(self) -> dict[str, int]:
        compte: dict[str, int] = {}
        for d in self.dirigeants:
            compte[d.role] = compte.get(d.role, 0) + 1
        return compte

    def montant_apport(self, associe: AssocieContexte) -> Decimal | None:
        """Montant apporté = capital × pourcentage (même formule que le rendu
        des statuts, `_valeurs_apports_numeraire_par_associe`)."""
        if self.capital_social is None or associe.pourcentage_capital is None:
            return None
        return self.capital_social * associe.pourcentage_capital / 100
