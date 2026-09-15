"""Blocs Legifrance a collecter pour les assurances obligatoires par secteur
(service 1.1.10) — pure donnee, aucune logique. Meme forme que
`blocs_formes_juridiques.py` mais fichier distinct (SRP : la liste des blocs
assurance change independamment de celle des formes juridiques).

Chaque bloc identifie une section du Code des assurances, Code de la sante
publique, etc. contenant des obligations d'assurance specifiques a un ou
plusieurs secteurs startup.

`secteurs_concernes` : liste fermee de secteurs, fixee par bloc (meme
principe que `forme_juridique_concernee` dans `blocs_formes_juridiques.py` :
jamais devinee par le LLM).

`legifrance_source_id` / `legifrance_section_id` : identifiants LEGITEXT /
LEGISCTA pour l'API PISTE, reutilisant `legifrance_client.py` tel quel.

IDENTIFIANTS VERIFIES le 2026-09-11 par de vrais appels API (contenu de
chaque section inspecte, article de reference cle confirme present) — la
version precedente de ce fichier contenait des identifiants LEGISCTA devines
depuis les URLs publiques legifrance.gouv.fr, qui se sont reveles faux a
l'execution (`Section '...' introuvable`). Ne plus jamais deviner un
identifiant LEGISCTA sans le verifier par un appel `consult/legiPart` reel
(voir script de diagnostic utilise pour cette verification, non conserve
dans le depot — jetable).

Note API : `consult/legiPart` a echoue une fois avec un 500 generique sur le
Code civil (texte volumineux) puis a reussi au retry immediat — erreur
transitoire, pas un probleme d'identifiant. A garder en tete si la collecte
echoue sans raison apparente sur un bloc : retenter avant de suspecter l'id.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BlocAssurance:
    code_source: str
    description: str
    legifrance_source_id: str
    legifrance_section_id: str
    domaine_reglementaire: str
    secteurs_concernes: list[str]
    # Libelle humain du type d'assurance couvert par ce bloc (ex: "RC Pro"),
    # fixe a l'avance — meme principe que secteurs_concernes : chaque bloc est
    # choisi precisement parce qu'il correspond a un type d'obligation connu,
    # jamais devine par le LLM article par article (voir plan de correction,
    # 11/09/2026 : l'ancienne version faisait classifier type_assurance par le
    # LLM, une fois par article x secteur — redondant et source d'ecrasement).
    type_assurance: str


# --- Codes sources ---
_CODE_DES_ASSURANCES = "LEGITEXT000006073984"
_CODE_SANTE_PUBLIQUE = "LEGITEXT000006072665"
_CODE_MONETAIRE_FINANCIER = "LEGITEXT000006072026"
_CODE_ENVIRONNEMENT = "LEGITEXT000006074220"
_CODE_CIVIL = "LEGITEXT000006070721"

# --- Blocs transversaux (plusieurs secteurs) ---

BLOCS_ASSURANCE: list[BlocAssurance] = [
    # RC Pro generale — Code des assurances, Livre I, Titre II, Chapitre IV
    # (le Titre etait errone dans la version precedente : Titre II, pas Titre I)
    BlocAssurance(
        "Code des assurances",
        "Livre I, Titre II, Chapitre IV — Les assurances de responsabilite",
        _CODE_DES_ASSURANCES,
        "LEGISCTA000006157248",
        "assurance_rc_pro",
        [
            "SaaS / Tech generique",
            "FinTech",
            "HealthTech",
            "E-commerce / Marketplace",
            "Conseil / Services professionnels",
            "GreenTech / CleanTech / Energie",
            "DeepTech Hardware / Robotique / IoT",
            "Mobilite / Transport / Logistique",
            "AgriTech / FoodTech",
            "Construction Tech / PropTech",
            "Industrie / Manufacturing",
        ],
        "RC Pro",
    ),

    # --- Blocs sectoriels specifiques ---

    # Assurance decennale — Construction (Titre IV entier : Chapitre I
    # responsabilite obligatoire + Chapitre II dommages obligatoire, art. L241-1 s.)
    BlocAssurance(
        "Code des assurances",
        "Livre II, Titre IV — L'assurance des travaux de construction",
        _CODE_DES_ASSURANCES,
        "LEGISCTA000006142820",
        "assurance_decennale",
        ["Construction Tech / PropTech"],
        "Assurance decennale",
    ),

    # Assurance automobile obligatoire — Mobilite/Transport (art. L211-1 s.)
    BlocAssurance(
        "Code des assurances",
        "Livre II, Titre Ier, Chapitre Ier — L'obligation de s'assurer",
        _CODE_DES_ASSURANCES,
        "LEGISCTA000006157480",
        "assurance_auto",
        ["Mobilite / Transport / Logistique"],
        "Assurance auto obligatoire",
    ),

    # RC Pro professions de sante — HealthTech (art. L1142-2)
    BlocAssurance(
        "Code de la sante publique",
        "Premiere partie, Livre Ier, Titre IV, Chapitre II, Section 1 — Principes generaux",
        _CODE_SANTE_PUBLIQUE,
        "LEGISCTA000006185260",
        "assurance_sante",
        ["HealthTech"],
        "RC Pro sante",
    ),

    # RC Pro IOBSP — FinTech (art. L519-3-4) — bloc distinct du CIF ci-dessous :
    # les deux sont dans des sous-arbres differents du Code monetaire et
    # financier (Titre Ier vs Titre IV du Livre V), pas un seul bloc commun
    # comme suppose dans la version precedente.
    BlocAssurance(
        "Code monetaire et financier",
        "Livre V, Titre Ier, Chapitre IX — Les intermediaires en operations de banque et en services de paiement",
        _CODE_MONETAIRE_FINANCIER,
        "LEGISCTA000022962870",
        "assurance_fintech",
        ["FinTech"],
        "RC Pro IOBSP",
    ),

    # RC Pro CIF — FinTech (art. L541-3)
    BlocAssurance(
        "Code monetaire et financier",
        "Livre V, Titre IV, Chapitre Ier — Les conseillers en investissements financiers",
        _CODE_MONETAIRE_FINANCIER,
        "LEGISCTA000006154698",
        "assurance_fintech",
        ["FinTech"],
        "RC Pro CIF",
    ),

    # Responsabilite environnementale — GreenTech (art. L161-1 s.)
    BlocAssurance(
        "Code de l'environnement",
        "Livre Ier, Titre VI — Prevention et reparation de certains dommages causes a l'environnement",
        _CODE_ENVIRONNEMENT,
        "LEGISCTA000019280495",
        "assurance_environnement",
        ["GreenTech / CleanTech / Energie"],
        "RC environnementale",
    ),

    # RC produit defectueux — Hardware/IoT, Industrie, AgriTech/FoodTech (art. 1245 s.)
    BlocAssurance(
        "Code civil",
        "Livre III, Titre III, Sous-titre II, Chapitre II — La responsabilite du fait des produits defectueux",
        _CODE_CIVIL,
        "LEGISCTA000032021490",
        "assurance_rc_produit",
        [
            "DeepTech Hardware / Robotique / IoT",
            "Industrie / Manufacturing",
            "AgriTech / FoodTech",
        ],
        "RC produit defectueux",
    ),
]

# Table d'alias : secteurs a rattacher semantiquement a un secteur collecte.
# Utilisee par le service 1.1.10 pour le matching texte libre → secteur connu.
SECTOR_ALIASES: dict[str, str] = {
    "Intelligence Artificielle": "SaaS / Tech generique",
    "Cybersecurite": "SaaS / Tech generique",
    "EdTech": "SaaS / Tech generique",
    "Legal Tech": "Conseil / Services professionnels",
    "RH Tech": "Conseil / Services professionnels",
    "Gaming": "SaaS / Tech generique",
    "Media": "SaaS / Tech generique",
    "InsurTech": "FinTech",
}
