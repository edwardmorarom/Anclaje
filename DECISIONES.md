# Decisiones

- El texto pegado define la base técnica y el HTML aporta el contexto académico; no se inventan entregas, fuentes ni resultados del estudiante.
- Python 3.12 es el entorno de validación; Python 3.14 instalado en el equipo no es compatible con todas las dependencias fijadas.
- El acceso a contraparte en la nube se habilita únicamente con ALLOW_COUNTERPART_CLOUD=true; ningún selector ni parámetro YAML puede saltarlo.
- Los tamaños de fragmento se expresan en caracteres y el solapamiento permanece dentro de la misma página; es una base simple y medible.
- TXT y MD usan página 1 o saltos de formulario explícitos; DOCX usa saltos de página explícitos o renderizados y no promete la paginación de Word.
- El modelo se descarga al reindexar; buscar y preguntar cargan únicamente pesos presentes en caché para impedir conexiones de embeddings durante la consulta.
- Se conserva deepseek-chat como valor solicitado y se permite DEEPSEEK_MODEL; la documentación consultada el 2026-10-05 anuncia su retirada y muestra deepseek-flash (https://api-docs.deepseek.com/updates/, https://api-docs.deepseek.com/api/create-chat-completion/). La disponibilidad real exige probar la API.
- La coincidencia de una cita textual verifica su existencia, no que todas las afirmaciones de la respuesta se deduzcan de ella; revision_manual es necesaria.
