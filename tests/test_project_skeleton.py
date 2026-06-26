"""Basic tests for the first project skeleton."""

from 后端 import data_analysis, history, numeric_calc, plotting, symbolic_calc, utils


def test_backend_modules_importable():
    assert symbolic_calc.module_ready()
    assert numeric_calc.module_ready()
    assert data_analysis.module_ready()
    assert plotting.module_ready()
    assert history.module_ready()
    assert utils.module_ready()
