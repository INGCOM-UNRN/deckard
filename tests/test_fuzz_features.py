"""Tests para las funcionalidades avanzadas de deckard fuzz: progreso, log de fallos y desverificación."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import cargar_ejercicio, guardar_ejercicio
from deckard.core.models import Ejercicio, NivelBloom

runner = CliRunner()


@pytest.fixture()
def banco_fuzz(tmp_path) -> Path:
    banco = tmp_path / "banco"
    banco.mkdir()

    # Ejercicio 1: Con solucion.c y verificado=True inicialmente
    ej1 = Ejercicio(
        id="ej-fuzz-ok",
        titulo="Ejercicio Fuzz OK",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="Enunciado 1",
        solucion_c="#include <stdio.h>\nint main(void){return 0;}\n",
        verificado=True,
    )
    guardar_ejercicio(ej1, banco)

    # Ejercicio 2: Con solucion.c que provocará fallo en fuzz
    ej2 = Ejercicio(
        id="ej-fuzz-fallo",
        titulo="Ejercicio Fuzz Fallo",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="Enunciado 2",
        solucion_c="#include <stdio.h>\nint main(void){return 0;}\n",
        verificado=True,
    )
    guardar_ejercicio(ej2, banco)

    # Ejercicio 3: Sin solucion.c pero marcado verificado=True
    ej3 = Ejercicio(
        id="ej-fuzz-sin-solucion",
        titulo="Ejercicio Sin Solucion",
        tema="punteros",
        bloom=NivelBloom.COMPRENDER,
        minutos_estimados=15,
        enunciado_md="Enunciado 3",
        solucion_c="",
        verificado=True,
    )
    dir_ej3 = guardar_ejercicio(ej3, banco)
    # Borrar solucion.c para simular ejercicio incompleto
    (dir_ej3 / "solucion.c").unlink(missing_ok=True)

    return banco


def test_fuzz_marca_no_verificado_en_fallo(banco_fuzz, tmp_path):
    log_file = tmp_path / "fallos.log"

    def mock_subprocess_run(cmd, *args, **kwargs):
        mock_res = MagicMock()
        if "ej-fuzz-ok" in cmd:
            mock_res.returncode = 0
            mock_res.stderr = ""
        else:
            mock_res.returncode = 1
            mock_res.stderr = "Fuzzing timeout / sanitizer crash"
        return mock_res

    with patch("shutil.which", return_value="/usr/bin/dredd"), \
         patch("subprocess.run", side_effect=mock_subprocess_run):

        res = runner.invoke(app, [
            "fuzz", "*",
            "--banco", str(banco_fuzz),
            "--log-fallos", str(log_file)
        ])

        # Verifica que el código de salida refleje que hubo fallos
        assert res.exit_code == 1

        # Verificar que el log de fallos se generó correctamente
        assert log_file.is_file()
        contenido_log = log_file.read_text(encoding="utf-8")
        assert "ej-fuzz-fallo" in contenido_log
        assert "ej-fuzz-sin-solucion" in contenido_log
        assert "Fuzzing timeout / sanitizer crash" in contenido_log

        # Verificar que los ejercicios con fallo u omitidos quedaron con verificado: false
        ej_ok = cargar_ejercicio(banco_fuzz / "ej-fuzz-ok")
        ej_fallo = cargar_ejercicio(banco_fuzz / "ej-fuzz-fallo")
        ej_sin_sol = cargar_ejercicio(banco_fuzz / "ej-fuzz-sin-solucion")

        assert ej_ok.verificado is True
        assert ej_fallo.verificado is False
        assert ej_sin_sol.verificado is False


def test_fuzz_single_marca_no_verificado(banco_fuzz, tmp_path):
    log_file = tmp_path / "single_fallo.log"

    def mock_subprocess_run(cmd, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.returncode = 1
        mock_res.stderr = "Compilation error in fuzz test"
        return mock_res

    with patch("shutil.which", return_value="/usr/bin/dredd"), \
         patch("subprocess.run", side_effect=mock_subprocess_run):

        res = runner.invoke(app, [
            "fuzz", "ej-fuzz-fallo",
            "--banco", str(banco_fuzz),
            "--log-fallos", str(log_file)
        ])

        assert res.exit_code == 1
        assert "Marcado como no-verificado" in res.stdout

        # Comprobar estado en disco
        ej_fallo = cargar_ejercicio(banco_fuzz / "ej-fuzz-fallo")
        assert ej_fallo.verificado is False

        # Comprobar log
        assert log_file.is_file()
        assert "Compilation error in fuzz test" in log_file.read_text(encoding="utf-8")


def test_verify_fuzz_subcommand(banco_fuzz):
    # Probar que 'verify fuzz' funciona idénticamente
    with patch("shutil.which", return_value="/usr/bin/dredd"), \
         patch("subprocess.run") as mock_run:
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stderr = ""
        mock_run.return_value = mock_res

        res = runner.invoke(app, [
            "verify", "fuzz", "ej-fuzz-ok",
            "--banco", str(banco_fuzz),
        ])
        assert res.exit_code == 0
        assert mock_run.called
