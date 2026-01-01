from flask import (
    Flask, render_template, redirect,
    url_for, request, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

from validators import (
    validate_common,
    validate_founder,
    validate_investor
)
from config import Config
from datetime import date, timedelta, datetime
import os, time, json
import google.genai as genai

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

# Session + flash
app.secret_key = app.config.get("SECRET_KEY", "dev-secret-key")

# -------------------------------------------------
# FILE UPLOAD CONFIG
# -------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------
def calculate_match_score(founder, investor, pitch_score):
    score = 0
    reasons = []

    # 1️⃣ Stage fit (30)
    if founder["stage"] and founder["stage"] in investor["investment_stage"]:
        score += 30
        reasons.append("Stage alignment")

    # 2️⃣ Sector fit (25)
    if founder["sector"] and investor["sector_focus"]:
        if founder["sector"].lower() in investor["sector_focus"].lower():
            score += 25
            reasons.append("Sector alignment")

    # 3️⃣ Check size fit (15)
    if (
        investor["typical_check_min"]
        and investor["typical_check_max"]
        and founder["min_check_size"]
    ):
        if investor["typical_check_min"] <= founder["min_check_size"] <= investor["typical_check_max"]:
            score += 15
            reasons.append("Check size compatibility")

    # 4️⃣ Geography fit (10)
    if founder["country"] and investor["geography_focus"]:
        if founder["country"].lower() in investor["geography_focus"].lower():
            score += 10
            reasons.append("Geographic focus")

    # 5️⃣ Trust & activity (10)
    if investor["verification_status"] == "verified":
        score += 6
        reasons.append("Verified investor")

    if investor["activity_status"] == "active":
        score += 4

    # 6️⃣ Founder readiness boost (10)
    if pitch_score >= 80:
        score += 10
        reasons.append("Strong pitch readiness")
    elif pitch_score >= 60:
        score += 5

    return score, ", ".join(reasons)

# -------------------------------------------------
# ENTRY PAGE
# -------------------------------------------------
@app.route("/")
def entry():
    return render_template("entry.html")

# -------------------------------------------------
# ROLE SELECTION
# -------------------------------------------------
@app.route("/continue/<role>")
def continue_as(role):
    if role not in ["founder", "investor"]:
        return redirect(url_for("entry"))

    session.clear()
    session["selected_role"] = role
    return redirect(url_for("register", role=role))

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    role = session.get("selected_role")

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            return render_template("login.html", error="Email and password are required.", role=role)

        user = db.session.execute(
            text("SELECT id, role, password_hash FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if not user or not check_password_hash(user.password_hash, password):
            return render_template("login.html", error="Invalid email or password.", role=role)

        session.clear()
        session["user_id"] = user.id
        session["role"] = user.role

        if user.role == "founder":
            return redirect(url_for("founder_home"))
        if user.role == "investor":
            return redirect(url_for("investor_home"))

    return render_template("login.html", role=role)

# -------------------------------------------------
# REGISTER
# -------------------------------------------------
@app.route("/register/<role>", methods=["GET", "POST"])
def register(role):
    if role not in ["founder", "investor"]:
        return redirect(url_for("entry"))

    if request.method == "POST":
        form = request.form

        if not validate_common(form):
            return render_template(f"register_{role}.html", error="Please fill all required fields.")

        if role == "founder" and not validate_founder(form):
            return render_template("register_founder.html", error="Please complete all founder fields.")

        if role == "investor" and not validate_investor(form):
            return render_template("register_investor.html", error="Please complete all investor fields.")

        try:
            existing = db.session.execute(text("SELECT id FROM users WHERE email = :email"), {"email": form["email"]}).fetchone()
            if existing:
                return render_template(f"register_{role}.html", error="An account with this email already exists.")

            # Create User
            result = db.session.execute(
                text("""
                    INSERT INTO users (role, full_name, email, password_hash, phone, country, referral_source)
                    VALUES (:role, :full_name, :email, :password, :phone, :country, :referral)
                """),
                {
                    "role": role, "full_name": form["full_name"], "email": form["email"],
                    "password": generate_password_hash(form["password"]), "phone": form["phone"],
                    "country": form["country"], "referral": form.get("referral")
                }
            )
            user_id = result.lastrowid

            # Create Profile
            if role == "founder":
                actively_raising = True if form["actively_raising"] == "yes" else False
                fundraising_status = "raising" if actively_raising else "preparing"
                db.session.execute(
                    text("""
                        INSERT INTO founder_profiles 
                        (user_id, company_name, founding_year, stage, sector, business_model, actively_raising, fundraising_status, raise_target, raise_raised, min_check_size)
                        VALUES (:user_id, :company_name, :founding_year, :stage, :sector, :business_model, :actively_raising, :fundraising_status, 0, 0, NULL)
                    """),
                    {
                        "user_id": user_id, "company_name": form["company_name"], "founding_year": form["founding_year"],
                        "stage": form["stage"], "sector": form["sector"], "business_model": form["business_model"],
                        "actively_raising": actively_raising, "fundraising_status": fundraising_status
                    }
                )

            if role == "investor":
                db.session.execute(
                    text("""
                        INSERT INTO investor_profiles 
                        (user_id, fund_name, investment_stage, sector_focus, geography_focus, typical_check_min, accredited)
                        VALUES (:user_id, :fund_name, :investment_stage, :sector_focus, :geography_focus, :check_size, :accredited)
                    """),
                    {
                        "user_id": user_id, "fund_name": form["fund_name"], "investment_stage": form["investment_stage"],
                        "sector_focus": form["sector_focus"], "geography_focus": form["geography_focus"],
                        "check_size": form["check_size"], "accredited": form["accredited"]
                    }
                )

            db.session.commit()
            return render_template(f"register_{role}.html", success=True)

        except Exception as e:
            db.session.rollback()
            return render_template(f"register_{role}.html", error=f"Database Error: {str(e)}")

    return render_template(f"register_{role}.html")

# -------------------------------------------------
# 1️⃣ FOUNDER HOME (Updated Completion Logic)
# -------------------------------------------------
@app.route("/founder/home")
def founder_home():
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")

    # Fetch Profile with NEW fields
    founder = db.session.execute(text("""
        SELECT f.*, u.full_name, u.email, u.phone, u.country
        FROM users u
        JOIN founder_profiles f ON u.id = f.user_id
        WHERE u.id = :uid
    """), {"uid": user_id}).fetchone()
    
    if not founder: return redirect(url_for("login"))

    # --- UPDATED COMPLETION LOGIC ---
    # We weight fields differently or just count them all
    fields_to_check = [
        # Basic (User)
        founder.full_name, founder.phone, founder.country,
        # Identity
        founder.logo_url, founder.company_name, founder.website_url,
        # Business
        founder.stage, founder.sector, founder.business_model, founder.product_stage,
        # Fundraising
        founder.raise_target, founder.min_check_size,
        # Social
        founder.linkedin_url
    ]
    
    filled_count = sum(1 for f in fields_to_check if f and str(f).strip())
    total_fields = len(fields_to_check)
    completion_percent = int((filled_count / total_fields) * 100)

    # Missing Fields (for suggestions)
    missing_fields = []
    if not founder.logo_url: missing_fields.append("Company Logo")
    if not founder.website_url: missing_fields.append("Website URL")
    
    # Check for pitch deck existence
    has_deck = db.session.execute(
        text("SELECT id FROM pitch_decks WHERE founder_id = :fid LIMIT 1"),
        {"fid": founder.id}
    ).scalar()
    
    if not has_deck: missing_fields.append("Pitch Deck")

    # Pitch Score Logic (unchanged)
    pitch_score = 0
    if founder.company_name: pitch_score += 10
    if founder.stage: pitch_score += 10
    if founder.sector: pitch_score += 10
    if founder.business_model: pitch_score += 10
    if founder.actively_raising: pitch_score += 10
    if founder.founding_year: pitch_score += 5
    if completion_percent >= 90: pitch_score += 15
    if has_deck: pitch_score += 30

    pitch_label = "Investor-Ready" if pitch_score >= 80 else "Good" if pitch_score >= 50 else "Needs Work"

    # Timeline
    weeks_elapsed = 0
    if founder.fundraising_start_date:
        delta = date.today() - founder.fundraising_start_date
        weeks_elapsed = delta.days // 7

    # Metrics
    recent_views_count = db.session.execute(text("SELECT COUNT(*) FROM investor_profile_views WHERE founder_id=:fid AND viewed_at >= NOW() - INTERVAL 7 DAY"), {"fid": founder.id}).scalar()
    expressed_interest_count = db.session.execute(text("SELECT COUNT(*) FROM matches WHERE founder_id=:fid AND status='interested'"), {"fid": founder.id}).scalar()
    total_matches = db.session.execute(text("SELECT COUNT(*) FROM matches WHERE founder_id=:fid"), {"fid": founder.id}).scalar()

    # Activity Feed
    views = db.session.execute(text("SELECT 'view' as type, v.viewed_at as created_at, ip.fund_name as detail FROM investor_profile_views v JOIN investor_profiles ip ON v.investor_id = ip.id WHERE v.founder_id = :fid ORDER BY v.viewed_at DESC LIMIT 3"), {"fid": founder.id}).fetchall()
    matches = db.session.execute(text("SELECT 'match' as type, m.created_at, CONCAT(ip.fund_name, ' (', m.match_score, '% Match)') as detail FROM matches m JOIN investor_profiles ip ON m.investor_id = ip.id WHERE m.founder_id = :fid AND m.match_score > 70 ORDER BY m.created_at DESC LIMIT 3"), {"fid": founder.id}).fetchall()
    msgs = db.session.execute(text("SELECT 'message' as type, m.created_at, u.full_name as detail FROM messages m JOIN conversations c ON m.conversation_id = c.id JOIN users u ON m.sender_id = u.id WHERE c.founder_id = :fid AND m.sender_id != :uid ORDER BY m.created_at DESC LIMIT 3"), {"fid": founder.id, "uid": user_id}).fetchall()

    activity_feed = sorted(views + matches + msgs, key=lambda x: x.created_at, reverse=True)[:6]

    # AI Alert
    ai_alert = None
    if pitch_score < 50:
        ai_alert = "Your Pitch Score is low. Upload a deck and fill missing fields to rank higher."
    elif recent_views_count > 5 and not has_deck:
        ai_alert = "📈 Traffic spike! Investors are looking. Upload your deck now to convert them."
    elif expressed_interest_count > 0:
        ai_alert = f"🔥 Momentum! {expressed_interest_count} investors expressed interest. Reply immediately."
    else:
        ai_alert = "Profile is looking good. Check your 'Investor Matches' to start outreach."

    raise_target = founder.raise_target or 1
    raise_percent = int((founder.raise_raised / raise_target * 100) if founder.raise_raised else 0)

    # Pass calculated data to template
    return render_template(
        "dashboard/founder_home.html",
        founder=founder,
        completion_percent=completion_percent,
        missing_fields=missing_fields,
        pitch_score=pitch_score,
        pitch_label=pitch_label,
        raise_target=founder.raise_target,
        raise_raised=founder.raise_raised,
        raise_percent=raise_percent,
        weeks_elapsed=weeks_elapsed,
        recent_views=recent_views_count,
        expressed_interest=expressed_interest_count,
        ai_alert=ai_alert,
        activity_feed=activity_feed,
        has_deck=has_deck,
        total_matches=total_matches
    )


# -------------------------------------------------
# 2️⃣ FOUNDER MATCHES
# -------------------------------------------------
@app.route("/founder/matches")
def founder_matches():
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")

    # Fetch matches: Saved first, then by score
    matches = db.session.execute(text("""
        SELECT m.id AS match_id, m.match_score, m.status, m.ai_reason,
               u.full_name AS investor_name, ip.fund_name, ip.investment_stage,
               ip.sector_focus, ip.geography_focus, ip.typical_check_min
        FROM matches m
        JOIN investor_profiles ip ON m.investor_id = ip.id
        JOIN users u ON ip.user_id = u.id
        WHERE m.founder_id = (SELECT id FROM founder_profiles WHERE user_id = :uid)
          AND m.status != 'declined'
        ORDER BY CASE WHEN m.status = 'saved' THEN 1 ELSE 0 END DESC, m.match_score DESC
        LIMIT 50
    """), {"uid": user_id}).fetchall()

    return render_template("dashboard/founder_matches.html", matches=matches)

@app.route("/founder/matches/generate")
def generate_matches():
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")

    founder = db.session.execute(text("SELECT * FROM founder_profiles WHERE user_id=:uid"), {"uid": user_id}).mappings().first()
    if not founder: return redirect(url_for("founder_home"))
    
    # Get active investors
    investors = db.session.execute(text("SELECT * FROM investor_profiles WHERE activity_status='active'")).mappings().all()
    pitch_score = 70 # Placeholder, should ideally come from live score

    for inv in investors:
        score, reason = calculate_match_score(founder, inv, pitch_score)
        if score >= 40:
            db.session.execute(text("""
                INSERT INTO matches (founder_id, investor_id, match_score, status, ai_reason)
                VALUES (:fid, :iid, :sc, 'new', :rs)
                ON DUPLICATE KEY UPDATE match_score=:sc, ai_reason=:rs
            """), {"fid": founder["id"], "iid": inv["id"], "sc": score, "rs": reason})
    
    db.session.commit()
    return redirect(url_for("founder_matches"))

@app.route("/founder/matches/update/<int:match_id>/<action>")
def update_match_status(match_id, action):
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")

    # Get match details
    match = db.session.execute(text("SELECT * FROM matches WHERE id=:mid"), {"mid": match_id}).mappings().first()
    
    # Update Status
    db.session.execute(text("UPDATE matches SET status = :st, updated_at = NOW() WHERE id = :mid"), {"st": action, "mid": match_id})
    
    # IF ACTION IS INTERESTED -> CREATE CONVERSATION
    if action == "interested":
        exists = db.session.execute(text("""
            SELECT id FROM conversations 
            WHERE founder_id=:fid AND investor_id=:iid
        """), {"fid": match.founder_id, "iid": match.investor_id}).fetchone()

        if not exists:
            db.session.execute(text("""
                INSERT INTO conversations (founder_id, investor_id, created_at)
                VALUES (:fid, :iid, NOW())
            """), {"fid": match.founder_id, "iid": match.investor_id})

    db.session.commit()
    return redirect(url_for("founder_matches"))

# -------------------------------------------------
# 3️⃣ PITCH HUB (AI-POWERED)
# -------------------------------------------------
@app.route("/founder/pitch")
def founder_pitch():
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")

    # Fetch the latest deck
    deck = db.session.execute(text("""
        SELECT * FROM pitch_decks 
        WHERE founder_id = (SELECT id FROM founder_profiles WHERE user_id = :uid) 
        ORDER BY created_at DESC LIMIT 1
    """), {"uid": user_id}).fetchone()

    # Parse the JSON analysis if it exists
    analysis = None
    if deck and deck.analysis_json:
        try:
            analysis = json.loads(deck.analysis_json)
        except:
            analysis = None

    return render_template("dashboard/founder_pitch.html", deck=deck, analysis=analysis)

@app.route("/founder/pitch/upload", methods=["POST"])
def upload_pitch():
    if session.get("role") != "founder": return redirect(url_for("login"))
    
    file = request.files.get("pitch_deck")
    if not file or not file.filename.lower().endswith(".pdf"):
        flash("Only PDF files are allowed.")
        return redirect(url_for("founder_pitch"))

    user_id = session.get("user_id")
    filename = f"pitch_{user_id}_{int(time.time())}.pdf"
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    # -------------------------------------------------
    # 🤖 GEMINI AI ANALYSIS START
    # -------------------------------------------------
    try:
        # 1. Configure Gemini
        genai.configure(api_key=app.config["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")

        # 2. Upload file to Gemini (Temporary storage)
        uploaded_file = genai.upload_file(path=file_path, display_name="Pitch Deck")

        # 3. Wait for file processing (usually instant for small PDFs)
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        # 4. Generate Analysis
        prompt = """
        You are a top-tier Venture Capital Analyst. Analyze this pitch deck PDF.
        Provide the output in strict JSON format with no markdown formatting.
        The JSON keys must be:
        - "score": An integer from 0 to 100 representing investability.
        - "summary": A 2-sentence executive summary.
        - "strengths": A list of 3 key strengths (strings).
        - "weaknesses": A list of 3 key weaknesses (strings).
        - "verdict": One word: "Invest", "Maybe", or "Pass".
        """
        
        response = model.generate_content([prompt, uploaded_file])
        
        # 5. Clean & Parse JSON
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        analysis_data = json.loads(raw_text)
        
        score = analysis_data.get("score", 0)
        summary = analysis_data.get("summary", "No summary available.")
        
    except Exception as e:
        print(f"AI Error: {e}")
        score = 50 # Default if AI fails
        analysis_data = {}
        summary = "AI Analysis failed. Please try again later."

    # -------------------------------------------------
    # DATABASE SAVE
    # -------------------------------------------------
    file_url = f"/static/uploads/{filename}"
    founder_id = db.session.execute(text("SELECT id FROM founder_profiles WHERE user_id=:uid"), {"uid": user_id}).scalar()

    db.session.execute(text("""
        INSERT INTO pitch_decks (founder_id, file_url, deck_score, analysis_json, feedback_summary) 
        VALUES (:fid, :url, :score, :json, :summ)
    """), {
        "fid": founder_id, 
        "url": file_url, 
        "score": score,
        "json": json.dumps(analysis_data),
        "summ": summary
    })
    db.session.commit()
    
    flash("Pitch deck analyzed by AI successfully!")
    return redirect(url_for("founder_pitch"))


# -------------------------------------------------
# 4️⃣ TRACTION (Charts & AI CFO)
# -------------------------------------------------
@app.route("/founder/traction", methods=["GET", "POST"])
def founder_traction():
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")
    
    # 1. Fetch Profile & Saved Report
    founder_profile = db.session.execute(
        text("SELECT id, raise_target, traction_report FROM founder_profiles WHERE user_id=:uid"),
        {"uid": user_id}
    ).fetchone()

    # HANDLE ADDING DATA
    if request.method == "POST" and "add_metric" in request.form:
        db.session.execute(text("""
            INSERT INTO traction_metrics (founder_id, month_label, revenue, expenses, active_users)
            VALUES (:fid, :m, :r, :e, :u)
        """), {
            "fid": founder_profile.id, 
            "m": request.form.get("month"),
            "r": request.form.get("revenue"), 
            "e": request.form.get("expenses"), 
            "u": request.form.get("users") or 0
        })
        db.session.commit()
        flash("Metric added successfully.")
        return redirect(url_for("founder_traction"))

    # FETCH METRICS
    metrics = db.session.execute(
        text("SELECT * FROM traction_metrics WHERE founder_id=:fid ORDER BY id ASC"),
        {"fid": founder_profile.id}
    ).fetchall()
    
    # PREPARE DATA FOR CHARTS/KPIs
    labels = [m.month_label for m in metrics]
    revenue = [float(m.revenue) for m in metrics]
    expenses = [float(m.expenses) for m in metrics]
    
    # CALCULATE KPIS
    kpis = {"mrr": 0, "burn": 0, "runway": 0, "growth": 0, "users": 0, "profit": False}

    if metrics:
        last = metrics[-1]
        kpis["mrr"] = float(last.revenue)
        kpis["users"] = last.active_users
        kpis["burn"] = float(last.expenses) - float(last.revenue)
        
        # Simple Runway Calc
        cash_in_bank = float(founder_profile.raise_target or 0) * 0.5 
        if kpis["burn"] > 0:
            kpis["runway"] = cash_in_bank / kpis["burn"]
        else:
            kpis["profit"] = True
            
        # MoM Growth
        if len(metrics) > 1:
            prev = metrics[-2]
            prev_rev = float(prev.revenue)
            if prev_rev > 0:
                kpis["growth"] = int(((kpis["mrr"] - prev_rev) / prev_rev) * 100)

    return render_template(
        "dashboard/founder_traction.html", 
        labels=json.dumps(labels), 
        revenue=json.dumps(revenue), 
        expenses=json.dumps(expenses), 
        metrics=metrics, 
        kpis=kpis,
        traction_report=founder_profile.traction_report
    )

@app.route("/founder/traction/delete/<int:metric_id>")
def delete_traction(metric_id):
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")
    founder = db.session.execute(text("SELECT id FROM founder_profiles WHERE user_id=:uid"), {"uid": user_id}).fetchone()
    
    db.session.execute(text("DELETE FROM traction_metrics WHERE id=:mid AND founder_id=:fid"), 
                       {"mid": metric_id, "fid": founder.id})
    db.session.commit()
    flash("Entry deleted.")
    return redirect(url_for("founder_traction"))

@app.route("/founder/traction/analyze", methods=["POST"])
def analyze_traction():
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")
    
    founder = db.session.execute(text("SELECT id, stage, sector, raise_target FROM founder_profiles WHERE user_id=:uid"), {"uid": user_id}).mappings().first()
    
    metrics = db.session.execute(text("SELECT * FROM traction_metrics WHERE founder_id=:fid ORDER BY id ASC LIMIT 12"), {"fid": founder.id}).fetchall()
    
    if not metrics:
        flash("We can't analyze empty air. Add your numbers.")
        return redirect(url_for("founder_traction"))

    data_summary = []
    latest_burn = 0
    for m in metrics:
        burn = float(m.expenses) - float(m.revenue)
        latest_burn = burn
        data_summary.append(f"{m.month_label}: Rev ${m.revenue}, Exp ${m.expenses}, Burn ${burn}")
    
    data_str = "\n".join(data_summary)
    bank_balance = float(founder.raise_target or 0) * 0.5 
    runway_est = (bank_balance / latest_burn) if latest_burn > 0 else 99

    try:
        import google.generativeai as genai
        api_key = app.config.get("GEMINI_API_KEY")
        if not api_key:
            flash("System Error: AI Key missing.")
            return redirect(url_for("founder_traction"))

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = f"""
        You are a **brutal, no-nonsense Venture Capitalist** evaluating a portfolio company. 
        **The Numbers:**
        {data_str}
        **The Reality:**
        - Stage: {founder.stage}
        - Estimated Runway: {int(runway_est)} months
        **Instructions:**
        Analyze this data critically. Provide feedback in **raw HTML** (no markdown). Use this exact structure:
        <div class="cfo-insight">
            <h4 class="text-emerald-400">💎 The One Good Thing</h4>
            <p>[Find the single best metric.]</p>
        </div>
        <div class="cfo-insight">
            <h4 class="text-rose-500">💀 The Kill Switch</h4>
            <p>[Identify the #1 thing that will kill this company in the next 6 months.]</p>
        </div>
        <div class="cfo-insight">
            <h4 class="text-blue-400">⚔️ War Room Orders</h4>
            <ul>
                <li><strong>Cut:</strong> [Specific expense to eliminate]</li>
                <li><strong>Fix:</strong> [Specific metric to improve]</li>
            </ul>
        </div>
        """
        
        response = model.generate_content(prompt)
        ai_advice = response.text.replace("```html", "").replace("```", "").strip()
        
        db.session.execute(
            text("UPDATE founder_profiles SET traction_report = :rpt WHERE id = :fid"),
            {"rpt": ai_advice, "fid": founder.id}
        )
        db.session.commit()
        flash("Financial stress test complete.")
        
    except Exception as e:
        print(f"AI Error: {e}")
        flash(f"AI Service Error: {str(e)}")

    return redirect(url_for("founder_traction"))

# -------------------------------------------------
# 5️⃣ MESSAGES (Real-Time API & View)
# -------------------------------------------------

# VIEW: Main Messages Page
@app.route("/founder/messages")
@app.route("/founder/messages/<int:conversation_id>")
def founder_messages(conversation_id=None):
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")

    founder = db.session.execute(text("SELECT id FROM founder_profiles WHERE user_id=:uid"), {"uid": user_id}).fetchone()

    # 1. Fetch Conversations List (Left Sidebar)
    conversations = db.session.execute(text("""
        SELECT 
            c.id, 
            u.full_name, 
            ip.fund_name, 
            (SELECT message FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_msg, 
            (SELECT created_at FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_time,
            (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id AND is_read = 0 AND sender_id != :uid) AS unread_count
        FROM conversations c
        JOIN investor_profiles ip ON c.investor_id = ip.id
        JOIN users u ON ip.user_id = u.id
        WHERE c.founder_id = :fid
        ORDER BY last_time DESC
    """), {"fid": founder.id, "uid": user_id}).fetchall()

    active_partner = None
    if conversation_id:
        # Mark messages as read immediately upon load
        db.session.execute(text("""
            UPDATE messages SET is_read = 1 
            WHERE conversation_id = :cid AND sender_id != :uid
        """), {"cid": conversation_id, "uid": user_id})
        db.session.commit()

        # Get Partner Name for Header
        active_partner = db.session.execute(text("""
            SELECT u.full_name, ip.fund_name 
            FROM conversations c
            JOIN investor_profiles ip ON c.investor_id = ip.id
            JOIN users u ON ip.user_id = u.id
            WHERE c.id = :cid
        """), {"cid": conversation_id}).fetchone()

    return render_template(
        "dashboard/founder_messages.html", 
        conversations=conversations, 
        current_convo=conversation_id, 
        active_partner=active_partner,
        user_id=user_id
    )

# API: Get Messages (JSON for Polling)
@app.route("/api/chat/<int:conversation_id>")
def api_get_messages(conversation_id):
    if session.get("role") != "founder": return {"error": "Unauthorized"}, 401
    user_id = session.get("user_id")

    # Mark as read (Async)
    db.session.execute(text("UPDATE messages SET is_read=1 WHERE conversation_id=:cid AND sender_id!=:uid"), 
                       {"cid": conversation_id, "uid": user_id})
    db.session.commit()

    # Fetch messages
    msgs = db.session.execute(text("""
        SELECT m.id, m.message, m.created_at, m.sender_id
        FROM messages m 
        WHERE m.conversation_id = :cid
        ORDER BY m.created_at ASC
    """), {"cid": conversation_id}).fetchall()
    
    # Return JSON
    return {
        "messages": [{
            "id": m.id,
            "text": m.message,
            "is_me": (m.sender_id == user_id),
            "time": m.created_at.strftime('%H:%M')
        } for m in msgs]
    }

# API: Send Message (AJAX)
@app.route("/api/chat/send", methods=["POST"])
def api_send_message():
    if session.get("role") != "founder": return {"error": "Unauthorized"}, 401
    user_id = session.get("user_id")
    data = request.json
    
    if not data.get("message") or not data.get("conversation_id"):
        return {"error": "Empty message"}, 400

    db.session.execute(text("""
        INSERT INTO messages (conversation_id, sender_id, message)
        VALUES (:cid, :uid, :msg)
    """), {"cid": data["conversation_id"], "uid": user_id, "msg": data["message"]})
    db.session.commit()
    
    return {"status": "success"}

# -------------------------------------------------
# 6️⃣ SETTINGS (Updated Profile Management)
# -------------------------------------------------
@app.route("/founder/settings", methods=["GET", "POST"])
def founder_settings():
    if session.get("role") != "founder": return redirect(url_for("login"))
    user_id = session.get("user_id")

    if request.method == "POST":
        f = request.form
        
        # 1. Handle Logo Upload
        logo_url = None
        if "logo" in request.files:
            file = request.files["logo"]
            if file and file.filename:
                filename = f"logo_{user_id}_{int(time.time())}.png" # Force PNG/JPG extension in real app
                file.save(os.path.join(UPLOAD_FOLDER, filename))
                logo_url = f"/static/uploads/{filename}"

        # 2. Update User Table
        db.session.execute(text("""
            UPDATE users SET full_name=:fn, phone=:ph, country=:co WHERE id=:uid
        """), {"fn": f["full_name"], "ph": f["phone"], "co": f["location"], "uid": user_id}) 
        # Note: We map 'location' form field to 'country' DB field for now, or use separate if available

        # 3. Update Founder Profile Table
        # We build the query dynamically or just list all fields
        query = """
            UPDATE founder_profiles SET 
            company_name=:cn, tagline=:tag, website_url=:web, linkedin_url=:lin,
            location=:loc, team_size=:ts, stage=:stg, product_stage=:pstg,
            sector=:sec, business_model=:bm, 
            actively_raising=:ar, raise_target=:rt, min_check_size=:mcs
        """
        params = {
            "cn": f["company_name"], "tag": f["tagline"], "web": f["website_url"], "lin": f["linkedin_url"],
            "loc": f["location"], "ts": f["team_size"], "stg": f["stage"], "pstg": f["product_stage"],
            "sec": f["sector"], "bm": f["business_model"],
            "ar": (1 if f.get("actively_raising") else 0), 
            "rt": f["raise_target"] or 0, "mcs": f["min_check_size"] or 0,
            "uid": user_id
        }

        if logo_url:
            query += ", logo_url=:logo"
            params["logo"] = logo_url
            
        query += " WHERE user_id=:uid"

        db.session.execute(text(query), params)
        db.session.commit()
        
        flash("Profile updated successfully! Dashboard completion recalculated.")
        return redirect(url_for("founder_settings"))

    # Fetch Data
    data = db.session.execute(text("""
        SELECT u.full_name, u.email, u.phone, u.country, f.* FROM users u JOIN founder_profiles f ON u.id = f.user_id 
        WHERE u.id=:uid
    """), {"uid": user_id}).fetchone()

    return render_template("dashboard/founder_settings.html", data=data)
# -------------------------------------------------
# INVESTOR DASHBOARD
# -------------------------------------------------
@app.route("/investor/home")
def investor_home():
    if session.get("role") != "investor": return redirect(url_for("login"))
    return "Investor Dashboard (Coming Soon)"

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("entry"))

if __name__ == "__main__":
    app.run(debug=True)