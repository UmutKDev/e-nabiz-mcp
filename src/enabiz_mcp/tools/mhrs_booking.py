"""MHRS randevu alma ve iptal — **YAZMA** (`readOnlyHint: False`).

Projenin salt-okunur invaryantından bilinçli sapma; gerekçe `docs/notes/decisions.md`
D7. e-Nabız **sağlık verisi** salt-okunur KALIR; yazma yalnız burada, yalnız MHRS
randevu alanında.

**İki adımlı onay — `login_start`/`login_verify` deseninin aynası:**

    book_prepare(slot_id)  → slotu sunucuda doğrular, insan-okunur özet + confirm_token
    book_confirm(token)    → randevuyu ALIR

Neden tek adımlı `book(slot_id)` YOK: yanlış randevunun gerçek bir bedeli var. T.C.
Sağlık Bakanlığı politikası (saglik.gov.tr TR,94138) — randevusuna gitmeyen ve iptal
etmeyen kişi **aynı branştan 15 gün** randevu alamaz. (Para cezası iddiası YALAN;
AA Teyit "Yanlış" damgalı.) Tek adımlı bir tool'da modelin uydurduğu bir slot id
kullanıcıya gerçek bir branş yasağı yazdırabilir. `confirm_token` bunu YAPISAL olarak
engeller: token yalnız `book_prepare`'in sunucuda DOĞRULADIĞI slot için üretilir ve
süreç belleğinde tutulur — model onu uyduramaz.

⚠️ `book_prepare` masum DEĞİL: `randevu-bilgileri?fkSlotId=` sunucuda slot kilidi
kuruyor olabilir (istemci onay modalı iptal edilince `DELETE slot-kilitleme`
çağırıyor). Bu yüzden `readOnlyHint: True` DEĞİL ve `book_cancel_prepare` kilidi
bırakır.
"""

from __future__ import annotations

import secrets
from typing import Any

from fastmcp import FastMCP

from ..config import Config
from ..mhrs.auth import mhrs_session
from ..mhrs.client import api_client, unwrap
from ._common import auth_guarded

SLOT_INFO_PATH = "kurum/randevu/slot-sorgulama/randevu-bilgileri"
BOOK_PATH = "kurum/randevu/randevu-ekle"
UNLOCK_PATH = "kurum/randevu/slot-kilitleme"
CANCEL_PATH = "kurum/randevu/iptal-et/{hrn}"

#: MHRS'nin beklediği tarih biçimi (bundle: `restDateFormat.dateTime`).
DATETIME_FMT = "YYYY-MM-DD HH:mm:ss"

#: `confirm_token` → doğrulanmış randevu-ekle gövdesi. SÜREÇ BELLEĞİNDE tutulur,
#: diske YAZILMAZ ve LLM'e VERİLMEZ. Modelin gördüğü tek şey opak token'dır; gövdeyi
#: uyduramaz, çünkü gövde sunucunun doğruladığı slottan üretildi.
_PENDING: dict[str, dict] = {}


def _text(v: Any) -> str | None:
    if v is None or isinstance(v, (dict, list)):
        return None
    return str(v)


def _ozet(data: dict) -> dict:
    """Sunucunun slot yanıtından insan-okunur özet — kullanıcı BUNU onaylayacak."""
    slot = data.get("slot") if isinstance(data.get("slot"), dict) else {}
    klinik = data.get("klinik") if isinstance(data.get("klinik"), dict) else {}
    kurum = data.get("kurum") if isinstance(data.get("kurum"), dict) else {}
    my = data.get("muayeneYeri") if isinstance(data.get("muayeneYeri"), dict) else {}
    bas = data.get("randevuBaslangicZamaniStr")
    bas = bas if isinstance(bas, dict) else {}
    bit = data.get("randevuBitisZamaniStr")
    bit = bit if isinstance(bit, dict) else {}
    out = {
        "kurum": _text(kurum.get("anaKurumAdi")) or _text(kurum.get("kurumAdi")),
        "klinik": _text(klinik.get("mhrsKlinikAdi")),
        "muayene_yeri": _text(my.get("adi")),
        "tarih": _text(bas.get("tarih")),
        "gun": _text(bas.get("gun")),
        "saat": _text(bas.get("saat")),
        "bitis_saati": _text(bit.get("saat")),
        "ek_slot": _text(data.get("ek")),
        "slot_baslangic": _text(slot.get("baslangicZamani")),
    }
    return {k: v for k, v in out.items() if v is not None}


def register(mcp: FastMCP) -> None:
    """MHRS randevu YAZMA tool'larını kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_book_prepare(slot_id: str) -> dict:
        """Randevu almadan ÖNCE slotu sunucuda doğrular ve onay özeti döndürür.

        **Randevu ALMAZ.** Ama masum de değil: MHRS bu çağrıda slotu geçici olarak
        kilitliyor olabilir — bu yüzden `readOnlyHint: False` ve vazgeçerseniz
        `enabiz_mhrs_book_cancel_prepare` çağırın.

        - `slot_id`: `enabiz_mhrs_search_slots`'tan gelen `slot_id`. UYDURMAYIN —
          uydurma id ya hata döner ya da BAŞKA birinin slotunu doğrular.

        Dönen `confirm_token`'ı kullanıcıya GÖSTERMEYİN; önce `summary`'yi gösterip
        **kullanıcıdan açık onay alın**, sonra `enabiz_mhrs_book_confirm(token)`.
        Onay almadan confirm çağırmayın: yanlış randevu, gitmediğiniz takdirde aynı
        branştan 15 gün randevu yasağı demektir.
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.get(SLOT_INFO_PATH, params={"fkSlotId": slot_id}))
        if not isinstance(data, dict):
            return {"error": "mhrs_error", "message": "Slot bilgisi beklenen şekilde gelmedi."}

        slot = data.get("slot") if isinstance(data.get("slot"), dict) else {}
        if slot.get("id") is None or slot.get("fkCetvelId") is None:
            return {
                "error": "mhrs_error",
                "message": "Slot doğrulanamadı (id/cetvel yok) — dolmuş olabilir.",
            }

        my = data.get("muayeneYeri") if isinstance(data.get("muayeneYeri"), dict) else {}
        # Gövde SUNUCUNUN döndürdüğü slottan kurulur — tool argümanından değil.
        body = {
            "fkSlotId": slot["id"],
            "fkCetvelId": slot["fkCetvelId"],
            "yenidogan": False,
            "muayeneYeriId": my.get("id", -1),
            "baslangicZamani": slot.get("baslangicZamani"),
            "bitisZamani": slot.get("bitisZamani"),
            "randevuNotu": "",
        }
        token = secrets.token_urlsafe(24)
        _PENDING[token] = body
        return {
            "confirm_token": token,
            "summary": _ozet(data),
            "next": (
                "Bu özeti kullanıcıya gösterin ve AÇIK ONAY alın. Onaylarsa "
                "enabiz_mhrs_book_confirm(confirm_token) çağırın — o çağrı GERÇEK "
                "randevu alır. Vazgeçerse enabiz_mhrs_book_cancel_prepare çağırın."
            ),
        }

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_book_confirm(confirm_token: str) -> dict:
        """**GERÇEK RANDEVU ALIR.** Yalnız kullanıcı açık onay verdikten sonra çağırın.

        - `confirm_token`: `enabiz_mhrs_book_prepare`'in döndürdüğü token.

        Token `book_prepare`'den gelmiyorsa reddedilir — bu, modelin uydurduğu bir
        slot id ile randevu almasını YAPISAL olarak engeller. Token tek kullanımlıktır.
        """
        body = _PENDING.pop(confirm_token, None)
        if body is None:
            return {
                "error": "invalid_token",
                "message": (
                    "confirm_token geçersiz veya kullanılmış. Randevu ALINMADI. "
                    "Önce enabiz_mhrs_book_prepare(slot_id) çağırın."
                ),
            }
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        # allow_write=True — AÇIK niyet beyanı; yazma kapısı yalnız burada açılır.
        with api_client(cfg, session.jwt, allow_write=True) as client:
            data = unwrap(client.post(BOOK_PATH, json=body))
        out = {"booked": True}
        if isinstance(data, dict):
            hrn = _text(data.get("hastaRandevuNumarasi"))
            if hrn:
                out["hrn"] = hrn
        return out

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_book_cancel_prepare(confirm_token: str) -> dict:
        """Hazırlanan randevudan vazgeçer ve sunucudaki slot kilidini bırakır.

        `book_prepare` sonrası kullanıcı vazgeçerse çağırın — aksi hâlde slot bir süre
        başkasına da kapalı kalabilir.
        """
        vardi = _PENDING.pop(confirm_token, None) is not None
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt, allow_write=True) as client:
            unwrap(client.delete(UNLOCK_PATH))
        return {"released": True, "token_vardi": vardi}

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_cancel(hrn: str, confirm: bool = False) -> dict:
        """**RANDEVU İPTAL EDER.** `confirm=True` zorunlu.

        - `hrn`: `enabiz_mhrs_list_upcoming`'den gelen hasta randevu numarası.
        - `confirm`: kullanıcı açıkça onaylamadan `True` GEÇMEYİN.

        MHRS bu ucu **GET** ile sunar (`iptal-et/{hrn}`) — ama yazmadır. `hrn`'i
        uydurmayın; listeden alın.
        """
        if not confirm:
            return {
                "error": "confirm_required",
                "message": (
                    "İptal edilmedi. Kullanıcıya hangi randevunun iptal edileceğini "
                    "gösterip onay alın, sonra confirm=True ile çağırın."
                ),
            }
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt, allow_write=True) as client:
            unwrap(client.get(CANCEL_PATH.format(hrn=hrn)))
        return {"cancelled": True, "hrn": hrn}
