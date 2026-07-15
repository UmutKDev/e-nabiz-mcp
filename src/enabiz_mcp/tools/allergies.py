"""Alerji tool'ları (salt-okunur).

Liste: GET /Home/Alerjilerim → sayfa-içi 3 tablo (ilaç / tanı-bazlı / deri testi).
Aksiyon endpoint'leri (AlerjiEkle/Sil/Duzenle) KULLANILMAZ.
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.apps import AppConfig

from .. import auth
from ..config import Config
from ..parsers import Allergy, parse_allergies
from ..ui import app_capable
from ..ui.schema import ALLERGIES
from ._common import apply_limit, auth_guarded

PAGE = "/Home/Alerjilerim"


def fetch_allergies(category: str | None = None) -> list[Allergy]:
    """Alerji kayıtlarını çeker ve ayrıştırır — sunum/zarf mantığı YOK.

    Tool gövdesinden ayrı durur çünkü iki çağıranı var: `enabiz_list_allergies`
    (modele metin döner) ve `enabiz_ui_data` (widget'a PHI döner). Zarflama
    (`apply_limit`) ve `model_dump()` çağıranın işi — bu fonksiyon model
    nesnesi döner.

    `category` filtresi burada, çünkü sunum değil VERİ seçimidir; iki çağıran da
    aynı filtreyi ister.
    """
    cfg = Config.from_env()
    with auth.session_scope(cfg) as client:
        html = client.get(PAGE).text
        if 'name="TCKimlikNo"' in html:
            raise auth.AuthRequired("Oturum düşmüş görünüyor.")
        items = parse_allergies(html)

    if category:
        # Düz `.lower()` — `category` parser'ın atadığı ASCII slug'ı (`ilac`/`tani`/
        # `deri`); `tr_lower` BURAYA GİRMEZ (CLAUDE.md: `tr_lower("DIGER")=="dığer"`).
        q = category.lower()
        items = [a for a in items if a.category == q]

    return items


def register(mcp: FastMCP) -> None:
    """Alerji tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(
        app=AppConfig(resource_uri=ALLERGIES.widget_uri),
        annotations={"readOnlyHint": True, "openWorldHint": True},
    )
    @auth_guarded
    def enabiz_list_allergies(
        category: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """E-Nabız alerji kayıtlarını listeler — salt-okunur.

        Üç kategoriyi birleştirir: `ilac` (ilaç alerjileri), `tani` (tanı bazlı),
        `deri` (deri/prick testleri). Her kayıt tarih, kategori, alerji türü, ilaç
        adı ve belirtileri ile döner. `category` verilirse yalnız o kategori döner.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.

        Panel render edebilen istemcilerde kayıtlar kullanıcıya panelde gösterilir
        ve bu tool yalnız kayıt SAYISINI döner — değerler yanıtta yer almaz.

        - `limit`: en fazla kaç kayıt döner (varsayılan 50; `0` = sınırsız).
          `truncated: true` ise liste kırpılmıştır. Panel yolunda `limit` etkisizdir;
          panel kayıtların tamamını kendi getirir.
        """
        items = fetch_allergies(category)

        if app_capable():
            # PHI BURADA DURUR. Panel kayıtları `enabiz_ui_data` ile kendi çeker;
            # o yanıt modele uğramaz. Sayı geçer, çünkü sıfır bilgi modeli kör
            # bırakır ve kör model uydurur — sayı, asgari uygulanabilir açıklamadır.
            return {
                "domain": "allergies",
                "params": {"category": category} if category else {},
                "count": len(items),
                "rendered_in_app": True,
                "note": (
                    "Kayıtlar kullanıcıya panelde gösterildi. Değerler bu yanıtta YOK "
                    "ve senin bağlamına girmedi — içerik hakkında tahminde BULUNMA. "
                    "Kullanıcı kayıtların yorumlanmasını isterse, panelde gördüğü ilgili "
                    "satırı paylaşmasını iste."
                ),
            }

        items, env = apply_limit(items, limit)
        return {
            **env,
            "allergies": [a.model_dump() for a in items],
        }
