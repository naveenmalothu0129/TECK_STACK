"""Start the PA Review Copilot web app.

Run: python start_app.py      then open http://localhost:8000 (opens automatically)
"""
import webbrowser

from backend.api_server import run_server
from backend.settings import MODEL, use_claude

if __name__ == "__main__":
    server = run_server(8000)
    url = "http://localhost:8000"
    print(f"PA Review Copilot running at {url}")
    print(f"AI mode: {'Claude (' + MODEL + ')' if use_claude() else 'Offline rules (no API key found)'}")
    print("Press Ctrl+C to stop.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
