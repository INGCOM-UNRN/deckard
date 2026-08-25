# Instrucciones para el Agente (deckard)

1. **Commits semánticos en español**: `<tipo>: <descripción breve en minúsculas>`
   (feat, fix, docs, style, refactor, test, chore).
2. **Dominio**: curaduría pedagógica de ejercicios (Bloom 1-5, carga horaria,
   pistas progresivas). El análisis técnico SIEMPRE se delega en `ripley`;
   la orquestación masiva en `dredd`. Deckard no compila por su cuenta salvo
   a través de esas herramientas.
3. Los metadatos de cada ejercicio viven en YAML versionado junto al código.
4. Tests pytest por unidad; `verify` nunca debe ejecutar código de alumno sin sandbox.
