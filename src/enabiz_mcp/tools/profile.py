"""Profil tool'ları (salt-okunur).

GET /Home/ProfilBilgilerim → sayfada render edilen profil verisi (inline `orgData`
JS objesi + kimlik kartı). Yalnız okunur; `KiloBoyGuncelle`/`ProfilGuncelle` gibi
yazma uçlarına dokunulmaz. Gizlilik: TCKN/e-posta/telefon çıktıya DAHİL EDİLMEZ.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .. import auth
from ..config import Config
from ..parsers import parse_profile
from ._common import auth_guarded

PAGE = "/Home/ProfilBilgilerim"


def register(mcp: FastMCP) -> None:
    """Profil tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_get_profile() -> dict:
        """E-Nabız profil özetini döndürür — salt-okunur.

        Ad soyad, doğum tarihi, **kan grubu**, boy, kilo ve aile hekimi bilgisini
        döndürür. Gizlilik gereği TCKN, e-posta ve telefon **dahil edilmez**.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        cfg = Config.from_env()
        with auth.session_scope(cfg) as client:
            html = client.get(PAGE).text
            if 'name="TCKimlikNo"' in html:
                raise auth.AuthRequired("Oturum düşmüş görünüyor.")
            profile = parse_profile(html)

        return {"profile": profile.model_dump()}
