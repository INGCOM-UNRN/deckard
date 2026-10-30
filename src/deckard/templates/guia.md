{#
================================================================================
PLANTILLA MYST MARKDOWN: GUÍA DE TRABAJOS PRÁCTICOS (Deckard + MyST Tools)
================================================================================

Propósito:
    Renderizar una guía compuesta de ejercicios en formato MyST Markdown
    para publicación de colecciones pedagógicas, evaluaciones y prácticas
    grupales e individuales en Programación 1.

Variables de Contexto esperadas (Jinja2):
    - guia: dict u objeto Guia (metadata de la guía compuesta).
        * id: str (opcional, identificador kebab-case de la guía).
        * nombre: str (nombre legible de la guía).
        * unidad: int | str (opcional, unidad curricular).
        * modulo: str (opcional, bloque curricular).
        * minutos_totales: int (suma de minutos calculada por knapsack/deckard).
        * dificultad_promedio: str (opcional, nivel medio de dificultad).
        * distribucion_bloom: dict[str, int] (conteo de ejercicios por nivel Bloom).
    - items: list[dict | GuiaItem] (lista ordenada de items que componen la guía).
        * ejercicio: dict u objeto Ejercicio (con toda la metadata del ejercicio).
        * rol_guia: str (opcional: calentamiento | nuclear | integrador | desafio).
    - ejercicios: list (alias alternativo de items para compatibilidad con Deckard).
    - total_minutos: int (alias alternativo para carga horaria total).
    - rel_starter_path: str (opcional, ruta relativa al starter repo o pack de la guía).
    - incluir_pistas: bool (default True).
    - incluir_soluciones: bool (default False o True según perfil de entrega).
    - incluir_rubricas: bool (default True).

Compatibilidad:
    - Deckard CLI (deckard export guias/<guia>.yaml --type=md).
    - MyST CLI (myst build / myst start).
================================================================================
#}

# {{ guia.nombre }}

**Universidad Nacional de Río Negro — Programación 1 (Ingeniería en Computación)**

{% set cant_ejercicios = items | length if items else (ejercicios | length if ejercicios else 0) %}
{% set carga = guia.minutos_totales or total_minutos or 0 %}

> **Ejercicios:** {{ cant_ejercicios }}
{%- if guia.unidad %} · **Unidad:** {{ guia.unidad }}{% endif %}
{%- if guia.modulo %} · **Módulo:** {{ guia.modulo }}{% endif %}
 · **Carga Total:** ~{{ carga }} min ({{ (carga / 60) | round(1) }} hs cátedra)
{%- if guia.dificultad_promedio %} · **Dificultad:** {{ guia.dificultad_promedio | capitalize }}{% endif %}
{%- if guia.distribucion_bloom %}
>
> **Distribución Bloom:** {% for bloom_name, count in guia.distribucion_bloom.items() %}{{ bloom_name }}: {{ count }}{% if not loop.last %}, {% endif %}{% endfor %}
{%- endif %}

::: {admonition} 🛠️ Entorno de Trabajo y Autoevaluación
:class: note

Esta guía puede ser resuelta y validada localmente mediante **Ripley**:
```bash
ripley run guias/{{ guia.id or 'guia' }}.yaml
```
{% if rel_starter_path %}
- [📥 **Descargar Starter Kit de la Guía**]({{ rel_starter_path }})
{% endif %}
:::

---

{% for item in items %}
{% set ej = item.ejercicio %}
{% set bloom_val = ej.bloom.value if ej.bloom.value is defined else ej.bloom %}
{% set bloom_nombres = {1: 'Recordar', 2: 'Comprender', 3: 'Aplicar', 4: 'Analizar', 5: 'Evaluar / Crear'} %}
{% set bloom_nom = ej.bloom.name.capitalize() if ej.bloom.name is defined else bloom_nombres.get(bloom_val, 'Desconocido') %}

## {{ loop.index }}. {{ ej.titulo }}

> **ID:** `{{ ej.id }}` · **Tema:** `{{ ej.tema }}`
{%- if ej.subtema %} / `{{ ej.subtema }}`{% endif %}
 · **Bloom:** B{{ bloom_val }} ({{ bloom_nom }})
{%- if ej.dificultad %} · **Dificultad:** {{ ej.dificultad | capitalize }}{% endif %}
{%- if item.rol_guia %} · **Rol:** {{ item.rol_guia | capitalize }}{% endif %}
 · **Carga:** ~{{ ej.minutos_estimados }} min
{%- if ej.tags %}
>
> **Etiquetas:** {% for tag in ej.tags %}`{{ tag }}`{% if not loop.last %}, {% endif %}{% endfor %}
{%- endif %}

{% if item.rel_ripkg_path %}
📦 [Paquete `{{ ej.id }}.ripkg`]({{ item.rel_ripkg_path }}) · `ripley run {{ ej.id }}.ripkg`
{% endif %}

{{ ej.enunciado_md | desplegar_contratos }}

{% if (incluir_pistas is not defined or incluir_pistas) and ej.pistas %}
#### 💡 Pistas
````{tab-set}
{% for pista in ej.pistas %}
```{tab-item} Pista {{ loop.index }}
{{ pista }}
```
{% endfor %}
````
{% endif %}

{% if ej.funciones %}
#### Prototipos de Funciones Requeridas
::::{dropdown} Ver los prototipos

| Función | Retorno | Parámetros | Descripción |
| :--- | :--- | :--- | :--- |
{% for f in ej.funciones -%}
| `{{ f.nombre }}` | `{{ f.retorno or 'void' }}` | `{{ f.parametros or 'void' }}` | {{ f.descripcion or '-' }} |
{% endfor %}
::::
{% endif %}

{% if (incluir_rubricas is not defined or incluir_rubricas) and ej.rubrica %}
#### Criterios de Evaluación
| Criterio | Ponderación |
| :--- | :---: |
{% for rub in ej.rubrica -%}
| {{ rub.criterio }} | {{ rub.peso }}% |
{% endfor %}
{% endif %}



---
{% endfor %}

{% if incluir_soluciones %}
# 📖 Apéndice: Soluciones Canónicas de Cátedra

{% for item in items %}
{% set ej = item.ejercicio %}
{% if ej.solucion_c and ej.visibilidad_solucion != 'oculta' %}
### {{ loop.index }}. {{ ej.titulo }} (`{{ ej.id }}`)

::::{dropdown} 🔍 Revelar solución de cátedra

```c
{{ ej.solucion_c }}
```
::::
{% endif %}
{% endfor %}
{% endif %}
