"""Testler için paylaşılan yardımcılar.

`FX = Path(__file__).parent / "fixtures"` 21 dosyada birebir tekrar ediyordu;
`scripts/` paket olmadığı için importlib makinesi de 2 dosyada kopyalanmıştı.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_html(name: str) -> str:
    """Sentetik fixture'ı okur (PHI yok). `.html` uzantısı isteğe bağlı."""
    if not name.endswith(".html"):
        name += ".html"
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_script(name: str) -> ModuleType:
    """`scripts/` altındaki bir betiği dosya yolundan yükler (paket değil)."""
    path = Path(__file__).resolve().parent.parent / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
