"""Benchmark case definition and generator for the 100+ scenario Quality Harness."""

from __future__ import annotations

import json
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent
CASES_DIR = HARNESS_ROOT / "cases"
DEFECTS_DIR = HARNESS_ROOT / "defects"

# 24 Content Domains
DOMAINS = [
    "history", "geography", "economics", "science", "biology", "physics",
    "chemistry", "technology", "artificial_intelligence", "cybersecurity",
    "cloud", "finance", "healthcare", "business", "marketing", "education",
    "research", "corporate_reports", "project_updates", "strategy",
    "training", "case_studies", "product_presentations", "architecture",
]

# 12 Source Types
SOURCE_TYPES = [
    "prompt_only", "pdf_single", "pdf_plus_prompt", "multi_pdf",
    "pdf_image_heavy", "pdf_text_heavy", "pdf_tables", "pdf_timelines",
    "docx_source", "pptx_reference", "data_heavy_kpi", "vague_user_prompt"
]

# Slide Counts
SLIDE_SIZES = [5, 8, 10, 12, 15, 20, 25, 30]


def build_100_plus_cases() -> list[dict]:
    """Builds 105 diversified real-world generation benchmark scenarios."""
    cases = []

    # Domain mapping with realistic prompt templates and expectations
    scenarios_seed = [
        # History
        ("hist_001", "history", "prompt_only", 8, "8 slides on Maratha Empire military tactics, fort architectures, naval expansion, and administrative governance.", True, False),
        ("hist_002", "history", "pdf_plus_prompt", 10, "10 slides summarizing Harappan urban planning, craft technology, and trade routes from attached NCERT chapter.", True, True, "NCERT-Bricks-Beads-and-Bones.pdf"),
        ("hist_003", "history", "pdf_timelines", 12, "12 slides historical chronology of the rise of empires, key treaties, territorial expansions, and societal shifts.", True, True, "source data.pdf"),
        ("hist_004", "history", "vague_user_prompt", 6, "Make school history presentation from this chapter with key points and timeline.", True, False),
        ("hist_005", "history", "prompt_only", 15, "15 slides detailed presentation on the Industrial Revolution, technological inventions, and global socioeconomic impacts.", True, False),

        # Artificial Intelligence & Tech
        ("ai_001", "artificial_intelligence", "prompt_only", 10, "10 slides pitch deck for enterprise multimodal presentation generation platform covering LLMs, vision QA, and market size.", False, False),
        ("ai_002", "artificial_intelligence", "data_heavy_kpi", 8, "8 slides benchmarking open-source LLM inference latency, token throughput, and GPU memory efficiency.", False, False),
        ("ai_003", "artificial_intelligence", "prompt_only", 12, "12 slides technical architecture deep-dive on agentic workflows, multi-agent consensus, and tool calling.", False, False),
        ("ai_004", "artificial_intelligence", "vague_user_prompt", 5, "Create ppt on AI agents in healthcare.", False, False),

        # Technology & Cloud
        ("tech_001", "technology", "prompt_only", 6, "6 slides overview of Kubernetes cluster orchestration, container security, and service meshes.", False, False),
        ("tech_002", "cloud", "prompt_only", 8, "8 slides cloud cost optimization strategies covering spot instances, autoscaling, and egress reductions.", False, False),
        ("tech_003", "cybersecurity", "prompt_only", 10, "10 slides executive presentation on Zero Trust Architecture, identity federation, and threat mitigation.", False, False),
        ("tech_004", "technology", "docx_source", 7, "7 slides devops CI/CD pipeline modernization and automated regression testing.", False, False),

        # Finance & Economics
        ("fin_001", "finance", "data_heavy_kpi", 8, "8 slides Q3 financial performance review: ARR growth, net retention, EBITDA margins, and CAC payback.", False, False),
        ("fin_002", "economics", "pdf_plus_prompt", 10, "10 slides on macroeconomic indicators, interest rate cycles, inflation dynamics, and labor market liquidity.", False, False, "hees106.pdf"),
        ("fin_003", "finance", "prompt_only", 12, "12 slides series B venture capital pitch deck with unit economics, cohort retention, and 5-year projections.", False, False),
        ("fin_004", "economics", "prompt_only", 6, "6 slides comparative analysis of monetary policy vs fiscal stimulus during supply shocks.", False, False),

        # Business & Strategy
        ("biz_001", "strategy", "prompt_only", 10, "10 slides corporate strategy: international market expansion, channel partnerships, and risk register.", False, False),
        ("biz_002", "business", "data_heavy_kpi", 7, "7 slides supply chain resilience framework, dual sourcing, buffer stocks, and vendor scoring.", False, False),
        ("biz_003", "corporate_reports", "prompt_only", 8, "8 slides annual ESG report: carbon neutrality roadmaps, governance standards, and social equity.", False, False),
        ("biz_004", "case_studies", "prompt_only", 6, "6 slides business turnaround case study: cost restructuring, digital transformation, and customer NPS.", False, False),

        # Healthcare & Biology
        ("health_001", "healthcare", "prompt_only", 10, "10 slides clinical review of targeted immunotherapy mechanisms, trial phases, and patient outcomes.", False, False),
        ("health_002", "biology", "pdf_plus_prompt", 8, "8 slides on cellular respiration, mitochondrial ATP synthesis, and metabolic regulation.", False, True, "NCERT SSC 0908-Understanding Society Grade 9 (3).pdf"),
        ("health_003", "healthcare", "prompt_only", 6, "6 slides digital health remote monitoring: wearable biosensors, telehealth adoption, and HIPAA compliance.", False, False),
        ("health_004", "biology", "prompt_only", 12, "12 slides genetic engineering CRISPR-Cas9 precision editing, ethical guardrails, and agriculture applications.", False, False),

        # Science, Physics & Chemistry
        ("sci_001", "physics", "prompt_only", 8, "8 slides quantum computing principles: superposition, entanglement, qubit decoherence, and error mitigation.", False, False),
        ("sci_002", "chemistry", "prompt_only", 6, "6 slides green chemistry and sustainable catalytic synthesis for carbon capture and battery storage.", False, False),
        ("sci_003", "science", "prompt_only", 10, "10 slides James Webb Space Telescope deep-space observations, exoplanet atmospheric spectra, and early galaxy formation.", False, False),
        ("sci_004", "physics", "prompt_only", 7, "7 slides nuclear fusion plasma confinement in tokamaks: magnetic coils, Lawson criterion, and net energy gain.", False, False),

        # Marketing & Product
        ("mkt_001", "marketing", "prompt_only", 8, "8 slides B2B demand generation playbook: account-based marketing, inbound funnels, and multi-touch attribution.", False, False),
        ("mkt_002", "product_presentations", "prompt_only", 6, "6 slides new SaaS product launch: user personas, core workflows, competitive matrix, and pricing tiers.", False, False),
        ("mkt_003", "marketing", "data_heavy_kpi", 7, "7 slides performance marketing analytics: ROAS by channel, CAC trends, conversion funnels, and LTV.", False, False),

        # Education, Research & Training
        ("edu_001", "education", "pdf_plus_prompt", 10, "10 slides educational module on sociological perspectives, social stratification, and institutional mobility.", False, False, "hees106.pdf"),
        ("edu_002", "research", "prompt_only", 12, "12 slides academic thesis presentation on autonomous robotics navigation, SLAM algorithms, and sensor fusion.", False, False),
        ("edu_003", "training", "prompt_only", 8, "8 slides manager onboarding training: feedback loops, active listening, conflict mediation, and OKR setting.", False, False),
        ("edu_004", "project_updates", "prompt_only", 5, "5 slides sprint review: deliverables completed, velocity burndown, technical debt, and next milestones.", False, False),
    ]

    # Expand to 105 comprehensive scenarios covering all matrix permutations
    case_counter = 1
    # First add all specific seed scenarios
    for item in scenarios_seed:
        cid = f"case_{case_counter:03d}_{item[1]}"
        domain = item[1]
        src_type = item[2]
        slides = item[3]
        prompt = item[4]
        req_timeline = item[5]
        req_images = item[6]
        pdf_file = item[7] if len(item) > 7 else None

        cases.append({
            "case_id": cid,
            "domain": domain,
            "source_type": src_type,
            "target_slides": slides,
            "prompt": prompt,
            "sources": [pdf_file] if pdf_file else [],
            "expected_rules": {
                "min_slides": max(3, slides - 1),
                "max_slides": slides + 2,
                "requires_timeline": req_timeline,
                "requires_source_images": req_images,
                "minimum_source_utilization": 0.65 if pdf_file else 0.0,
                "maximum_critical_issues": 0,
                "maximum_high_issues": 1,
                "minimum_quality_score": 88.0,
            }
        })
        case_counter += 1

    # Systematically generate remaining cases up to 105 to span the complete domain x size matrix
    matrix_domains = DOMAINS
    matrix_sizes = [5, 8, 10, 12, 15, 20]

    for d in matrix_domains:
        for sz in matrix_sizes:
            if len(cases) >= 105:
                break
            # Avoid duplicate case_id
            cid = f"case_{case_counter:03d}_{d}_{sz}s"
            is_timeline = (d in ("history", "strategy", "project_updates"))
            cases.append({
                "case_id": cid,
                "domain": d,
                "source_type": "prompt_only" if sz < 15 else "data_heavy_kpi",
                "target_slides": sz,
                "prompt": f"{sz} slides professional presentation covering strategic overview, key drivers, analytical frameworks, and execution roadmap for {d.replace('_', ' ').title()}.",
                "sources": [],
                "expected_rules": {
                    "min_slides": max(3, sz - 1),
                    "max_slides": sz + 2,
                    "requires_timeline": is_timeline,
                    "requires_source_images": False,
                    "minimum_source_utilization": 0.0,
                    "maximum_critical_issues": 0,
                    "maximum_high_issues": 1,
                    "minimum_quality_score": 88.0,
                }
            })
            case_counter += 1

    return cases


def generate_benchmark_directories() -> int:
    """Generates filesystem cases under tests/presentation_harness/cases/ and defects/."""
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    DEFECTS_DIR.mkdir(parents=True, exist_ok=True)

    # Defect subcategories
    defect_categories = [
        "text_overflow", "text_clipping", "text_overlap", "card_misaligned",
        "missing_icon", "broken_image", "timeline_collision", "footer_collision",
        "underfilled_slide", "overcrowded_slide", "wrong_layout_semantics",
    ]
    for dcat in defect_categories:
        (DEFECTS_DIR / dcat).mkdir(parents=True, exist_ok=True)

    cases = build_100_plus_cases()
    manifest = []

    for c in cases:
        c_dir = CASES_DIR / c["case_id"]
        c_dir.mkdir(parents=True, exist_ok=True)

        (c_dir / "case.json").write_text(json.dumps(c, indent=2), encoding="utf-8")
        (c_dir / "user_prompt.txt").write_text(c["prompt"], encoding="utf-8")
        (c_dir / "expected_rules.json").write_text(json.dumps(c["expected_rules"], indent=2), encoding="utf-8")

        manifest.append({
            "case_id": c["case_id"],
            "domain": c["domain"],
            "target_slides": c["target_slides"],
            "source_type": c["source_type"],
            "has_sources": len(c["sources"]) > 0,
        })

    (HARNESS_ROOT / "cases_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return len(cases)


if __name__ == "__main__":
    count = generate_benchmark_directories()
    print(f"Successfully generated {count} benchmark test scenarios in {CASES_DIR}")
