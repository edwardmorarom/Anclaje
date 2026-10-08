"""Copia materiales CIEX localmente sin API, sin indexar y sin alterar originales."""
import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from docx import Document


def copiar(origen, destino):
    contenido = origen.read_bytes()
    if destino.exists() and destino.read_bytes() != contenido:
        raise ValueError(f"Destino distinto ya existente; conserva ambas versiones antes de continuar: {destino}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    return hashlib.sha256(contenido).hexdigest()


def preparar(base, banco, destino):
    informe = base / 'edward/Estado_del_arte_Mercado_Publico_y_Mascoplan_solo_PDF.docx'
    grupos = [('Edward', 'C', base / 'edward/Fuentes_seleccionadas'),
              ('Harold', 'A', base / 'Harold'), ('Natalia', 'B', base / 'natalia')]
    archivos = []
    for persona, tratamiento, carpeta in grupos:
        if not carpeta.is_dir():
            raise ValueError(f'No existe la carpeta: {carpeta}')
        for archivo in sorted(carpeta.glob('*.pdf')):
            relativo = (Path('corpus/publicos/Edward') if tratamiento == 'C'
                        else Path('evidencias') / tratamiento / persona) / archivo.name
            archivos.append((archivo, relativo, persona, tratamiento))
    for archivo in [informe, banco]:
        if not archivo.is_file():
            raise ValueError(f'No existe el documento: {archivo}')
    doc = Document(banco)
    preguntas = []
    for tabla in doc.tables:
        for fila in tabla.rows[1:]:
            celdas = [celda.text.strip() for celda in fila.cells]
            if len(celdas) != 4 or not celdas[0].isdigit():
                raise ValueError('El banco debe tener columnas número, fuente, pregunta y respuesta.')
            preguntas.append(dict(numero=int(celdas[0]), fuente_declarada=celdas[1],
                                  pregunta=celdas[2], respuesta_conocida=celdas[3],
                                  tipo_propuesto='fuera_de_corpus' if 'Vacío de Información' in celdas[1] else 'en_corpus',
                                  documento='', pagina='', estado='pendiente_verificacion'))
    if not preguntas:
        raise ValueError('El documento no contiene preguntas en tabla.')
    inventario = []
    for origen, relativo, persona, tratamiento in archivos:
        digest = copiar(origen, destino / relativo)
        inventario.append(dict(archivo=relativo.as_posix(), responsable=persona,
                               tratamiento=tratamiento, sha256=digest,
                               fecha_copia=date.today().isoformat(),
                               verificacion='pendiente; copia no acredita licencia ni fidelidad'))
    copiar(informe, destino / 'informe_base' / informe.name)
    copiar(banco, destino / 'evaluacion' / banco.name)
    copiar(base / 'edward/Fuentes_seleccionadas/README_fuentes.md', destino / 'procedencia/README_fuentes_Edward.md')
    # No generar banco.csv: las ubicaciones vacías no son aptas para evaluar.
    borrador = destino / 'evaluacion/banco_pendiente.csv'
    borrador.parent.mkdir(parents=True, exist_ok=True)
    if not borrador.exists():
        with borrador.open('w', encoding='utf-8-sig', newline='') as salida:
            escritor = csv.DictWriter(salida, fieldnames=list(preguntas[0]), delimiter=';')
            escritor.writeheader()
            escritor.writerows(preguntas)
    mesa = destino / 'evaluacion/mesa_inicial.json'
    if not mesa.exists():
        mesa.write_text(json.dumps([
            {'Pregunta': p['pregunta'], 'Respuesta conocida': p['respuesta_conocida'],
             'Página informe confirmada': ''} for p in preguntas
        ], ensure_ascii=False, indent=2), encoding='utf-8')
    (destino / 'inventario.json').write_text(json.dumps(inventario, ensure_ascii=False, indent=2), encoding='utf-8')
    procedencia = destino / 'corpus/PROCEDENCIA.md'
    if not procedencia.exists():
        filas = ['# Procedencia del corpus C', '',
                 'Copia local. Fecha de copia no equivale a fecha de obtención original.',
                 'Identificadores declarados en ../procedencia/README_fuentes_Edward.md (desde local/).', '',
                 '| archivo | origen | fecha de obtención | licencia o permiso | quién verificó |',
                 '| --- | --- | --- | --- | --- |']
        filas += [f"| publicos/Edward/{o.name} | publicos | Pendiente | Pendiente | Pendiente |"
                  for o, _, _, t in archivos if t == 'C']
        procedencia.parent.mkdir(parents=True, exist_ok=True)
        procedencia.write_text('\n'.join(filas) + '\n', encoding='utf-8')
    (destino / 'corpus/.indice_pendiente').touch()
    conteos = {persona: sum(r['responsable'] == persona for r in inventario)
               for persona, _, _ in grupos}
    print(json.dumps(dict(documentos=conteos, preguntas=len(preguntas),
                          fuera_propuestas=sum(p['tipo_propuesto'] == 'fuera_de_corpus' for p in preguntas),
                          destino=str(destino), indice='pendiente: preparar en la app'), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True, help='Carpeta que contiene edward, Harold y natalia.')
    parser.add_argument('--banco', type=Path, required=True, help='Banco DOCX con tabla de preguntas.')
    args = parser.parse_args()
    preparar(args.base.resolve(), args.banco.resolve(), Path(__file__).resolve().parents[1] / 'Extraccion/local')
