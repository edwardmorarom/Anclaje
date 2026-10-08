"""Crea una muestra identificada para comprobar tildes y ñ en Excel, sin API."""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anclaje.exportaciones import guardar_tabla


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destino', type=Path, required=True, help='Carpeta elegida para guardar la muestra.')
    args = parser.parse_args()
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = args.destino.resolve() / f'muestra_codificacion_{tag}.csv'
    guardar_tabla(path, [{
        'modalidad': 'MUESTRA DE CODIFICACIÓN; no es una evaluación del corpus',
        'pregunta': '¿Dónde está la información de Bogotá y la población canina?',
        'respuesta_obtenida': 'áéíóú ÁÉÍÓÚ ñ Ñ ü Ü — acción, niñez, pingüino.\nSegunda línea; misma celda.',
        'respuesta_conocida': 'Muestra técnica, sin respuesta académica.',
        'documento': '', 'pagina': '', 'tratamiento': 'Muestra',
        'sostenida_por_fragmento': 'No aplica',
    }])
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(f'Muestra guardada: {path}\nExcel: {path.with_suffix(".xlsx")}')
