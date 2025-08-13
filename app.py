import os
import json
import re
import streamlit as st

# Optional PDF parsing (keep lightweight)
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

# -------------- UI CONFIG --------------
st.set_page_config(page_title="CultureMatch.AI – Prototype", page_icon="🧭", layout="centered")
st.title("🧭 CultureMatch.AI – Prototype")
st.caption("Paste a resume/LinkedIn profile or upload a PDF. Select a target company culture. The app uses Gemini to generate simulated culture-fit insights.")

# -------------- API KEY --------------
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.warning("Set GEMINI_API_KEY in Streamlit Secrets (or environment) to enable AI analysis.")

# -------------- SAMPLE CULTURE PROFILES --------------
CULTURES = {
    "Product-led Startup": "Fast iteration, user-centric decisions, ownership, bias to ship, scrappy experimentation, async collaboration.",
    "Enterprise FinTech": "Risk management, compliance, stakeholder alignment, documentation, predictable delivery, secure coding, cross-functional reviews.",
    "OSS Dev Tool": "Open-source ethos, transparency, code-first communication, RFC culture, community support, performance benchmarks, DX obsession.",
    "EdTech Mission": "Learning impact, pedagogy awareness, accessibility, experimentation with A/B tests, empathy for students/teachers, long-term retention.",
    "AI Research Lab": "Paper-to-product pipeline, reproducible experiments, reading groups, evals, ablations, ethics & safety reviews, MLOps discipline."
}

# -------------- HELPERS --------------
def read_pdf(file) -> str:
    if not PdfReader:
        return ""
    try:
        reader = PdfReader(file)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text
    except Exception:
        return ""


def extract_json(text: str):
    """Extract first JSON object from a string; return dict or None."""
    try:
        # direct load attempt
        return json.loads(text)
    except Exception:
        pass
    # Try to find a JSON block
    match = re.search(r"\{[\s\S]*\}")
    if match:
        chunk = match.group(0)
        try:
            return json.loads(chunk)
        except Exception:
            return None
    return None


@st.cache_data(show_spinner=False)
def build_prompt(resume_text: str, company_profile: str, job_desc: str = "") -> str:
    return f"""
You are an expert talent evaluator.
Analyze the candidate profile and estimate culture fit against the given company culture profile.
If job description is provided, consider it.

Return ONLY JSON with this schema:
{{
  "culture_match_percent": <integer 0-100>,
  "work_style_archetype": "string (e.g., Builder, Researcher, Operator, Collaborator)",
  "top_strengths": ["string", "string", "string"],
  "risks_or_gaps": ["string", "string"],
  "interview_questions": ["string", "string", "string"],
  "summary": "3-4 sentence concise summary"
}}

Candidate Profile (resume/linkedin):
"""
{resume_text}
"""

Company Culture Profile:
"""
{company_profile}
"""

Job Description (optional):
"""
{job_desc}
"""

Only output the JSON. No preamble.
"""


# -------------- SIDEBAR --------------
st.sidebar.header("Settings")
company = st.sidebar.selectbox("Target culture", list(CULTURES.keys()), index=0)
with st.sidebar.expander("Optional: add job description"):
    job_desc = st.text_area("Paste JD", height=120, key="jd")

# -------------- INPUTS --------------
with st.form("profile_form"):
    uploaded = st.file_uploader("Upload resume (.pdf or .txt)", type=["pdf", "txt"])
    raw_text = st.text_area("Or paste profile text", height=240, placeholder="Paste resume/LinkedIn profile text here…")
    submitted = st.form_submit_button("Analyze →")

profile_text = ""
if uploaded is not None:
    if uploaded.name.lower().endswith(".pdf"):
        profile_text = read_pdf(uploaded)
        if not profile_text:
            st.info("Couldn't parse PDF text. Consider uploading a .txt or pasting text.")
    else:
        profile_text = uploaded.read().decode(errors="ignore")

if not profile_text and raw_text:
    profile_text = raw_text.strip()

# -------------- ANALYSIS --------------
if submitted:
    if not profile_text:
        st.error("Please upload a resume or paste profile text.")
        st.stop()
    if not GEMINI_API_KEY:
        st.error("Missing GEMINI_API_KEY. Add it to Streamlit secrets and rerun.")
        st.stop()

    with st.spinner("Calling Gemini and generating insights…"):
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-pro")
            prompt = build_prompt(profile_text, CULTURES[company], job_desc)
            resp = model.generate_content(prompt)
            text = resp.text or "{}"
        except Exception as e:
            st.exception(e)
            st.stop()

    data = extract_json(text) or {}

    # Fallback defaults if model didn't return well-formed JSON
    match_pct = int(data.get("culture_match_percent", 62))
    archetype = data.get("work_style_archetype", "Builder")
    strengths = data.get("top_strengths", ["Ownership", "User empathy", "Shipping velocity"])
    risks = data.get("risks_or_gaps", ["Limited domain exposure", "Needs deeper system design examples"])
    questions = data.get("interview_questions", [
        "Tell me about a time you navigated ambiguous product goals.",
        "How do you validate culture fit before joining a team?",
        "Walk through a decision where you traded speed vs quality."
    ])
    summary = data.get("summary", "Candidate demonstrates strong bias to action and user empathy, suitable for product-led teams. Some gaps in formal process for regulated environments.")

    st.subheader("Results")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Culture Match", f"{match_pct}%")
        st.progress(match_pct / 100)
    with col2:
        st.markdown(f"**Work Style Archetype:** {archetype}")
        st.markdown(f"**Target Culture:** {company}")

    st.markdown("---")
    st.markdown("### Top strengths")
    for s in strengths:
        st.write(f"• {s}")

    st.markdown("### Risks / gaps")
    for r in risks:
        st.write(f"• {r}")

    st.markdown("### Suggested interview questions")
    for q in questions:
        st.write(f"• {q}")

    st.markdown("### Summary")
    st.write(summary)

    # Downloadable report
    report = {
        "target_culture": company,
        "culture_match_percent": match_pct,
        "work_style_archetype": archetype,
        "top_strengths": strengths,
        "risks_or_gaps": risks,
        "interview_questions": questions,
        "summary": summary,
    }
    st.download_button("Download JSON report", data=json.dumps(report, indent=2), file_name="culturematch_report.json")

st.markdown("\n\n—\n*This is a demo prototype for showcasing capabilities. It does not represent validated hiring decisions.*")
