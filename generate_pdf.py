import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)

def create_hackathon_pdf(output_filename="TraceLens_Hackathon_Presentation.pdf"):
    # 16:9 Widescreen Landscape Setup
    doc = SimpleDocTemplate(
        output_filename,
        pagesize=landscape(letter),
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    PRIMARY = colors.HexColor("#1E293B")    # Slate Dark
    ACCENT = colors.HexColor("#2563EB")     # Electric Blue
    MUTED = colors.HexColor("#64748B")      # Slate Muted
    SUCCESS = colors.HexColor("#16A34A")    # Emerald Green
    BG_LIGHT = colors.HexColor("#F8FAFC")   # Off-white

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=30,
        leading=36,
        textColor=ACCENT,
        alignment=1
    )
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=20,
        textColor=PRIMARY,
        alignment=1
    )
    slide_header = ParagraphStyle(
        'SlideHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY
    )
    slide_subheader = ParagraphStyle(
        'SlideSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=MUTED
    )
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=PRIMARY
    )
    bullet_style = ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=PRIMARY
    )
    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=ACCENT
    )

    elements = []

    # ==========================================
    # SLIDE 1: COVER SLIDE
    # ==========================================
    elements.append(Spacer(1, 100))
    elements.append(Paragraph("TraceLens AI 🔍🕸️", title_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Autonomous Microservice Incident Triage & Root-Cause Localization Engine", subtitle_style))
    elements.append(Spacer(1, 20))
    
    meta_info = [
        [Paragraph("<b>Category:</b> AIOps & Cloud Reliability", body_style), Paragraph("<b>Tech Stack:</b> GNNs + DAG Critical Path + LLM Agents", body_style)],
        [Paragraph("<b>Live Demo:</b> Streamlit Cloud / GitHub", body_style), Paragraph("<b>Target MTTR Reduction:</b> 85%", body_style)]
    ]
    meta_table = Table(meta_info, colWidths=[300, 300])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
    ]))
    elements.append(meta_table)
    elements.append(PageBreak())

    # ==========================================
    # SLIDE 2: THE PROBLEM
    # ==========================================
    elements.append(Paragraph("1. The Problem: The High Cost of Alert Storms", slide_header))
    elements.append(Paragraph("Modern microservices cause catastrophic alert noise and delayed triage", slide_subheader))
    elements.append(Spacer(1, 15))

    problem_data = [
        [
            Paragraph("<b>$9,000 / Minute</b><br/>Average cost of enterprise downtime for Tier-1 services (Gartner).", callout_style),
            Paragraph("<b>70% MTTR Waste</b><br/>SREs spend over 45 minutes manually correlating spans and logs across siloed tools.", callout_style)
        ],
        [
            Paragraph("<b>Alert Storm Blindness</b><br/>A single database deadlock fires 50+ secondary alerts across downstream services.", body_style),
            Paragraph("<b>Legacy Tool Gaps</b><br/>Datadog and Dynatrace alert on symptoms, not the mathematical root-cause culprit.", body_style)
        ]
    ]
    t_prob = Table(problem_data, colWidths=[350, 350])
    t_prob.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 14),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(t_prob)
    elements.append(PageBreak())

    # ==========================================
    # SLIDE 3: THE SOLUTION & ARCHITECTURE
    # ==========================================
    elements.append(Paragraph("2. The Solution: Hybrid Graph AI & SRE Agent", slide_header))
    elements.append(Paragraph("Deterministic graph mathematics combined with LLM incident reasoning", slide_subheader))
    elements.append(Spacer(1, 15))

    steps_data = [
        [Paragraph("<b>Step 1: DAG Ingestion</b>", callout_style), Paragraph("Parses distributed OpenTelemetry & Jaeger traces into Directed Acyclic Graphs.", body_style)],
        [Paragraph("<b>Step 2: Critical Path Slack</b>", callout_style), Paragraph("Calculates earliest/latest schedules to filter out non-blocking asynchronous noise.", body_style)],
        [Paragraph("<b>Step 3: Edge-GAT Neural Net</b>", callout_style), Paragraph("Propagates inter-service network latency and error status to rank root-cause culprit spans.", body_style)],
        [Paragraph("<b>Step 4: Agentic Remediation</b>", callout_style), Paragraph("Synthesizes graph telemetry with logs to auto-generate exact <code>kubectl</code> / SQL fix scripts.", body_style)],
    ]
    t_steps = Table(steps_data, colWidths=[200, 500])
    t_steps.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(t_steps)
    elements.append(PageBreak())

    # ==========================================
    # SLIDE 4: TECHNICAL ORIGINALITY
    # ==========================================
    elements.append(Paragraph("3. Technical Originality: Beyond Prompt Wrappers", slide_header))
    elements.append(Paragraph("Why TraceLens achieves zero-hallucination, predictable diagnosis", slide_subheader))
    elements.append(Spacer(1, 15))

    diff_data = [
        [Paragraph("<b>Dimension</b>", callout_style), Paragraph("<b>Generic LLM Wrappers</b>", callout_style), Paragraph("<b>TraceLens AI (Ours)</b>", callout_style)],
        [Paragraph("<b>Graph Topology</b>", body_style), Paragraph("Ignored (flattened to raw text)", body_style), Paragraph("<b>Preserved as DAG with edge latency weights</b>", body_style)],
        [Paragraph("<b>Context Window</b>", body_style), Paragraph("Overflows on large 1,000+ span traces", body_style), Paragraph("<b>Pre-filtered algorithmically via Critical Path</b>", body_style)],
        [Paragraph("<b>Output Precision</b>", body_style), Paragraph("Prone to hallucinated microservices", body_style), Paragraph("<b>Mathematical proof of bottleneck culprit</b>", body_style)],
        [Paragraph("<b>Actionability</b>", body_style), Paragraph("Generic text advice ('investigate DB')", body_style), Paragraph("<b>Executable bash / kubectl recovery commands</b>", body_style)]
    ]
    t_diff = Table(diff_data, colWidths=[160, 260, 280])
    t_diff.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, 1), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(t_diff)
    elements.append(PageBreak())

    # ==========================================
    # SLIDE 5: MARKET ANALYSIS & REVENUE MODEL
    # ==========================================
    elements.append(Paragraph("4. Market Opportunity & Business Model", slide_header))
    elements.append(Paragraph("High-margin B2B SaaS in a rapidly expanding observability landscape", slide_subheader))
    elements.append(Spacer(1, 15))

    market_data = [
        [
            Paragraph("<b>Market Sizing (AIOps & Observability)</b><br/><br/>"
                      "• <b>TAM:</b> $61.3B Cloud Observability by 2028 (11.7% CAGR)<br/>"
                      "• <b>SAM:</b> $14.2B Cloud-Native & Kubernetes Telemetry<br/>"
                      "• <b>SOM:</b> $1.8B Mid-to-Enterprise DevOps Teams", body_style),
            Paragraph("<b>Tiered Revenue Model</b><br/><br/>"
                      "• <b>Developer Tier (Free / OSS):</b> Local CLI & UI up to 10k spans/mo.<br/>"
                      "• <b>Team Tier ($49/seat/mo):</b> Real-time Slack/PagerDuty bot.<br/>"
                      "• <b>Enterprise ($0.05/1k spans):</b> On-prem GNN inference & automated Kubernetes remediation.", body_style)
        ]
    ]
    t_mkt = Table(market_data, colWidths=[350, 350])
    t_mkt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 14),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    elements.append(t_mkt)
    elements.append(PageBreak())

    # ==========================================
    # SLIDE 6: COMPETITIVE MATRIX
    # ==========================================
    elements.append(Paragraph("5. Competitive Advantage Matrix", slide_header))
    elements.append(Paragraph("How TraceLens outclasses legacy observability vendors", slide_subheader))
    elements.append(Spacer(1, 15))

    comp_data = [
        [Paragraph("<b>Capability</b>", callout_style), Paragraph("<b>Datadog / Dynatrace</b>", callout_style), Paragraph("<b>PagerDuty / incident.io</b>", callout_style), Paragraph("<b>TraceLens AI</b>", callout_style)],
        [Paragraph("Root-Cause Engine", body_style), Paragraph("Thresholds & Heuristics", body_style), Paragraph("Manual SRE Triage", body_style), Paragraph("<b>Mathematical DAG GNN</b>", body_style)],
        [Paragraph("Remediation Scripts", body_style), Paragraph("No", body_style), Paragraph("Runbooks (Manual)", body_style), Paragraph("<b>Automated Kubectl/Bash</b>", body_style)],
        [Paragraph("Pricing Model", body_style), Paragraph("High Host/GB Tax", body_style), Paragraph("Per User Seat", body_style), Paragraph("<b>Usage-based Spans</b>", body_style)],
        [Paragraph("Mean Time to Triage", body_style), Paragraph("15 - 45 min", body_style), Paragraph("20 - 40 min", body_style), Paragraph("<b>< 5 Seconds</b>", body_style)]
    ]
    t_comp = Table(comp_data, colWidths=[160, 180, 180, 180])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ('BACKGROUND', (0, 1), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(t_comp)
    elements.append(PageBreak())

    # ==========================================
    # SLIDE 7: ROADMAP & FUTURE VISION
    # ==========================================
    elements.append(Paragraph("6. Roadmap & Execution Milestones", slide_header))
    elements.append(Paragraph("From intelligent assistant to autonomous closed-loop self-healing", slide_subheader))
    elements.append(Spacer(1, 15))

    roadmap_data = [
        [Paragraph("<b>Phase 1: Now (Hackathon MVP)</b>", callout_style), Paragraph("• Streamlit Cloud Web UI + Chaos Simulator<br/>• OpenTelemetry / Jaeger DAG Ingestion<br/>• Groq LLM SRE Report & Remediation Generator", body_style)],
        [Paragraph("<b>Phase 2: Q3 2025 (Integrations)</b>", callout_style), Paragraph("• Bidirectional Slack & PagerDuty bot integrations<br/>• GitHub Actions CI/CD trace regression detection", body_style)],
        [Paragraph("<b>Phase 3: Q4 2025 (Closed-Loop)</b>", callout_style), Paragraph("• Kubernetes Self-Healing Operator (auto-restart, circuit breaking)<br/>• eBPF kernel-level zero-code instrumentation", body_style)]
    ]
    t_road = Table(roadmap_data, colWidths=[240, 460])
    t_road.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(t_road)
    elements.append(PageBreak())

    # ==========================================
    # SLIDE 8: SUMMARY & DEMO CTA
    # ==========================================
    elements.append(Spacer(1, 60))
    elements.append(Paragraph("Transforming Cloud Observability with TraceLens AI", title_style))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Reducing MTTR from 45 minutes to 5 seconds with Graph AI and Automated Remediation.", subtitle_style))
    elements.append(Spacer(1, 30))

    summary_box = [
        [Paragraph("<b>Live Demo:</b> Accessible on Streamlit Cloud", callout_style)],
        [Paragraph("<b>GitHub Codebase:</b> Fully open-source with unit tests & GNN engine", callout_style)],
        [Paragraph("<b>Thank you! Questions & Discussion</b>", subtitle_style)]
    ]
    t_sum = Table(summary_box, colWidths=[600])
    t_sum.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
        ('PADDING', (0, 0), (-1, -1), 14),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1.5, ACCENT)
    ]))
    elements.append(t_sum)

    # Build Document
    doc.build(elements)
    print(f"✅ Successfully created {output_filename}")

if __name__ == "__main__":
    create_hackathon_pdf()