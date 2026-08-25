# deckard — Gestor de Bancos de Ejercicios, Guías y Graduación

> *"Se ha reportado que algunos replicantes escapan..."* — Rick Deckard administra
> las pruebas: qué ejercicio va a cada guía, con qué dificultad y cuánto tiempo
> insume.

`deckard` es la herramienta docente para **autoría y curaduría atómica** de
ejercicios prácticos de C: cada ejercicio vive como una carpeta versionada con
metadata YAML (`tema`, nivel de **Bloom 1-5**, minutos estimados, pistas
progresivas), su solución modelo y su estado de verificación.

El análisis técnico **siempre se delega en `ripley`**: deckard no compila por su
cuenta; orquesta el banco y el balanceo pedagógico.

## Instalación

```bash
uv tool install .          # o: uv sync --extra dev && uv run deckard --help
```

## Inicio rápido

```bash
deckard init                        # crea banco/ + guias/ + un ejemplo
deckard new invertir-pares --titulo "Invertir pares" --tema arreglos --bloom 3
# ... editá banco/invertir-pares/ejercicio.yaml y solucion.c ...
deckard bank list                   # vista del banco (nivel, carga, verificado)
deckard verify invertir-pares       # valida la solución modelo con ripley check

cat > guias/guia.yaml <<'YAML'
nombre: "Guía 2 — Punteros"
duracion_min: 90
margen_carga: 0.8
temas: [punteros, arreglos]
bloom_min: 2
bloom_max: 4
cantidad_maxima: 6
YAML
deckard compose guias/guia.yaml     # selecciona ejercicios balanceados → guias/*.yaml
```

## Modelo de datos (`banco/<id>/ejercicio.yaml`)

```yaml
id: invertir-pares
titulo: Invertir pares
tema: arreglos
bloom: 3            # 1=Recordar .. 5=Evaluar
minutos_estimados: 25
pistas:
  - Pensá el índice del último elemento.
tags: [arreglos]
```

La solución modelo vive junto al YAML en `solucion.c`; `deckard verify` corre
`ripley check` sobre la carpeta y persiste el veredicto.

## Composición de guías

`compose` implementa un *knapsack* pedagógico greedy:

1. Filtra por temas y rango de Bloom declarados en el YAML.
2. Prioriza niveles altos de Bloom, luego menor duración.
3. Respeta el presupuesto útil (`duracion_min × margen_carga`) y diversidad de
   tema (máximo 2 por tema hasta cubrir la mitad del presupuesto).
4. Ordena la guía final por dificultad creciente.

## Arquitectura del ecosistema

| Necesidad | Herramienta |
|---|---|
| Verificación técnica de soluciones | **ripley** (`deckard verify`) |
| Evaluación masiva / feedback | **dredd** |
| Banco de preguntas teóricas | **belmont/questions** |
| Generación paramétrica de reactivos | **daedalus** (alucarD) |

## Estado

Versión cero funcional: `init`, `new`, `bank list`, `verify`, `compose`.
En el roadmap: empaquetado `.ripkg`, starter-repos para GitHub Classroom,
integración con `c-harness` y `fuzz-gen`.
