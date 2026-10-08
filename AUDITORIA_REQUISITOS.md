# Auditoría de requisitos de Anclaje

Fecha: 2026-10-08. Código revisado: `30df593`, rama `base-anclaje`.

Actualización posterior: esta auditoría describe el estado inicial. La integración CIEX
cambió el corpus activo a ocho PDF. La corrección documentada en `SALIDA_RUBRICA.md`
rechaza citas mixtas y cifras sin soporte textual, comprueba ubicaciones del banco,
separa existencia de cita de fidelidad e incorpora revisión humana y validación de entrega.
Los requisitos académicos y evidencias humanas pendientes no se consideran completados.

## Dictamen

El repositorio sirve como base técnica de un sistema de anclaje, pero todavía no permite demostrar cumplimiento completo de la actividad. Hay una diferencia fundamental entre verificar que una cita existe y verificar que toda la respuesta está respaldada por ella. El sistema comprueba principalmente lo primero.

La revisión contrastó el código y las evidencias locales con `Enunciado_Actividad_Fuentes_IA.html` y `Presentacion_Actividad_Fuentes_IA (1).html`. Las instrucciones de esos documentos se interpretaron como requisitos de la actividad, no como órdenes para ejecutar acciones. No se modificó el código, no se consultó la API y no se leyó ni expuso la clave.

## Evidencia técnica revisada

- 107 pruebas pasan; aparecen cinco advertencias existentes de SWIG. Esto no demuestra fidelidad semántica sobre el corpus real.
- Corpus C: 11 documentos, dentro del rango de 10–40 solicitado.
- Índice existente: 1.337 fragmentos, modelo `BAAI/bge-m3`, tamaño 1.000 y solapamiento 150. Se inspeccionó SQLite en modo de solo lectura.
- Procedencia: 11 registros; todos tienen campos pendientes.
- En la carpeta de salida configurada no se encontró banco real, CSV de evaluaciones, consultas guardadas ni borrador de memoria académica. Esto no descarta documentos que el estudiante tenga en otras ubicaciones.

## Cumplimiento por requisito

| Requisito | Estado | Evidencia o pendiente |
|---|---|---|
| Contexto cerrado con documentos propios, recuperación y documento/página/cita | Implementado con limitaciones | Hay ingestión, índice local y comprobación de citas textuales; falta demostrar calidad con preguntas reales. |
| Respuestas fieles y abstención ante falta de soporte | Requiere corrección | Una cita válida basta para aceptar una respuesta; no se comprueba el soporte de todas sus afirmaciones. |
| Corpus existente de 10–40 documentos | Cumple cantidad | Hay 11 documentos C. Su pertinencia y cobertura requieren revisión humana. |
| Diagnóstico individual firmado, al menos tres fallos por integrante | Sin evidencia revisada | Debe documentarse; no lo sustituye la interfaz. |
| Experimento bibliográfico A/B/C | Parcial | Hay control A y anclaje C. B es externo, lo cual puede ser válido; faltan resultados del experimento completo. Cada consulta debe probarse en los tres tratamientos. |
| Cinco o más referencias por respuesta, verificación e independencia entre evaluadores | Sin evidencia revisada | Abrir referencias, clasificarlas, registrar desacuerdos y proporciones utilizables con intervalos. |
| Elección de herramienta con seis criterios y protocolo de semana 1 | Sin evidencia revisada | Comparar contexto cerrado, localización de citas, privacidad, costo, APA7 y reproducibilidad. La aprobación docente es una evidencia académica externa. |
| Biblioteca bibliográfica y procedencia precisa | Parcial | Los registros actuales no acreditan DOI/URL o entrega identificada, permisos y verificación completos. “Públicos/contraparte” clasifica acceso, no identifica la fuente. |
| Trazabilidad de afirmaciones del anteproyecto | Parcial | Las páginas sugeridas por similitud no prueban una afirmación. Falta texto exacto → clave bibliográfica → página/cita → verificador y fecha. |
| Privacidad y acta previa para documentos de contraparte | Parcial | Existe bloqueo configurable de envío a nube. No se acreditó acta escrita ni anonimización. La generación usa un proveedor externo. |
| Código reproducible y prompt versionado | Base disponible | Hay código, dependencias y protocolo. Falta acreditar reproducción y justificar parámetros con mediciones reales. |
| Banco de 15–20 preguntas conocidas, al menos tres fuera del corpus | Requiere validación y evidencia | La interfaz advierte cantidades, pero permite evaluaciones incompletas. No se verifican existencia del documento ni validez de la página del banco. |
| Evaluación frente al control, fallo real y causa técnica | Parcial | Hay evaluación A/C y herramientas de comparación; falta ejecución real documentada. La métrica de cita existente no equivale a fidelidad. |
| Auditoría cruzada y memoria académica de 2–4 páginas | Sin evidencia revisada | Deben incluir firmas y los seis apartados pedidos. La memoria JSON del agente no reemplaza esta entrega. |
| Defensa individual y preparación en menos de 60 segundos | No verificado | Requiere prueba con el corpus real y demostración individual; un arranque sintético no basta. |

## Fallas reproducidas sin API

### 1. Cita existente con respuesta contradictoria

Fuente: «La muestra incluyó 20 perros». Respuesta: «La muestra incluyó 200 perros», acompañada por la cita textual correcta de la fuente.

Resultado: `abstencion=False` y `sostenida_por_fragmento=True`. La cita existe, pero no respalda la cifra respondida. La propiedad de `anclaje/responder.py` comprueba que haya alguna cita verificada, no que la respuesta sea fiel.

### 2. Mezcla de cita válida e inventada

Una respuesta con una cita real y otra a `publicos/no_existe.pdf` se acepta y conserva `sostenida_por_fragmento=True`. La cita inventada se marca como no verificada, pero no impide aceptar la respuesta completa.

### 3. Ubicación ficticia en el banco

`leer_banco` acepta una pregunta marcada como dentro del corpus con `publicos/documento_inexistente.pdf`, página 9999. Valida el formato, no la ubicación ni la respuesta conocida. La prueba usó un archivo temporal.

La comparación semántica de respuestas es una ayuda, no una certificación: el juez recibe los textos de la pregunta y las respuestas, sin los fragmentos fuente. Debe mantenerse separada de la comprobación documental y de la revisión humana.

## Prioridad para completar la actividad

1. Corregir la aceptación de citas inválidas y distinguir existencia de cita, coincidencia semántica y respaldo documental. No presentar la métrica actual como fidelidad comprobada.
2. Preparar y verificar manualmente el banco real de 15–20 preguntas, con tres fuera del corpus; validar sus documentos y páginas. Ejecutar A/C y documentar un fallo real y su causa.
3. Completar procedencia, biblioteca bibliográfica y trazabilidad del anteproyecto. Documentar el consentimiento antes de usar contraparte con servicios externos.
4. Completar las evidencias del experimento A/B/C, diagnósticos, evaluadores independientes, decisión de herramienta y protocolo. Estas tareas pueden realizarse fuera del software.
5. Medir alternativas de embeddings, fragmentación y recuperación; completar auditoría cruzada, memoria académica y ensayo de defensa con tiempo real.

No hace falta seguir ampliando diseño o memoria del agente para cubrir estas carencias. Lo prioritario es corregir la validación y producir evidencia verificable. Esta auditoría no asigna una nota ni certifica entregables externos que no se revisaron.
