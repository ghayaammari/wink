"""Generation PDF du rapport de conformite telechargeable -- un rapport par

domaine (RGPD, AI Act, HealthTech, FinTech), declenche quand l'entrepreneur
clique "Terminer" sur une page de diagnostic apres y etre arrive depuis le
copilot (voir CopilotSidebar.tsx frontend, marqueur ?from=copilot).

Fichier partage entre les 4 domaines, meme raisonnement que
compliance_score_service.py : chaque domaine convertit sa propre forme de
stockage (lignes DB RGPD/AI Act, JSONB HealthTech/FinTech) en une liste
d'ObligationRapport avant d'appeler build_obligations_report_pdf -- pure
mise en forme deterministe de donnees deja calculees/persistees, aucun appel
LLM ici (coherent avec la regle "l'agent ne redige jamais lui-meme le
rapport final", le PDF est un formatage de donnees deja verifiees).

reportlab est la seule dependance d'ECRITURE de PDF du projet (pypdf/
pdf2image, deja presents, ne font que LIRE du PDF existant) -- ajoutee a
requirements.txt specifiquement pour ce besoin.
"""
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class ObligationRapport:
    nom: str
    description: str
    accompli: bool


def build_obligations_report_pdf(*, titre: str, obligations: list[ObligationRapport], score: int | None) -> bytes:
    """Construit un PDF : titre, score en tete, puis un tableau d'obligations

    (coche/non coche, nom, description). `score` a `None` (aucune obligation
    evaluee) affiche une mention neutre plutot qu'un pourcentage trompeur --
    meme regle que ComplianceScoreBadge cote frontend.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )
    styles = getSampleStyleSheet()
    cell_style = styles["Normal"]
    story = []

    story.append(Paragraph(titre, styles["Title"]))
    story.append(
        Paragraph(
            f"Genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    score_texte = (
        f"Score de conformite : <b>{score}%</b>" if score is not None else "Score de conformite : aucune obligation evaluee"
    )
    story.append(Paragraph(score_texte, styles["Heading2"]))
    story.append(Spacer(1, 0.5 * cm))

    if not obligations:
        story.append(Paragraph("Aucune obligation generee pour ce diagnostic.", styles["Normal"]))
    else:
        data = [["Statut", "Obligation", "Description"]]
        for obligation in obligations:
            data.append(
                [
                    "Fait" if obligation.accompli else "A faire",
                    Paragraph(obligation.nom, cell_style),
                    Paragraph(obligation.description, cell_style),
                ]
            )
        table = Table(data, colWidths=[2.2 * cm, 4.3 * cm, 9.2 * cm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ]
            )
        )
        story.append(table)

    doc.build(story)
    return buffer.getvalue()
