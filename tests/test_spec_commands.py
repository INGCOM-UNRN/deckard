"""Tests para los comandos de gestión de especificaciones (deckard spec)."""

from pathlib import Path
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import guardar_ejercicio
from deckard.core.guides import cargar_spec
from deckard.core.models import Ejercicio, NivelBloom

runner = CliRunner()


@pytest.fixture()
def banco_para_specs(tmp_path) -> Path:
    banco = tmp_path / "banco"
    banco.mkdir()

    ej1 = Ejercicio(
        id="ej-arreglos-1",
        titulo="Arreglos 1",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=30,
        enunciado_md="Enunciado arreglos",
        solucion_c="#include <stdio.h>\nint main(void){return 0;}\n",
        verificado=True,
    )
    guardar_ejercicio(ej1, banco)

    ej2 = Ejercicio(
        id="ej-punteros-1",
        titulo="Punteros 1",
        tema="punteros",
        bloom=NivelBloom.COMPRENDER,
        minutos_estimados=20,
        enunciado_md="Enunciado punteros",
        solucion_c="#include <stdio.h>\nint main(void){return 0;}\n",
        verificado=False,
    )
    guardar_ejercicio(ej2, banco)
    return banco


def test_spec_lifecycle(banco_para_specs, tmp_path):
    g_dir = tmp_path / "guias"

    # 1. Crear nuevo spec
    res_new = runner.invoke(app, [
        "spec", "new", "parcial1.yaml",
        "--titulo", "Primer Parcial P1",
        "--duracion", "60",
        "--margen", "0.8",
        "--temas", "arreglos,punteros",
        "--bloom-min", "2",
        "--bloom-max", "4",
        "--guias", str(g_dir)
    ])
    assert res_new.exit_code == 0
    spec_path = g_dir / "parcial1.yaml"
    assert spec_path.is_file()

    # 2. Listar specs
    res_list = runner.invoke(app, ["spec", "list", "--guias", str(g_dir)])
    assert res_list.exit_code == 0
    assert "parcial1" in res_list.stdout
    assert "Primer" in res_list.stdout
    assert "B2..B4" in res_list.stdout

    # 3. Mostrar spec y candidatos del banco
    res_show = runner.invoke(app, [
        "spec", "show", "parcial1.yaml",
        "--banco", str(banco_para_specs),
        "--guias", str(g_dir)
    ])
    assert res_show.exit_code == 0
    assert "Primer" in res_show.stdout
    assert "ej-arreglos-1" in res_show.stdout
    assert "ej-punteros-1" in res_show.stdout

    # 4. Validar satisfactibilidad (30 + 20 = 50 min disponibles >= 48 min requeridos)
    res_val = runner.invoke(app, [
        "spec", "validate", "parcial1.yaml",
        "--banco", str(banco_para_specs),
        "--guias", str(g_dir)
    ])
    assert res_val.exit_code == 0
    assert "Spec satisfactible" in res_val.stdout

    # 5. Editar spec
    res_edit = runner.invoke(app, [
        "spec", "edit", "parcial1.yaml",
        "--duracion", "120",
        "--guias", str(g_dir)
    ])
    assert res_edit.exit_code == 0
    spec_mod = cargar_spec(spec_path)
    assert spec_mod.duracion_min == 120

    # 6. Re-validar (ahora requiere 120 * 0.8 = 96 min y solo hay 50 min -> debe fallar)
    res_val_fail = runner.invoke(app, [
        "spec", "validate", "parcial1.yaml",
        "--banco", str(banco_para_specs),
        "--guias", str(g_dir)
    ])
    assert res_val_fail.exit_code == 1
    assert "Spec NO satisfactible" in res_val_fail.stdout
