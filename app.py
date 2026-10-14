
import os
import re
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
)

from werkzeug.utils import secure_filename

from screening import extract_text, analyze_resume


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "screening.db")

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

app = Flask(__name__)

app.secret_key = "change-this-secret-key-for-production"

app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:

        # Jobs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                skills TEXT NOT NULL,
                education TEXT,
                experience TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # Candidates table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                filename TEXT NOT NULL,

                score INTEGER NOT NULL,
                skill_score INTEGER NOT NULL,
                education_score INTEGER NOT NULL,
                experience_score INTEGER NOT NULL,
                project_score INTEGER NOT NULL,
                semantic_score INTEGER NOT NULL,

                matched_skills TEXT,
                missing_skills TEXT,
                strengths TEXT,
                summary TEXT,

                status TEXT NOT NULL DEFAULT 'Review',
                created_at TEXT NOT NULL,

                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def allowed(filename):
    """Check whether uploaded file has an allowed extension."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def extract_name(text, filename):
    """
    Try to extract candidate name from resume text.
    If not found, use filename.
    """

    # Look at first 1500 characters
    first_part = text[:1500]

    # Example:
    # Name: Ambika Thippeswamy
    name_match = re.search(
        r"(?im)^\s*name\s*[:\-]\s*([A-Za-z][A-Za-z.' -]{2,50})\s*$",
        first_part,
    )

    if name_match:
        return name_match.group(1).strip()

    # Try first non-empty line
    lines = [line.strip() for line in first_part.splitlines() if line.strip()]

    if lines:
        first_line = lines[0]

        # Avoid using obvious headings as name
        excluded = {
            "resume",
            "curriculum vitae",
            "cv",
            "profile",
            "professional summary",
            "career objective",
        }

        if first_line.lower() not in excluded:
            if (
                2 <= len(first_line.split()) <= 5
                and re.match(r"^[A-Za-z][A-Za-z.' -]+$", first_line)
            ):
                return first_line

    # Fallback to filename
    return os.path.splitext(filename)[0].replace("_", " ")


def extract_email(text):
    """Extract email address from resume text."""

    email_match = re.search(
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        text,
    )

    if email_match:
        return email_match.group(0)

    return ""


# ============================================================
# ERROR HANDLING
# ============================================================

@app.errorhandler(413)
def too_large(error):
    flash(
        "File is too large. Please upload files smaller than 12 MB.",
        "error",
    )

    return redirect(
        request.referrer or url_for("dashboard")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
def dashboard():

    with db() as conn:

        jobs = conn.execute(
            """
            SELECT *
            FROM jobs
            ORDER BY id DESC
            """
        ).fetchall()

        candidate_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM candidates
            """
        ).fetchone()[0]

        shortlisted = conn.execute(
            """
            SELECT COUNT(*)
            FROM candidates
            WHERE status = 'Shortlisted'
            """
        ).fetchone()[0]

        review = conn.execute(
            """
            SELECT COUNT(*)
            FROM candidates
            WHERE status = 'Review'
            """
        ).fetchone()[0]

        recent = conn.execute(
            """
            SELECT
                c.*,
                j.title AS job_title
            FROM candidates c
            JOIN jobs j
                ON j.id = c.job_id
            ORDER BY c.id DESC
            LIMIT 6
            """
        ).fetchall()

    return render_template(
        "dashboard.html",
        jobs=jobs,
        candidate_count=candidate_count,
        shortlisted=shortlisted,
        review=review,
        recent=recent,
    )


# ============================================================
# CREATE NEW JOB
# ============================================================

@app.route("/jobs/new", methods=["GET", "POST"])
def new_job():

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        skills = request.form.get("skills", "").strip()
        education = request.form.get("education", "").strip()
        experience = request.form.get("experience", "").strip()
        description = request.form.get("description", "").strip()

        if not title or not skills:

            flash(
                "Job title and required skills are needed.",
                "error",
            )

            return render_template("new_job.html")

        with db() as conn:

            cur = conn.execute(
                """
                INSERT INTO jobs
                (
                    title,
                    skills,
                    education,
                    experience,
                    description,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    skills,
                    education,
                    experience,
                    description,
                    datetime.now().isoformat(timespec="minutes"),
                ),
            )

            job_id = cur.lastrowid

        flash(
            "Job created. Upload resumes to screen candidates.",
            "success",
        )

        return redirect(
            url_for(
                "upload_resumes",
                job_id=job_id,
            )
        )

    return render_template("new_job.html")


# ============================================================
# UPLOAD RESUMES
# ============================================================

@app.route(
    "/jobs/<int:job_id>/upload",
    methods=["GET", "POST"],
)
def upload_resumes(job_id):

    # Find job
    with db() as conn:

        job = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    if not job:

        flash(
            "Job not found.",
            "error",
        )

        return redirect(
            url_for("dashboard")
        )

    # POST = upload resumes
    if request.method == "POST":

        uploaded = request.files.getlist("resumes")

        valid_files = [
            file
            for file in uploaded
            if file
            and file.filename
            and allowed(file.filename)
        ]

        if not valid_files:

            flash(
                "Choose at least one PDF, DOCX, or TXT resume.",
                "error",
            )

            return render_template(
                "upload.html",
                job=job,
            )

        added = 0
        errors = []

        # Process each resume
        for file in valid_files:

            original = secure_filename(
                file.filename
            )

            stamp = datetime.now().strftime(
                "%Y%m%d%H%M%S%f"
            )

            stored = f"{stamp}_{original}"

            path = os.path.join(
                UPLOAD_DIR,
                stored,
            )

            # Save uploaded file
            file.save(path)

            try:

                # ----------------------------------------
                # Extract resume text
                # ----------------------------------------

                resume_text = extract_text(path)

                if not resume_text.strip():

                    raise ValueError(
                        "No readable text found. "
                        "For scanned PDFs, use a text-based PDF."
                    )

                # ----------------------------------------
                # Analyze resume
                # ----------------------------------------

                result = analyze_resume(
                    resume_text,
                    dict(job),
                )

                # ----------------------------------------
                # Candidate information
                # ----------------------------------------

                name = extract_name(
                    resume_text,
                    original,
                )

                email = extract_email(
                    resume_text
                )

                # ----------------------------------------
                # Candidate status
                # ----------------------------------------

                score = int(
                    result.get("score", 0)
                )

                if score >= 75:

                    status = "Shortlisted"

                elif score >= 50:

                    status = "Review"

                else:

                    status = "Not shortlisted"

                # ----------------------------------------
                # Insert candidate into database
                # ----------------------------------------

                with db() as conn:

                    conn.execute(
                        """
                        INSERT INTO candidates
                        (
                            job_id,
                            name,
                            email,
                            filename,
                            score,
                            skill_score,
                            education_score,
                            experience_score,
                            project_score,
                            semantic_score,
                            matched_skills,
                            missing_skills,
                            strengths,
                            summary,
                            status,
                            created_at
                        )
                        VALUES
                        (
                            ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            job_id,
                            name,
                            email,
                            stored,

                            result.get(
                                "score",
                                0,
                            ),

                            result.get(
                                "skill_score",
                                0,
                            ),

                            result.get(
                                "education_score",
                                0,
                            ),

                            result.get(
                                "experience_score",
                                0,
                            ),

                            result.get(
                                "project_score",
                                0,
                            ),

                            result.get(
                                "semantic_score",
                                0,
                            ),

                            ", ".join(
                                result.get(
                                    "matched_skills",
                                    [],
                                )
                            ),

                            ", ".join(
                                result.get(
                                    "missing_skills",
                                    [],
                                )
                            ),

                            " | ".join(
                                result.get(
                                    "strengths",
                                    [],
                                )
                            ),

                            result.get(
                                "summary",
                                "",
                            ),

                            status,

                            datetime.now().isoformat(
                                timespec="minutes"
                            ),
                        ),
                    )

                added += 1

            except Exception as exc:

                errors.append(
                    f"{original}: {str(exc)}"
                )

                # Remove failed upload
                try:

                    os.remove(path)

                except OSError:

                    pass

        # ----------------------------------------
        # Display result messages
        # ----------------------------------------

        if added:

            flash(
                f"Screening complete: {added} resume(s) analyzed.",
                "success",
            )

        for error in errors:

            flash(
                error,
                "error",
            )

        return redirect(
            url_for(
                "job_candidates",
                job_id=job_id,
            )
        )

    # GET request
    return render_template(
        "upload.html",
        job=job,
    )


# ============================================================
# JOB CANDIDATES
# ============================================================

@app.route(
    "/jobs/<int:job_id>/candidates"
)
def job_candidates(job_id):

    with db() as conn:

        job = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        candidates = conn.execute(
            """
            SELECT *
            FROM candidates
            WHERE job_id = ?
            ORDER BY score DESC, id DESC
            """,
            (job_id,),
        ).fetchall()

    if not job:

        flash(
            "Job not found.",
            "error",
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "candidates.html",
        job=job,
        candidates=candidates,
    )


# ============================================================
# ALL CANDIDATES
# ============================================================

@app.route("/candidates")
def all_candidates():

    with db() as conn:

        candidates = conn.execute(
            """
            SELECT
                c.*,
                j.title AS job_title
            FROM candidates c
            JOIN jobs j
                ON j.id = c.job_id
            ORDER BY c.score DESC
            """
        ).fetchall()

    return render_template(
        "all_candidates.html",
        candidates=candidates,
    )


# ============================================================
# CANDIDATE DETAILS
# ============================================================

@app.route(
    "/candidate/<int:candidate_id>"
)
def candidate_detail(candidate_id):

    with db() as conn:

        candidate = conn.execute(
            """
            SELECT
                c.*,
                j.title AS job_title,
                j.skills AS job_skills
            FROM candidates c
            JOIN jobs j
                ON j.id = c.job_id
            WHERE c.id = ?
            """,
            (candidate_id,),
        ).fetchone()

    if not candidate:

        flash(
            "Candidate not found.",
            "error",
        )

        return redirect(
            url_for("all_candidates")
        )

    return render_template(
        "candidate_detail.html",
        candidate=candidate,
    )


# ============================================================
# UPDATE CANDIDATE STATUS
# ============================================================

@app.route(
    "/candidate/<int:candidate_id>/status",
    methods=["POST"],
)
def update_status(candidate_id):

    status = request.form.get(
        "status",
        "Review",
    )

    allowed_statuses = {
        "Shortlisted",
        "Review",
        "Not shortlisted",
    }

    if status not in allowed_statuses:

        status = "Review"

    with db() as conn:

        row = conn.execute(
            """
            SELECT job_id
            FROM candidates
            WHERE id = ?
            """,
            (candidate_id,),
        ).fetchone()

        if not row:

            flash(
                "Candidate not found.",
                "error",
            )

            return redirect(
                url_for("all_candidates")
            )

        conn.execute(
            """
            UPDATE candidates
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                candidate_id,
            ),
        )

    flash(
        "Candidate status updated.",
        "success",
    )

    return redirect(
        url_for(
            "candidate_detail",
            candidate_id=candidate_id,
        )
    )


# ============================================================
# DOWNLOAD UPLOADED RESUME
# ============================================================

@app.route(
    "/uploads/<path:filename>"
)
def uploaded_file(filename):

    return send_from_directory(
        UPLOAD_DIR,
        filename,
        as_attachment=True,
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return {
        "status": "ok",
        "app": "AI Candidate Screening Pipeline",
    }


# ============================================================
# START APPLICATION
# ============================================================

init_db()


if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )
