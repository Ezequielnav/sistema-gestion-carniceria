"""DF-01: corre las pruebas de static/js/lector.js con el ejecutor de pruebas de Node."""

import shutil
import subprocess
from pathlib import Path

import pytest

PRUEBAS = Path(__file__).parent / "js" / "lector.test.cjs"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_df01_deteccion_del_lector_en_el_campo_de_peso():
    resultado = subprocess.run(
        ["node", "--test", str(PRUEBAS)], capture_output=True, text=True, timeout=60
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
