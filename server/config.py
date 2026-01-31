import os

PORT = int(os.environ.get("PORT", 8787))
BASE_URL = os.environ.get("BASE_URL", f"http://localhost:{PORT}")
