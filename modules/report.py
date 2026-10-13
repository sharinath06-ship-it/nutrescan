from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import os

def generate_pdf(grade, score, results):

    os.makedirs("reports", exist_ok=True)

    filename = "reports/NutriScan_Report.pdf"

    doc = SimpleDocTemplate(filename)

    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("<b>NutriScan Report</b>", styles["Title"]))

    story.append(Paragraph(f"<b>Food Grade:</b> {grade}", styles["Normal"]))

    story.append(Paragraph(f"<b>Penalty Score:</b> {score}", styles["Normal"]))

    story.append(Paragraph("<br/>Detected Ingredients", styles["Heading2"]))

    for item in results:

        story.append(
            Paragraph(
                f"<b>{item['ingredient']}</b> ({item['risk_level']})<br/>"
                f"{item['health_impact']}<br/>"
                f"Alternative: {item['alternative']}<br/><br/>",
                styles["Normal"]
            )
        )

    doc.build(story)

    return filename