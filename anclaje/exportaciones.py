"""Salidas Unicode para Excel; el CSV siempre usa punto y coma y BOM UTF-8."""
import csv
import io
import math
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


def celda_segura(valor):
    if isinstance(valor, str) and valor.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + valor
    return valor


def csv_bytes(filas, campos=None):
    filas = list(filas)
    campos = campos or list(dict.fromkeys(k for fila in filas for k in fila))
    salida = io.StringIO(newline='')
    escritor = csv.DictWriter(salida, fieldnames=campos, delimiter=';', extrasaction='ignore')
    escritor.writeheader()
    for fila in filas:
        escritor.writerow({k: celda_segura(v) for k, v in fila.items()})
    return salida.getvalue().encode('utf-8-sig')


def xlsx_bytes(filas, campos=None):
    """Libro con cadenas explícitas: no depende de la codificación regional de Excel."""
    filas = list(filas)
    campos = campos or list(dict.fromkeys(k for fila in filas for k in fila))

    def columna(numero):
        texto = ''
        while numero:
            numero, resto = divmod(numero - 1, 26)
            texto = chr(65 + resto) + texto
        return texto

    datos = []
    for numero, fila in enumerate([campos, *[[f.get(c, '') for c in campos] for f in filas]], 1):
        celdas = []
        for posicion, valor in enumerate(fila, 1):
            texto = '' if valor is None else str(valor)
            texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', texto)
            if len(texto) > 32767:
                raise ValueError('Una celda supera el límite de Excel; conserva el contenido completo en CSV/JSON.')
            ref = f'{columna(posicion)}{numero}'
            if isinstance(valor, bool):
                celdas.append(f'<c r="{ref}" t="b"><v>{int(valor)}</v></c>')
            elif isinstance(valor, (int, float)) and math.isfinite(valor) and (not isinstance(valor, int) or abs(valor) < 10**15):
                celdas.append(f'<c r="{ref}" t="n"><v>{valor}</v></c>')
            else:
                celdas.append(f'<c r="{ref}" t="inlineStr" s="{1 if numero == 1 else 0}"><is><t xml:space="preserve">{escape(texto)}</t></is></c>')
        datos.append(f'<row r="{numero}">{"".join(celdas)}</row>')
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    hoja = f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="{max(1,len(campos))}" width="36" customWidth="1"/></cols><sheetData>{"".join(datos)}</sheetData></worksheet>'
    partes = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Resultados" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': hoja,
        'xl/styles.xml': f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf fontId="1" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
    }
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as libro:
        for nombre, texto in partes.items():
            libro.writestr(nombre, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + texto)
    return salida.getvalue()


def guardar_tabla(path, filas, campos=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(csv_bytes(filas, campos))
    path.with_suffix('.xlsx').write_bytes(xlsx_bytes(filas, campos))


def avisos_unicode(fila):
    textos = [v for v in fila.values() if isinstance(v, str)]
    if any('\ufffd' in v for v in textos):
        return 'El texto contiene caracteres de reemplazo: revisar el original; no se pueden recuperar por conjetura.'
    if any(re.search(r'Ã[\x80-\xbf]|Â[\x80-\xbf]|â€', v) for v in textos):
        return 'Posible texto mal decodificado en el origen; contrastar con el documento original.'
    return ''
