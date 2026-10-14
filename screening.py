import os, re, math
from collections import Counter

SKILL_ALIASES = {
    "python": ["python"], "java": ["java"], "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning"], "sql": ["sql", "mysql", "postgresql", "sqlite"],
    "pandas": ["pandas"], "numpy": ["numpy"], "scikit-learn": ["scikit-learn", "sklearn"],
    "tensorflow": ["tensorflow"], "pytorch": ["pytorch"], "nlp": ["nlp", "natural language processing"],
    "html": ["html"], "css": ["css"], "javascript": ["javascript", "js"],
    "react": ["react", "react.js"], "node.js": ["node.js", "nodejs"], "flask": ["flask"],
    "django": ["django"], "mongodb": ["mongodb", "mongo db"], "git": ["git", "github"],
    "excel": ["excel"], "power bi": ["power bi"], "data analysis": ["data analysis", "data analytics"],
    "aws": ["aws", "amazon web services"], "docker": ["docker"], "c++": ["c++"],
    "c": ["c programming", " c language "], "communication": ["communication"]
}

def extract_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    if ext == ".pdf":
        import fitz
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    if ext == ".docx":
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Unsupported file format.")

def normalize(text):
    return " " + re.sub(r"[^a-z0-9+#.\-]+", " ", text.lower()) + " "

def find_skills(text):
    normalized = normalize(text)
    found = []
    for skill, aliases in SKILL_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            found.append(skill)
    return found

def token_set(text):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}", text.lower())
    stop = {"with","from","that","this","have","will","your","their","using","into","and","the","for","are","was","has","you","our","not","but","can","all","job","role"}
    return {w for w in words if w not in stop and len(w) > 2}

def similarity(a, b):
    A, B = token_set(a), token_set(b)
    if not A or not B: return 0
    # Cosine similarity on binary token vectors
    return len(A & B) / math.sqrt(len(A) * len(B))

def analyze_resume(text, job):
    required = [s.strip().lower() for s in re.split(r"[,;\n]+", job.get("skills", "")) if s.strip()]
    # Resolve job skill aliases to recognized names; keep unknown skills as literal terms.
    resume_skills = find_skills(text)
    normalized = normalize(text)
    matched, missing = [], []
    for skill in required:
        aliases = SKILL_ALIASES.get(skill, [skill])
        if any(a in normalized for a in aliases):
            matched.append(skill)
        else:
            missing.append(skill)
    skill_score = round(100 * len(matched) / max(1, len(required)))
    education_terms = ["b.e", "b.tech", "bachelor", "b.sc", "mca", "m.tech", "master", "degree", "university", "college"]
    education_score = 85 if any(t in normalized for t in education_terms) else 35
    years = [int(x) for x in re.findall(r"\b(\d{1,2})\+?\s*(?:years|year|yrs|yr)\b", text.lower())]
    years_found = max(years) if years else 0
    exp_text = (job.get("experience") or "").lower()
    req_match = re.search(r"(\d+)\s*(?:-|to)\s*(\d+)", exp_text)
    if req_match:
        low, high = int(req_match.group(1)), int(req_match.group(2))
        experience_score = 100 if low <= years_found <= high else (75 if years_found > high else 60 if low == 0 else 35)
    else:
        experience_score = 75 if years_found else 55
    project_score = 90 if re.search(r"(?i)\b(project|developed|built|implemented|created|designed)\b", text) else 30
    description = (job.get("description") or "") + " " + (job.get("title") or "") + " " + (job.get("skills") or "")
    semantic_score = min(100, round(similarity(text, description) * 220))
    # Explainable weighted score. This is a demo heuristic, not a validated hiring model.
    score = round(skill_score * .40 + education_score * .15 + experience_score * .15 + project_score * .15 + semantic_score * .15)
    strengths = []
    if matched: strengths.append("Matched skills: " + ", ".join(matched[:8]))
    if project_score >= 80: strengths.append("Resume mentions projects or hands-on development.")
    if education_score >= 80: strengths.append("Education-related terms were found.")
    if not strengths: strengths.append("Review resume manually for relevant experience and evidence.")
    summary = ("Good initial match based on listed skills and resume text." if score >= 75 else
               "Some relevant signals found; recruiter review is recommended." if score >= 50 else
               "Low text-based match; review the resume manually before making a decision.")
    return {"score": max(0, min(100, score)), "skill_score": skill_score,
            "education_score": education_score, "experience_score": experience_score,
            "project_score": project_score, "semantic_score": semantic_score,
            "matched_skills": matched, "missing_skills": missing,
            "strengths": strengths, "summary": summary}
