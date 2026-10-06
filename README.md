# Anclaje

Base para «Nada sin fuente» (Estadística, USTA): recuperación local de documentos
en español, generación con DeepSeek, citas comprobadas por código y evaluación
con intervalos de Wilson. Los documentos, el índice y los resultados permanecen
fuera de Git. Desarrollo en `base-anclaje`.

## Instalación

Se recomienda **Python 3.12**. Las dependencias directas tienen versiones fijas
en `requirements.txt`. Python 3.14 queda fuera del rango compatible de esta base.

```text
python -m venv .venv
```

Activa el entorno: en PowerShell, `.venv\Scripts\Activate.ps1`; en Linux/macOS,
`source .venv/bin/activate`. Después:

```text
python -m pip install -r requirements.txt
python -m pytest
python -m anclaje humo
```

En este equipo ya está preparado `.venv` con Python 3.12. Sin activación puedes
ejecutar `.venv\Scripts\python.exe -m pytest` y los otros módulos de la misma forma.

`humo` revisa las dependencias y el protocolo, reconstruye un índice sintético
en `indice/humo/` y consulta con embeddings y cliente falsos. Comprueba que la
cita existe y que no se envía el fragmento privado. Además informa del estado
del índice configurado; si falta, indica que debes reindexar. No requiere clave,
documentos reales, descargas ni conexión. Los vectores falsos sirven para probar
el circuito, no para medir calidad semántica.

## Configuración y documentos

Copia `.env.example` a `.env` con tu editor y establece `DEEPSEEK_API_KEY` allí
o en el entorno. No compartas ni publiques el archivo. Las variables de entorno
tienen prioridad sobre `.env`. No se necesitan credenciales para las pruebas.

`deepseek-chat` es el valor por defecto solicitado. La documentación consultada
el 5 de octubre de 2026 anuncia la retirada de los nombres antiguos y muestra
`deepseek-flash` en sus ejemplos. Antes de la demo, comprueba el nombre disponible
y cambia `DEEPSEEK_MODEL` en tu `.env` si corresponde; no se validó una llamada
real. Véanse el [registro de cambios](https://api-docs.deepseek.com/updates/)
y la [API de chat](https://api-docs.deepseek.com/api/create-chat-completion/).

Pon tus archivos en `docs/publicos/` o `docs/contraparte/`. Se admiten PDF, TXT,
MD y DOCX, incluidos subdirectorios. La primera ingesta crea
`docs/PROCEDENCIA.md`: completa archivo relativo a `docs`, origen, fecha de
obtención, licencia/permiso y persona que verificó. Se advierte de los archivos
sin fila de procedencia. Ninguno de estos datos se incorpora a Git.

PDF usa páginas reales desde 1 y avisa de páginas sin texto: no incluye OCR.
TXT/MD usa página 1 o saltos de formulario `\f`. DOCX usa saltos explícitos o
renderizados; **exporta a PDF para citar la paginación visual de Word**.
No se siguen enlaces que cambien el origen de los documentos.

En `config.yaml` puedes cambiar modelo de embeddings, tamaño y solapamiento
en caracteres, `top_k`, umbral de similitud coseno, temperatura, modelo LLM,
tokens, tiempo de espera, rutas y protocolo. Si cambias el modelo de embeddings
o la fragmentación, reconstruye el índice. El sistema rechaza un modelo distinto
del usado al indexar y parámetros de fragmentación distintos. El umbral inicial
0,45 es una hipótesis que debes calibrar.

El modelo predeterminado es `BAAI/bge-m3`; alternativa:
`intfloat/multilingual-e5-base`, con prefijos `query: ` y `passage: `.
La primera reindexación puede descargar pesos de Hugging Face y tardar varios
minutos. Reserva espacio y memoria para esos pesos. El contenido se procesa
localmente. `buscar` y la recuperación de `preguntar` cargan únicamente pesos
ya presentes en caché: no descargan modelos ni usan una API de embeddings.

## Comandos

La app tiene un recorrido con **Anterior**, **Continuar** y acceso a cada paso
desde el menú lateral. Conserva los borradores al cambiar de pantalla.

| Paso | Qué haces |
| --- | --- |
| 1. Inicio | Compruebas documentos, índice, clave y banco. Puedes probar la API con una pregunta sintética. |
| 2. Fuentes | Seleccionas documentos del computador y los incorporas. |
| 3. Preparar | Pulsas Preparar documentos para construir el índice local. |
| 4. Consultar | Pruebas una pregunta conocida, revisas citas y compruebas la abstención. |
| 5. Evaluar | Agregas preguntas o importas un CSV, ejecutas A/C y descargas resultados. |
| 6. Memoria | Redactas los seis apartados y guardas o descargas el borrador. |

Puedes incorporar documentos desde el **paso Fuentes** de la app:

1. Pulsa **Elegir carpeta del computador** o pega la ruta. El selector nativo
   requiere Tk y se abre en el computador que ejecuta Streamlit. Puedes elegir
   archivos con el navegador si usas la app desde otro computador.
2. Pulsa **Revisar carpeta**. Activa **Incluir subcarpetas** para reconocer una
   estructura como `II/edward`, `II/Harold` y `II/natalia`.
3. Revisa el tratamiento sugerido y selecciona los documentos. `Edward → C`,
   `Harold → A`, `Natalia → B`; los nombres se reconocen sin distinguir mayúsculas.
4. Pulsa **Importar selección**. Se conservan originales y nombres, se copian
   solo los documentos seleccionados y se registra su procedencia. Si un nombre
   ya existe con contenido distinto, la copia nueva recibe un sufijo; repetir
   el mismo archivo no duplica su contenido en ese grupo.
5. Pulsa **Continuar a preparar** y **Preparar documentos**. La app prepara los embeddings
   localmente y vuelve a habilitar las consultas. Este estado pendiente se
   conserva al recargar la app. El CLI `reindexar` también actualiza ese estado.

La importación C va a `docs/publicos/` o `docs/contraparte/`, según la privacidad
seleccionada. A y B se conservan bajo `resultados/evidencias/A/` y
`resultados/evidencias/B/`: son evidencias del experimento y no forman parte del
contexto C. Los temporales Word `~$...`, archivos ocultos y formatos CSV/XLSX se
omiten del corpus. La app no determina automáticamente si un archivo es público.

El paso **Consultar** ofrece C y A; A envía exclusivamente la pregunta al
LLM. B se realiza en la herramienta bibliográfica externa elegida. La asignación
por integrante organiza el trabajo: para comparar tratamientos deben repetir
la misma pregunta en A, B y C.

El paso **Evaluar** permite agregar preguntas conocidas y guardarlas en
`eval/banco.csv`, o importar un CSV existente validando su formato antes de
reemplazarlo. Muestra la cantidad de preguntas y las que están fuera del corpus.
Puedes probar el circuito con cliente falso o ejecutar A/C con la API real.
En demo el banco se guarda por separado bajo `resultados/humo/`.

El paso **Memoria** reproduce los seis apartados de la imagen del enunciado:
Diagnóstico; Experimento y decisión; El sistema; Evaluación; Qué corrigieron de
su propio anteproyecto; Declaración de uso de IA. Permite editar, guardar el
borrador local y descargar Markdown. No completa resultados ni afirmaciones:
debes aportar tus evidencias y verificar la extensión final de 2 a 4 páginas.
Los borradores se guardan en `resultados/memoria/`, fuera de Git.

El diagnóstico actualizado y los pendientes están en [PENDIENTES.md](PENDIENTES.md).

```text
python -m anclaje reindexar
python -m anclaje buscar "frase del anteproyecto"
python -m anclaje buscar "frase" --origen contraparte
python -m anclaje preguntar "¿Qué dicen las fuentes sobre la media?"
python -m anclaje preguntar "¿Qué dicen las fuentes?" --json
python -m anclaje preguntar "¿Qué dicen las fuentes?" --falso
python -m anclaje evaluar eval/banco.csv
python -m anclaje evaluar eval/banco.csv --falso
python -m anclaje barrido eval/banco.csv
python -m anclaje humo
streamlit run app.py
```

Para otra configuración: `python -m anclaje --config otra.yaml preguntar "..."`.
Las rutas de configuración se resuelven respecto a ese archivo. Para Streamlit
puedes establecer `ANCLAJE_CONFIG` con su ruta. Reinicia Streamlit después de
cambiar `.env` o sus variables; los recursos se reutilizan dentro del proceso.

La app reutiliza el índice persistente y carga los embeddings al consultar.
Muestra citas verificadas/no verificadas, soporte, fragmentos y tiempo de
preparación. Para practicar sin clave ni pesos reales:

```text
streamlit run app.py -- --demo
```

En ese modo usa datos sintéticos y clientes falsos en un índice independiente.
Prueba «media aritmética suma valores número observaciones». La demostración
sintética está identificada en pantalla y no sustituye la demo con tu corpus.

`reindexar` reemplaza la colección activa después de calcular los embeddings;
ejecútalo sin consultas concurrentes. Si se interrumpe durante la escritura,
el índice queda marcado incompleto y debes repetir el comando. No borra las
carpetas ni modifica los documentos. Evita otros procesos de reindexación.

## Privacidad

Solo `publicos` se envía a DeepSeek por defecto. `buscar` consulta ambos
orígenes localmente y no llama a ningún LLM. Para enviar contraparte se necesitan
**autorización escrita** y `ALLOW_COUNTERPART_CLOUD=true`, además de seleccionar
`--origen contraparte` o `--origen ambos`. El selector de la app no habilita
el permiso. Cada ejecución con el permiso activo muestra una advertencia.
La evaluación bloquea bancos identificados como contraparte antes de llamar
al tratamiento A. No copies información privada dentro de preguntas de un banco
público: el texto de la pregunta también se envía al proveedor.

Chroma y sus registros son locales, con telemetría anónima desactivada. La
generación real envía pregunta, fragmentos seleccionados y sus metadatos a
DeepSeek. Protege también los archivos locales: `.gitignore` no cifra los datos.

## Citas, abstención y límites

El protocolo `protocolo/v1.md` pide un objeto JSON con `respuesta`, `abstencion`
y `citas`. Para cambiarlo crea `v2.md` y actualiza la ruta; conserva v1.
Se usa [JSON mode de DeepSeek](https://api-docs.deepseek.com/guides/json_mode/).

Cada cita debe coincidir con documento y página recuperados, y su texto debe
aparecer en un fragmento enviado, normalizando espacios, mayúsculas y tildes.
Las inválidas aparecen como `no_verificada`. Si no hay fuentes sobre el umbral,
no se llama al LLM. Si no hay ninguna cita válida, o la salida JSON es inválida,
la respuesta se convierte en «No está en las fuentes.».

La verificación demuestra existencia del texto citado. **No demuestra que todas
las afirmaciones se deduzcan de él**: una respuesta puede mezclar una cita real
con una interpretación incorrecta. Revisa cifras, negaciones, unidades y
atribuciones manualmente. El sistema no incorpora nuevas referencias ni ejecuta
cálculos; un fallo de API se informa como error y no como abstención correcta.

## Evaluación

Copia el formato de `eval/banco_ejemplo.csv` a `eval/banco.csv` y reemplaza los
ejemplos con tu corpus. Los documentos de ejemplo no se distribuyen. Usa rutas
como `publicos/articulo.pdf`, página desde 1 y tipos `en_corpus` o
`fuera_de_corpus`. Las filas en corpus exigen respuesta conocida y ubicación.
Para la actividad completa prepara 15–20 preguntas, al menos tres fuera del corpus.

`evaluar` ejecuta A (sin fuentes) y C (anclado). B requiere una herramienta
bibliográfica externa y revisión del estudiante. Guarda respuestas y métricas
en `resultados/`, con parámetros y huella del protocolo para identificar la
ejecución. Deja `revision_manual` vacía para tu clasificación; no usa un LLM juez.
`--falso` identifica sus resultados como sintéticos y solo valida el recorrido.

| Métrica | Denominador |
| --- | --- |
| hit@k, C | Preguntas válidas en corpus; documento y página presentes en top_k, antes del umbral |
| Cita verificada | Todas las respuestas válidas de cada tratamiento |
| Abstención correcta fuera | Preguntas válidas fuera del corpus |
| Invención fuera | Preguntas válidas fuera del corpus; respuesta sin abstención |

Cada proporción incluye aciertos, n e IC95% Wilson. En A, hit@k no aplica
(n=0); no hay citas verificadas porque no recibió fragmentos. Con n=0 la
proporción queda vacía. Los errores de API/JSON se guardan y se reportan como
exclusiones; compara tasas de error además de las proporciones. El CLI devuelve
código 2 si hubo errores. «Invención fuera» es una definición operativa de
respuesta fuera del corpus, no una comprobación universal de falsedad.

`barrido` compara los tamaños, top_k y modelos indicados en `sweep` sin llamar
al LLM. Indexa ambos orígenes en colecciones locales bajo `indice/barridos/`
y conserva el índice activo. Reporta hit@k con Wilson sobre las mismas preguntas
en corpus. Esa recuperación local de ambos orígenes difiere del filtro público
por defecto de la generación; usa un banco público al comparar ese escenario.
No se toma la respuesta conocida como juez automático de la generación.

El tiempo reproducible de servidor y primera pantalla sintética se mide con
`python scripts/medir_arranque.py`. La carga inicial de pesos y las consultas
reales deben medirse aparte sobre tu corpus.

La base técnica no reemplaza inventarios de fallos, clasificación bibliográfica
A/B/C, gestor de referencias, trazabilidad del anteproyecto, auditoría cruzada,
autorización de la contraparte ni memoria académica. Completa esas entregas con
evidencia real. El uso de Codex para construir el código debe declararse.
