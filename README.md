# AI-Assisted Candidate Screening Pipeline

A beginner-friendly recruitment demo built with Flask, SQLite, HTML/CSS, and explainable text-based resume matching.

## Features
- Create job profiles and list required skills
- Upload multiple PDF, DOCX, or TXT resumes
- Extract resume text and estimate skill/education/experience/project relevance
- Rank candidates and show match breakdown, matched skills, and missing skills
- Shortlist, review, or mark candidates as not shortlisted
- Local SQLite database; no separate database server required

## Requirements
- Python 3.10 or newer (Python 3.12 is a safe choice)
- VS Code
- Internet connection only for installing Python packages

## Run on Windows (VS Code)
1. Extract the ZIP file to a folder such as `C:\Users\YOUR_NAME\Documents\ai_candidate_screening_pipeline`.
2. Open VS Code → **File → Open Folder** → select that folder.
3. Open **Terminal → New Terminal**.
4. Create a virtual environment:
   ```powershell
   py -m venv .venv
   ```
5. Activate it:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, run this for the current terminal only, then activate again:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```
6. Install dependencies:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
7. Start the website:
   ```powershell
   python app.py
   ```
8. Open `http://127.0.0.1:5000` in your browser.
9. Create a job, upload a few text-based resumes, and review the candidate ranking.

## Demo job
- Title: AI/ML Intern
- Skills: Python, Machine Learning, SQL, Pandas, Scikit-learn
- Education: BE/BTech/MCA
- Experience: 0-2 years

## Important limitations
- This is a college project prototype, not a validated hiring system.
- Match scores are heuristic indicators and can be inaccurate. Always have a human recruiter review candidates.
- Do not use protected traits (age, gender, religion, caste, disability, etc.) for ranking.
- Scanned/image-only PDFs may not contain extractable text; use text-based PDFs or DOCX/TXT files.
- For real deployment, add authentication, privacy/security controls, audit logs, malware scanning, consent/retention policies, and robust parsing.
- The default database is SQLite so the app runs immediately. MongoDB can be added later if required by your project specification.
