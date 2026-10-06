# Estado y próximos pasos — 6 de octubre de 2026

La base técnica está implementada: ingesta, índice local, generación JSON,
verificación de citas, abstención, privacidad, interfaz guiada, evaluación,
barrido y memoria. El funcionamiento con dobles se comprueba con 86 pruebas
sin red ni clave. Eso no confirma el funcionamiento real sobre el corpus.

## Para consultar tus documentos

| Requisito | Comprobación local | Acción |
| --- | --- | --- |
| Entorno y dependencias | Instalados en .venv, Python 3.12 | Inicia Streamlit con ese entorno. |
| Clave de DeepSeek | Configurada; no se mostró ni modificó | En Inicio pulsa Probar conexión con DeepSeek. |
| Fuentes del proyecto | 0 documentos incorporados a docs | En Fuentes selecciona edward, revisa y pulsa Importar selección. |
| Índice real | No hay colección activa preparada | En Preparar pulsa Preparar documentos; la primera vez puede descargar pesos. |
| Consulta real con cita | Pendiente | En Consultar haz una pregunta conocida y revisa documento, página y soporte. |

La clave configurada no demuestra saldo, permisos o acceso real al servicio.
No se hizo una solicitud real a DeepSeek durante esta revisión. La prueba de
conexión de la app envía una pregunta sintética solo cuando el usuario la pide.

El modelo configurado localmente es `deepseek-v4-flash`. La documentación actual
lo acepta temporalmente como alias y recomienda `deepseek-flash`; no se cambió
tu .env. Consulta el [registro oficial de cambios](https://api-docs.deepseek.com/updates/).
La llamada del SDK desactiva thinking para que temperatura 0 tenga efecto,
según la [documentación de thinking](https://api-docs.deepseek.com/guides/thinking_mode/).

Para iniciar desde el repositorio:

```text
.venv\Scripts\python.exe -m streamlit run app.py
```

Sigue **Inicio → Fuentes → Preparar → Consultar**. No necesitas un banco para
una primera consulta. El estado del inicio se vuelve a calcular al usar la app;
los valores de esta tabla describen la revisión, no sustituyen ese estado vivo.

## Para medir resultados y entregar la actividad

- Crear el banco real de 15–20 preguntas, con al menos tres fuera del corpus.
  No existe aún `eval/banco.csv`; el paso Evaluar permite crearlo o importarlo.
- Ejecutar A/C con el mismo banco y revisar manualmente las respuestas.
  B se realiza en la herramienta bibliográfica externa; la app conserva evidencias.
- Comparar parámetros con `barrido` sobre el banco real. No se han medido BGE-M3/E5
  ni los tamaños de fragmento con tus preguntas.
- Completar procedencia, gestor de referencias y tabla de trazabilidad.
- Obtener el visto bueno del protocolo y las autorizaciones escritas pertinentes;
  la app no comprueba firmas ni acuerdos externos.
- Completar el experimento bibliográfico A/B/C: abrir referencias, clasificarlas,
  contar resultados y medir acuerdo entre integrantes. Las métricas de recuperación
  del banco no sustituyen esa revisión bibliográfica.
- Documentar un caso de fallo real, realizar auditoría cruzada, declarar correcciones
  del anteproyecto y terminar la memoria de 2–4 páginas con uso de IA declarado.
- Probar el arranque y la operación real antes de la sustentación; los tiempos
  medidos hasta ahora son con fuentes sintéticas y carga de pesos aplazada.

## Límites de implementación

- No hay OCR integrado: los PDF escaneados requieren extraer su texto antes.
- No hay buscador bibliográfico B integrado: se utiliza una herramienta externa.
- La comprobación de citas valida existencia del texto y ubicación; no demuestra
  que todas las afirmaciones se deduzcan del soporte. Se necesita revisión manual.
- La memoria se exporta a Markdown; el formato final y su extensión en páginas
  se revisan al preparar el documento de entrega.

Esos límites no impiden consultar PDFs con texto. Para operar ahora, los dos
pendientes principales son **importar las fuentes y preparar el índice**;
después debe verificarse la respuesta real de la API.
