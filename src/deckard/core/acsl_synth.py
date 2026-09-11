"""Síntesis de casos de prueba unitarios a partir de contratos formales ACSL (callahan)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from deckard.core.models import CasoTestFuncion, Ejercicio, FuncionSpec


def extraer_contratos_acsl(codigo: str) -> List[dict]:
    """Extrae bloques de contratos ACSL (requires, ensures) asociados a funciones C."""
    patron = r"/\*@\s*(.*?)\s*\*/\s*([\w\s\*]+?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)"
    matches = re.finditer(patron, codigo, re.DOTALL)
    contratos = []

    for m in matches:
        acsl_block = m.group(1)
        ret_type = m.group(2).strip()
        fn_name = m.group(3).strip()
        params = m.group(4).strip()

        precondiciones = re.findall(r"@?\s*requires\s+([^;]+);", acsl_block)
        postcondiciones = re.findall(r"@?\s*ensures\s+([^;]+);", acsl_block)
        assigns = re.findall(r"@?\s*assigns\s+([^;]+);", acsl_block)

        contratos.append({
            "funcion": fn_name,
            "retorno": ret_type,
            "parametros": params,
            "requires": [p.strip() for p in precondiciones],
            "ensures": [p.strip() for p in postcondiciones],
            "assigns": [a.strip() for a in assigns],
        })

    return contratos


def sintetizar_tests_de_acsl(ej: Ejercicio, codigo_c: Optional[str] = None) -> List[CasoTestFuncion]:
    """Genera casos de prueba granulares CasoTestFuncion basados en las postcondiciones ACSL."""
    fuente = codigo_c or ej.solucion_c
    if not fuente and ej.archivos:
        fuente = ej.archivos.get(f"{ej.id}.c", "")

    contratos = extraer_contratos_acsl(fuente)
    nuevos_tests: List[CasoTestFuncion] = []

    for c in contratos:
        fn_nombre = c["funcion"]
        ensures = c["ensures"]
        requires = c["requires"]

        for idx, ens in enumerate(ensures, 1):
            # Traducir \result de ACSL a C
            c_postcond = ens.replace("\\result", f"{fn_nombre}()" if not c["parametros"] or c["parametros"] == "void" else "res")
            
            # Construir bloque de código representativo
            desc = f"Verificación ACSL contract [{ens}]"
            if requires:
                desc += f" (asumiendo: {', '.join(requires)})"

            codigo = f"""    /* Contrato ACSL sintetizado: ensures {ens}; */
    // Requiere: {', '.join(requires) if requires else 'Sin precondiciones especiales'}
    // Validar postcondición en runtime
    assert({c_postcond});"""

            nuevos_tests.append(CasoTestFuncion(
                nombre=f"acsl_{fn_nombre}_ensures_{idx}",
                funcion=fn_nombre,
                descripcion=desc,
                postcondiciones=c_postcond,
                codigo=codigo,
            ))

    return nuevos_tests


def actualizar_ejercicio_con_tests_acsl(dir_ejercicio: Path) -> int:
    """Inspecciona solucion.c, sintetiza tests ACSL y los guarda en ejercicio.yaml."""
    from deckard.core.bank import cargar_ejercicio, guardar_ejercicio

    ej = cargar_ejercicio(dir_ejercicio)
    tests_sintetizados = sintetizar_tests_de_acsl(ej)
    if not tests_sintetizados:
        return 0

    nombres_existentes = {t.nombre for t in ej.tests_funciones}
    agregados = 0
    for st in tests_sintetizados:
        if st.nombre not in nombres_existentes:
            ej.tests_funciones.append(st)
            agregados += 1

    if agregados > 0:
        guardar_ejercicio(ej, dir_ejercicio.parent)

    return agregados
