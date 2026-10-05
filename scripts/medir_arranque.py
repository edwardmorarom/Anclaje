"""Mide servidor y primera pantalla en procesos nuevos, con datos sintéticos."""

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from time import perf_counter, sleep
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pantalla():
    start = perf_counter()
    os.environ["ANCLAJE_DEMO"] = "true"
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=55).run()
    if app.exception:
        raise RuntimeError("No se pudo preparar la pantalla de demostración.")
    print(json.dumps({"pantalla_segundos": perf_counter() - start}))


def medir():
    environment = os.environ.copy()
    environment["ANCLAJE_DEMO"] = "true"
    environment["ANONYMIZED_TELEMETRY"] = "False"
    environment.pop("DEEPSEEK_API_KEY", None)
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    start = perf_counter()
    process = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.headless=true", f"--server.port={port}",
        "--server.address=127.0.0.1", "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none", "--", "--demo",
    ], cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=hidden)
    try:
        while perf_counter() - start < 55:
            if process.poll() is not None:
                raise RuntimeError("El servidor salió antes de estar disponible.")
            try:
                with urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                sleep(0.1)
        else:
            raise RuntimeError("El servidor no estuvo disponible en 55 segundos.")
        server_seconds = perf_counter() - start
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    start = perf_counter()
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--pantalla"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60,
        creationflags=hidden,
    )
    if completed.returncode:
        raise RuntimeError("Falló la preparación de la pantalla con índice sintético.")
    screen = json.loads(completed.stdout)
    print(json.dumps({
        "servidor_hasta_health_segundos": round(server_seconds, 3),
        "pantalla_proceso_nuevo_segundos": round(perf_counter() - start, 3),
        "pantalla_app_segundos": round(screen["pantalla_segundos"], 3),
        "modo": "sintético; sin pesos reales ni API",
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    pantalla() if "--pantalla" in sys.argv else medir()
