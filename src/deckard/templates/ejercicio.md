# {{ ejercicio.titulo }}

{% if incluir_meta %}
> **ID:** `{{ ejercicio.id }}` | **Tema:** {{ ejercicio.tema }} | **Bloom:** B{{ ejercicio.bloom.value }} ({{ ejercicio.bloom.name.lower() }}) | **Tiempo estimado:** ~{{ ejercicio.minutos_estimados }} min{% if ejercicio.tags %} | **Tags:** {{ ejercicio.tags | join(', ') }}{% endif %}
{% endif %}

{{ ejercicio.enunciado_md }}

{% if incluir_pistas and ejercicio.pistas %}
### 💡 Pistas Progresivas
{% for pista in ejercicio.pistas %}
{{ loop.index }}. {{ pista }}
{% endfor %}
{% endif %}

{% if incluir_tests and tests_casos %}
### 🧪 Casos de Prueba
| Caso | Entrada (`.in`) | Salida Esperada (`.out`) |
| :--- | :--- | :--- |
{% for caso in tests_casos %}
| **{{ caso.nombre }}** | `{{ caso.entrada | replace('\n', ' ') | trim }}` | `{{ caso.salida | replace('\n', ' ') | trim }}` |
{% endfor %}
{% endif %}

{% if incluir_solucion and ejercicio.solucion_c %}
### ✓ Solución Modelo de Cátedra
```c
{{ ejercicio.solucion_c }}
```
{% endif %}
