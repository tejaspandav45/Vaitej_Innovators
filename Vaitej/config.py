import os
class Config():
    SECRET_KEY ="super-key"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:PASSWORD@localhost/vaitej_ventures"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini API key
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyAA7yvVK0YCnDpIOTfdgIabYQMv-P7hscY"
