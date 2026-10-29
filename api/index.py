import sys
import os

# Add backend directory to Python path for Vercel serverless
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.main import app

# Vercel serverless function handler
handler = app
