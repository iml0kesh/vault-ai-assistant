"""
Entry point — run this to start the Vault Self-Service Portal.
Usage: python run.py
"""
from flask import Flask
from app.routes import register_routes
from config.settings import FLASK_PORT, FLASK_DEBUG

app = Flask(__name__, static_folder="static", template_folder="templates")
register_routes(app)

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print("  Vault Self-Service Portal")
    print(f"  Running on http://localhost:{FLASK_PORT}")
    print(f"{'='*50}\n")
    app.run(debug=FLASK_DEBUG, port=FLASK_PORT)
