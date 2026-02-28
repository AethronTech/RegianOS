import sys
import subprocess
import os

def main():
    print("🚀 Regian OS Cockpit wordt opgestart via Streamlit...")
    
    # Pad naar het dashboard bestand
    dashboard_path = os.path.join("regian", "interface", "dashboard.py")
    
    # Start Streamlit als submodule.
    # Hiermee behoud je de flexibiliteit van de `dashboard.py` code
    # waar je in de sidebar kunt switchen tussen Ollama en Gemini.
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", dashboard_path,
             "--server.headless=true",
             "--server.address=0.0.0.0",
             "--server.enableCORS=false",
             "--server.enableXsrfProtection=false"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Fout bij het starten van Streamlit: {e}")
    except KeyboardInterrupt:
        print("\n👋 Regian OS Cockpit gestopt.")

if __name__ == "__main__":
    main()