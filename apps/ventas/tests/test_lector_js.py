"""Corre las pruebas de JavaScript con el ejecutor de pruebas de Node (DF-01, DEC-47)."""

import shutil
import subprocess
from pathlib import Path

import pytest

CARPETA = Path(__file__).parent / "js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_df01_deteccion_del_lector_en_el_campo_de_peso():
    resultado = subprocess.run(
        ["node", "--test", str(CARPETA / "lector.test.cjs")],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_cp94_venta_en_curso_guardada_en_la_pestana():
    resultado = subprocess.run(
        ["node", "--test", str(CARPETA / "venta_guardada.test.cjs")],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no está instalado")
def test_cp106_lista_del_buscador_sin_romper_el_lector():
    resultado = subprocess.run(
        ["node", "--test", str(CARPETA / "buscador.test.cjs")],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
