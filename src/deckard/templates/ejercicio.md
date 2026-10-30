{#
================================================================================
PLANTILLA MYST MARKDOWN: EJERCICIO INDIVIDUAL (Deckard + MyST Tools)
================================================================================

Propósito:
    Renderizar un ejercicio pedagógico individual en formato MyST Markdown
    para publicación en sitios web estáticos (Sphinx / Curvenote / MyST CLI)
    y sincronización con la herramienta de verificación Ripley.

Variables de Contexto esperadas (Jinja2):
    - ejercicio: dict u objeto Ejercicio (con campos estándar y enriquecidos).
        * id: str (identificador kebab-case del ejercicio).
        * titulo: str (título legible del ejercicio).
        * unidad: int | str (opcional, número de unidad del programa).
        * modulo: str (opcional, nombre del bloque curricular).
        * tema: str (slug temático canónico).
        * subtema: str (opcional, foco específico dentro del tema).
        * bloom: int o Enum (nivel cognitivo de Bloom, 1 a 5).
        * dificultad: str (opcional: inicial | intermedia | avanzada | desafio).
        * minutos_estimados: int (tiempo de resolución previsto).
        * esfuerzo_lineas_codigo: int (opcional, estimación de líneas de código).
        * tags: list[str] (etiquetas conceptuales).
        * prerrequisitos: list[str] (opcional, IDs de ejercicios previos necesarios).
        * correquisitos: list[str] (opcional, temas o IDs paralelos).
        * siguiente_recomendado: list[str] (opcional, IDs de ejercicios de continuidad).
        * tipo: str (opcional: concepto | practica_guiada | laboratorio | desafio | parcial_previo).
        * obligatorio: bool (opcional, relevancia dentro de la cursada).
        * referencias_teoria: dict (opcional, {apunte, seccion, bibliografia}).
        * visibilidad_solucion: str (opcional: publica | desplegable | protegida | oculta).
        * rubrica: list[dict] (opcional, [{criterio: str, peso: int}]).
        * funciones: list[dict] (especificaciones de firmas de funciones).
        * tests_funciones / tests_casos: list[dict] (casos de prueba unitarios).
        * pistas: list[str] (pistas didácticas escalonadas).
        * solucion_c: str (código fuente modelo de cátedra).
        * header_c: str (opcional, archivo .h de cabecera).
        * header_name: str (opcional, nombre del archivo .h).
        * enunciado_md: str (texto Markdown con la consigna del ejercicio).
    - rel_ripkg_path: str (ruta relativa hacia el paquete <id>.ripkg compilado).
    - incluir_meta: bool (default True, bandera para encabezado de metadata).
    - incluir_pistas: bool (default True, incluir pistas progresivas).
    - incluir_tests: bool (default True, incluir tabla de casos de prueba).
    - incluir_solucion: bool (default True, incluir bloque de solución modelo).

Compatibilidad de Motor:
    - MyST CLI (myst build / myst start).
    - Sphinx con myst-parser.
    - Deckard CLI (deckard export --type=md).
================================================================================
#}

# {{ ejercicio.titulo }}

{%- set bloom_val = ejercicio.bloom.value if ejercicio.bloom.value is defined else ejercicio.bloom -%}
{%- set bloom_nombres = {1: 'Recordar', 2: 'Comprender', 3: 'Aplicar', 4: 'Analizar', 5: 'Evaluar / Crear'} -%}
{%- set bloom_nom = ejercicio.bloom.name.capitalize() if ejercicio.bloom.name is defined else bloom_nombres.get(bloom_val, 'Desconocido') -%}
{%- set tags_dep = [] -%}
{%- set tags_otros = [] -%}
{%- if ejercicio.tags -%}
  {%- for t in ejercicio.tags -%}
    {%- if t.startswith('dep:') or t.startswith('req:') or t.startswith('prereq:') -%}
      {%- set _ = tags_dep.append(t) -%}
    {%- else -%}
      {%- set _ = tags_otros.append(t) -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif -%}

{% if incluir_meta is not defined or incluir_meta %}
> **ID:** `{{ ejercicio.id }}`
{%- if ejercicio.unidad %} · **Unidad:** {{ ejercicio.unidad }}{% endif %}
{%- if ejercicio.modulo %} ({{ ejercicio.modulo }}){% endif %}
 · **Tema:** `{{ ejercicio.tema }}`
{%- if ejercicio.subtema %} / `{{ ejercicio.subtema }}`{% endif %}
 · **Bloom:** B{{ bloom_val }} ({{ bloom_nom }})
{%- if ejercicio.dificultad %} · **Dificultad:** {{ ejercicio.dificultad | capitalize }}{% endif %}
 · **Carga:** ~{{ ejercicio.minutos_estimados }} min
{%- if ejercicio.esfuerzo_lineas_codigo %} · **Esfuerzo:** ~{{ ejercicio.esfuerzo_lineas_codigo }} líneas{% endif %}
{%- if ejercicio.tipo %} · **Tipo:** {{ ejercicio.tipo | replace('_', ' ') | title }}{% endif %}
{%- if tags_dep %}
>
> **🏷️ Prerrequisitos temáticos (tags):** {% for tag in tags_dep %}`{{ tag }}`{% if not loop.last %}, {% endif %}{% endfor %}
{%- endif %}
{%- if tags_otros %}
>
> **Etiquetas conceptuales:** {% for tag in tags_otros %}`{{ tag }}`{% if not loop.last %}, {% endif %}{% endfor %}
{%- endif %}
{% endif %}

::: {admonition} 📦 Paquete de Verificación Local (Ripley)
:class: tip

Para compilar, resolver y autoevaluar tu entrega con pruebas unitarias en tu máquina:

- [📥 **Descargar paquete `{{ ejercicio.id }}.ripkg`**]({{ rel_ripkg_path or ('../../paquetes/' ~ ejercicio.id ~ '.ripkg') }})

Ejecución con el asistente de cátedra:
```bash
ripley run {{ ejercicio.id }}.ripkg
```
:::

{% if ejercicio.referencias_teoria %}
### 📚 Articulación Teórica
{% if ejercicio.referencias_teoria.apunte %}
- **Apunte de Cátedra:** [{{ ejercicio.referencias_teoria.apunte }}]({{ ejercicio.referencias_teoria.apunte }}){% if ejercicio.referencias_teoria.seccion %} (Sección: *{{ ejercicio.referencias_teoria.seccion }}*){% endif %}
{% endif %}
{% if ejercicio.referencias_teoria.bibliografia %}
- **Bibliografía de Consulta:**
{% for ref in ejercicio.referencias_teoria.bibliografia %}
  * {{ ref }}
{% endfor %}
{% endif %}
{% endif %}

{% set lista_prerreqs = ejercicio.prerrequisitos or ejercicio.dependencias_temas or [] %}
{% if lista_prerreqs or ejercicio.siguiente_recomendado %}
### 🗺️ Itinerario Pedagógico

```mermaid
flowchart LR
    {% if lista_prerreqs %}
    subgraph Prerrequisitos ["🏷️ Prerrequisitos (dep:*)"]
        {% for pre in lista_prerreqs %}
        node_pre_{{ loop.index }}["{{ pre }}"]
        {% endfor %}
    end
    {% for pre in lista_prerreqs %}
    node_pre_{{ loop.index }} --> current_node
    {% endfor %}
    {% endif %}

    current_node["🎯 {{ ejercicio.id }}<br/><small>{{ ejercicio.tema }} · B{{ bloom_val }}</small>"]

    {% if ejercicio.siguiente_recomendado %}
    subgraph Continuidad ["Desbloquea"]
        {% for sig in ejercicio.siguiente_recomendado %}
        node_sig_{{ loop.index }}["{{ sig }}"]
        {% endfor %}
    end
    {% for sig in ejercicio.siguiente_recomendado %}
    current_node --> node_sig_{{ loop.index }}
    {% endfor %}
    {% endif %}
```
{% endif %}

## 📖 Consigna

{{ ejercicio.enunciado_md }}

{% if ejercicio.header_c %}
## 📋 Prototipos y Cabecera (`{{ ejercicio.header_name or (ejercicio.id ~ '.h') }}`)

```{code-block} c
{{ ejercicio.header_c }}
```
{% endif %}

{% if ejercicio.funciones %}
## ⚙️ Especificación de Funciones

| Función | Retorno | Parámetros | Descripción |
| :--- | :--- | :--- | :--- |
{% for f in ejercicio.funciones %}
| `{{ f.nombre }}` | `{{ f.retorno or 'void' }}` | `{{ f.parametros or 'void' }}` | {{ f.descripcion or '-' }} |
{% endfor %}
{% endif %}

{% if ejercicio.rubrica %}
## 🎯 Rúbrica de Evaluación

| Criterio de Evaluación | Ponderación |
| :--- | :---: |
{% for item in ejercicio.rubrica %}
| {{ item.criterio }} | **{{ item.peso }}%** |
{% endfor %}
{% endif %}

{% if (incluir_pistas is not defined or incluir_pistas) and ejercicio.pistas %}
## 💡 Pistas Progresivas

````{tab-set}
{% for pista in ejercicio.pistas %}
```{tab-item} Pista {{ loop.index }}
{{ pista }}
```
{% endfor %}
````
{% endif %}

{% if (incluir_tests is not defined or incluir_tests) and (tests_casos or ejercicio.tests_funciones) %}
## 🧪 Casos de Prueba
{% if tests_casos %}
| Caso | Entrada (`.in`) | Salida Esperada (`.out`) |
| :--- | :--- | :--- |
{% for caso in tests_casos %}
| **{{ caso.nombre }}** | `{{ caso.entrada | replace('\n', ' ') | trim }}` | `{{ caso.salida | replace('\n', ' ') | trim }}` |
{% endfor %}
{% elif ejercicio.tests_funciones %}
| Prueba Unitaria | Función Objetivo | Verificación |
| :--- | :--- | :--- |
{% for t in ejercicio.tests_funciones %}
| **{{ t.nombre }}** | `{{ t.funcion }}` | `{{ (t.codigo or (t.funcion ~ '(' ~ (t.args or '') ~ ')' ~ (' == ' ~ t.retorno_esperado if t.retorno_esperado else ''))) | replace('\n', ' ') | trim }}` |
{% endfor %}
{% endif %}
{% endif %}

{% set visibilidad = ejercicio.visibilidad_solucion or 'desplegable' %}
{% if (incluir_solucion is not defined or incluir_solucion) and ejercicio.solucion_c and visibilidad != 'oculta' %}
## ✓ Solución Modelo de Cátedra

```{dropdown} 🔍 Revelar solución canónica en C
:open: false

```{code-block} c
{{ ejercicio.solucion_c }}
```
```
{% endif %}
