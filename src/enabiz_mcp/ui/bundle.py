"""Vendor'lanmış ext-apps tarayıcı paketini widget HTML'ine gömer.

Paket bir ESM modülü: sonu tek bir `export{a as App,...}` ifadesiyle biter.
Widget iframe'i CSP yüzünden `import` EDEMEZ (ne CDN'den ne de kendinden) —
kod `<script type="module">` gövdesine düz metin olarak girmeli. Bu yüzden
`export{…}` bir `globalThis.ExtApps={…}` atamasına çevrilir; widget da paketi
`globalThis.ExtApps`'ten okur.

Çevrim çalışma zamanında yapılır, vendor dosyası ELLE düzenlenmez: dosya
üretilmiştir ve bir sonraki `npm pack` onu olduğu gibi getirir.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

#: Widget HTML'lerinde paketin gömüleceği yeri işaretleyen belirteç.
BUNDLE_PLACEHOLDER = "/*__EXT_APPS_BUNDLE__*/"

_VENDOR = Path(__file__).parent / "vendor" / "ext-apps.js"

#: ESM paketinin kapanış ifadesi: `export{eI as App,VN as applyHostStyleVariables}`.
#: `[^}]` güvenli — export listesi yalnız `yerel as dışarı` çiftleri içerir, süslü
#: parantez içermez (1.7.4'te doğrulandı).
_EXPORT_RE = re.compile(r"export\{([^}]+)\};?\s*$")


def _to_global_assignment(match: re.Match[str]) -> str:
    """`export{a as App,b as c}` → `globalThis.ExtApps={App:a,c:b}`."""
    pairs = []
    for item in match.group(1).split(","):
        local, _, exported = item.strip().partition(" as ")
        name = exported.strip() or local.strip()
        pairs.append(f"{name}:{local.strip()}")
    return "globalThis.ExtApps={" + ",".join(pairs) + "};"


@functools.lru_cache(maxsize=1)
def ext_apps_bundle() -> str:
    """Paketi okur ve `globalThis.ExtApps` atayan biçimiyle döner.

    ~330KB; süreç ömrü boyunca bir kez okunup önbelleklenir, tüm widget'lar
    aynı dizeyi paylaşır.
    """
    source = _VENDOR.read_text(encoding="utf-8")
    rewritten, count = _EXPORT_RE.subn(_to_global_assignment, source)
    if count != 1:
        # Sessiz bozulma yasak (invaryant #2): çevrim tutmadıysa widget iframe'de
        # `ExtApps is not defined` ile BOŞ render eder ve sebebi görünmez. Paket
        # sürümü kapanış ifadesini değiştirmiş olabilir — gürültüyle patla.
        raise RuntimeError(
            f"ext-apps paketinde beklenen tek `export{{…}}` ifadesi bulunamadı "
            f"(eşleşme: {count}). Vendor sürümü değişmiş olabilir — "
            f"src/enabiz_mcp/ui/vendor/README.md'ye bakın."
        )
    return rewritten


def inline_bundle(html: str) -> str:
    """Widget HTML'indeki `/*__EXT_APPS_BUNDLE__*/` belirtecini paketle doldurur.

    `str.replace` KULLANILIR, `re.sub` DEĞİL: minified paket `\\1` gibi diziler
    içerir ve `re.sub` onları geri-referans sanıp bozar. (JS tarafında aynı tuzak
    `$&` için geçerli.) `str.replace` hiçbir kaçış dizisini yorumlamaz.
    """
    if BUNDLE_PLACEHOLDER not in html:
        raise RuntimeError(
            f"Widget HTML'inde {BUNDLE_PLACEHOLDER} belirteci yok — paket gömülemez, "
            f"widget boş render eder."
        )
    return html.replace(BUNDLE_PLACEHOLDER, ext_apps_bundle())
