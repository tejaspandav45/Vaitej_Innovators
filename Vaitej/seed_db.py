import sys
import json
import random
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash
from sqlalchemy import text

# Import your Flask app and db instance
# Ensure this script is in the same directory as app.py
from app import app, db

def run_seed():
    """Populates the database with sample data based on the provided schema."""
    
    print("🌱 Starting Database Seeding...")

    with app.app_context():
        try:
            # OPTIONAL: Clear existing data (Order matters due to Foreign Keys)
            print("   Cleaning old data...")
            tables = [
                "audit_logs", "admin_users", "ai_sessions", "messages", "conversations", 
                "deck_access_logs", "investment_reports", "qa_sessions", "due_diligence",
                "traction_metrics", "pitch_decks", "investor_profile_views", "matches", 
                "founder_updates", "founder_profiles", "investor_profiles", "users"
            ]
            for t in tables:
                db.session.execute(text(f"DELETE FROM {t}"))
                db.session.execute(text(f"ALTER TABLE {t} AUTO_INCREMENT = 1"))
            db.session.commit()

            # ---------------------------------------------------------
            # 1. CREATE USERS
            # ---------------------------------------------------------
            print("   Creating Users...")
            password = generate_password_hash("password123")
            
            users_data = [
                # (Role, Name, Email)
                ("founder", "Alice Chen", "alice@nebula.ai"),
                ("founder", "David Ross", "david@greenblocks.io"),
                ("founder", "Sarah Miller", "sarah@medtech.co"),
                ("investor", "Bob Venture", "bob@apexvc.com"),
                ("investor", "Jessica Capital", "jessica@horizonfund.com"),
                ("admin", "Admin User", "admin@vaitej.com")
            ]

            user_ids = {} # Map email -> id

            for role, name, email in users_data:
                result = db.session.execute(
                    text("""
                        INSERT INTO users 
                        (role, full_name, email, password_hash, phone, country, is_verified, status)
                        VALUES (:role, :name, :email, :pwd, '555-0100', 'USA', 1, 'active')
                    """),
                    {"role": role, "name": name, "email": email, "pwd": password}
                )
                user_ids[email] = result.lastrowid
            
            db.session.commit()

            # ---------------------------------------------------------
            # 2. CREATE FOUNDER PROFILES
            # ---------------------------------------------------------
            print("   Creating Founder Profiles...")
            
            # Founder 1: Alice (Nebula AI) - High Tech / AI
            db.session.execute(text("""
                INSERT INTO founder_profiles 
                (user_id, company_name, tagline, website_url, location, founding_year, stage, sector, business_model, 
                 fundraising_status, raise_target, min_check_size, actively_raising, team_size, product_stage, profile_completion, traction_report)
                VALUES 
                (:uid, 'Nebula AI', 'Generative AI for Enterprise Workflows', 'https://nebula.ai', 'San Francisco, CA', 
                 2023, 'seed', 'Artificial Intelligence', 'B2B', 'raising', 2000000, 50000, 1, 8, 'Beta', 90, 'Growing fast with low burn.')
            """), {"uid": user_ids["alice@nebula.ai"]})
            alice_pid = db.session.execute(text("SELECT id FROM founder_profiles WHERE user_id=:uid"), {"uid": user_ids["alice@nebula.ai"]}).scalar()

            # Founder 2: David (GreenBlocks) - CleanTech
            db.session.execute(text("""
                INSERT INTO founder_profiles 
                (user_id, company_name, tagline, location, founding_year, stage, sector, business_model, 
                 fundraising_status, raise_target, actively_raising, team_size, product_stage, profile_completion)
                VALUES 
                (:uid, 'GreenBlocks', 'Sustainable construction materials', 'Austin, TX', 
                 2022, 'series-a', 'CleanTech', 'B2B', 'preparing', 5000000, 0, 15, 'Live', 75)
            """), {"uid": user_ids["david@greenblocks.io"]})

            # Founder 3: Sarah (MedTech) - Health
            db.session.execute(text("""
                INSERT INTO founder_profiles 
                (user_id, company_name, tagline, location, founding_year, stage, sector, business_model, 
                 fundraising_status, raise_target, actively_raising, team_size, product_stage, profile_completion)
                VALUES 
                (:uid, 'MediFlow', 'Streamlining patient intake', 'Boston, MA', 
                 2024, 'pre-seed', 'HealthTech', 'SaaS', 'raising', 500000, 1, 3, 'MVP', 85)
            """), {"uid": user_ids["sarah@medtech.co"]})
            sarah_pid = db.session.execute(text("SELECT id FROM founder_profiles WHERE user_id=:uid"), {"uid": user_ids["sarah@medtech.co"]}).scalar()

            db.session.commit()

            # ---------------------------------------------------------
            # 3. CREATE INVESTOR PROFILES
            # ---------------------------------------------------------
            print("   Creating Investor Profiles...")

            # Investor 1: Bob (Apex VC) - AI Focus
            db.session.execute(text("""
                INSERT INTO investor_profiles 
                (user_id, fund_name, fund_size, typical_check_min, typical_check_max, 
                 investment_stage, sector_focus, geography_focus, accredited, verification_status, activity_status)
                VALUES 
                (:uid, 'Apex Ventures', 50000000, 100000, 2000000, 
                 'seed', 'Artificial Intelligence, SaaS', 'USA', 1, 'verified', 'active')
            """), {"uid": user_ids["bob@apexvc.com"]})
            bob_iid = db.session.execute(text("SELECT id FROM investor_profiles WHERE user_id=:uid"), {"uid": user_ids["bob@apexvc.com"]}).scalar()

            # Investor 2: Jessica (Horizon Fund) - Generalist
            db.session.execute(text("""
                INSERT INTO investor_profiles 
                (user_id, fund_name, fund_size, typical_check_min, typical_check_max, 
                 investment_stage, sector_focus, geography_focus, accredited, verification_status, activity_status)
                VALUES 
                (:uid, 'Horizon Capital', 120000000, 500000, 5000000, 
                 'series-a', 'CleanTech, HealthTech', 'Global', 1, 'verified', 'active')
            """), {"uid": user_ids["jessica@horizonfund.com"]})
            jessica_iid = db.session.execute(text("SELECT id FROM investor_profiles WHERE user_id=:uid"), {"uid": user_ids["jessica@horizonfund.com"]}).scalar()

            db.session.commit()

            # ---------------------------------------------------------
            # 4. TRACTION METRICS (For Charts)
            # ---------------------------------------------------------
            print("   Adding Traction Metrics...")
            
            # Alice (Nebula AI) - Growing
            months = ["Aug 2025", "Sep 2025", "Oct 2025", "Nov 2025", "Dec 2025"]
            revenues = [10000, 12500, 16000, 22000, 28500]
            expenses = [15000, 16000, 18000, 20000, 22000] # Almost profitable
            
            for i, m in enumerate(months):
                db.session.execute(text("""
                    INSERT INTO traction_metrics (founder_id, month_label, revenue, expenses, active_users)
                    VALUES (:fid, :m, :rev, :exp, :users)
                """), {
                    "fid": alice_pid, "m": m, "rev": revenues[i], 
                    "exp": expenses[i], "users": (i+1)*500
                })

            db.session.commit()

            # ---------------------------------------------------------
            # 5. PITCH DECKS
            # ---------------------------------------------------------
            print("   Adding Pitch Decks...")
            
            analysis_sample = json.dumps({
                "score": 85,
                "summary": "Strong team and tech, but market sizing is vague.",
                "strengths": ["Technical Team", "Early Traction"],
                "weaknesses": ["Competition", "Burn Rate"]
            })

            db.session.execute(text("""
                INSERT INTO pitch_decks (founder_id, file_url, deck_score, version, analysis_json, is_published)
                VALUES (:fid, '/static/uploads/sample_deck.pdf', 85, 1, :json, 1)
            """), {"fid": alice_pid, "json": analysis_sample})

            db.session.commit()

            # ---------------------------------------------------------
            # 6. MATCHES & INTERACTIONS
            # ---------------------------------------------------------
            print("   Creating Matches...")

            # Match 1: Bob matches with Alice (High Score, Interested)
            db.session.execute(text("""
                INSERT INTO matches (founder_id, investor_id, match_score, status, ai_reason)
                VALUES (:fid, :iid, 92, 'interested', 'Strong Sector (AI) and Stage (Seed) fit.')
            """), {"fid": alice_pid, "iid": bob_iid})

            # Match 2: Jessica saved Sarah (HealthTech)
            db.session.execute(text("""
                INSERT INTO matches (founder_id, investor_id, match_score, status, ai_reason)
                VALUES (:fid, :iid, 78, 'saved', 'Good geo fit, but revenue slightly low.')
            """), {"fid": sarah_pid, "iid": jessica_iid})

            # Match 3: Bob passed on Sarah (Sector Mismatch)
            db.session.execute(text("""
                INSERT INTO matches (founder_id, investor_id, match_score, status, ai_reason)
                VALUES (:fid, :iid, 45, 'declined', 'Investor focuses on AI, Founder is HealthTech.')
            """), {"fid": sarah_pid, "iid": bob_iid})

            db.session.commit()

            # ---------------------------------------------------------
            # 7. CONVERSATIONS & MESSAGES
            # ---------------------------------------------------------
            print("   Creating Conversations...")

            # Conversation between Alice (Founder) and Bob (Investor)
            # 1. Create Conversation
            db.session.execute(text("""
                INSERT INTO conversations (founder_id, investor_id) VALUES (:fid, :iid)
            """), {"fid": alice_pid, "iid": bob_iid})
            
            convo_id = db.session.execute(text("SELECT id FROM conversations WHERE founder_id=:fid AND investor_id=:iid"), 
                                          {"fid": alice_pid, "iid": bob_iid}).scalar()

            # 2. Add Messages
            msgs = [
                (user_ids["bob@apexvc.com"], "Hi Alice, I saw your deck on Vaitej. Impressive traction."),
                (user_ids["alice@nebula.ai"], "Thanks Bob! We are growing 20% MoM. Would love to chat."),
                (user_ids["bob@apexvc.com"], "Are you free this Tuesday for a zoom?")
            ]

            for sender_id, msg in msgs:
                db.session.execute(text("""
                    INSERT INTO messages (conversation_id, sender_id, message, is_read)
                    VALUES (:cid, :sid, :msg, 0)
                """), {"cid": convo_id, "sid": sender_id, "msg": msg})

            db.session.commit()

            # ---------------------------------------------------------
            # 8. DUE DILIGENCE (Investor View)
            # ---------------------------------------------------------
            print("   Adding Due Diligence Data...")

            checklist_data = json.dumps({"team_vetted": True, "market_sized": True, "legal_check": False})
            db.session.execute(text("""
                INSERT INTO due_diligence (investor_id, founder_id, private_notes, checklist_json)
                VALUES (:iid, :fid, 'Really like the CTO. need to check IP ownership.', :chk)
            """), {"iid": bob_iid, "fid": alice_pid, "chk": checklist_data})
            
            db.session.commit()

            print("✅ Database seeded successfully!")
            print("   Founder Login: alice@nebula.ai / password123")
            print("   Investor Login: bob@apexvc.com / password123")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding database: {e}")
            sys.exit(1)

if __name__ == "__main__":
    run_seed()