# {{ guia.nombre }}

**Universidad Nacional de Río Negro · Cátedra de Programación 1**

> **Ejercicios:** {{ ejercicios | length }} | **Carga total:** ~{{ guia.minutos_totales or total_minutos }} min{% if guia.distribucion_bloom %} | **Bloom:** {% for bloom_name, count in guia.distribucion_bloom.items() %}{{ bloom_name }}: {{ count }}{% if not loop.last %}, {% endif %}{% endfor %}{% endif %}

---

{% for item in items %}
## {{ loop.index }}. {{ item.ejercicio.titulo }}

> **Tema:** {{ item.ejercicio.tema }} | **Bloom:** B{{ item.ejercicio.bloom.value }} | **Carga:** ~{{ item.ejercicio.minutos_estimados }} min | `{{ item.ejercicio.id }}`

{{ item.ejercicio.enunciado_md }}

{% if incluir_pistas and item.ejercicio.pistas %}
#### 💡 Pistas
{% for pista in item.ejercicio.pistas %}
{{ loop.index }}. {{ pista }}
{% endfor %}
{% endif %}

---
{% endfor %}

{% if incluir_soluciones %}
# Apéndice: Soluciones Modelo

{% for item in items %}
{% if item.ejercicio.solucion_c %}
### {{ loop.index }}. {{ item.ejercicio.titulo }} (`{{ item.ejercicio.id }}`)
```c
{{ item.ejercicio.solucion_c }}
```
{% endif %}
{% endfor %}
{% endif %}
