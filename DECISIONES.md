# Decisiones

- El texto pegado define la base técnica y el HTML aporta el contexto académico; no se inventan entregas, fuentes ni resultados del estudiante.
- Python 3.12 es el entorno de validación; Python 3.14 instalado en el equipo no es compatible con todas las dependencias fijadas.
- El acceso a contraparte en la nube se habilita únicamente con ALLOW_COUNTERPART_CLOUD=true; ningún selector ni parámetro YAML puede saltarlo.
- Los tamaños de fragmento se expresan en caracteres y el solapamiento permanece dentro de la misma página; es una base simple y medible.
- TXT y MD usan página 1 o saltos de formulario explícitos; DOCX usa saltos de página explícitos o renderizados y no promete la paginación de Word.
- El modelo se descarga al reindexar; buscar y preguntar cargan únicamente pesos presentes en caché para impedir conexiones de embeddings durante la consulta.
- Se conserva deepseek-chat como valor solicitado y se permite DEEPSEEK_MODEL; la documentación consultada el 2026-10-05 anuncia su retirada y muestra deepseek-flash (https://api-docs.deepseek.com/updates/, https://api-docs.deepseek.com/api/create-chat-completion/). La disponibilidad real exige probar la API.
- La coincidencia de una cita textual verifica su existencia, no que todas las afirmaciones de la respuesta se deduzcan de ella; revision_manual es necesaria.
- Los errores de API o JSON se guardan y se excluyen de las proporciones con su conteo explícito; no deben mejorar artificialmente la abstención correcta.
- El hit@k usa top_k antes del umbral y se mide solo en preguntas en corpus; en A no aplica porque no hay recuperación.
- El barrido es local sobre ambos orígenes y usa índices separados dentro de indice/barridos; conserva el índice activo y no envía fuentes a un LLM.
- Chroma conserva su configuración de distancia al actualizar metadatos sin repetir hnsw:space; repetirla provoca un error en la versión fijada.
- Los nombres de documento son rutas relativas a docs con el origen incluido; evitan confundir archivos homónimos públicos y privados.
- El arranque se mide en procesos nuevos con un índice sintético persistente; no se presenta como tiempo de carga de pesos reales ni de consulta a DeepSeek.
- La demo sintética usa indice/humo y se etiqueta de forma visible; no crea un corpus real ni sustituye las mediciones académicas.
