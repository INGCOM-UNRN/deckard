# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
versiones según [SemVer](https://semver.org/lang/es/).

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
