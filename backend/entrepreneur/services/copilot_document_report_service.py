"""Generation PDF d'un document libre genere par le copilot en conversation

(voir agents/orchestrator/copilot_agent_service.py::CopilotResponse.titre_document
et copilot_service.py::get_message_document) -- distinct de
compliance_report_service.py, qui formate une liste d'obligations deja
structurees (ObligationRapport), pas un texte libre.

CORRECTIF du 27/09/2026 -- premiere version (un simple decoupage sur "\n\n")
produisait un pave de texte illisible : le contenu genere par l'agent
utilisait deja des puces "-"/"1." mais TOUT sur une seule ligne (aucun retour
a la ligne reel), donc rien a exploiter cote PDF. Le prompt (prompts.yaml)
impose desormais un vrai retour a la ligne par titre de section/puce/element
numerote -- ce fichier parse cette structure ligne par ligne pour produire de
vrais titres, listes a puces et listes numerotees (reportlab ListFlowable),
plutot que du texte brut. Coherent avec la charte Wink (memes teintes de vert
que frontend/src/index.css --color-wink-*, garde le PDF visuellement aligne
avec l'app plutot qu'un design generique).

Meme dependance reportlab que compliance_report_service.py (deja dans
requirements.txt), aucun appel LLM ici -- pure mise en forme d'un texte deja
produit et deja verifie (voir grounding_verification_service.py, applique en
amont dans send_message).
"""
import re
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Memes teintes que --color-wink-* (frontend/src/index.css) -- un seul
# endroit a changer si la charte Wink evolue un jour, pas de couleurs
# inventees ici.
_WINK_600 = colors.HexColor("#278058")
_WINK_700 = colors.HexColor("#216749")
_WINK_50 = colors.HexColor("#eefaf3")
_GRIS_META = colors.HexColor("#6b7280")

_LIGNE_PUCE_RE = re.compile(r"^[-•]\s+(.*)$")
_LIGNE_NUMEROTEE_RE = re.compile(r"^\d+[.)]\s+(.*)$")
# Titre de section : courte, se termine par ":", n'est ni une puce ni un
# element numerote (sinon "1. Faire X:" serait pris pour un titre).
_LIGNE_TITRE_MAX_LONGUEUR = 70


def _styles():
    base = getSampleStyleSheet()
    return {
        "titre_doc": ParagraphStyle(
            "TitreDocument", parent=base["Title"], textColor=colors.white, alignment=TA_LEFT, fontSize=18
        ),
        "meta": ParagraphStyle("Meta", parent=base["Normal"], textColor=_GRIS_META, fontSize=9),
        "titre_section": ParagraphStyle(
            "TitreSection",
            parent=base["Heading3"],
            textColor=_WINK_700,
            spaceBefore=10,
            spaceAfter=4,
            fontSize=12,
        ),
        "corps": ParagraphStyle("Corps", parent=base["Normal"], fontSize=10.5, leading=15, spaceAfter=4),
        "item": ParagraphStyle("Item", parent=base["Normal"], fontSize=10.5, leading=14.5),
    }


def _est_titre_section(ligne: str) -> bool:
    return (
        ligne.endswith(":")
        and len(ligne) <= _LIGNE_TITRE_MAX_LONGUEUR
        and not _LIGNE_PUCE_RE.match(ligne)
        and not _LIGNE_NUMEROTEE_RE.match(ligne)
    )


def _parse_contenu(contenu: str, styles: dict) -> list:
    """Transforme le texte brut (voir docstring de module pour le format

    attendu, impose par prompts.yaml) en flowables reportlab : titres de
    section, listes a puces, listes numerotees, paragraphes simples. Ignore
    silencieusement les lignes vides (juste des separateurs visuels dans le
    texte source).
    """
    story: list = []
    lignes = [l.strip() for l in contenu.splitlines()]

    puces_en_cours: list[str] = []
    numeros_en_cours: list[str] = []

    def _vider_puces():
        if puces_en_cours:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(p, styles["item"]), bulletColor=_WINK_600) for p in puces_en_cours],
                    bulletType="bullet",
                    start="•",
                    leftIndent=14,
                    spaceAfter=6,
                )
            )
            puces_en_cours.clear()

    def _vider_numeros():
        if numeros_en_cours:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(p, styles["item"]), bulletColor=_WINK_600) for p in numeros_en_cours],
                    bulletType="1",
                    leftIndent=14,
                    spaceAfter=6,
                )
            )
            numeros_en_cours.clear()

    for ligne in lignes:
        if not ligne:
            continue

        match_puce = _LIGNE_PUCE_RE.match(ligne)
        match_numero = _LIGNE_NUMEROTEE_RE.match(ligne)

        if match_puce:
            _vider_numeros()
            puces_en_cours.append(match_puce.group(1))
            continue
        if match_numero:
            _vider_puces()
            numeros_en_cours.append(match_numero.group(1))
            continue

        # Ligne "normale" (titre de section ou paragraphe) -- termine tout
        # groupe de puces/numeros en cours avant de l'ajouter.
        _vider_puces()
        _vider_numeros()
        if _est_titre_section(ligne):
            story.append(Paragraph(ligne, styles["titre_section"]))
        else:
            story.append(Paragraph(ligne, styles["corps"]))

    _vider_puces()
    _vider_numeros()
    return story


def build_copilot_document_pdf(*, titre: str, contenu: str) -> bytes:
    """Construit un PDF avec une banniere de titre (charte Wink), puis le

    contenu parse en titres de section/listes/paragraphes (voir
    _parse_contenu) -- remplace le simple decoupage par paragraphe de la
    premiere version (voir CORRECTIF du 27/09/2026 en tete de fichier).
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )
    styles = _styles()

    banniere = Table(
        [[Paragraph(titre, styles["titre_doc"])]],
        colWidths=[doc.width],
    )
    banniere.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _WINK_600),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )

    story = [
        banniere,
        Spacer(1, 0.3 * cm),
        Paragraph(f"Genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')} par le copilot Wink", styles["meta"]),
        Spacer(1, 0.5 * cm),
    ]
    story.extend(_parse_contenu(contenu, styles))

    doc.build(story)
    return buffer.getvalue()
