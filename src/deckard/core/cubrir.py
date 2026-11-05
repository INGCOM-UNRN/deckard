"""Casos de prueba de un ejercicio de funciones generados con tyrell (Ola 32, decisión D).

Un ejercicio de funciones (`funciones:` con sus prototipos) no tiene entrada y salida propias:
cada alumno escribe su `main`. Para probarlo con casos `.in`/`.out`:

1. `driver_c` arma un driver: lee de stdin líneas `<función> <argumentos…>`, llama a la función y
   escribe el resultado, una línea por llamada. Sólo para parámetros y retornos escalares
   (enteros, `char`, `bool`, `float`, `double`) o `void`; las demás funciones se omiten, y si no
   queda ninguna el ejercicio no se automatiza (`NoAutomatizable`). Tampoco las de relleno, que
   no resuelven la consigna: sus `.out` rechazarían soluciones correctas (Ola 45).
2. `especificacion` escribe, por función, el YAML de `tyrell generate`/`cubrir` con una regla por
   parámetro. Los rangos, ampliados con las constantes que compara la solución, son una
   propuesta: el docente los revisa (que no pidan algo que el enunciado no pide) y vuelve a
   generar.
3. `generar` compila la solución de la cátedra con el driver (su `main` queda renombrado) como
   referencia, con UBSan: los casos en que la solución desborda o tiene comportamiento indefinido
   se descartan, porque su salida no es un resultado esperable.

Todo queda en `tests/funciones/` del ejercicio: `driver.c`, `tyrell/<función>.yaml` y los pares
`<función>_NN.in/.out`. ripley no los ve (sólo lee `tests/*.in`); dredd los corre compilando el
archivo del alumno junto al driver.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Collection, Dict, List, Optional, Sequence, Set, Tuple

import yaml

from deckard.core.models import Ejercicio, FuncionSpec

DIR_CASOS = Path("tests") / "funciones"
MAIN_RENOMBRADO = "deckard_main_original"

# tipo C normalizado → (formato de scanf, formato de printf, regla de tyrell por omisión)
_ESCALARES: Dict[str, Tuple[str, str, Dict[str, object]]] = {
    "int": ("%d", "%d", {"type": "integer", "min_val": -10, "max_val": 30}),
    "short": ("%hd", "%hd", {"type": "integer", "min_val": -10, "max_val": 30}),
    "long": ("%ld", "%ld", {"type": "integer", "min_val": -10, "max_val": 30}),
    "long long": ("%lld", "%lld", {"type": "integer", "min_val": -10, "max_val": 30}),
    "unsigned int": ("%u", "%u", {"type": "integer", "min_val": 0, "max_val": 40}),
    "unsigned short": ("%hu", "%hu", {"type": "integer", "min_val": 0, "max_val": 40}),
    "unsigned long": ("%lu", "%lu", {"type": "integer", "min_val": 0, "max_val": 40}),
    "unsigned long long": ("%llu", "%llu", {"type": "integer", "min_val": 0, "max_val": 40}),
    "size_t": ("%zu", "%zu", {"type": "integer", "min_val": 0, "max_val": 40}),
    "float": ("%f", "%.4f", {"type": "float", "min_val": -100, "max_val": 100}),
    "double": ("%lf", "%.4f", {"type": "float", "min_val": -100, "max_val": 100}),
    "bool": ("%d", "%d", {"type": "integer", "min_val": 0, "max_val": 1}),
    "char": (" %c", "%c", {"type": "string", "length": 1}),
}
_SIN_CALIFICADORES = re.compile(r"\b(const|volatile|signed)\b")
_COMENTARIOS = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
# La función que el banco trae en lugar de una solución: no tiene relación con la consigna.
_RELLENO = re.compile(r"\b(\w+)\s*\(\s*int\s+val\s*\)\s*\{\s*if\s*\(\s*val\s*<=\s*0\s*\)\s*return\s*0;"
                      r"\s*return\s*val\s*\*\s*2;\s*\}")
# Lo que puede tener llaves sin abrir un bloque.
_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*', re.S)
_NO_LLAMADAS = re.compile(rf"\b(?:{MAIN_RENOMBRADO}|test_\w+)\s*\([^)]*\)\s*\{{")
_CONSTANTE = re.compile(r"(?:[<>]=?|[=!]=)\s*(-?\d+)\b|\bcase\s+(-?\d+)\s*:")
# Más allá de esto una constante suele ser un tope de tamaño, no un borde que convenga recorrer.
CONSTANTE_MAXIMA = 5000


class NoAutomatizable(ValueError):
    """El ejercicio no se puede probar con un driver de escalares (punteros, arreglos, structs…)."""


@dataclass
class Parametro:
    tipo: str
    nombre: str


@dataclass
class FuncionDriver:
    nombre: str
    retorno: str
    parametros: List[Parametro]


def _normalizar(tipo: str) -> str:
    t = " ".join(_SIN_CALIFICADORES.sub(" ", tipo.replace("_Bool", "bool")).split())
    if t in ("unsigned", "unsigned int"):
        return "unsigned int"
    for largo, corto in (("long long int", "long long"), ("long int", "long"), ("short int", "short")):
        t = t.replace(largo, corto)
    return t


def _parametros(fn: FuncionSpec) -> List[Parametro]:
    texto = (fn.parametros or "").strip()
    if texto in ("", "void"):
        return []
    salida = []
    for i, crudo in enumerate(p.strip() for p in texto.split(",")):
        if any(c in crudo for c in "*[]()") or re.search(r"\b(struct|union|enum)\b", crudo):
            raise NoAutomatizable(f"{fn.nombre}: el parámetro «{crudo}» no es escalar")
        palabras = crudo.split()
        nombre = palabras[-1] if len(palabras) > 1 else f"p{i}"
        tipo = _normalizar(" ".join(palabras[:-1]) if len(palabras) > 1 else crudo)
        if tipo not in _ESCALARES:
            raise NoAutomatizable(f"{fn.nombre}: tipo «{tipo}» sin soporte en el driver")
        salida.append(Parametro(tipo, nombre))
    return salida


def funciones_de_relleno(texto: str) -> Set[str]:
    """Nombres de las funciones de una solución cuyo cuerpo es el relleno del banco."""
    return set(_RELLENO.findall(_COMENTARIOS.sub("", texto)))


def constantes_comparadas(texto: str) -> List[int]:
    """Las constantes enteras con que la solución compara, para que el rango propuesto las alcance."""
    valores = {int(a or b) for a, b in _CONSTANTE.findall(_COMENTARIOS.sub("", texto))}
    return sorted(v for v in valores if abs(v) <= CONSTANTE_MAXIMA)


def _funcion_driver(fn: FuncionSpec) -> FuncionDriver:
    retorno = _normalizar(fn.retorno or "void")
    if retorno != "void" and retorno not in _ESCALARES:
        raise NoAutomatizable(f"{fn.nombre}: el retorno «{fn.retorno}» no es escalar")
    return FuncionDriver(fn.nombre, retorno, _parametros(fn))


def funciones_driver(ej: Ejercicio, excluir: Collection[str] = ()) -> List[FuncionDriver]:
    """Las funciones que el driver puede llamar; si no queda ninguna, `NoAutomatizable`."""
    if not ej.funciones:
        raise NoAutomatizable("el ejercicio no declara funciones")
    salida = []
    motivos = []
    for fn in ej.funciones:
        if fn.nombre in excluir:
            motivos.append(f"{fn.nombre}: es una función de relleno, no una solución")
            continue
        try:
            salida.append(_funcion_driver(fn))
        except NoAutomatizable as exc:
            motivos.append(str(exc))
    if not salida:
        raise NoAutomatizable(motivos[0])
    return salida


def driver_c(ej: Ejercicio, excluir: Collection[str] = ()) -> str:
    """Fuente del driver: lee `<función> <args>` por línea y escribe el resultado de cada llamada."""
    fns = funciones_driver(ej, excluir)
    lineas = [
        f"/* Driver de casos de {ej.id}, generado por deckard (Ola 32): no editar a mano. */",
        "#include <stdbool.h>", "#include <stddef.h>", "#include <stdio.h>", "#include <string.h>", "",
    ]
    lineas += [f"{FuncionSpec(nombre=f.nombre, retorno=f.retorno, parametros=', '.join(f'{p.tipo} {p.nombre}' for p in f.parametros) or 'void').firma}" for f in fns]
    lineas += ["", "int main(void)", "{", "    char funcion[64];",
               '    while (scanf("%63s", funcion) == 1)', "    {"]
    for k, f in enumerate(fns):
        cond = "if" if k == 0 else "else if"
        lineas.append(f'        {cond} (strcmp(funcion, "{f.nombre}") == 0)')
        lineas.append("        {")
        for p in f.parametros:
            ctipo = "int" if p.tipo == "bool" else p.tipo
            lineas.append(f"            {ctipo} {p.nombre} = 0;")
        if f.parametros:
            fmt = " ".join(_ESCALARES[p.tipo][0].strip() for p in f.parametros)
            refs = ", ".join(f"&{p.nombre}" for p in f.parametros)
            lineas.append(f'            if (scanf("{fmt}", {refs}) != {len(f.parametros)})')
            lineas += ["            {", '                printf("ERROR_ENTRADA\\n");', "                return 2;", "            }"]
        args = ", ".join(f"({p.tipo}){p.nombre}" if p.tipo == "bool" else p.nombre for p in f.parametros)
        llamada = f"{f.nombre}({args})"
        valor = f"(int){llamada}" if f.retorno == "bool" else llamada
        if f.retorno == "void":
            lineas.append(f"            {llamada};")
        else:
            lineas.append(f'            printf("{_ESCALARES[f.retorno][1]}\\n", {valor});')
        lineas.append("        }")
    lineas += ["        else", "        {", '            printf("FUNCION_DESCONOCIDA %s\\n", funcion);',
               "            return 2;", "        }", "    }", "    return 0;", "}", ""]
    return "\n".join(lineas)


def _regla(parametro: Parametro, constantes: Sequence[int]) -> Dict[str, object]:
    regla: Dict[str, object] = {"name": parametro.nombre, **_ESCALARES[parametro.tipo][2]}
    if regla["type"] == "integer" and parametro.tipo != "bool" and constantes:
        minimo = int(regla["min_val"])
        regla["min_val"] = min(minimo, 0 if minimo == 0 else min(constantes) - 1)  # sin signo no baja de 0
        regla["max_val"] = max(int(regla["max_val"]), max(constantes) + 1)
    return regla


def especificacion(ej: Ejercicio, fn: FuncionDriver, cantidad: int = 12, semilla: int = 32,
                   constantes: Sequence[int] = ()) -> Dict[str, object]:
    reglas = [_regla(p, constantes) for p in fn.parametros]
    plantilla = " ".join([fn.nombre] + [f"{{{p.nombre}}}" for p in fn.parametros]) + "\n"
    if not reglas:
        raise NoAutomatizable(f"{fn.nombre}: sin parámetros, una sola llamada no necesita tyrell")
    return {"name": fn.nombre, "count": cantidad, "seed": semilla, "format_template": plantilla, "rules": reglas}


@dataclass
class ResultadoCubrir:
    ejercicio: str
    casos: Dict[str, int] = field(default_factory=dict)          # función → casos que quedaron
    descartados: Dict[str, List[str]] = field(default_factory=dict)  # función → casos con UB en la solución
    cobertura: Dict[str, bool] = field(default_factory=dict)        # función → si midió ramas (tyrell cubrir)
    omitidas: List[str] = field(default_factory=list)               # funciones que el driver no llama
    ramas: Optional[Dict[str, int]] = None                          # {"tomadas", "totales"} de la solución
    error: Optional[str] = None


def solucion_sin_main(solucion: Path, destino: Path) -> Path:
    """Copia de la solución con su `main` renombrado, para enlazarla con el driver. Es una copia y no
    un `#include`: gcov (y con él `tyrell cubrir`) no atribuye cobertura a un .c incluido."""
    texto = re.sub(r"\bmain\s*\(", f"{MAIN_RENOMBRADO}(", solucion.read_text(encoding="utf-8"))
    destino.write_text(texto, encoding="utf-8")
    return destino


def _compilar_referencia(fuentes: List[Path], destino: Path) -> None:
    proc = subprocess.run(
        # Con trap no hace falta libubsan: el comportamiento indefinido corta la ejecución (SIGILL).
        ["gcc", "-std=c11", "-O0", "-g", "-fsanitize=undefined", "-fsanitize-trap=undefined",
         *map(str, fuentes), "-o", str(destino), "-lm"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise NoAutomatizable(f"la solución no compila con el driver:\n{proc.stderr.strip()[:800]}")


def generar(dir_ejercicio: Path, ej: Ejercicio, tyrell: Optional[str] = None, cobertura: bool = True,
            regenerar_specs: bool = False) -> ResultadoCubrir:
    """Escribe tests/funciones/ con el driver, las especificaciones (si no existen) y los casos."""
    res = ResultadoCubrir(ej.id)
    tyrell = tyrell or shutil.which("tyrell")
    if tyrell is None:
        raise NoAutomatizable("falta tyrell: uv tool install git+https://github.com/INGCOM-UNRN-P1/tyrell")
    solucion = dir_ejercicio / "solucion.c"
    if not solucion.is_file():
        raise NoAutomatizable("falta solucion.c: la referencia de los .out es la solución de la cátedra")
    texto_solucion = solucion.read_text(encoding="utf-8")
    relleno = funciones_de_relleno(texto_solucion)
    fns = funciones_driver(ej, relleno)
    res.omitidas = [fn.nombre for fn in ej.funciones if fn.nombre not in {f.nombre for f in fns}]
    constantes = constantes_comparadas(texto_solucion)
    salida = dir_ejercicio / DIR_CASOS
    (salida / "tyrell").mkdir(parents=True, exist_ok=True)
    driver = salida / "driver.c"
    driver.write_text(driver_c(ej, relleno), encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="deckard-cubrir-") as tmp:
        tmpd = Path(tmp)
        referencia = tmpd / "referencia"
        for cabecera in dir_ejercicio.glob("*.h"):  # la copia de la solución los incluye por ruta relativa
            shutil.copy(cabecera, tmpd)
        fuentes = [solucion_sin_main(solucion, tmpd / "solucion.c"), driver]
        _compilar_referencia(fuentes, referencia)
        for viejo in list(salida.glob("*.in")) + list(salida.glob("*.out")):
            viejo.unlink()
        for fn in fns:
            spec = salida / "tyrell" / f"{fn.nombre}.yaml"
            if regenerar_specs or not spec.is_file():
                try:
                    datos = especificacion(ej, fn, constantes=constantes)
                except NoAutomatizable:
                    continue
                spec.write_text(
                    "# Especificación propuesta por deckard (Ola 32): revisá que los rangos no pidan algo que el\n"
                    "# enunciado no pide y volvé a generar con `deckard exercise cubrir`.\n"
                    + yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")
            casos = tmpd / fn.nombre
            comando = ([tyrell, "cubrir", str(spec), *map(str, fuentes), "-o", str(casos), "--reference", str(referencia)]
                       if cobertura else [tyrell, "generate", str(spec), "-o", str(casos), "--reference", str(referencia)])
            proc = subprocess.run(comando, capture_output=True, text=True)
            res.cobertura[fn.nombre] = proc.returncode == 0 and cobertura
            if proc.returncode != 0 and cobertura:
                # Sin dietrich/gcov, la suite de la especificación sin los casos de cobertura.
                proc = subprocess.run([tyrell, "generate", str(spec), "-o", str(casos), "--reference", str(referencia)],
                                      capture_output=True, text=True)
            if proc.returncode != 0:
                raise NoAutomatizable(f"tyrell falló con {fn.nombre}: {(proc.stderr or proc.stdout).strip()[:500]}")
            buenos, malos = _copiar_sin_ub(casos, referencia, salida, fn.nombre)
            res.casos[fn.nombre] = buenos
            if malos:
                res.descartados[fn.nombre] = malos
        if cobertura:
            res.ramas = medir_ramas(fuentes[0], driver, sorted(salida.glob("*.in")))
    return res


def _sin_lo_que_el_driver_no_llama(texto: str) -> str:
    """El fuente con vacíos el `main` renombrado y los `test_*` que traen algunas soluciones: sus
    ramas (los `assert`) no son la lógica de la consigna y ningún caso las puede ejercitar."""
    for inicio in reversed(list(_NO_LLAMADAS.finditer(texto))):
        profundidad, i = 1, inicio.end()
        while i < len(texto) and profundidad:
            literal = _LITERAL.match(texto, i)
            if literal:
                i = literal.end()
                continue
            profundidad += (texto[i] == "{") - (texto[i] == "}")
            i += 1
        texto = texto[:inicio.end()] + "}" + texto[i:]
    return texto


def medir_ramas(solucion: Path, driver: Path, entradas: Sequence[Path]) -> Optional[Dict[str, int]]:
    """Ramas de la solución que ejecutan los casos. None si no se pudo medir (sin dietrich o sin casos)."""
    dietrich = shutil.which("dietrich")
    if dietrich is None or not entradas:
        return None
    medida = solucion.with_name("solucion_medida.c")
    medida.write_text(_sin_lo_que_el_driver_no_llama(solucion.read_text(encoding="utf-8")), encoding="utf-8")
    comando = [dietrich, "lines", str(medida), str(driver), "--only", str(medida), "--json"]
    for entrada in entradas:
        comando += ["-i", str(entrada)]
    try:
        proc = subprocess.run(comando, capture_output=True, text=True, timeout=120)
        archivo = json.loads(proc.stdout)["archivos"][0]
    except (subprocess.TimeoutExpired, ValueError, KeyError, IndexError):
        return None
    return {"tomadas": archivo["ramas_tomadas"], "totales": archivo["ramas_totales"]}


def _copiar_sin_ub(origen: Path, referencia: Path, destino: Path, prefijo: str) -> Tuple[int, List[str]]:
    """Copia los casos cuya ejecución en la solución termina bien; los que desbordan o fallan, no."""
    vistos = set()
    n = 0
    descartados = []
    for entrada in sorted(origen.glob("*.in")):
        texto = entrada.read_text(encoding="utf-8")
        if texto in vistos:  # tyrell puede repetir bordes cuando el rango es chico
            continue
        vistos.add(texto)
        try:
            proc = subprocess.run([str(referencia)], input=texto, capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:  # un .out que no termina no es un resultado esperable
            descartados.append(texto.strip())
            continue
        if proc.returncode != 0 or "runtime error" in proc.stderr:
            descartados.append(texto.strip())
            continue
        n += 1
        (destino / f"{prefijo}_{n:02d}.in").write_text(texto, encoding="utf-8")
        (destino / f"{prefijo}_{n:02d}.out").write_text(proc.stdout, encoding="utf-8")
    return n, descartados
