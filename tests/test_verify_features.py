"""Tests para las funcionalidades avanzadas de deckard verify: barra de progreso, log de fallos y desverificación."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from deckard.cli import app
from deckard.core.bank import cargar_ejercicio, guardar_ejercicio
from deckard.core.models import Ejercicio, NivelBloom
from deckard.core.verify import ResultadoVerify

runner = CliRunner()


@pytest.fixture()
def banco_verify(tmp_path) -> Path:
    banco = tmp_path / "banco"
    banco.mkdir()

    ej1 = Ejercicio(
        id="ej-verif-ok",
        titulo="Ejercicio Verif OK",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="Enunciado 1",
        solucion_c="#include <stdio.h>\nint main(void){return 0;}\n",
        verificado=False,
    )
    guardar_ejercicio(ej1, banco)

    ej2 = Ejercicio(
        id="ej-verif-fallo",
        titulo="Ejercicio Verif Fallo",
        tema="arreglos",
        bloom=NivelBloom.APLICAR,
        minutos_estimados=20,
        enunciado_md="Enunciado 2",
        solucion_c="#include <stdio.h>\nint main(void){return 0;}\n",
        verificado=True,
    )
    guardar_ejercicio(ej2, banco)

    return banco


def test_verify_batch_progress_and_failure_log(banco_verify, tmp_path):
    log_file = tmp_path / "fallos_verify.log"

    def mock_verificar(dir_ej, *args, **kwargs):
        if "ej-verif-ok" in str(dir_ej):
            return ResultadoVerify(ejercicio="ej-verif-ok", ok=True, detalle="0x0000h OK")
        return ResultadoVerify(ejercicio="ej-verif-fallo", ok=False, detalle="0x0001h GCC Error")

    with patch("deckard.cli.verify.verificar_ejercicio", side_effect=mock_verificar):
        res = runner.invoke(app, [
            "verify", "--all",
            "--banco", str(banco_verify),
            "--log-fallos", str(log_file)
        ])

        assert res.exit_code == 1
        assert "Verificación completada: 1/2 exitosos" in res.stdout

        # Comprobar log
        assert log_file.is_file()
        contenido_log = log_file.read_text(encoding="utf-8")
        assert "ej-verif-fallo" in contenido_log
        assert "0x0001h GCC Error" in contenido_log

        # Comprobar estado en YAML
        ej_ok = cargar_ejercicio(banco_verify / "ej-verif-ok")
        ej_fallo = cargar_ejercicio(banco_verify / "ej-verif-fallo")
        assert ej_ok.verificado is True
        assert ej_fallo.verificado is False


def test_verify_single_marks_unverified_on_failure(banco_verify, tmp_path):
    log_file = tmp_path / "single_verif_fallo.log"

    def mock_verificar(dir_ej, *args, **kwargs):
        return ResultadoVerify(ejercicio="ej-verif-fallo", ok=False, detalle="0x0002h Linker Error")

    with patch("deckard.cli.verify.verificar_ejercicio", side_effect=mock_verificar):
        res = runner.invoke(app, [
            "verify", "ej-verif-fallo",
            "--banco", str(banco_verify),
            "--log-fallos", str(log_file)
        ])

        assert res.exit_code == 1
        assert "Marcado como no-verificado" in res.stdout

        # Comprobar estado en YAML
        ej_fallo = cargar_ejercicio(banco_verify / "ej-verif-fallo")
        assert ej_fallo.verificado is False

        # Comprobar log
        assert log_file.is_file()
        assert "0x0002h Linker Error" in log_file.read_text(encoding="utf-8")
