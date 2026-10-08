import csv
import io
import json
import zipfile
from dataclasses import replace
from xml.etree import ElementTree as ET

import pytest

from anclaje.evaluar import Pregunta, validar_banco, evaluar, guardar_csv, leer_banco, guardar_revision
from anclaje.exportaciones import csv_bytes, xlsx_bytes, avisos_unicode
from anclaje.llm import ClienteFalso
from anclaje.modelos import Fragmento
from anclaje.responder import interpretar


def test_csv_y_excel_preservan_acentos_multilinea_y_no_ejecutan_formulas():
    texto = '¿Dónde está la información? Bogotá, acción, niñez, pingüino: áéíóú ÁÉÍÓÚ ñ Ñ ü Ü.\nOtra línea; 20 %'
    filas = [{'pregunta': texto, 'respuesta': '=HIPERVINCULO("dato")', 'n': 15, 'proporcion': 0.8}]
    raw = csv_bytes(filas)
    assert raw.startswith(b'\xef\xbb\xbf')
    row = next(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), delimiter=';'))
    assert row['pregunta'] == texto
    assert row['respuesta'].startswith("'=")
    with zipfile.ZipFile(io.BytesIO(xlsx_bytes(filas))) as libro:
        for nombre in libro.namelist():
            ET.fromstring(libro.read(nombre))
        hoja = ET.fromstring(libro.read('xl/worksheets/sheet1.xml'))
        ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        valores = [t.text for t in hoja.findall('.//x:t', ns)]
        assert texto in valores and filas[0]['respuesta'] in valores
        assert not hoja.findall('.//x:f', ns)
        assert [c.find('x:v', ns).text for c in hoja.findall('.//x:c', ns) if c.attrib.get('t') == 'n'] == ['15', '0.8']


def test_cita_real_no_certifica_respaldo_y_rechaza_cifra_modificada():
    fuente = Fragmento('a', 'publicos/a.pdf', 1, 'publicos', 'La muestra incluyó 20 perros.', 0.9)
    cita = {'documento': fuente.documento, 'pagina': 1, 'cita_textual': fuente.texto}
    result = interpretar({'respuesta': 'La muestra incluyó 200 perros.', 'abstencion': False, 'citas': [cita]}, [fuente])
    assert result.abstencion and result.motivo == 'cifras_sin_respaldo'
    assert '200' in result.respuesta_propuesta
    result = interpretar({'respuesta': 'Se estudiaron 20 caninos.', 'abstencion': False, 'citas': [cita]}, [fuente])
    assert not result.abstencion and result.citas_verificadas
    assert result.como_dict()['sostenida_por_fragmento'] is None


def test_citas_mixtas_y_tildes_alteradas_no_pasan():
    fuente = Fragmento('a', 'publicos/a.pdf', 1, 'publicos', 'La población de Bogotá.', 0.9)
    cita = {'documento': fuente.documento, 'pagina': 1, 'cita_textual': fuente.texto}
    falsa = {**cita, 'documento': 'publicos/no_existe.pdf'}
    result = interpretar({'respuesta': fuente.texto, 'abstencion': False, 'citas': [cita, falsa]}, [fuente])
    assert result.abstencion and result.motivo == 'citas_invalidas'
    result = interpretar({'respuesta': fuente.texto, 'abstencion': False,
                          'citas': [{**cita, 'cita_textual': 'La poblacion de Bogota.'}]}, [fuente])
    assert result.abstencion


def test_banco_comprueba_existencia_pagina_y_cita_antes_de_la_api(config):
    q = Pregunta('¿Cuánto?', '20', 'publicos/a.txt', 9999, 'en_corpus')
    with pytest.raises(ValueError, match='inexistente'):
        validar_banco([q], config.docs_dir)
    archivo = config.docs_dir / q.documento
    archivo.parent.mkdir(parents=True)
    archivo.write_text('La muestra incluyó 20 perros.', encoding='utf-8')
    with pytest.raises(ValueError, match='Página'):
        validar_banco([q], config.docs_dir)
    with pytest.raises(ValueError, match='cita'):
        validar_banco([replace(q, pagina=1, cita_conocida='200 perros')], config.docs_dir)
    validar_banco([replace(q, pagina=1, cita_conocida='20 perros')], config.docs_dir)
    class SinAPI:
        def generar(self, mensajes):
            pytest.fail('La API no debe ejecutarse con un banco inválido.')
    path = config.root / 'banco.csv'
    guardar_csv(path, [vars(q)])
    with pytest.raises(ValueError, match='Página'):
        evaluar(path, config, None, SinAPI())


def test_entrega_no_acepta_banco_pequeno_ni_cliente_falso(config):
    q = Pregunta('¿Cuánto?', 'No está en las fuentes.', '', None, 'fuera_de_corpus')
    with pytest.raises(ValueError, match='15–20'):
        validar_banco([q], config.docs_dir, entrega=True)
    path = config.root / 'banco.csv'
    guardar_csv(path, [vars(q)])
    with pytest.raises(ValueError, match='falso'):
        evaluar(path, config, None, ClienteFalso(), entrega=True)


def test_entrega_exige_diez_contenidos_distintos_y_evidencia_completa(config):
    root = config.docs_dir / 'publicos'
    root.mkdir(parents=True)
    for n in range(10):
        (root / f'{n}.txt').write_text(f'La muestra incluyó 20 perros. Identificador de prueba {n}.', encoding='utf-8')
    questions = [Pregunta(f'Pregunta {n}', '20 perros', 'publicos/0.txt', 1, 'en_corpus',
                         '20 perros', 'ClavePrueba', 'Revisor', '2026-10-08') for n in range(12)]
    questions += [Pregunta(f'Fuera {n}', 'No está en las fuentes.', '', None, 'fuera_de_corpus') for n in range(3)]
    validar_banco(questions, config.docs_dir, entrega=True)
    with pytest.raises(ValueError, match='clave del gestor'):
        validar_banco([replace(questions[0], clave_gestor=''), *questions[1:]], config.docs_dir, entrega=True)
    for n in range(10):
        (root / f'{n}.txt').write_text('La muestra incluyó 20 perros.', encoding='utf-8')
    with pytest.raises(ValueError, match='10–40'):
        validar_banco(questions, config.docs_dir, entrega=True)


def test_revision_identificada_produce_fidelidad_sin_repetir_api(config):
    q = Pregunta('¿Cuánto?', '20 perros', 'publicos/a.txt', 1, 'en_corpus')
    path = config.root / 'banco.csv'
    guardar_csv(path, [vars(q)])
    class Indice:
        def consultar(self, *args):
            return [Fragmento('a', q.documento, 1, 'publicos', '20 perros', .9)]
    cliente = ClienteFalso()
    output, _ = evaluar(path, config, Indice(), cliente)
    with output.open(encoding='utf-8-sig', newline='') as archivo:
        filas = list(csv.DictReader(archivo, delimiter=';'))
    for fila in filas:
        fila['abstencion'] = fila['abstencion'] == 'True'
        fila['hit'] = fila['hit'] == 'True'
        fila['citas_textuales_validas'] = fila['citas_textuales_validas'] == 'True'
    llamadas = len(cliente.llamadas)
    assert all(r['sostenida_por_fragmento'] == 'Pendiente' for r in filas)
    filas[1]['sostenida_por_fragmento'] = 'Sí'
    with pytest.raises(ValueError, match='verificador'):
        guardar_revision(output, filas)
    filas[1].update(verificado_por='Revisor de prueba', fecha_verificacion='2026-10-08', observaciones_revision='Se abrió la página 1 y sostiene la cifra.')
    metricas = guardar_revision(output, filas)
    fidelidad = next(m for m in metricas if m['tratamiento'] == 'C' and m['metrica'] == 'fidelidad_revisada')
    assert fidelidad['n'] == 1 and fidelidad['proporcion'] == 1
    assert len(cliente.llamadas) == llamadas
    assert output.with_suffix('.xlsx').exists() and output.with_suffix('.md').exists()
    original = output.read_bytes()
    filas[1]['citas_textuales_validas'] = 'False'
    with pytest.raises(ValueError, match='sin citas válidas'):
        guardar_revision(output, filas)
    assert output.read_bytes() == original


def test_lectura_banco_acepta_coma_y_punto_y_coma_sin_perder_unicode(tmp_path):
    fila = vars(Pregunta('¿Dónde está Bogotá?', 'No está en las fuentes.', '', None, 'fuera_de_corpus'))
    for separador in [',', ';']:
        path = tmp_path / 'banco.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as salida:
            writer = csv.DictWriter(salida, fieldnames=list(fila), delimiter=separador)
            writer.writeheader(); writer.writerow(fila)
        assert leer_banco(path)[0].pregunta == fila['pregunta']


def test_texto_corrupto_se_advierte_sin_inventar_letras():
    assert avisos_unicode({'respuesta': 'Bogot\ufffd'})
    assert avisos_unicode({'respuesta': 'BogotÃ¡'})
    assert not avisos_unicode({'respuesta': 'Bogotá, niño, pingüino'})
