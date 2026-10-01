# Deckard — Gestor de Bancos de Ejercicios, Guías y Graduación

> *"Se ha reportado que algunos replicantes escapan..."* — Rick Deckard administra
> las pruebas: qué ejercicio va a cada guía, con qué dificultad taxonómica y cuánto tiempo insume.

`deckard` es la herramienta docente del ecosistema P1 para la **autoría atómica, curaduría pedagógica, verificación técnica y exportación multiformato** de ejercicios prácticos de C.

Cada ejercicio vive en una carpeta aislada con metadata YAML (`tema`, nivel de **Bloom 1-5**, minutos estimados, pistas progresivas), su solución modelo en C (`solucion.c`), su enunciado en Markdown y su suite de tests.

---

## 🎯 Alcance

### Qué cubre
- Autoría, catalogación y gestión de bancos de ejercicios prácticos de programación en C.
- Clasificación pedagógica según la taxonomía de Bloom (Recordar, Comprender, Aplicar, Analizar, Evaluar, Crear).
- Calibración y modelado de presupuestos de tiempo de resolución para estudiantes universitarios.
- Serialización y sincronización bidireccional entre metadatos YAML (`ejercicio.yaml`) y documentos Markdown.
- Composición de guías de trabajos prácticos estructuradas y balanceadas.

### Qué no cubre (Límites y Delegación)
- Compilación o ejecución de soluciones de alumnos (delegado a `daedalus` y `nostromo`).
- Corrección masiva de cohortes y base de datos de calificaciones (delegado a `dredd`).
- Generación de exámenes impresos OMR (delegado a `alucard`).

---

## 📋 Requisitos

### Requisitos de Sistema y Entorno
- Multiplataforma. Python >= 3.11.

### Dependencias Externas y Binarios
- **gcc** (o **daedalus**): Requerido para verificación y compilación de soluciones modelo en C (`deckard verify`, `lint`).
- **ripley**: Requerido para verificación estática/dinámica de reglas de cátedra y tests I/O (`deckard verify`).
- **typst**: Motor prioritario y recomendado para generación de PDFs de alta fidelidad (`deckard export`). *WeasyPrint se mantiene como fallback legacy.*
- **vasquez**: Motor de inyección de fallos para arneses de resiliencia (`deckard verify test-harness`).
- **dredd**: Orquestador y generador de testcases por fuzzing (`deckard verify fuzz`).

### Integración en el Ecosistema
- CLI `deckard` con soporte `--version` y `--json` en flujos de inspección y automatización.
- Diagnóstico del entorno mediante `deckard doctor`. Conexión directa con `ripley`, `dredd` y `vasquez`.

---

## ⚡ Instalación

```bash
# Instalación global editable con uv
uv tool install . --editable --force

# O en entorno virtual local
uv sync
uv run deckard --help
```

---

## 🚀 Inicio Rápido

```bash
# 1. Inicializar la estructura del banco y guías (crea banco/ejemplo-invertir)
deckard init

# 2. Crear un nuevo ejercicio
deckard new invertir-pares --titulo "Invertir pares" --tema arreglos --bloom 3 --minutos 25

# 3. Inspeccionar el banco y enunciados (soporta --json)
deckard bank list
deckard show invertir-pares -s -p

# 4. Verificar la solución modelo con Ripley (soporta --json)
deckard verify invertir-pares

# 5. Crear una especificación y componer una guía balanceada
deckard spec new parcial1.yaml --duracion 90 --margen 0.8 --temas "arreglos,punteros" --bloom-min 2 --bloom-max 4
deckard spec compose parcial1.yaml

# 6. Exportar la guía a PDF (Typst) y Markdown
deckard export guias/parcial1.yaml --type=pdf,md -o dist/
```

---

## 🧭 Mapa de Comandos de Deckard

### 1. Banco y Enunciados
* `deckard init`: Inicializa la estructura `banco/`, `guias/` y un ejercicio de ejemplo (`ejemplo-invertir`).
* `deckard new <id>`: Crea un nuevo ejercicio con esqueleto completo (`ejercicio.yaml`, `solucion.c`, `enunciado.md`, `tests/`).
* `deckard bank list`: Catálogo tabular del banco con filtros por tema, nivel de Bloom, estado de verificación y salida `--json`.
* `deckard show <id>`: Inspección en consola de enunciados, soluciones, pistas progresivas, tests y metadata (`-s`, `-p`, `--tests`, `--todos`, `--raw`).
* `deckard browse`: Navegador interactivo de ejercicios en consola.
* `deckard sync`: Sincronización bidireccional entre `ejercicio.yaml` y documentos Markdown.
* `deckard cache`: Inspección y actualización de la caché del banco de ejercicios.

### 2. Especificaciones Pedagógicas (`deckard spec`)
* `deckard spec new <archivo>`: Crea especificaciones de diseño curricular (`GuiaSpec`).
* `deckard spec list`: Lista specs con duración nominal, carga útil calculada, temas y rango Bloom.
* `deckard spec show <archivo>`: Detalle del spec y candidatos elegibles en el banco.
* `deckard spec validate <archivo>`: Diagnóstico de satisfactibilidad temática y temporal contra el banco actual.
* `deckard spec edit <archivo>`: Modificación de parámetros de la especificación por CLI.
* `deckard spec compose <archivo>`: Composición directa de la guía a partir del spec.

### 3. Guías de Trabajos Prácticos (`deckard guide`)
* `deckard guide list`: Lista guías compuestas en `guias/` con desglose de ejercicios y verificación.
* `deckard guide show <guia>`: Muestra ejercicios, carga horaria, temas y enunciados.
* `deckard guide compose <spec>`: Algoritmo knapsack de balanceo pedagógico.
* `deckard guide add <guia> <ejercicio>`: Incorpora un ejercicio y recalcula métricas.
* `deckard guide remove <guia> <ejercicio>`: Remueve un ejercicio y actualiza la guía.
* `deckard guide verify <guia>`: Verifica todas las soluciones modelo de la guía con Ripley.
* `deckard guide export <guia>`: Exporta la guía completa a PDF, Markdown o HTML.

### 4. Exportación Multiformato (`deckard export`)
* `deckard export <objetivo>`: Exporta ejercicios o guías a **PDF** (vía Typst oficial o WeasyPrint legacy), **Typst**, **Markdown** o **HTML** (`--type=pdf,md,html,typ` y `--json`).
* `deckard export templates init`: Copia plantillas por defecto (Typst, HTML, Markdown y CSS) a `./templates/` o global (`--global`).
* `deckard export templates list`: Lista plantillas descubiertas (locales, globales y built-in).

### 5. Verificación, Fuzzing y Arnés (`deckard verify`)
* `deckard verify [id]`: Verificación de reglas pedagógicas y compilación con `ripley check`. Admite comodines, `--all`, reporte de fallos (`--log-fallos`) y salida estructurada `--json`.
  > Los ejercicios que fallan se marcan automáticamente como no-verificados (`verificado: false`).
* `deckard verify fuzz [id]`: Fuzzing y endurecimiento de testcases con `dredd fuzz-gen` y libFuzzer.
* `deckard verify test-harness <id> <spec>`: Arnés de pruebas con inyección de fallos de memoria vía `vasquez inject`.

### 6. Diagnóstico, Auditoría y Calidad
* `deckard doctor`: Diagnóstico integral del estado de herramientas externas (gcc, typst, daedalus, ripley, git).
* `deckard stats`: Histogramas ASCII de distribución Bloom, carga horaria y resumen estadístico (`--json`).
* `deckard lint`: Verificación y auditoría de starter code y compilabilidad previa a exportar.
* `deckard deps` / `deckard graph`: Análisis y visualización de grafo de dependencias temáticas entre ejercicios.
* `deckard audit`: Detección de placeholders, omisiones y estado de completitud pedagógica del banco.
* `deckard languagetool`: Auditoría ortográfica y gramatical de consignas con LanguageTool.

### 7. Empaquetado y Distribución
* `deckard pack <objetivo>`: Empaqueta ejercicios/guías en archivos firmados `.ripkg` y genera starter repos para GitHub Classroom.
* `deckard unpack <paquete.ripkg>`: Desempaqueta y restaura ejercicios desde paquetes `.ripkg`.
* `deckard multiplex <spec>`: Generador de variantes combinatorias de TPs con asignación determinista por padrón/legajo.

### 8. Curaduría y Mejora con OpenCode (`deckard improve` / `ai`)
* `deckard improve clarity <id|banco|gift>`: Claridad y desambiguación con verbos operativos de Bloom.
* `deckard improve edge-cases <id|banco|gift>`: Especificación exhaustiva de casos borde, pre y postcondiciones.
* `deckard improve examples <id|banco|gift>`: Enriquecimiento con ejemplos de I/O y trazas de ejecución.
* `deckard improve hints <id|banco|gift>`: Generación de pistas pedagógicas progresivas de 3 niveles.
* `deckard improve bloom <id|banco|gift>`: Alineación estricta con la taxonomía de Bloom del ejercicio.
* `deckard improve testcases <id|banco|gift>`: Casos de prueba exhaustivos (borde, típicos, error).
* `deckard improve starter <id|banco|gift>`: Código esqueleto inicial (`starter_code`) y cabeceras Doxygen.
* `deckard improve all <id|banco|gift>`: Mejora holística e integral de la consigna en una única pasada.
* `deckard improve models [provider]`: Interroga a OpenCode por los modelos disponibles (`--raw` para lista plana).
  > Todos los subcomandos de mejora aceptan selección de modelo con `-m` / `--model` (ej: `-m "opencode-go/deepseek-v4-pro"`), `--prompt` (`-p`), `--prompt-file` (`-P`), `--apply` (`-a`), `--diff` y `--show-prompt`.

---

## 📖 Documentación Detallada

Para una guía paso a paso con todos los flujos pedagógicos, modelos de datos, personalización de plantillas y ejemplos de integración con Ripley, Dredd y Vasquez, consultá el [**Manual Integral de Uso (`MANUAL.md`)**](MANUAL.md).

---

## 🏗️ Integración en el Ecosistema

| Herramienta | Rol en el ecosistema |
| :--- | :--- |
| **deckard** | Banco de ejercicios, balanceo pedagógico (Bloom) y exportación multiformato. |
| **ripley** | Verificación estática/dinámica de soluciones modelo y sandbox docente. |
| **dredd** | Corrección masiva de entregas de alumnos, feedback y fuzzing de testcases. |
| **vasquez** | Inyección de fallos de memoria en tiempo de ejecución para arneses de prueba (`test-harness`). |
| **alucard** | Síntesis de exámenes, question banks (GIFT/Moodle) y tracing C con GCC. |
| **idkfa** | Generador de cuestionarios Moodle XML aleatorizados y anti-trampas. |
| **myst-tools** | Validador y gestor de enlaces/anclas para documentación MyST Markdown. |

*(Nota de diseño: Deckard no consume ni depende de `tyrell`, la síntesis y fuzzing de casos de prueba se delega enteramente a `dredd`).*

<!-- p1:referencia:inicio — generado por p1-tools/scripts/readme_generado.py: no editar a mano -->

## Referencia rápida

### Requisitos

- Python ≥ 3.11 y [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Programas del sistema: `gcc`, `typst`.

| Sistema | `gcc` | `typst` |
|:--|:--|:--|
| Debian / Ubuntu | `sudo apt install gcc` | binario de https://github.com/typst/typst/releases |
| Fedora | `sudo dnf install gcc` | binario de https://github.com/typst/typst/releases |
| Windows | incluido en el entorno de la cátedra (MSYS2 UCRT64) | `winget install --id Typst.Typst` |
| macOS | `xcode-select --install` (clang como `gcc`) | `brew install typst` |

### Comandos

| Comando | Descripción |
|:--|:--|
| `deckard init` | Inicializa la estructura del banco (banco/, guias/). |
| `deckard new` | Crea un ejercicio nuevo con esqueleto de metadata, funciones, enunciado.md y solución. |
| `deckard organize` | Reorganiza los ejercicios en carpetas según nivel de Bloom, tipo (funciones vs io) y/o tema. |
| `deckard show` | Muestra el enunciado y detalles de un ejercicio con control de secciones. |
| `deckard audit` | Audita la salud del banco: longitud y calidad de redacción del enunciado, y completitud de especificación. |
| `deckard compose` | Compone una guía balanceada por carga cognitiva y taxonomía de Bloom. |
| `deckard pack` | Empaqueta ejercicios o guías como .ripkg para Ripley y starter repos. |
| `deckard multiplex` | tp-multiplexer: Genera variantes combinatorias y asignación determinista por alumno. |
| `deckard stats` | Grafica la distribución de Bloom y tiempos acumulados con histogramas ASCII en terminal. |
| `deckard lint` | Verifica que los metadatos y el starter_code de los ejercicios compilen limpiamente antes de exportar. |
| `deckard duplicate` | Clona y versiona variantes de ejercicios conservando enunciados, solución y tests. |
| `deckard graph`, `deckard deps` | Detecta y grafica dependencias conceptuales y grafo de prerrequisitos entre ejercicios. |
| `deckard index`, `deckard cache` | Actualiza o reconstruye el índice SQLite (~/.cache/deckard/index.db) para acelerar búsquedas en bancos masivos. |
| `deckard unpack` | Extrae un bundle .deckard.tar.gz en el banco o directorio especificado. |
| `deckard doctor` | Verifica dependencias externas del sistema (GCC, Typst, Daedalus, Git). |
| `deckard browse` | Navega y visualiza interactivamente ejercicios del banco con Rich. |
| `deckard publish-classroom`, `deckard export-classroom` | Genera la estructura completa de un repositorio para GitHub Classroom (README, starter code, Makefile, CI). |
| `deckard export-notebook` | Exporta un ejercicio en formato interactivo Jupyter Notebook (.ipynb) con kernel C. |
| `deckard check-load` | Audita la carga horaria acumulada y el balance Bloom de una guía. |
| `deckard compose-variant`, `deckard variant` | Genera automáticamente una variante homóloga para recuperatorios respetando niveles Bloom. |
| `deckard sync` | Sincroniza el banco de ejercicios con un repositorio Git descentralizado. |
| `deckard audit-guide` | Audita la completitud y calidad técnica de todos los ejercicios de una guía. |
| `deckard languagetool`, `deckard grammar`, `deckard spellcheck` | Verifica y corrige ortografía y gramática en enunciados y pistas de ejercicios usando LanguageTool. |
| `deckard export-zip`, `deckard pack-zip` | Empaqueta un starter kit o guía completa en un archivo ZIP con clave de entrega (QoL 11). |
| `deckard audit-statements`, `deckard check-ambiguity` | Audita ambigüedades, términos vagos y calidad pedagógica en los enunciados (QoL 12). |
| `deckard diagram-ascii`, `deckard ascii-diagram`, `deckard diagram` | Genera diagramas y esquemas de estructuras de datos en formato ASCII, Mermaid o PlantUML para enunciados (QoL 14). |
| `deckard hints`, `deckard export-hints` | Exporta o genera pistas escalonadas (Hints) progresivas para un ejercicio (QoL 15). |
| `deckard init-tests` | Genera plantillas de tests unitarios embebidas en C utilizando p1_test o assert. |
| `deckard to-md` | Convierte un ejercicio estructurado en un único Markdown interactivo con YAML frontmatter. |
| `deckard from-md` | Importa un Markdown interactivo y reconstruye la estructura canónica de Deckard. |
| `deckard export-web` | Genera páginas Web estáticas o MyST Markdown con soluciones desplegables. |
| `deckard sanitizers`, `deckard audit-sanitizers` | Audita la solución modelo contra fugas de memoria (ASan) y comportamientos indefinidos (UBSan). |
| `deckard acsl-tests` | Sintetiza casos de prueba a partir de contratos formales ACSL (requires/ensures). |
| `deckard anki`, `deckard export-anki` | Exporta ejercicios y firmas a tarjetas mnemotécnicas Anki / Flashcards en formato TSV. |
| `deckard rubric` | Calibra pesos de evaluación y genera especificaciones de rúbricas para Dredd y Markdown. |
| `deckard init-io-files` | Inicializa plantillas y fixtures para ejercicios basados en flujos de archivos. |
| `deckard select-prereqs` | Selecciona y filtra ejercicios del banco cuyos prerrequisitos temáticos estén satisfechos. |
| `deckard check-terms` | Verifica la consistencia terminológica de consignas y detecta términos no válidos en C. |
| `deckard diagram-memory` | Genera esquemas de memoria Stack/Heap con convenciones Bishop para enunciados. |
| `deckard export-moodle` | Exporta ejercicios a formato Moodle XML para cuestionarios virtuales. |
| `deckard find-duplicates` | Detecta redundancias y ejercicios duplicados en el banco según similitud léxica y estructural. |
| `deckard lint-consigna` | Linter pedagógico de precondiciones y casos borde en consignas (NULL, vector vacío, archivos). |
| `deckard scaffold` | Genera plantillas de esqueletos de código con andamiaje pedagógico graduado. |
| `deckard bundle-offline` | Empaqueta guías y ejercicios en un bundle portable ZIP con visor web HTML/CSS 100% offline. |
| `deckard check-tone` | Audita ambigüedades lingüísticas, dobles negaciones y consistencia de tono en consignas. |
| `deckard checklist` | Genera listas de autoevaluación previas a la entrega en formato Markdown. |
| `deckard check-signatures` | Valida la consistencia de firmas de función entre el enunciado y la solución canónica. |
| `deckard license-manager` | Gestiona metadatos de autoría, licencias educativas y headers de copyright. |
| `deckard failure-hints` | Brinda orientación pedagógica y preguntas guía ante fallas en tests o ejecución. |
| `deckard bank` | Inspección del banco de ejercicios. |
| `deckard verify` | Verificación pedagógica (ripley check), fuzzing (dredd) y arnés de pruebas (vasquez inject). |
| `deckard tag` | Gestión y consulta de etiquetas (tags) en el banco. |
| `deckard export` | Exportación multiformato (PDF, Markdown, HTML) y gestión de plantillas. |
| `deckard guide` | Gestión, inspección y exportación de guías. |
| `deckard spec` | Gestión, validación y composición de especificaciones de guías (GuiaSpec). |
| `deckard improve` | Mejora y curaduría pedagógica de consignas y bancos de ejercicios con OpenCode. |

Ayuda de cada comando: `deckard <comando> -h`.

### Salida JSON

Con `--json`, estos comandos emiten el resultado como JSON por la salida estándar, para usarlo desde scripts, ripley o dredd: `deckard audit`, `deckard stats`, `deckard doctor`, `deckard languagetool`, `deckard grammar`, `deckard spellcheck`, `deckard audit-statements`, `deckard check-ambiguity`. El de `doctor --json` lleva `schema_version` y `ok`.

### Códigos de salida

| Código | Significado |
|:--|:--|
| `0` | Terminó bien (en `doctor`: está todo lo requerido). |
| `1` | El comando encontró problemas (hallazgos, pruebas que fallan, un umbral que no se alcanza) o un dato no se pudo usar (un archivo ilegible, un formato inválido). |
| `2` | Error de uso: comando, opción o argumento inválido. |

<!-- p1:referencia:fin -->
