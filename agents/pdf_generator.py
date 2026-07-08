import textwrap
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def create_pdf_report(pdf_path, ai_report, transcript, source_name, today, analytics):
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=22, spaceAfter=18)
    heading_style = ParagraphStyle("HeadingStyle", parent=styles["Heading2"], fontSize=14, spaceBefore=14, spaceAfter=8)
    body_style = ParagraphStyle("BodyStyle", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=8)

    story = []

    story.append(Paragraph("Meeting Organizer AI", title_style))
    story.append(Paragraph("Smart Meeting Analytics Report", heading_style))
    story.append(Paragraph(f"<b>Date:</b> {today}", body_style))
    story.append(Paragraph(f"<b>Source:</b> {source_name}", body_style))
    story.append(Spacer(1, 16))

    analytics_data = [
        ["Metric", "Result"],
        ["Words Spoken", str(analytics["word_count"])],
        ["Estimated Reading Time", f'{analytics["reading_time"]} minutes'],
        ["Questions Asked", str(analytics["question_count"])],
        ["Possible Action Items", str(analytics["action_count"])],
        ["Possible Decisions", str(analytics["decision_count"])],
    ]

    table = Table(analytics_data, colWidths=[220, 220])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(table)
    story.append(Spacer(1, 18))

    story.append(Paragraph("Most Common Topics", heading_style))
    for topic, count in analytics["common_topics"]:
        story.append(Paragraph(f"• {topic} ({count} mentions)", body_style))

    story.append(PageBreak())
    story.append(Paragraph("AI Meeting Report", heading_style))

    for line in ai_report.split("\n"):
        clean = line.strip()
        if not clean:
            story.append(Spacer(1, 8))
        elif clean.lower().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "executive", "key topics", "action", "decisions", "unanswered", "important")):
            story.append(Paragraph(clean, heading_style))
        else:
            story.append(Paragraph(clean, body_style))

    story.append(PageBreak())
    story.append(Paragraph("Full Transcript", heading_style))

    wrapped_transcript = textwrap.wrap(transcript, width=95)
    for line in wrapped_transcript:
        story.append(Paragraph(line, body_style))

    doc.build(story)