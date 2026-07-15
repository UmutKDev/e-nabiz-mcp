"""Belge indirme tool'u (salt-okunur) — dört alanın PDF'i tek uçtan.

Önceden dört ayrı tool vardı; `enabiz_get_pathology_pdf` ile
`enabiz_get_discharge_summary_pdf` gövde gövdeye AYNI fonksiyondu (yalnız yol sabiti
ve dosya adı öneki farklıydı), diğer ikisi de aynı zarfla bitiyordu. Dördü de her
istekte ayrı şema olarak bağlam yiyordu.

Ayrıca boş/HTML yanıt guard'ı yalnız radyolojide vardı: epikriz/patoloji 0 baytlık
veya HTML hata sayfasını PDF diye kaydedip sha256'sıyla "başarılı" diyordu. Guard
artık tek yerde ve dördü için de geçerli.
"""

from __future__ import annotations

import base64
import datetime

from fastmcp import FastMCP

from .. import auth
from ..client import xhr_post
from ..config import Config
from ..downloads import save_download
from ._common import auth_guarded

RADYOLOJI_PAGE = "/Home/RadyolojikGoruntulerim"
_PATHS = {
    "lab": "/Tahlil/TahlillerPdf",
    "pathology": "/Patoloji/GetPatolojiPdf",
    "discharge": "/Epikriz/GetEpikrizPdf",
    "radiology": "/RadyolojikGoruntu/GetRaporPdfByOrder",
}
#: kind → (zorunlu parametreler, dosya adı öneki, kaynak liste tool'u)
_SPECS = {
    "lab": (("card_tarih", "kurum_kodu"), "tahlil", "enabiz_list_lab_tests"),
    "pathology": (("reference_no", "sys_no"), "patoloji", "enabiz_list_pathology"),
    "discharge": (("reference_no", "sys_no"), "epikriz", "enabiz_list_discharge_summaries"),
    "radiology": (("order_id",), "radyoloji_rapor", "enabiz_list_radiology_studies"),
}


def _missing(kind: str, given: dict) -> dict | None:
    required, _, source = _SPECS[kind]
    absent = [p for p in required if not given.get(p)]
    if not absent:
        return None
    return {
        "error": "missing_params",
        "message": f"kind={kind!r} için zorunlu parametre eksik: {', '.join(absent)}.",
        "hint": f"Bu alanları `{source}` çıktısındaki ilgili kayıttan alın.",
    }


def register(mcp: FastMCP) -> None:
    """Belge indirme tool'unu verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_download_document(
        kind: str,
        reference_no: str | None = None,
        sys_no: str | None = None,
        order_id: str | None = None,
        card_tarih: str | None = None,
        kurum_kodu: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
        dil: str = "tr-TR",
    ) -> dict:
        """Bir sağlık belgesinin PDF'ini indirir ve yerel diske kaydeder.

        `kind` ve ona ait parametreler (hepsi ilgili liste tool'unun çıktısından alınır):
          - `"lab"`       → `card_tarih` + `kurum_kodu` (`enabiz_list_lab_tests`).
                            Opsiyonel: `start_year`/`end_year`, `dil` (`tr-TR` | `en-US`).
          - `"pathology"` → `reference_no` + `sys_no` (`enabiz_list_pathology`).
          - `"discharge"` → `reference_no` + `sys_no` (`enabiz_list_discharge_summaries`).
          - `"radiology"` → `order_id` (`enabiz_list_radiology_studies`).

        PDF `ENABIZ_DOWNLOAD_DIR`'e (chmod 600) yazılır; **içerik LLM'e verilmez**,
        yalnız `{saved_path, byte_size, sha256, content_type}` döner — PHI diskte kalır.
        Kimlikli oturum gerektirir; yoksa `error: "auth_required"`.
        """
        if kind not in _SPECS:
            return {
                "error": "unknown_kind",
                "message": f"Bilinmeyen kind: {kind!r}.",
                "hint": f"Geçerli değerler: {', '.join(sorted(_SPECS))}.",
            }
        given = {
            "reference_no": reference_no, "sys_no": sys_no, "order_id": order_id,
            "card_tarih": card_tarih, "kurum_kodu": kurum_kodu,
        }
        if (err := _missing(kind, given)) is not None:
            return err

        cfg = Config.from_env()
        ctype = "application/pdf"
        with auth.session_scope(cfg) as client:
            if kind == "radiology":
                # Tek istisna: PDF, JSON içinde base64 gelir (GET binary değil).
                token = auth.scrape_token(client, RADYOLOJI_PAGE)
                resp = xhr_post(
                    client, _PATHS[kind], token, {"orderId": order_id}, referer=RADYOLOJI_PAGE
                )
                try:
                    b64 = resp.json().get("rapor")
                except ValueError:
                    b64 = None
                content = base64.b64decode(b64) if b64 else b""
            else:
                if kind == "lab":
                    this_year = datetime.date.today().year
                    params = {
                        "baslangicYil": str(start_year or this_year - 5),
                        "bitisYil": str(end_year or this_year),
                        "cardTarih": card_tarih,
                        "kurumKodu": kurum_kodu,
                        "dil": dil,
                        "sonucTuru": "",
                    }
                else:
                    params = {"referansNo": reference_no, "sysNo": sys_no}
                resp = client.get(_PATHS[kind], params=params)
                if b"TCKimlikNo" in resp.content[:5000]:
                    raise auth.AuthRequired("Oturum düşmüş görünüyor.")
                content = resp.content
                ctype = resp.headers.get("content-type", "application/pdf")

        # Guard eskiden yalnız radyolojide vardı: epikriz/patoloji 0 baytlık veya HTML
        # hata sayfasını PDF diye kaydedip sha256'sıyla "başarılı" diyordu.
        if not content:
            return {
                "error": "no_pdf",
                "message": f"{kind} PDF'i alınamadı (boş yanıt).",
                "hint": "Parametreleri liste tool'unun çıktısından birebir kopyalayın.",
            }
        if not content.startswith(b"%PDF-"):
            return {
                "error": "not_a_pdf",
                "message": f"Sunucu PDF yerine başka bir içerik döndürdü ({ctype}).",
                "hint": "Portal geçici olarak hata veriyor olabilir; sonra tekrar deneyin.",
            }

        prefix = _SPECS[kind][1]
        stem = order_id or card_tarih or reference_no
        name = f"{prefix}_{stem}_{kurum_kodu}.pdf" if kind == "lab" else f"{prefix}_{stem}.pdf"
        return {"kind": kind, **save_download(content, name, cfg.download_dir, ctype)}
