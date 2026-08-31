---
title: "Manual de Referencia: deckard"
subtitle: "Deckard — Gestor de Bancos de Ejercicios, Guías de Trabajos Prácticos y Taxonomía Bloom"
author: "Cátedra de Algoritmos y Programación"
date: "2026-08-31"
---

(manual-deckard)=
# Deckard — Gestor de Bancos de Ejercicios, Guías de Trabajos Prácticos y Taxonomía Bloom

````{abstract}
**Rol en el ecosistema:** Curaduría pedagógica de ejercicios, composición de guías según carga horaria y niveles Bloom, exportación a Typst/Jupyter, starter ZIPs y control LanguageTool.
````

---

(manual-deckard-proposito)=
## 1. Propósito y Filosofía Pedagógica

La herramienta **`deckard`** forma parte del ecosistema oficial de software de la cátedra. Su diseño sigue principios pedagógicos rigurosos:

1. **Evidencia Técnica Directa**: Todo diagnóstico se fundamenta en la norma ISO C (C11/C23), en el modelo de memoria del sistema o en convenciones arquitectónicas formales.
2. **Acción Correctiva Concreta**: Cada advertencia incluye la prescripción técnica inmediata para resolver el defecto sin recurrir a conjeturas.
3. **Autonomía del Estudiante**: Facilita la autoevaluación local antes de la entrega final del trabajo práctico.
4. **Objetividad Docente**: Estandariza la corrección automática eliminando discrepancias subjetivas en la evaluación.

---

(manual-deckard-instalacion)=
## 2. Instalación y Diagnóstico del Entorno

````{important}
Asegurate de contar con el compilador GCC/Clang y las librerías del sistema instaladas antes de ejecutar `deckard`.
````

Para comprobar el estado de salud de tu entorno de trabajo y las dependencias auxiliares:

````{code-block} bash
# Comprobación de dependencias del sistema
deckard doctor
````

Si se detecta la falta de alguna utilidad (como `gdb`, `valgrind`, `clang-format` o `typst`), el comando indicará el paquete exacto a instalar según tu distribución GNU/Linux o entorno MSYS2.

---

(manual-deckard-comandos)=
## 3. Referencia Completa de Comandos CLI

A continuación se detallan los subcomandos principales disponibles en `deckard`:

| Sintaxis del Comando | Descripción y Efecto |
| :--- | :--- |
| `deckard compose <guia.yaml> -o guia.typ` | Compone la guía maquetada con ejercicios seleccionados. |
| `deckard pack-zip <ejercicio_o_guia> -o starter.zip` | Genera el starter kit ZIP con Makefile y clave de entrega. |
| `deckard check-ambiguity [ejercicio]` | Audita la claridad de consignas y ausencia de ambigüedades. |
| `deckard check-load <guia.yaml>` | Calcula la carga horaria acumulada y balance Bloom. |
| `deckard export-hints <ejercicio> --rot13` | Genera pistas escalonadas con ofuscación anti-spoilers. |
| `deckard spellcheck <guia.yaml>` | Audita ortografía y gramática con LanguageTool. |

````{tip}
Podés agregar el flag `--json` a la mayoría de los comandos para exportar resultados en formato estructurado o `--md` para generar reportes Markdown para el informe de entrega.
````

---

(manual-deckard-tutorial)=
## 4. Tutorial Paso a Paso con Ejemplos Reales

### Caso de Estudio

Considerá el siguiente fragmento de código representativo:

````{code-block} c
:linenos:
// Ejercicio gestionado en banco/punteros/01_invertir/
/*
 * ID: ptr_invertir_vector
 * Bloom: APLICAR | Tiempo: 30 min
 */
void invertir_vector(int *v, size_t n);
````

### Ejecución de la Herramienta

Ejecutá el análisis desde tu terminal:

````{code-block} bash
deckard compose <guia.yaml> -o guia.typ
````

### Salida Obtenida en Consola

````{code-block} text
[✓] Guía compuesta: TP2_Punteros_y_Memoria.typ (Typst 0.11)
[✓] Total de ejercicios: 6 | Carga horaria acumulada: 3.5 horas (Balance: 2 Recordar, 3 Aplicar, 1 Analizar)
[✓] Starter ZIP generado: starter_tp2.zip (Clave de entrega: DKD-A1B2-C3D4)
````

````{note}
Prestá atención a la explicación pedagógica generada: la herramienta no solo señala la línea del problema, sino que explica la causa raíz y el impacto en memoria o arquitectura.
````

---

(manual-deckard-ejercicios)=
## 5. Ejercicios Prácticos y Desafíos

Practicá el uso avanzado de **`deckard`** resolviendo los siguientes ejercicios:

````{exercise} Desafío 1: Composición de Guía Equilibrada
Crear una guía semanal con cota de 4 horas y balance Bloom.

**Instrucción de ejecución:**
```bash
deckard compose guias/tp1.yaml -o tp1.typ
```
````

````{solution} Desafío 1
```bash
deckard compose guias/tp1.yaml -o tp1.typ
# Verificá que la operación concluya exitosamente con código de salida 0.
```
````

````{exercise} Desafío 2: Empaquetado de Starter Kit con Clave
Generar el archivo ZIP descargable para los estudiantes.

**Instrucción de ejecución:**
```bash
deckard pack-zip guias/tp1.yaml -o entregas/starter_tp1.zip
```
````

````{solution} Desafío 2
```bash
deckard pack-zip guias/tp1.yaml -o entregas/starter_tp1.zip
# Revisá el archivo generado o el informe en terminal para confirmar la resolución del problema.
```
````

````{exercise} Desafío 3: Auditoría de Enunciados Docentes
Verificar que los ejercicios no contengan términos vagos ni falta de casos borde.

**Instrucción de ejecución:**
```bash
deckard check-ambiguity --banco ./banco
```
````

````{solution} Desafío 3
```bash
deckard check-ambiguity --banco ./banco
# Comprobá que la salida confirme la ausencia de advertencias o errores pendientes.
```
````

---

(manual-deckard-makefile)=
## 6. Integración en el Flujo de Trabajo y Makefile

Para incorporar `deckard` de forma automática a tu flujo de desarrollo, agregá la siguiente regla en el `Makefile` de tu proyecto:

````{code-block} makefile
check-deckard:
	@echo "=== Ejecutando verificación con deckard ==="
	deckard check src/ include/

.PHONY: check-deckard
````

Ejecutá `make check-deckard` antes de cada commit para asegurar que tu código conserve el estado de aprobación.

---

(manual-deckard-arquitectura)=
## 7. Arquitectura Interna y Mecanismo Técnico

La herramienta **`deckard`** implementa un motor de alta precisión basado en:

- **Tecnología Núcleo:** `Typst Compiler + PyYAML + Bloom Taxonomy Analyzer + ROT13 Hints Obfuscator + Zipfile Engine`.
- **Aislamiento y Determinismo:** Diseñada para operar sin efectos colaterales en entornos de integración continua (CI), terminales de estudiantes y servidores docentes headless.
- **Manejo de Errores Pedagógico:** Todo fallo de sintaxis, memoria o lógica se traduce en una acción prescriptiva concreta con su respectiva justificación técnica.

---

(manual-deckard-ecosistema)=
## 8. Integración y Conexión con el Ecosistema

````{note}
Ninguna herramienta opera de forma aislada. **`deckard`** forma parte del pipeline integral de evaluación, verificación y enseñanza de la cátedra.
````

### Diagrama de Flujo e Interoperabilidad

````{mermaid}
graph TD
    BNC[Banco de Ejercicios YAML] --> DKD[Deckard: Gestor de Guías]
    DKD -->|Starter Kits + Clave SHA-256| ZIP[Estudiantes: starter_tpX.zip]
    DKD -->|Guías Maquetadas Typst| PDF[Campus Virtual: Guías PDF]
    DKD -->|Pautas y Criterios| DRD[Dredd: Autograding Masivo]
    DKD -->|Preguntas de Código| ALU[Alucard: Generador de Parciales]
````

### Matriz de Intercambio de Datos

| Canal | Herramientas Conectadas | Tipo de Datos Transferidos |
| :--- | :--- | :--- |
| **Entradas (Inputs)** | - `Bancos de ejercicios YAML y soluciones canónicas` | Código fuente, AST, binarios, testcases, contratos |
| **Salidas (Outputs)** | - `dredd (consignas de evaluación)`
- `alucarD (exámenes)`
- `Estudiantes (starter ZIPs)` | Informes Markdown, diagnósticos Rich, JSON, actas |
| **Sincronización** | `dredd`, `alucarD`, `idkfa`, `myst-tools` | Validación cruzada, flags compartidos y autofix |

### Pipeline de Integración Recomendado

Podés encadenar `deckard` con otras herramientas del ecosistema en una única línea de comando:

````{code-block} bash
# Pipeline de integración típico
deckard compose guias/tp1.yaml -o tp1.typ && deckard pack-zip guias/tp1.yaml -o starter_tp1.zip
````

