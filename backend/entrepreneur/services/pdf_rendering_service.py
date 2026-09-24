"""Rendu d'un document généré (pacte de fondateurs v1/v2, futurs statuts...)
en PDF téléchargeable.

Service 1.1.13 (pacte de fondateurs) v2 : `render_text_as_pdf` (texte plat,
un seul style de paragraphe, pas de navigation) est remplacé par
`render_document_as_pdf`, qui prend en entrée les blocs typés produits par
`document_generation_service._assemble_document_blocks` (voir sa docstring)
plutôt qu'une chaîne assemblée -- nécessaire pour 3 exigences actées avec
l'utilisateur (21/09/2026) : (1) toute valeur injectée en rouge, (2) un style
par type de section (article/texte fixe/section en cours de rédaction), (3)
un sommaire PDF cliquable (signets) pour naviguer entre articles, présentable
dès cet incrément -- pas amélioré plus tard.

`render_text_as_pdf` (v1, texte plat) est retiré : `finalize_session` est
refactorisé pour appeler `_assemble_document_blocks` + `render_document_as_pdf`
pour v1 ET v2 (un seul moteur de rendu, pas deux qui divergent avec le temps
-- décision actée avec l'utilisateur, 21/09/2026) ; côté v1 ça ne change que
la présentation (mieux structurée, signets), aucune information perdue.

`reportlab` plutôt que weasyprint/wkhtmltopdf : pur Python, pip-installable,
aucune dépendance système à installer sur la machine de chaque développeur
(Cairo/Pango, ou un binaire wkhtmltopdf externe).
"""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# Chaîne littérale (pas HexColor(...).hexval(), qui ne rend pas un format
# "#RRGGBB" utilisable tel quel dans l'attribut color= d'une balise <font>).
_COULEUR_VALEUR_INJECTEE = "#C0392B"


def _runs_vers_xml(runs: list[dict]) -> str:
    """Concatène des "runs" (`{texte, valeur_utilisateur, nom_variable}`) en
    XML minimal reportlab : `escape()` d'abord (un texte source contenant par
    hasard `&`/`<`/`>`, ex. "Dupont & Associés", casserait sinon le rendu),
    puis balises `<font color=...>` autour des runs `valeur_utilisateur=True`
    et `<br/>` pour les retours à la ligne internes (liste d'associés,
    Article 1 sur plusieurs lignes...)."""
    morceaux = []
    for run in runs:
        texte = escape(run["texte"]).replace("\n", "<br/>")
        if not texte:
            continue
        if run.get("valeur_utilisateur"):
            morceaux.append(f'<font color="{_COULEUR_VALEUR_INJECTEE}"><b>{texte}</b></font>')
        elif run.get("gras"):
            # Sous-titre numéroté des statuts (« 6.2. Apports en nature »,
            # lot B -- voir statuts_sas_numerotation.py).
            morceaux.append(f"<b>{texte}</b>")
        else:
            morceaux.append(texte)
    return "".join(morceaux)


class _DocumentAvecSommaire(SimpleDocTemplate):
    """`SimpleDocTemplate` qui pose un signet PDF (bookmark + entrée de
    sommaire navigable) à chaque paragraphe de style `TitreArticle` --
    mécanisme standard reportlab (`afterFlowable` + `canv.bookmarkPage`/
    `addOutlineEntry`), pas une bibliothèque tierce supplémentaire."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._compteur_signets = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "TitreArticle":
            texte = flowable.getPlainText()
            cle = f"article-{self._compteur_signets}"
            self._compteur_signets += 1
            self.canv.bookmarkPage(cle)
            self.canv.addOutlineEntry(texte, cle, level=0, closed=False)


def render_document_as_pdf(blocks: list[dict], *, titre: str | None = None) -> bytes:
    """Convertit les blocs produits par `_assemble_document_blocks` en PDF A4
    structuré : un style par `block["type"]`, les runs `valeur_utilisateur=True`
    en rouge, un signet par bloc `content`/`texte_statique` portant un `titre`
    (navigation dans le lecteur PDF). Un bloc `placeholder` (section en cours
    de saisie, preview seulement -- jamais présent à la finalisation, voir
    `_assemble_document_blocks`) s'affiche en italique gris avec une mention
    explicite, pas de signet (rien à nommer tant que la section n'est pas
    remplie).
    """
    buffer = BytesIO()
    doc = _DocumentAvecSommaire(
        buffer,
        pagesize=A4,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    style_titre_document = ParagraphStyle("TitreDocument", parent=styles["Title"], fontSize=16, spaceAfter=18)
    style_titre_article = ParagraphStyle(
        "TitreArticle", parent=styles["Heading2"], fontSize=12.5, spaceBefore=14, spaceAfter=8,
    )
    style_corps = ParagraphStyle(
        "CorpsDocument", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=10, alignment=TA_JUSTIFY,
    )
    style_texte_statique = ParagraphStyle(
        "TexteStatique", parent=style_corps, fontName="Helvetica-Oblique",
    )
    style_placeholder_titre = ParagraphStyle(
        "PlaceholderTitre", parent=style_titre_article, textColor=HexColor("#7F8C8D"),
    )
    style_placeholder_corps = ParagraphStyle(
        "PlaceholderCorps", parent=style_corps, fontName="Helvetica-Oblique", textColor=HexColor("#7F8C8D"),
    )

    story = []
    if titre:
        story.append(Paragraph(escape(titre), style_titre_document))

    for bloc in blocks:
        if bloc["type"] == "placeholder":
            if bloc.get("titre"):
                story.append(Paragraph(escape(bloc["titre"]), style_placeholder_titre))
            story.append(Paragraph("(section en cours de rédaction)", style_placeholder_corps))
            story.append(Spacer(1, 6))
            continue

        contenu = _runs_vers_xml(bloc.get("runs", []))
        # Titre et contenu sont désormais indépendants (24/09/2026) : un bloc
        # "titre de chapitre" pur (ex. "Article 1 - ...", texte_statique=None
        # côté données, voir generate_pacte_fondateurs_v2.py) doit quand même
        # poser son signet/titre même sans corps -- avant, `continue` ici
        # sautait le bloc ENTIER dès que le corps était vide, donc perdait le
        # titre avec. Seul cas encore ignoré : ni titre ni contenu (rien à
        # afficher du tout).
        if not contenu and not bloc.get("titre"):
            continue
        if bloc.get("titre"):
            story.append(Paragraph(escape(bloc["titre"]), style_titre_article))
        if contenu:
            style_corps_bloc = style_texte_statique if bloc["type"] == "texte_statique" else style_corps
            story.append(Paragraph(contenu, style_corps_bloc))

    if not story:
        story.append(Paragraph("(document vide)", style_corps))

    doc.build(story)
    return buffer.getvalue()
