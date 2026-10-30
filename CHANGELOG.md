# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versiones según [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Agregado

- **export myst**: el sitio MyST del repositorio de enunciados (antes `gestionar_consignas.py` de ese repositorio): páginas de ejercicios y guías, portada, grafo temático desde `temas.yaml`, el `toc` de `myst.yml` (entre los comentarios `# deckard export myst: inicio` y `…: fin`, sin tocar el resto), un `.ripkg` por ejercicio sin pruebas ocultas y `paquetes/catalogo.json` con ejercicios y guías. Pensado para el CI.
- **ejercicio**: `tipo: laboratorio`, además de concepto, práctica guiada, desafío y parcial previo.
- **ejercicio**: `publicar: false` deja el ejercicio en el banco pero fuera del sitio, los paquetes y el catálogo. Esquema JSON regenerado.
- **exercise cubrir**: casos de ejercicios de funciones con un driver generado desde los prototipos, especificaciones de tyrell por función para revisar y la solución de la cátedra (con UBSan en modo trap) como referencia; en `tests/funciones/` (Ola 32).
- **ejercicio**: campos de las plantillas del repositorio de enunciados: `unidad`, `modulo`, `subtema`, `dificultad`, `esfuerzo_lineas_codigo`, `tipo`, `obligatorio`, `prerrequisitos`, `correquisitos`, `siguiente_recomendado`, `referencias_teoria` y `visibilidad_solucion` (con `oculta`, la solución no se exporta nunca); la cabecera `<id>.h` se carga para las plantillas. El itinerario entra en el grafo de dependencias y `verify audit` avisa de referencias rotas. Esquema JSON regenerado.
- **export**: plantillas Markdown/HTML/CSS por defecto tomadas del repositorio de enunciados (metadatos, itinerario en Mermaid, rúbrica, cabecera, MyST); se buscan también en `templates/` junto al banco.

### Cambiado

- **ejercicio**: `rubrica` es una lista de `{criterio, peso}` (la forma de las plantillas); el mapa `{criterio: peso}` se sigue aceptando al leer. `pesos_rubrica` da el mapa para la calibración y la calificación.

- **guide practica**: crea la práctica desde la guía compuesta sobre plantilla-TP (con su `tp.sh`), con las librerías declaradas en la guía (de la cátedra, a crear o reutilizadas de una guía anterior) y, del lado del docente, `dredd.mk`, las pruebas ocultas y `targets.json` para dredd; si la práctica ya existe, muestra las diferencias (Ola 30).
- **guías**: `librerias` y `targets_docente` en la spec y en la guía compuesta (`compose` los traslada); `spec validate` revisa las librerías reutilizadas y, con `--remoto`, los commits de la cátedra.

### Corregido

- **init_tests**: la suite generada para p1_test no compilaba: usaba `INIT_TESTS` y `ASSERT_EQ`, que p1_test no tiene, `ASSERT_TRUE` con dos argumentos y `assert()` de los bloques de código del banco (N-DECKARD-07).

## [0.2.0] - 2026-09-28

Primera versión con registro de cambios; lo anterior está en el historial de git.

### Agregado

- **cli**: cumplir el contrato de línea de comandos de LINEAMIENTOS §3.2 (N-ECO-04) (`e5ee322`)

### Corregido

- **cli**: mostrar los errores de datos como mensajes en lugar de tracebacks (N-DECKARD-03, N-ECO-05) (`956c7bd`)
- **tipos**: importar los nombres de typing usados en anotaciones (N-ECO-08) (`5709cde`)

### Documentación

- agregar el texto de la licencia GPL-3.0-or-later que declara pyproject (N-ECO-06) (`69e33ec`)
- **cli**: la ayuda de `deckard verify` cita vasquez inject, no ripley harness (N-DECKARD-04) (`d59c39b`)

### Mantenimiento

- **calidad**: verificar errores de Python y dependencias vulnerables (N-ECO-08, N-ECO-13) (`49d3c3e`)
- **deps**: actualizar weasyprint a 70.0 por aviso de seguridad (N-ECO-13) (`5e27742`)
- **deps**: mover las dependencias de desarrollo a dependency-groups (N-ECO-07) (`9e2e7c4`)
