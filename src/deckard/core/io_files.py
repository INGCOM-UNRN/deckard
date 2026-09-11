"""Soporte y scaffolding de ejercicios basados en flujos de entrada/salida estándar y archivos."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from deckard.core.models import Ejercicio


def generar_plantilla_archivos_c(ej_id: str, modo: str = "binario") -> str:
    """Genera código C idiomático con manejo seguro de archivos (fopen, fread/fwrite, fclose)."""
    if modo == "binario":
        return f"""#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

/* Estructura canónica para serialización binaria */
typedef struct {{
    int id;
    char codigo[16];
    double valor;
}} Registro;

/**
 * Procesa un archivo binario validando descriptores y retorno de fread/fwrite.
 */
int procesar_archivo_binario(const char* ruta_origen, const char* ruta_destino) {{
    if (!ruta_origen || !ruta_destino) return -1;

    FILE* origen = fopen(ruta_origen, "rb");
    if (!origen) {{
        perror("Error al abrir archivo de origen");
        return -2;
    }}

    FILE* destino = fopen(ruta_destino, "wb");
    if (!destino) {{
        perror("Error al abrir archivo de destino");
        fclose(origen);
        return -3;
    }}

    Registro reg;
    size_t leidos = 0;
    while ((leidos = fread(&reg, sizeof(Registro), 1, origen)) == 1) {{
        /* Aplicar lógica de negocio */
        reg.valor *= 1.21; // Ejemplo: cálculo de IVA
        if (fwrite(&reg, sizeof(Registro), 1, destino) != 1) {{
            perror("Error de escritura en archivo destino");
            fclose(origen);
            fclose(destino);
            return -4;
        }}
    }}

    fclose(origen);
    fclose(destino);
    return 0;
}}
"""
    else:  # texto / csv
        return f"""#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/**
 * Procesa un archivo de texto línea por línea mediante fgets() evitando desbordes.
 */
int procesar_archivo_texto(const char* ruta_csv) {{
    if (!ruta_csv) return -1;

    FILE* f = fopen(ruta_csv, "r");
    if (!f) {{
        perror("Error al abrir CSV");
        return -2;
    }}

    char linea[256];
    int lineas_procesadas = 0;
    while (fgets(linea, sizeof(linea), f) != NULL) {{
        // Eliminar salto de línea
        linea[strcspn(linea, "\\r\\n")] = '\\0';
        if (linea[0] == '\\0' || linea[0] == '#') continue; // Saltar comentarios

        // Tokenización segura
        char* token = strtok(linea, ",;");
        while (token) {{
            // TODO: Procesar columna
            token = strtok(NULL, ",;");
        }}
        lineas_procesadas++;
    }}

    fclose(f);
    return lineas_procesadas;
}}
"""


def scaffolding_ejercicio_archivos(
    dir_ejercicio: Path,
    modo: str = "binario",
) -> None:
    """Crea fixtures de archivos y código de partida para ejercicios de archivos."""
    from deckard.core.bank import cargar_ejercicio, guardar_ejercicio
    ej = cargar_ejercicio(dir_ejercicio)

    tests_dir = dir_ejercicio / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    sol_c = dir_ejercicio / "solucion.c"
    if not sol_c.exists() or not sol_c.read_text(encoding="utf-8").strip():
        sol_c.write_text(generar_plantilla_archivos_c(ej.id, modo=modo), encoding="utf-8")

    # Fixture de prueba
    if modo == "binario":
        fixture_dat = tests_dir / "entrada_muestra.bin"
        # 16 bytes estructurados
        import struct
        datos = struct.pack("=i16sd", 101, b"TEST_ITEM\x00\x00\x00\x00\x00\x00\x00", 99.5)
        fixture_dat.write_bytes(datos)
    else:
        fixture_csv = tests_dir / "entrada_muestra.csv"
        fixture_csv.write_text("id,codigo,valor\n1,ALPHA,10.5\n2,BETA,20.0\n", encoding="utf-8")

    # Registrar tag
    if "archivos" not in ej.tags:
        ej.tags.append("archivos")
    if modo not in ej.tags:
        ej.tags.append(modo)

    guardar_ejercicio(ej, dir_ejercicio.parent)
