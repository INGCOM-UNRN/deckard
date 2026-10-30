# Manual Integral de Uso de Deckard

> **Deckard** — Gestor de Bancos de Ejercicios Prácticos, Especificaciones Pedagógicas, Guías de Trabajos Prácticos y Graduación (Programación 1).

---

## 1. Arquitectura y Modelo de Dominio

Deckard organiza el material práctico de cátedra en tres capas desacopladas:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. BANCO DE EJERCICIOS                          │
│  banco/<id>/ (ejercicio.yaml, solucion.c, enunciado.md, tests/)        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│               2. ESPECIFICACIONES PEDAGÓGICAS (GuiaSpec)                │
│  guias/<spec>.yaml (duracion_min, margen_carga, temas, bloom_min/max)  │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ deckard compose / deckard spec compose
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       3. GUÍAS COMPUESTAS (Guía)                       │
│  guias/<guia>.yaml (lista ordenada de IDs, minutos totales, Bloom)     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  deckard export  │      │  deckard verify  │      │   deckard pack   │
│  PDF / MD / HTML │      │ Ripley / Fuzzing │      │ .ripkg / Starter │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### Conceptos Fundamentales
1. **Ejercicio Atómico**: Unidad mínima indivisible. Contiene metadata YAML (`tema`, nivel de Bloom 1 a 5, duración estimada en minutos, pistas progresivas), solución modelo en C (`solucion.c`), enunciado en Markdown y suite de casos de prueba (`tests/`).
2. **`GuiaSpec` (Especificación Pedagógica)**: Declaración de requisitos y presupuesto cognitivo para una clase o evaluación. No contiene ejercicios concretos, sino las restricciones que alimentan el algoritmo knapsack.
3. **`Guía` (Guía Compuesta)**: Instancia concreta con una lista ordenada de ejercicios seleccionados del banco, con cómputo de carga horaria y desglose de niveles taxonómicos.

---

## 2. Inicialización y Gestión del Banco

### Inicializar el entorno
Crea la estructura base con carpetas `banco/`, `guias/` y un ejercicio de ejemplo:
```bash
deckard init
```

### Crear un nuevo ejercicio
Crea la carpeta en el banco con el esqueleto de `ejercicio.yaml`, `solucion.c`, `enunciado.md` y `tests/`:
```bash
deckard new invertir-vector \
    --titulo "Invertir un vector de enteros" \
    --tema arreglos \
    --bloom 3 \
    --minutos 25
```

### Inspección del Banco
```bash
# Listar todos los ejercicios con estado de verificación y métricas
deckard bank list

# Filtrar por tema, nivel de Bloom o patrón comodín
deckard bank list "punteros-*" --tema punteros --bloom 3

# Filtrar ejercicios pendientes de verificación
deckard bank list --pendientes
```

### Visualización granular de enunciados (`deckard show`)
Permite inspeccionar cualquier ejercicio en consola con resaltado de sintaxis y control de secciones:
```bash
# Ver solo el enunciado en Markdown
deckard show invertir-vector

# Ver enunciado + solución modelo de cátedra
deckard show invertir-vector -s

# Ver enunciado + pistas progresivas + tests
deckard show invertir-vector -p --tests

# Ver todas las secciones (enunciado, solución, pistas, tests, metadata)
deckard show invertir-vector --todos

# Emitir texto plano sin formato Rich (útil para pipes o scripts)
deckard show invertir-vector --todos --raw
```

---

## 3. Especificaciones Pedagógicas (`deckard spec`)

El módulo `spec` administra las declaraciones de intención pedagógica antes de resolver los ejercicios concretos.

### Subcomandos disponibles
```bash
# 1. Crear una nueva especificación
deckard spec new parcial1.yaml \
    --titulo "Primer Parcial P1" \
    --duracion 90 \
    --margen 0.8 \
    --temas "punteros,arreglos" \
    --bloom-min 2 \
    --bloom-max 4 \
    --max-ejercicios 5

# 2. Listar todas las especificaciones disponibles
deckard spec list

# 3. Inspeccionar el spec y ver el universo de candidatos elegibles en el banco
deckard spec show parcial1.yaml

# 4. Validar satisfactibilidad contra el banco actual
deckard spec validate parcial1.yaml

# 5. Modificar parámetros del spec sin editar el archivo YAML manualmente
deckard spec edit parcial1.yaml --duracion 120 --margen 0.75 --bloom-max 5

# 6. Ejecutar el balanceo y componer la guía a partir del spec
deckard spec compose parcial1.yaml
```

---

## 4. Gestión de Guías (`deckard guide`)

El módulo `guide` administra las guías compuestas listas para los estudiantes.

### Subcomandos disponibles
```bash
# 1. Listar todas las guías en guias/ con estado y porcentaje verificado
deckard guide list

# 2. Inspeccionar el detalle pedagógico y ejercicios de una guía
deckard guide show guia_punteros.yaml
deckard guide show guia_punteros.yaml --enunciados --soluciones

# 3. Componer una guía usando el algoritmo knapsack balanceado
deckard guide compose guias/guia_spec.yaml

# 4. Agregar o remover ejercicios de una guía existente (recalcula métricas)
deckard guide add guia_punteros.yaml matrices-dinamicas
deckard guide remove guia_punteros.yaml punteros-basico

# 5. Verificar todas las soluciones modelo de la guía con Ripley
deckard guide verify guia_punteros.yaml

# 6. Exportar la guía completa
deckard guide export guia_punteros.yaml --type=pdf,md -o dist/
```

---

## 5. Exportación Multiformato y Plantillas (`deckard export`)

El motor de exportación permite generar documentos listos para imprenta (PDF), plataformas web (HTML) o repositorios (Markdown).

### Opciones de Exportación (`--type` / `-t`)
Se unifican todos los formatos bajo la opción `--type`, permitiendo formatos únicos o múltiples separados por comas:

```bash
# Exportar ejercicio individual a PDF
deckard export invertir-vector -t pdf -o ejercicio.pdf

# Exportar a múltiples formatos en simultáneo
deckard export invertir-vector --type=pdf,md,html -o dist/

# Exportar con apéndice de soluciones y pistas
deckard export invertir-vector -s -p -t pdf -o ejercicio_resuelto.pdf

# Exportar una guía completa a Markdown y PDF
deckard export guias/guia_punteros.yaml --type=pdf,md -o dist/

# Exportación masiva por comodín
deckard export "arreglos/*" --type=pdf,md -o dist/
```

### Pipeline Markdown → HTML → PDF
Para garantizar compatibilidad con diagramas y extensiones de Markdown antes de renderizar con WeasyPrint:
```bash
deckard export invertir-vector -t pdf --pipeline-md -o salida.pdf
```

### Gestión de Plantillas (`deckard export templates`)
```bash
# Copiar plantillas por defecto a ./templates/ para personalizarlas
deckard export templates init

# Inicializar plantillas en la configuración global del usuario
deckard export templates init --global

# Forzar sobrescritura
deckard export templates init --force

# Listar todas las plantillas descubiertas (locales, globales y built-in)
deckard export templates list
```

#### Jerarquía de resolución de plantillas
1. Ruta explícita pasada mediante `--template` / `-T`.
2. Plantilla local en `./templates/<nombre>` o `<banco>/templates/<nombre>`.
3. Plantilla global de usuario en `~/.config/deckard/templates/<nombre>`.
4. Plantillas integradas built-in (`ejercicio.html`, `guia.html`, `ejercicio.md`, `guia.md`, `estilos.css`).

### Sitio MyST del banco (`deckard export myst`)

Genera desde el banco y las guías todo lo que publica el repositorio de enunciados; está pensado
para correr en el CI, así que nada de lo que escribe se versiona:

```bash
deckard export myst                      # banco/ y guias/ → sitio/, y reescribe el toc de myst.yml
deckard export myst --agrupar-unidades   # TOC por unidad en lugar de por tema
```

- `sitio/consignas/<tema>/<id>.md`: una página por ejercicio (plantilla `ejercicio.md`), con enlace a su paquete.
- `sitio/guias/<guia>.md`: una página por guía compuesta (las specs de `compose` no se publican).
- `sitio/index.md` y `sitio/grafo_tematico.md`: portada con métricas y grafo de prerrequisitos.
- `sitio/paquetes/<id>.ripkg`: un paquete por ejercicio, **sin** las pruebas de `tests/hidden/`.
- `sitio/paquetes/catalogo.json`: ejercicios (metadatos, página, paquete con su SHA-256) y guías, para herramientas.

Los títulos, unidades, prerrequisitos y rutas de los temas salen de `temas.yaml`, junto al banco
(`--temas` para otro). Un ejercicio con `publicar: false` queda en el banco pero fuera del sitio,
de los paquetes y del catálogo. Los ejercicios inválidos se informan y el comando termina con
error (salvo `--permitir-invalidos`). `sitio/` se borra en cada corrida, por eso no puede contener
al banco ni a las guías.

---

## 6. Verificación Técnica, Fuzzing y Arnés (`deckard verify`)

La verificación garantiza que todas las soluciones modelo del banco sean sintáctica, semántica y pedagógicamente válidas.

```
                  ┌─────────────────────────────────────┐
                  │           deckard verify            │
                  └──────────────────┬──────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│    ripley check      │  │     verify fuzz      │  │ verify test-harness  │
│ Reglas P1 (0xXXXXh)  │  │   dredd fuzz-gen     │  │   ripley harness     │
│ GCC / Linker / ASan  │  │ libFuzzer / Sanitiz. │  │ Inyección de malloc  │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

### 1. Verificación Pedagógica con Ripley (`deckard verify`)
```bash
# Verificar un ejercicio puntual
deckard verify invertir-vector

# Verificar ejercicios por comodín o todo el banco con barra de progreso en vivo
deckard verify "arreglos/*"
deckard verify --all

# Filtrar solo ejercicios pendientes
deckard verify --all --pendientes

# Generar reporte estructurado en Markdown de los ejercicios que fallen
deckard verify --all --log-fallos dist/fallos_verificacion.md
```
> **Auto-desverificación:** Si un ejercicio falla la verificación o presenta errores de compilación, Deckard actualiza automáticamente su `ejercicio.yaml` a `verificado: false`.

#### Coherencia de la rúbrica (`deckard verify --rubric`)
Revisa la `rubrica:` de cada ejercicio sin compilar nada: los pesos tienen que ser números no
negativos que sumen 100 % y cada criterio `test:<nombre>` tiene que nombrar una prueba de
`tests_funciones` o `tests_ocultos`. Sale con 2 si alguna rúbrica no cumple; los criterios que no se
califican automáticamente (por ejemplo `defensa_oral`) sólo dan un aviso.

```bash
deckard verify --rubric --all
deckard verify --rubric potencia --json
```

#### Calificación con la rúbrica (`deckard exercise rubric --eval-results`)
Aplica la rúbrica a lo que evaluó `dredd eval` (la última revisión de cada estudiante: el
`resultado` de `rNi/auditoria.json` y `rNi/hallazgos.json`) y calcula la nota 0–10:

| Criterio | Logro (0 a 1) |
| :--- | :--- |
| `tests_unitarios` | Pruebas aprobadas / total. |
| `test:<nombre>` | 1 si esa prueba pasó. |
| `estilo_gaff`, `sanitizers_memoria`, `antipatrones_spunkmeyer`, `modularidad_y_diseño`, o una categoría de yutani (`memoria`, `punteros`…) | 1 menos 0,25 por error, 0,10 por advertencia y 0,05 por estilo; cada hallazgo cuenta para un solo criterio. `sanitizers_memoria` descuenta además 0,25 por prueba con fuga. |

Si la entrega no compila, todos los criterios valen 0. Un criterio sin evidencia automática no
entra en la nota (los demás se reescalan) y la nota queda provisoria. Escribe
`calificaciones.csv` (UTF-8 con BOM, columnas `Usuario`, `Calificación`, `Provisoria`, `Revisión`,
el logro de cada criterio y `Comentarios de retroalimentación`: en Moodle, *Importar
calificaciones → CSV*, vincular `Usuario` con el nombre de usuario) y `devoluciones/<alumno>.md`.

```bash
dredd eval tp01 --all
deckard exercise rubric potencia --eval-results tp01-submissions --salida tp01-notas
```

### 2. Endurecimiento de Tests (`deckard verify fuzz`)
Delega en `dredd fuzz-gen` para generar casos de prueba exhaustivos con libFuzzer:
```bash
# Endurecer un ejercicio puntual generando 8 casos
deckard verify fuzz invertir-vector -n 8

# Endurecer en lote con barra de progreso y reporte de fallos
deckard verify fuzz "arreglos/*" --segundos 15 --log-fallos dist/fallos_fuzz.md

# Fuzzing en modo determinista (sin libFuzzer)
deckard verify fuzz --all --sin-libfuzzer
```

### 3. Arnés de Pruebas con Inyección de Errores (`deckard verify test-harness`)
Evalúa el comportamiento del código ante fallos de memoria simulados:
```bash
deckard verify test-harness invertir-vector spec.yaml
```

---

## 7. Empaquetado y Variantes Combinatorias

### Empaquetado `.ripkg` y Starter Repos (`deckard pack`)
Genera paquetes protegidos y estructuras listas para GitHub Classroom:
```bash
# Empaquetar un ejercicio individual como .ripkg
deckard pack invertir-vector -o dist/

# Empaquetar una guía completa generando starter repos para los alumnos
deckard pack guias/guia_punteros.yaml --starter -o dist/classroom/

# Firmar paquetes con clave GPG
deckard pack invertir-vector --sign-key "Cátedra P1" -o dist/
```

### Generador de Variantes Combinatorias (`deckard multiplex`)
Genera variantes de trabajos prácticos y asignación determinista por legajo/padrón:
```bash
# Generar variantes de un TP combinatorio
deckard multiplex tp1_spec.yaml --salida dist/tps/

# Asignar variante determinista a un alumno por padrón
deckard multiplex tp1_spec.yaml --padron 123456
```

---

## 8. Resumen de Comandos

| Comando | Descripción |
| :--- | :--- |
| `deckard init` | Inicializa carpetas del banco y guías. |
| `deckard new <id>` | Crea un nuevo ejercicio en el banco. |
| `deckard bank list` | Cataloga ejercicios con filtros por tema y Bloom. |
| `deckard show <id>` | Muestra enunciado, solución, pistas y tests en consola. |
| `deckard spec <subcmd>` | Gestiona y valida especificaciones (`new`, `list`, `show`, `validate`, `edit`, `compose`). |
| `deckard guide <subcmd>` | Gestiona guías compuestas (`list`, `show`, `compose`, `add`, `remove`, `verify`, `export`). |
| `deckard export <obj>` | Exporta a PDF/MD/HTML (`--type=pdf,md`, `--pipeline-md`, `templates init/list`). |
| `deckard export myst` | Sitio MyST del banco: páginas de ejercicios y guías, TOC, `.ripkg` y `catalogo.json`. |
| `deckard verify [id]` | Verificación con Ripley, barra de progreso en batch y `--log-fallos`. |
| `deckard verify fuzz` | Endurecimiento masivo de tests con `dredd fuzz-gen`. |
| `deckard verify test-harness` | Arnés de pruebas con inyección de fallas vía `ripley harness`. |
| `deckard compose <spec>` | Algoritmo knapsack de balanceo pedagógico. |
| `deckard pack <obj>` | Empaquetador `.ripkg` y generador de starter repos. |
| `deckard multiplex <spec>` | Generador de variantes combinatorias de TPs por alumno. |
