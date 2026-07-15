"""Vendor'lanmış ext-apps paketinin gömme çevrimi.

Çevrim tutmazsa widget iframe'de `ExtApps is not defined` ile BOŞ render eder
ve sebebi sunucu tarafında hiç görünmez — sessiz bozulma (invaryant #2).
Bu yüzden çevrim burada, ağsız, doğrulanır.
"""

from __future__ import annotations

import pytest

from enabiz_mcp.ui.bundle import BUNDLE_PLACEHOLDER, ext_apps_bundle, inline_bundle


def test_export_ifadesi_global_atamaya_cevrilir():
    b = ext_apps_bundle()
    assert "export{" not in b, "ESM export kaldı — iframe'de `import` CSP'ye takılır"
    assert "globalThis.ExtApps={" in b


def test_widgetin_kullandigi_semboller_export_ediliyor():
    """`table.html` bu ikisini okur; paket sürümü birini düşürürse burada patla."""
    b = ext_apps_bundle()
    for sembol in ("App:", "applyHostStyleVariables:"):
        assert sembol in b, f"{sembol} paketten kayboldu — vendor sürümü değişmiş olabilir"


def test_paket_kaynagi_bozulmamis():
    """Çevrim yalnız kapanış ifadesine dokunmalı; gövde küçülmemeli."""
    b = ext_apps_bundle()
    assert len(b) > 250_000, "paket beklenenden küçük — vendor dosyası kırpılmış olabilir"


def test_belirtec_yoksa_gurultuyle_patlar():
    """Sessizce paketsiz HTML servis etmektense patlamak doğrudur."""
    with pytest.raises(RuntimeError, match="belirteci yok"):
        inline_bundle("<html>belirteç yok</html>")


def test_gomme_belirteci_tuketir():
    out = inline_bundle(f"<script>{BUNDLE_PLACEHOLDER}</script>")
    assert BUNDLE_PLACEHOLDER not in out
    assert "globalThis.ExtApps={" in out


def test_minified_kacis_dizileri_bozulmadan_gomulur():
    """`str.replace` kullanılmalı — `re.sub` `\\1`/`\\g` dizilerini yorumlar.

    Paket minified ve ters-bölü dolu; `re.sub` ile gömülseydi sessizce
    bozulurdu ve yalnız tarayıcıda fark edilirdi.
    """
    b = ext_apps_bundle()
    out = inline_bundle(f"<script>{BUNDLE_PLACEHOLDER}</script>")
    assert out == f"<script>{b}</script>", "paket gömülürken içeriği değişti"
