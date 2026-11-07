# Avance de Harold — fase del agente (7 de noviembre de 2026)

Rama: `agente-harold` (sale de `base-anclaje`). Este archivo dice qué se hizo,
qué no y por dónde seguir. No sustituye a `PENDIENTES.md`.

## Qué se hizo

- Se clonó el repositorio y se trabajó sobre la rama `base-anclaje`, que es la
  que tiene la integración CIEX (`Extraccion/`, protocolo v2, `preparar_ciex.py`).
  `main` no la tiene todavía.
- Se creó `.venv` con Python 3.12 y se instalaron las dependencias fijadas,
  **excepto** `torch`, `transformers` y `sentence-transformers` (ver límites).
- Pruebas: la suite pasa salvo 2 pruebas, que fallan solo porque falta
  `sentence-transformers` en ese entorno:
  - `test_humo_cli_sin_red`
  - `test_cli_recorrido_completo_con_documentos_sinteticos`
  En un entorno con la instalación completa deberían pasar (el README reporta 86).
- Se ejecutó `scripts/preparar_ciex.py` sin API. Resultado: 8 documentos de
  Edward (corpus C), 5 de Harold (A), 6 de Natalia (B), 20 preguntas extraídas
  del banco, 3 propuestas como fuera de corpus. Quedó en `Extraccion/local/`
  (excluido de Git, así que no se sube).
- Se confirmó que **el corpus de Edward ya está en el repositorio**, en
  `Extraccion/materiales/edward/Fuentes_seleccionadas/` (8 PDF). No hace falta
  pedírselo aparte: basta con ejecutar `preparar_ciex.py`.

## Qué NO se hizo (queda pendiente)

1. **Instalar `torch`, `transformers` y `sentence-transformers`** y correr
   `python -m anclaje humo` y las 86 pruebas completas. Falló la descarga de
   los paquetes grandes en el entorno donde se trabajó.
2. **Índice real**: no se construyó (requiere descargar pesos de BGE-M3).
3. **Conexión con DeepSeek**: no se probó. No hay clave en este trabajo.
   Verificar el nombre del modelo (`deepseek-flash` según PENDIENTES.md).
4. **Consulta real con cita** sobre el corpus.
5. **Revisión del banco**: `Extraccion/local/evaluacion/banco_pendiente.csv`
   es un borrador extraído del DOCX; hay que revisar las respuestas conocidas,
   páginas y las 3 preguntas fuera de corpus antes de usarlo como `eval/banco.csv`.
6. Todo lo académico: A/B/C, trazabilidad, auditoría cruzada, memoria de
   2–4 páginas y declaración de uso de IA.

## Cómo continuar (en la máquina de quien siga)

```powershell
git fetch
git checkout agente-harold
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m anclaje humo
.venv\Scripts\python.exe scripts\preparar_ciex.py
copy .env.example .env      # y poner la propia DEEPSEEK_API_KEY
.venv\Scripts\python.exe -m streamlit run app.py
```

Luego, en la app: Inicio (probar conexión) → Fuentes → Preparar → Consultar.

## Notas

- Cada integrante necesita su propia clave de DeepSeek en su `.env`; no se comparte.
- Esta rama no modifica código; solo agrega este archivo.
