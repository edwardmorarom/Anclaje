# Salida de anclaje y revisión de fidelidad

## Qué se genera y dónde

La app usa la carpeta confirmada en Inicio. Los lotes se guardan en `agente/`;
las evaluaciones A/C y sus métricas se guardan en la raíz de esa salida.
La CLI usa `results_dir` de su configuración: revisa esa ruta antes de ejecutarla.

Cada evaluación genera:

- `evaluacion_<fecha>.csv`: respuestas y campos de revisión, separados por `;`, UTF-8 con BOM.
- `evaluacion_<fecha>.xlsx`: los mismos datos, con cadenas Unicode explícitas, sin depender de la codificación regional.
- `metricas_<fecha>.csv` y `.xlsx`: conteos, proporciones, denominadores y Wilson al 95 % por tratamiento.
- `evaluacion_<fecha>.md`: correspondencia con el enunciado y evidencias pendientes.
- `evaluacion_<fecha>_trazabilidad_pendiente.csv` y `.xlsx`: plantilla para afirmaciones del estado del arte. No se sobrescribe al guardar una revisión.

En los lotes también se guardan CSV, XLSX y memoria JSON. El informe base permanece
separado del corpus. Las páginas sugeridas no se convierten en páginas confirmadas.

## Campos exactos del banco solicitado

| Enunciado | Columna de evaluación |
| --- | --- |
| Pregunta | `pregunta` |
| Respuesta conocida | `respuesta_conocida` |
| Dónde está (documento, página) | `documento`, `pagina` |
| Tratamiento | `tratamiento` |
| Respuesta obtenida | `respuesta_obtenida` |
| ¿Sostenida por un fragmento real?: sí/no | `sostenida_por_fragmento`, completada por revisión humana |

Se agregan `cita_conocida`, `clave_gestor`, identidad y fecha de quien verificó
la respuesta conocida, las citas de la respuesta obtenida y los parámetros
del sistema. La revisión final necesita verificador, fecha y observación documental.
Para preguntas fuera del corpus, el respaldo es `No aplica`: se mide la abstención.

Las preguntas y respuestas no necesitan coincidir literalmente. El comparador
de la mesa evalúa significado; la revisión de fidelidad determina si la respuesta
completa se sostiene en el documento. Son comprobaciones distintas.

## Ensayo y entrega

En Evaluar puedes hacer un ensayo pequeño. Activa **Validar requisitos de entrega**
para exigir antes de consultar:

1. Entre 15 y 20 preguntas distintas, con al menos tres fuera del corpus.
2. Corpus de 10–40 documentos con contenido distinto; una copia repetida no completa el mínimo.
3. Documento existente y página con texto para cada pregunta en corpus.
4. Cita conocida presente en esa página, clave del gestor, verificador y fecha.
5. Cliente real: el modo falso no produce una evaluación de entrega.

Los ensayos reales también comprueban archivos y páginas. El modo sintético
se etiqueta explícitamente y no mide calidad real. Tener clave del gestor declarada
no acredita por sí solo que el artículo esté incorporado y verificado en ese gestor.

El banco acepta CSV con coma o punto y coma, codificado en UTF-8. La exportación
usa siempre punto y coma. Conserva respuesta conocida y ubicación aunque el sistema
recupere un documento equivocado: se necesitan ambas para medir el error.

## Fidelidad y fallos

`citas_textuales_validas` comprueba que todas las citas existan en sus documentos
y páginas. Ya no se presenta como fidelidad de la respuesta. El sistema rechaza
mezclas de citas reales e inventadas y cifras de respuesta ausentes de sus citas.
Esa guardia es conservadora: no valida cálculos, conversiones, alcance, causalidad
ni todas las contradicciones. La revisión humana sigue siendo necesaria.

En **Revisar fidelidad y documentar el caso de fallo**, decide Sí/No, escribe quién
abrió el documento, la fecha y el motivo. Guarda para recalcular sin llamar de nuevo
a la API. La métrica de fidelidad solo incluye filas revisadas; las pendientes no
se cuentan como aciertos ni como errores. Se informa el denominador efectivo.

Registra al menos un fallo real con `caso_fallo=Sí`, `causa_tecnica` y `evidencia_fallo`.
La respuesta propuesta rechazada se conserva para inspección, pero bloquearla
preventivamente no demuestra que la respuesta final haya fallado.

La plantilla de trazabilidad necesita la afirmación textual de tu informe, la clave
del gestor, ubicación/cita y verificación independiente. La revisión de una pregunta
no se copia como aprobación automática de esa afirmación.

## Tildes, ñ y Excel

El texto original se conserva en CSV, XLSX y JSON. No se eliminan tildes para exportar
o para validar citas literales. Si Excel interpreta mal un CSV, usa **Datos → Desde
texto/CSV**, origen **UTF-8**, delimitador **punto y coma**, o abre directamente el XLSX.
Los textos multilínea y los puntos y comas dentro de una celda se conservan mediante
comillas CSV. Las celdas se protegen contra ejecución de fórmulas.

Si el texto ya contiene `�` o una secuencia de mala decodificación, se genera
`aviso_codificacion`. Se debe contrastar con el original: volver a guardar en UTF-8
no reconstruye letras perdidas. No se reparan por conjetura.

Puedes crear una muestra claramente identificada, sin llamadas a la API, indicando
primero dónde quieres guardarla:

```powershell
.venv\Scripts\python.exe scripts\verificar_exportacion.py --destino "C:\ruta\elegida"
```

## Qué no acredita esta salida

No certifica por sí sola la actividad completa. Sigue siendo necesario completar
el experimento bibliográfico A/B/C, procedencia y biblioteca reales, auditoría cruzada
firmada, memoria académica de 2–4 páginas, comparaciones de parámetros y defensa.
Las ocho fuentes seleccionadas actuales no permiten activar una entrega válida
de diez documentos; no se incorporan evidencias A/B automáticamente para completar el número.
