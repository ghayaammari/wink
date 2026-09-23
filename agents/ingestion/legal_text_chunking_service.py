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


_MAX_CHARS_GUIDE = 1500


def chunk_texte_guide(texte_brut: str, max_chars: int = _MAX_CHARS_GUIDE) -> list[str]:
    """Découpage pour du texte long non structuré en alinéas de loi (guides/
    FAQ/PDF CNIL, type_source != 'article_loi', voir chunk_and_embed_legal_texts.py) —
    chunk_texte_brut() ci-dessus ne convient pas ici : ses 2 stratégies
    ("aucun" = tout en un bloc, "par_alinea" = numérotation légale) sont
    pensées pour un article de loi court, pas pour un guide de plusieurs
    dizaines de milliers de caractères. Constaté en pratique le 16/09/2026 :
    17 pages CNIL collectées produisaient chacune UN SEUL chunk (jusqu'à
    111 656 caractères pour le guide DPO), rendant la recherche vectorielle
    inutilisable — un vecteur unique pour un texte aussi long ne représente
    plus aucun sujet précis.

    Découpe par paragraphe (`\\n`, simple ou double — le texte extrait par
    trafilatura ne garantit pas de double saut de ligne entre paragraphes,
    contrairement au HTML nettoyé de Légifrance dans legifrance_client.py),
    puis regroupe les paragraphes consécutifs jusqu'à `max_chars` — pas un
    paragraphe = un chunk (beaucoup de paragraphes web font 1-2 phrases,
    créerait des chunks trop petits pour un contexte utile au copilot).

    Un paragraphe à lui seul plus long que `max_chars` reste un chunk à part
    entière (jamais tronqué au milieu d'une phrase) : dépasser légèrement la
    cible est préférable à couper une idée en deux morceaux inexploitables.
    """
    paragraphes = [p.strip() for p in texte_brut.split("\n") if p.strip()]
    if not paragraphes:
        return [texte_brut]

    chunks: list[str] = []
    courant: list[str] = []
    longueur_courante = 0

    for paragraphe in paragraphes:
        if courant and longueur_courante + len(paragraphe) + 1 > max_chars:
            chunks.append("\n".join(courant))
            courant = []
            longueur_courante = 0
        courant.append(paragraphe)
        longueur_courante += len(paragraphe) + 1

    if courant:
        chunks.append("\n".join(courant))

    return chunks


_MAX_CHARS_ARTICLE = 3000

_SENTENCE_SEPARATOR = re.compile(r"(?<=[.!?])\s+")


def chunk_si_trop_long(texte: str, max_chars: int = _MAX_CHARS_ARTICLE) -> list[str]:
    """Garde-fou pour un chunk d'article de loi anormalement long (ex. article

    AI Act sans aucun saut de ligne après normalisation HTML, voir docstring
    de eu_ai_act_client.py::_normaliser_texte, qui aplati tout `\s+` en un
    espace) — chunk_texte_brut() ne peut rien découper sans séparateur de
    paragraphe détectable, donc ce garde-fou rattrape ici par un découpage
    par phrase, même logique de regroupement que chunk_texte_guide() ci-dessus
    mais à la granularité phrase plutôt que paragraphe (le texte source n'a
    plus de \n exploitable pour ces articles).

    Ne s'applique qu'au-delà de max_chars : un article court (cas normal)
    ressort inchangé en 1 élément. Ne remplace pas chunking_suggere — vient
    seulement rattraper le cas où celui-ci n'a rien pu découper (voir
    chunk_and_embed_legal_texts.py, appelé uniquement pour type_source='article_loi').
    """
    if len(texte) <= max_chars:
        return [texte]

    phrases = [p.strip() for p in _SENTENCE_SEPARATOR.split(texte) if p.strip()]
    if len(phrases) <= 1:
        # Aucune frontiere de phrase non plus (constate en pratique : certains
        # articles europeens enumerent leurs points avec des points-virgules,
        # un seul "." final) - dernier recours, decoupage force par mots.
        return _decoupage_force(texte, max_chars)

    chunks: list[str] = []
    courant: list[str] = []
    longueur_courante = 0

    for phrase in phrases:
        # Une "phrase" elle-meme plus longue que max_chars (meme cas que
        # ci-dessus, a l'echelle d'une seule phrase) est forcee a son tour
        # plutot que de rester un chunk demesure.
        if len(phrase) > max_chars:
            if courant:
                chunks.append(" ".join(courant))
                courant = []
                longueur_courante = 0
            chunks.extend(_decoupage_force(phrase, max_chars))
            continue
        if courant and longueur_courante + len(phrase) + 1 > max_chars:
            chunks.append(" ".join(courant))
            courant = []
            longueur_courante = 0
        courant.append(phrase)
        longueur_courante += len(phrase) + 1

    if courant:
        chunks.append(" ".join(courant))

    return chunks


def _decoupage_force(texte: str, max_chars: int) -> list[str]:
    """Dernier recours de chunk_si_trop_long : aucune frontiere de phrase

    exploitable (liste a puces separee par des virgules/points-virgules, pas
    de point avant des milliers de caracteres) - on regroupe par mots jusqu'a
    max_chars, plutot que de laisser un chunk demesure entrer dans le prompt
    envoye a Groq (cause du 413 Payload Too Large constate le 19/09/2026)."""
    mots = texte.split(" ")
    chunks: list[str] = []
    courant: list[str] = []
    longueur_courante = 0

    for mot in mots:
        if courant and longueur_courante + len(mot) + 1 > max_chars:
            chunks.append(" ".join(courant))
            courant = []
            longueur_courante = 0
        courant.append(mot)
        longueur_courante += len(mot) + 1

    if courant:
        chunks.append(" ".join(courant))

    return chunks
