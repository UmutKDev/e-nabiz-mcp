"""Her liste tool'unu gerçekten ÇAĞIRAN duman testi — ağ yok (httpx.MockTransport).

Neden gerekli: tool gövdeleri `register(mcp)` içinde closure'dır ve testlerin geri
kalanı yalnız parser'ları çağırır. Yani bir tool'daki `NameError` (ör. eksik import)
tüm suite yeşilken canlıda patlar. Bu dosya o boşluğu kapatır: kayıt + çağrı +
zarf sözleşmesi.
"""

from __future__ import annotations

import contextlib

import httpx
import pytest

from enabiz_mcp import auth
from enabiz_mcp.tools import (
    administrative,
    allergies,
    appointments,
    chronic_followups,
    diagnoses,
    discharge_summaries,
    hospital_visits,
    labs,
    medications,
    pathology,
    prescription_types,
    prescriptions,
    profile,
    radiology,
    reports,
    vaccinations,
)

_MODULES = (
    administrative, allergies, appointments, chronic_followups, diagnoses,
    discharge_summaries, hospital_visits, labs, medications, pathology,
    prescription_types, prescriptions, profile, radiology, reports, vaccinations,
)
_TOKEN = '<input name="__RequestVerificationToken" value="tok"/>'


class _FakeMCP:
    """`register()`'ın kaydettiği closure'ları yakalar (FastMCP iç yapısına bağlanmadan)."""

    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, **_kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco


@pytest.fixture
def tools(monkeypatch):
    client = httpx.Client(
        base_url="https://enabiz.gov.tr",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=_TOKEN)),
    )

    @contextlib.contextmanager
    def fake_scope(_cfg):
        yield client

    monkeypatch.setattr(auth, "session_scope", fake_scope)
    fake = _FakeMCP()
    for m in _MODULES:
        m.register(fake)
    return fake.tools


def _list_tools(tools):
    return {n: f for n, f in tools.items() if n.startswith("enabiz_list_")}


def test_every_list_tool_is_callable(tools):
    """Hiçbir liste tool'u çağrıldığında patlamamalı (boş yanıtta bile)."""
    listers = _list_tools(tools)
    assert len(listers) >= 17, "liste tool'ları kaybolmuş olabilir"
    for name, fn in listers.items():
        out = fn()
        assert isinstance(out, dict), name
        assert "error" not in out, f"{name} → {out.get('error')}"


def test_every_list_tool_reports_truncation(tools):
    """Model kırpıldığını görebilmeli — aksi hâlde kısmi listeyi tam sanar."""
    for name, fn in _list_tools(tools).items():
        assert "truncated" in fn(), f"{name} truncated bayrağı döndürmüyor"


def test_every_list_tool_accepts_limit(tools):
    for fn in _list_tools(tools).values():
        assert fn(limit=1)["truncated"] is False  # boş liste → kırpma yok
        assert fn(limit=0)["truncated"] is False  # 0 = sınırsız
