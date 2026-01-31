import sys
import os

# Add the parent directory to sys.path so we can import 'invoice'
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from invoice.app import app
from vercel_wsgi import make_handler

# This is the entry point for Vercel
handler = make_handler(app)
