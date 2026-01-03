import os
class Config():
    SECRET_KEY ="super-key"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:PASSWORD@localhost/vaitej_ventures"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Gemini API key
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyCpXZeMfm9lJOH3iKnVAupPxPHDTqGBh7c"
