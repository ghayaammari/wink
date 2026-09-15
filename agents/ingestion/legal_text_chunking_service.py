"""Découpage effectif des articles `legal_texts` en chunks (Phase 2, Étape 2.2
du plan Notion) — fonction pure, aucun accès DB, aucun appel LLM : la décision
de méthode a déjà été prise à l'Étape 1.4 (LLM) et confirmée par la relecture
humaine (Phase 1.5, dashboard). Ce module ne fait que l'appliquer (Étape 2.1 :
"aucune redécision, la valeur est déjà confirmée").

Séparé de `legal_text_structuring_service.py` (appels LLM) : responsabilité
différente, pas de dépendance à Groq ici.
"""
import re

# Même règle indicative que legal_texts_validation_router.py (nb_alineas_detectes,
# Étape 1.5.1) — réutilisée ici pour le découpage réel afin que ce qui a été
# montré à l'humain pendant la validation soit exactement ce qui est chunké.
_ALINEA_SEPARATOR = re.compile(r"\n\s*\n|(?:^|\n)\s*\d+°")


def chunk_texte_brut(texte_brut: str, chunking_suggere: str) -> list[str]:
    """Retourne la liste des chunks, dans l'ordre — chunk_index côté appelant
    est simplement la position dans cette liste (voir chunk_and_embed_legal_texts.py).

    "aucun" : le chunk = texte_brut entier (liste à 1 élément).
    "par_alinea" : découpe sur double saut de ligne ou numérotation "1°"/"2°"/
    "3°" — un alinéa vide (ponctuation seule, espaces) est ignoré. Si le
    découpage ne trouve qu'un seul morceau malgré chunking_suggere="par_alinea"
    (texte sans séparateur détectable), on retombe sur 1 chunk = texte entier
    plutôt que de planter — cohérent avec le compromis déjà assumé ailleurs
    (nb_alineas_detectes "pas fiable à 100%", voir plan Notion).
    """
    if chunking_suggere != "par_alinea":
        return [texte_brut]

    parts = [p.strip() for p in _ALINEA_SEPARATOR.split(texte_brut) if p.strip()]
    return parts if parts else [texte_brut]
