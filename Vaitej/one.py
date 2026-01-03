# import google.generativeai as genai

# # 🔑 Replace with your Gemini API key
# API_KEY = "AIzaSyAA7yvVK0YCnDpIOTfdgIabYQMv-P7hscY"

# try:
#     # Configure API key
#     genai.configure(api_key=API_KEY)

#     print("✅ API key is valid\n")
#     print("📦 Models available for this API key:\n")

#     for model in genai.list_models():
#         # Filter models that support text generation
#         if "generateContent" in model.supported_generation_methods:
#             print(f"- {model.name}")

# except Exception as e:
#     print("❌ API key is invalid or restricted")
#     print("Error:", e)
import shutil
import os

# Define paths (adjust relative path if running from a different folder)
source = "static/uploads/pitch_1_1767183944.pdf"
destination = "static/uploads/sample_deck.pdf"

if os.path.exists(source):
    shutil.copy(source, destination)
    print("✅ Created sample_deck.pdf successfully!")
else:
    print(f"❌ Could not find source file: {source}")