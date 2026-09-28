"""Integraciones opcionales sin instalar: mensaje claro, sin traceback (N-ECO-01).

deckard ya no busca myst-tools, daedalus ni nostromo en carpetas hermanas:
llegan con los extras `languagetool` y `ecosistema`. Sin ellos, el comando que
los necesita explica cómo instalarlos y el resto funciona igual.
"""

from __future__ import annotations

import sys

from typer.testing import CliRunner

from deckard.cli import app
from deckard.core import function_runner, sanitizer_audit

runner = CliRunner()


def test_spellcheck_sin_myst_tools_explica_el_extra(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "myst_tools", None)
    monkeypatch.setitem(sys.modules, "myst_tools.languagetool_checker", None)
    monkeypatch.delitem(sys.modules, "deckard.core.languagetool_checker", raising=False)
    (tmp_path / "banco").mkdir()
    resultado = runner.invoke(app, ["spellcheck", "--banco", str(tmp_path / "banco")])
    assert resultado.exit_code == 1
    assert "extra languagetool" in resultado.output
    assert resultado.exception is None or isinstance(resultado.exception, SystemExit)


def test_sin_daedalus_ni_nostromo_se_usa_el_camino_propio(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "daedalus.core.compiler", None)
    monkeypatch.setitem(sys.modules, "nostromo.core.sandbox", None)
    assert function_runner._compilar_con_daedalus(tmp_path / "a.c", tmp_path / "a") is None
    assert function_runner._try_import_nostromo() is None
    assert sanitizer_audit._compilar_con_daedalus([tmp_path / "a.c"], tmp_path / "a", []) is None
