"""Generate realistic financial 10-K and earnings PDFs for testing."""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

DOCS_DIR = Path(__file__).resolve().parents[1] / "data" / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def create_tesla_report():
    pdf_path = DOCS_DIR / "tesla_fy2025_financial_report.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#1E293B'))
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=14, leading=18, textColor=colors.HexColor('#0F172A'), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#334155'), spaceAfter=8)
    bold_style = ParagraphStyle('BoldStyle', parent=body_style, fontName='Helvetica-Bold')

    elements = []
    
    # Title & Metadata
    elements.append(Paragraph("Tesla, Inc. - Form 10-K Annual Report", title_style))
    elements.append(Paragraph("Fiscal Year Ended December 31, 2025 | SEC File Number: 001-34756", bold_style))
    elements.append(Spacer(1, 14))

    # Item 1. Business
    elements.append(Paragraph("Item 1. Business Overview", h2_style))
    elements.append(Paragraph(
        "Tesla designs, develops, manufactures, sells, and leases high-performance fully electric vehicles, energy generation and storage systems, and offers services related to its products. "
        "During fiscal year 2025, vehicle deliveries reached 2,150,000 units globally, supported by expansion at Gigafactory Texas, Gigafactory Berlin-Brandenburg, and Gigafactory Shanghai.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    # Item 7. MD&A - Results of Operations
    elements.append(Paragraph("Item 7. Management's Discussion and Analysis (MD&A)", h2_style))
    elements.append(Paragraph(
        "In fiscal 2025, total revenue was $118.5 billion, representing an increase of 22% compared to $96.8 billion in fiscal 2024. "
        "Automotive segment revenue was $98.2 billion, energy storage and solar revenue was $12.8 billion, and services and other revenue was $7.5 billion. "
        "Gross margin for the full year 2025 was 21.4%, improving 210 basis points from 19.3% in the prior fiscal year.",
        body_style
    ))
    elements.append(Paragraph(
        "Operating income for fiscal 2025 was $14.2 billion, compared to $8.9 billion in 2024. "
        "Net income attributable to common stockholders reached $12.6 billion, resulting in diluted earnings per share (EPS) of $3.62. "
        "Operating expenses were $11.1 billion, consisting of $4.8 billion in Research and Development (R&D) and $6.3 billion in Selling, General and Administrative (SG&A) expenses.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    # Financial Summary Table
    table_data = [
        ["Financial Metric ($ in millions)", "FY2023", "FY2024", "FY2025", "YoY Growth"],
        ["Total Automotive Revenue", "$82,419", "$80,820", "$98,200", "+21.5%"],
        ["Energy Generation & Storage", "$6,035", "$8,250", "$12,800", "+55.2%"],
        ["Total Revenues", "$96,773", "$96,770", "$118,500", "+22.5%"],
        ["Gross Profit", "$17,660", "$18,676", "$25,359", "+35.8%"],
        ["Gross Margin %", "18.2%", "19.3%", "21.4%", "+2.1%"],
        ["Operating Income", "$8,891", "$8,900", "$14,200", "+59.6%"],
        ["Net Income (Profit)", "$14,997", "$7,100", "$12,600", "+77.5%"],
        ["Diluted EPS", "$4.30", "$2.04", "$3.62", "+77.5%"],
        ["Free Cash Flow", "$4,358", "$3,600", "$8,400", "+133.3%"]
    ]
    t = Table(table_data, colWidths=[150, 80, 80, 80, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))

    # Future Predictions and Guidance
    elements.append(Paragraph("Item 7A. Future Predictions, Guidance and Market Outlook", h2_style))
    elements.append(Paragraph(
        "For fiscal year 2026, management provides the following forward-looking guidance and projections:\n"
        "• Vehicle deliveries are forecasted to grow by 20% to 30%, reaching approximately 2.6 million units.\n"
        "• Total revenue is projected to reach $138 billion to $145 billion in FY2026.\n"
        "• Energy storage deployment is expected to grow over 75% year-over-year, contributing over $20 billion in high-margin revenue.\n"
        "• Capital expenditures (CapEx) are estimated between $10.0 billion and $12.0 billion to support autonomous driving infrastructure and next-generation vehicle manufacturing.\n"
        "• Market rate and price elasticity: The average selling price (ASP) of vehicles is expected to stabilize at $44,500.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    # Item 1A. Risk Factors & Red Flags
    elements.append(Paragraph("Item 1A. Risk Factors and Red Flags", h2_style))
    elements.append(Paragraph(
        "We are exposed to several critical risk factors and potential red flags:\n"
        "1. Supply Chain Concentration: High reliance on single-source suppliers for lithium hydroxide, nickel, and synthetic graphite anode materials.\n"
        "2. Regulatory Scrutiny: Active regulatory investigations regarding Autonomous Driving and Full Self-Driving (FSD) driver assistance features.\n"
        "3. Market Rate & Interest Rate Sensitivity: Higher benchmark interest rates directly increase vehicle financing costs for retail consumers, dampening demand.\n"
        "4. Competitive Pressure: Increasing EV price wars in Asian and European markets threatening operating margin stability.\n"
        "5. Going Concern Assessment: Management evaluated liquidity and confirmed strong going-concern status with $34.5 billion in cash, cash equivalents, and short-term investments.",
        body_style
    ))

    doc.build(elements)
    print(f"Generated {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return pdf_path


def create_microsoft_report():
    pdf_path = DOCS_DIR / "microsoft_fy2025_annual_report.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#1E293B'))
    h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontSize=14, leading=18, textColor=colors.HexColor('#0F172A'), spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#334155'), spaceAfter=8)
    bold_style = ParagraphStyle('BoldStyle', parent=body_style, fontName='Helvetica-Bold')

    elements = []

    # Title & Metadata
    elements.append(Paragraph("Microsoft Corporation - FY2025 Annual Financial Report", title_style))
    elements.append(Paragraph("Fiscal Year Ended June 30, 2025 | Form 10-K Annual Filing", bold_style))
    elements.append(Spacer(1, 14))

    # Executive Overview
    elements.append(Paragraph("Executive Overview & Segment Performance", h2_style))
    elements.append(Paragraph(
        "Microsoft achieved historic revenue and operating profit growth in fiscal 2025, driven by unprecedented adoption of Microsoft Cloud and Azure AI services. "
        "Total company revenue was $261.8 billion, an increase of 16% over fiscal year 2024 revenue of $245.1 billion. "
        "Net income for fiscal 2025 rose to $95.4 billion (up 18% YoY) with diluted earnings per share of $12.80.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    # Segment Breakdown Table
    table_data = [
        ["Operating Segment ($ in millions)", "FY2024", "FY2025", "Growth Rate %", "Operating Margin"],
        ["Productivity & Business Processes", "$69,258", "$77,500", "+11.9%", "53.2%"],
        ["Intelligent Cloud (Azure)", "$105,362", "$128,400", "+21.9%", "46.8%"],
        ["More Personal Computing", "$70,500", "$55,900", "-20.7%", "31.5%"],
        ["Total Revenue", "$245,120", "$261,800", "+6.8%", "45.1%"],
        ["Gross Profit Margin", "69.8%", "71.2%", "+1.4%", "-"],
        ["Net Income (Profit)", "$88,136", "$95,400", "+8.2%", "36.4%"]
    ]
    t = Table(table_data, colWidths=[160, 80, 80, 80, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))

    # Future Predictions and Growth Projections
    elements.append(Paragraph("Future Guidance, Projections and Flow Predictions", h2_style))
    elements.append(Paragraph(
        "Management provides the following guidance for fiscal year 2026:\n"
        "• Intelligent Cloud is forecasted to accelerate with 24% to 26% constant-currency growth.\n"
        "• Consolidated fiscal 2026 revenue is expected to surpass $300 billion.\n"
        "• Annual capital expenditure is projected at $65 billion to support AI data center infrastructure.\n"
        "• Commercial remaining performance obligations (RPO) increased 20% to $269 billion, providing long-term predictable cash flow.\n"
        "• Market pricing and rate trends: Azure AI token pricing remained resilient despite volume discounting for enterprise commitments.",
        body_style
    ))
    elements.append(Spacer(1, 10))

    # Risk Factors & Red Flags
    elements.append(Paragraph("Risk Disclosures and Vulnerabilities", h2_style))
    elements.append(Paragraph(
        "Critical risks monitored by the audit committee include:\n"
        "1. Cybersecurity & Operational Resilience: Sophisticated nation-state cyberattacks targeted at cloud tenant identities.\n"
        "2. Energy & Power Grid Availability: Data center capacity expansion is constrained by regional electrical grid interconnection delays.\n"
        "3. Antitrust and Regulatory Challenges: Scrutiny by the FTC and European Commission regarding AI partnership structures.\n"
        "4. Going-Concern Disclosure: The company maintains an AAA credit rating and $80.2 billion in cash and cash equivalents, confirming undisputed going-concern stability.",
        body_style
    ))

    doc.build(elements)
    print(f"Generated {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return pdf_path


if __name__ == "__main__":
    create_tesla_report()
    create_microsoft_report()

