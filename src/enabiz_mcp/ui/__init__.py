"""MCP Apps (ext-apps) katmanı — `io.modelcontextprotocol/ui` uzantısı.

Widget desteklemeyen host'larda bu katman UYUR: FastMCP uzantıyı ilan eder,
istemci ilan etmezse `app_capable()` `False` döner ve tool'lar bugünkü metin
çıktısını verir. Belirsizlik daima metin yoluna düşer.
"""

from __future__ import annotations

from fastmcp.apps import UI_EXTENSION_ID
from fastmcp.server.dependencies import get_context

__all__ = ["UI_EXTENSION_ID", "app_capable"]


def app_capable() -> bool:
    """Bu çağrıyı yapan istemci panel (widget) render edebiliyor mu?

    Bağlamı `get_context()` ile ALIR, tool imzasına `ctx: Context` EKLEMEZ.
    Gerekçe ölçülmüş: imzaya eklenince `tests/test_tools_smoke.py` tool'ları
    doğrudan çağırdığı için `TypeError` ile kırıldı. Testi düzeltmek yanlış
    cevaptı — mevcut testin kırılması metin yolunun çağrı sözleşmesini
    bozduğumuzun kanıtıydı. Bu yol sözleşmeyi hiç değiştirmez.

    Aktif bağlam yoksa (doğrudan çağrı, test) `False` — yani METİN yolu. Yön
    kasıtlı: yanlış tarafa düşmek "panel yok ama veri de yok" demek olurdu;
    bu yönde en kötü ihtimalle PHI bugünkü gibi modele gider — REGRESYON YOK.
    """
    try:
        ctx = get_context()
    except RuntimeError:
        # "No active context found." — sunucu isteği dışındayız.
        return False
    return ctx.client_supports_extension(UI_EXTENSION_ID)
