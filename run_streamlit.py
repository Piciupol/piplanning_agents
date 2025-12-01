"""Launch script for Streamlit PI Planning UI."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    app_path = Path(__file__).parent.parent / "src" / "ui" / "streamlit_app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)])

