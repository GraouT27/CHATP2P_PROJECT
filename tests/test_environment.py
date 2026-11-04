import importlib
import sys

import pytest


def test_python_version():
    assert sys.version_info >= (3, 10), "Can Python 3.10 tro len"


@pytest.mark.parametrize("module", ["PyQt6.QtWidgets", "cryptography", "psutil"])
def test_import(module):
    importlib.import_module(module)