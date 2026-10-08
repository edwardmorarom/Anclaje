# Trabajo CIEX

El estado del arte activo es `Estado_del_arte_Mercado_Publico_y_Mascoplan_solo_PDF.docx`.
El informe se audita contra los artículos; no se incorpora como fuente para que sus propias afirmaciones no se validen circularmente.

## Preparar los materiales en este computador

Desde la raíz del repositorio, en PowerShell:

```powershell
.venv\Scripts\python.exe scripts\preparar_ciex.py --base "C:\Users\edwar\Desktop\lll" --banco "C:\Users\edwar\Downloads\Preguntas_CIEX_en_cuadro (1).docx"
.venv\Scripts\python.exe -m streamlit run app.py
```

La preparación copia los originales, registra SHA-256 y extrae las preguntas sin llamar a ninguna API. Puedes repetirla con los mismos archivos. Rechaza originales modificados con destino ya ocupado para evitar sustituir versiones sin revisión. Conserva las modificaciones manuales del banco borrador y de procedencia.

La carpeta local, excluida de Git, queda así:

```text
Extraccion/local/
  corpus/publicos/Edward/       ocho PDF seleccionados: tratamiento C
  corpus/PROCEDENCIA.md         completar permisos, obtención y verificador
  evidencias/A/Harold/          cinco PDF: evidencias, no fuentes de C
  evidencias/B/Natalia/         seis PDF: evidencias, no fuentes de C
  informe_base/                estado del arte DOCX
  evaluacion/                  banco original y banco_pendiente.csv
  procedencia/                 README de fuentes de Edward
  inventario.json              archivos, responsables y hashes
```

`config.yaml` apunta únicamente al corpus nuevo; usa `indice/ciex` para aislarlo del índice anterior. No elimina el corpus ni el índice anteriores. La preparación no descarga modelos ni reconstruye el índice: se realiza en el paso Preparar de la app.

## Recorrido para ejecutar

1. En Inicio, elige dónde guardar resultados antes de ejecutar procesos. La preparación de entrada usa la carpeta local indicada arriba; no genera respuestas.
2. En Fuentes, revisa los ocho PDF C y completa su procedencia. No importes toda `Extraccion/local` al corpus: mezclaría informe, banco y evidencias A/B.
3. En Preparar, reconstruye el índice. Puede descargar pesos si no están disponibles. Ocho documentos todavía no alcanzan los diez exigidos por el enunciado: agrega al menos dos fuentes pertinentes y ajusta el banco antes de la evaluación final.
4. En Consultar → mesa de preguntas, carga el DOCX de `informe_base` y pulsa Guardar informe base. Para páginas estables, exporta el mismo informe a PDF desde Word y carga esa versión. Las páginas DOCX son aproximadas.
5. La mesa carga automáticamente las 20 preguntas preparadas si no tienes preguntas guardadas. Conserva las sesiones existentes. El CSV con punto y coma es un borrador de revisión, no un banco evaluable: faltan documentos y páginas, y varias preguntas tratan artículos excluidos de la selección C. Las preguntas 18–20 son abstenciones propuestas, pendientes de comprobar en el corpus definitivo.
6. Solo tras verificar respuestas y ubicaciones, crea el banco de evaluación con columnas `pregunta,respuesta_conocida,documento,pagina,tipo`, como `eval/banco_ejemplo.csv`. Admite coma o punto y coma en UTF-8. Para validar entrega agrega `cita_conocida,clave_gestor,verificado_por,fecha_verificacion`. Las exportaciones usan punto y coma y también ofrecen XLSX.
7. Ejecuta Evaluar A/C y revisa manualmente fidelidad, citas y abstenciones. B se realiza externamente. Cada pregunta bibliográfica del experimento debe ejecutarse en A, B y C, independientemente del responsable de las carpetas.

La clave se configura en `.env` como `DEEPSEEK_API_KEY`. El informe se analiza localmente para sugerir ubicaciones; las preguntas y fragmentos públicos recuperados sí se envían a DeepSeek al consultar. No se necesitan claves para preparar materiales o ejecutar pruebas.

## Límites conocidos

Una cita existente no demuestra por sí sola que toda la respuesta esté respaldada. La validación v2 rechaza citas mixtas y cifras sin respaldo textual; otras contradicciones requieren revisión documental. Consulta `SALIDA_RUBRICA.md` y la auditoría histórica `AUDITORIA_REQUISITOS.md`. No se certifica cumplimiento completo. La comparación semántica tampoco sustituye la revisión documental.

Se conservan los fallos de búsqueda en `FALLOS_BUSQUEDA.md`. DOI y URL se registran como declarados, sin afirmar que fueron abiertos o verificados en esta integración. No se descargan enlaces de la captura. El README de Edward contiene seis DOI y dos URL institucionales.

Git publica las instrucciones y el preparador, no los PDF, el informe, las preguntas, la clave ni los resultados locales. En otro computador hay que obtener legítimamente los originales y ejecutar la preparación con sus propias rutas.
