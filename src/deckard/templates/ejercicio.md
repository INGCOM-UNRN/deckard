# {{ ejercicio.titulo }}

{% if incluir_meta %}
> **ID:** `{{ ejercicio.id }}` | **Tema:** {{ ejercicio.tema }} | **Bloom:** B{{ ejercicio.bloom.value }} ({{ ejercicio.bloom.name.lower() }}) | **Tiempo estimado:** ~{{ ejercicio.minutos_estimados }} min{% if ejercicio.tags %} | **Tags:** {{ ejercicio.tags | join(', ') }}{% endif %}
{% endif %}

{{ ejercicio.enunciado_md }}

{% if ejercicio.funciones %}
### 🛠️ Funciones a Implementar
{% for fn in ejercicio.funciones %}
* `{{ fn.firma }}`{% if fn.descripcion %} — *{{ fn.descripcion }}*{% endif %}
{% endfor %}
{% endif %}

{% if incluir_pistas and ejercicio.pistas %}
### 💡 Pistas Progresivas
{% for pista in ejercicio.pistas %}
{{ loop.index }}. {{ pista }}
{% endfor %}
{% endif %}

{% if incluir_tests %}
{% if ejercicio.tests_funciones %}
### 🧪 Tests de Funciones
| Test | Función | Invocación / Aserción |
| :--- | :--- | :--- |
{% for tf in ejercicio.tests_funciones %}
| **{{ tf.nombre }}** | `{{ tf.funcion }}` | {% if tf.codigo %}`{{ tf.codigo | replace('\n', ' ') | trim }}`{% else %}`{{ tf.funcion }}({{ tf.args or '' }}) == {{ tf.retorno_esperado or 'void' }}`{% endif %} |
{% endfor %}
{% endif %}

{% if tests_casos %}
### 🧪 Casos de Prueba (I/O)
| Caso | Entrada (`.in`) | Salida Esperada (`.out`) |
| :--- | :--- | :--- |
{% for caso in tests_casos %}
| **{{ caso.nombre }}** | `{{ caso.entrada | replace('\n', ' ') | trim }}` | `{{ caso.salida | replace('\n', ' ') | trim }}` |
{% endfor %}
{% endif %}
{% endif %}

{% if incluir_solucion and ejercicio.solucion_c %}
### ✓ Solución Modelo de Cátedra
```c
{{ ejercicio.solucion_c }}
```
{% endif %}
