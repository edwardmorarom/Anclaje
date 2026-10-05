# Informe de construcción — 5 de octubre de 2026

## Qué quedó hecho

Base funcional en `base-anclaje`, con commits separados para configuración,
ingesta/índice, respuesta, comandos/app, evaluación y validación/documentación.
Se preservó el README inicial como descripción ampliada y no se modificó main.

- Ingesta PDF/TXT/MD/DOCX, ubicación por página, avisos de páginas sin texto y
  plantilla local de procedencia. Fragmentación sin cruzar páginas.
- Embeddings locales BGE-M3/E5 con carga perezosa y prefijos E5. Consulta solo
  desde caché; la descarga de pesos corresponde a la reindexación.
- Chroma persistente con filtro por origen, reconstrucción de colección y
  comprobación de modelo/fragmentación. Telemetría anónima desactivada.
- Cliente DeepSeek con SDK OpenAI, JSON mode, configuración por entorno,
  protocolo v1, citas comprobadas y abstención fija. Errores de API sanitizados.
- CLI `reindexar`, `buscar`, `preguntar`, `evaluar`, `barrido`, `humo`.
  App Streamlit con selector de origen, citas, soporte y tiempos.
- A/C, hit@k, citas verificadas, abstención e invención fuera del corpus, Wilson
  al 95 %, CSV para revisión manual y barrido local sin reemplazar el índice activo.
- Modo de demostración sintético separado, documentación en español y decisiones.
- 53 pruebas con sockets bloqueados, credenciales retiradas y clientes/vectores
  falsos. Los PDF/DOCX se generan durante las pruebas, fuera del historial.

## Qué se comprobó

Entorno local: Windows, Python 3.12.14 en `.venv`; el Python global es 3.14.3.
Se instalaron las versiones directas fijadas en `requirements.txt`.

```text
.venv\Scripts\python.exe -m pytest
53 passed, 5 warnings in 6.78s
```

Los cinco avisos proceden de tipos internos SWIG de PyMuPDF; no son fallos de
las pruebas. La suite cubre privacidad, abstención, citas reales/inventadas y
páginas equivocadas, persistencia/reconstrucción, Wilson, evaluación, barrido,
recorrido de CLI y consulta/bloqueo de contraparte en Streamlit.

`python -m anclaje humo` pasó con cita verificada y sin datos de contraparte en
el cliente falso: **1,848 s** de trabajo interno en la ejecución medida.
Comprobadas las importaciones de sentence-transformers, OpenAI y Streamlit.
También pasaron compilación de módulos y `git diff --check`.

Arranque medido con `scripts/medir_arranque.py`, en procesos nuevos:

| Medición | Segundos |
| --- | ---: |
| Streamlit desde lanzamiento hasta HTTP health local | 2,192 |
| Proceso nuevo hasta primera pantalla sintética preparada | 4,445 |
| Preparación medida dentro del proceso de la pantalla | 3,693 |

Son dos mediciones separadas de servidor y pantalla, con datos sintéticos e
índice persistente independiente. Están por debajo de 60 s. **No son una medida
de carga de BGE-M3, consulta real a DeepSeek ni rendimiento con tu corpus.**
La app real aplaza la carga del modelo hasta la primera consulta.

Se revisaron los archivos rastreados y el historial existente antes del commit
de documentación: ningún documento/índice/resultado/banco privado rastreado y
ningún patrón de clave o llave privada detectado. `.env.example` solo contiene
el campo de clave vacío. La revisión por patrones no es una auditoría universal
de secretos; no se incorporaron credenciales ni documentos del usuario.

## Qué queda por probar y por qué

- **Llamada real a DeepSeek:** no se hizo; no se solicitó ni usó una clave.
  El SDK y su integración están implementados, pero no se confirmó servicio,
  saldo, nombre de modelo disponible ni una respuesta real.
- **Inferencia con BGE-M3/E5 y corpus real:** no se descargaron los pesos ni
  se proporcionó un corpus del proyecto. Las pruebas usan vectores falsos y
  validan prefijos/carga local con dobles. No hay mediciones de calidad reales.
- **Demo con tus fuentes:** requiere completar `.env`, agregar documentos,
  procedencia y banco conocido; luego reindexar y ejecutar la evaluación.
- **Otro sistema operativo:** el código usa pathlib y APIs portables, pero
  esta ejecución solo validó Windows y Python 3.12.
- **Entregas académicas:** el tratamiento B, gestor bibliográfico, inventario de
  fallos, trazabilidad del anteproyecto, clasificación de referencias, actas,
  auditoría y memoria requieren trabajo y evidencia del estudiante. No se
  inventaron esas entregas ni resultados de la actividad.

La existencia de una cita textual no prueba que la interpretación sea correcta
o que cubra todas las afirmaciones. Esa limitación está documentada y exige
llenar `revision_manual`.

## Comandos exactos para probar mañana

Desde `C:\Users\edwar\Desktop\Anclaje`, sin activar el entorno:

```text
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m anclaje humo
.venv\Scripts\python.exe -m streamlit run app.py -- --demo
```

En la demo sintética consulta:
`media aritmética suma valores número observaciones`.
Detén Streamlit con Ctrl+C. Para repetir la medición:

```text
.venv\Scripts\python.exe scripts/medir_arranque.py
```

Para la demo real, copia `.env.example` a `.env` con tu editor, configura la
clave y el modelo vigente, coloca tus fuentes en `docs/publicos/` y completa
procedencia. Mantén contraparte local salvo autorización escrita.

```text
.venv\Scripts\python.exe -m anclaje reindexar
.venv\Scripts\python.exe -m anclaje buscar "frase del anteproyecto"
.venv\Scripts\python.exe -m anclaje preguntar "pregunta cuya respuesta está en mis fuentes"
.venv\Scripts\python.exe -m streamlit run app.py
```

Prepara `eval/banco.csv` con tus ubicaciones reales siguiendo el ejemplo:

```text
.venv\Scripts\python.exe -m anclaje evaluar eval/banco.csv
.venv\Scripts\python.exe -m anclaje barrido eval/banco.csv
```

Revisa los CSV locales en `resultados/` y completa `revision_manual`.
Un `evaluar` con errores devuelve código 2 y los errores quedan registrados.

## Problemas encontrados

- El acceso inicial a GitHub estaba restringido por el entorno; la clonación
  autorizada permitió continuar en el repositorio solicitado.
- Crear ramas y commits requiere escritura en `.git`, protegida por el entorno;
  se ejecutaron las operaciones autorizadas en `base-anclaje`.
- Python 3.14 global no se usó para las dependencias: se preparó un entorno 3.12.
- Chroma rechaza repetir `hnsw:space` al modificar metadatos. Se conserva la
  distancia configurada y se actualiza el estado de integridad por separado.
- El script de medición necesitaba incluir la raíz del proyecto al ejecutar
  AppTest desde `scripts/`; se corrigió y se volvió a medir.
- La documentación de DeepSeek consultada anuncia la retirada de
  `deepseek-chat` y muestra `deepseek-flash` en ejemplos actuales. Se conserva
  el valor por defecto solicitado, configurable con `DEEPSEEK_MODEL`, y se
  advierte en README/DECISIONES. No se asumió disponibilidad de la API.

## Uso de IA

Codex se usó para implementar, revisar y probar esta base y redactar su
documentación técnica. No se usó un LLM juez, no se verificaron referencias
bibliográficas del proyecto ni se generaron resultados académicos reales.
Incluye este uso en tu declaración de la actividad y añade tus correcciones
y la evidencia obtenida al trabajar con el corpus.
