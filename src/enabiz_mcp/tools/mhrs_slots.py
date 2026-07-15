"""MHRS kurum arama ve slot listeleme (salt-okunur).

İki uç da **gövdeli POST'tur ama OKUMA'dır** — filtre nesnesi query string'e sığmıyor.
`discovery._READ_POSTS` bunları adı adına istisna eder; varsayılan "POST = yazma"
olarak kalır (bkz. `docs/findings/mhrs.md`).

Zincir: `search_institutions` (arama) → adaylar → `search_slots` (slot) → boş saatler
→ `mhrs_booking.book_prepare(slot_id)`.

`aksiyon_id` TAHMİN EDİLEMEZ: arama sonucundaki `aksiyon.id`'den gelir. Slot ucu onu
zorunlu ister; bu yüzden slot doğrudan çağrılamaz, önce arama gerekir.

**Bu tool'lar döngüde çağrılmaz.** MHRS aşırı sorguyu `RNDS1010` ile karşılar ve
reCAPTCHA ister; captcha çözmüyoruz (invaryant #4), yani tekrar denemenin faydası
yok — yalnız eşiği derinleştirir.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..config import Config
from ..mhrs.auth import mhrs_session
from ..mhrs.client import api_client, unwrap
from ._common import auth_guarded

ARAMA_PATH = "kurum-rss/randevu/slot-sorgulama/arama"
SLOT_PATH = "kurum-rss/randevu/slot-sorgulama/slot"

#: "Farketmez / hepsi" sentinel'i — MHRS her boş form alanı için bunu gönderir.
ANY_ID = -1

#: Normal muayene randevusu. Bundle bunu varsayılan olarak kullanıyor
#: (`aksiyonId: e.hekimCalismaSaatiAksiyonId || 200`). Diğer değerler arama
#: sonucundaki `aksiyon.id`'den gelir — uydurulmaz.
DEFAULT_AKSIYON_ID = 200

#: Bundle'da SABİT KODLU (`cinsiyet:"F"`, vatandas-18-chunk.js) — formda cinsiyet
#: seçimi yok. Muhtemelen "Farketmez", ama bundle bunu doğrulamıyor; sabit tutmak
#: tarayıcının davranışını birebir taklit etmenin en güvenli yolu.
CINSIYET = "F"


def _id(value: str | None) -> int:
    """Tool argümanını MHRS'nin beklediği int id'ye çevirir; boşsa `-1`.

    MHRS gövdede int ister (tarayıcı `parseFloat` uyguluyor) — bu, sözleşmenin
    kendisi, bizim yorumumuz değil. Ev kuralı "değerler str kalır" ÇIKTI'ya dairdir;
    burası giden istek.

    `int(value) or ANY_ID` YAZILMAZ: `0` falsy'dir ve sessizce `-1`'e düşerdi.
    MHRS'nin kendi bundle'ı bu hatayı yapıp elle telafi ediyor
    (`mhrsHekimId: 0 !== e.mhrsHekimId ? e.mhrsHekimId : -1`).
    """
    if value is None or value == "":
        return ANY_ID
    try:
        return int(str(value).strip())
    except ValueError:
        return ANY_ID


def _saat(raw: Any) -> dict | None:
    """Tek bir saat slotunu indirger. `slot.id` `book_prepare`'in anahtarıdır."""
    if not isinstance(raw, dict):
        return None
    slot = raw.get("slot") if isinstance(raw.get("slot"), dict) else {}
    sid = slot.get("id")
    if sid is None:
        return None
    return {
        "slot_id": str(sid),
        "saat": str(raw["saatStr"]) if raw.get("saatStr") is not None else None,
        "bos": str(raw["bos"]) if raw.get("bos") is not None else None,
        # `ek` = fazla mesai slotu (bundle'da ayrı liste: saatSlotListEk).
        "ek": str(raw["ek"]) if raw.get("ek") is not None else None,
    }


def _gun(raw: Any) -> dict | None:
    """Bir günün slot ağacını düzleştirir: gün → hekim → muayene yeri → saatler."""
    if not isinstance(raw, dict) or raw.get("gun") is None:
        return None
    hekimler: list[dict] = []
    for h in raw.get("hekimSlotList") or []:
        if not isinstance(h, dict):
            continue
        hekim = h.get("hekim") if isinstance(h.get("hekim"), dict) else {}
        ad = " ".join(
            str(hekim[k]) for k in ("ad", "soyad") if hekim.get(k)
        ).strip()
        saatler: list[dict] = []
        for my in h.get("muayeneYeriSlotList") or []:
            if not isinstance(my, dict):
                continue
            # `saatSlotListEk` ayrı bir liste — fazla mesai slotları. İkisi de gerçek
            # randevu saatidir; bundle da ikisini birleştiriyor (`.concat`).
            for s in (my.get("saatSlotList") or []) + (my.get("saatSlotListEk") or []):
                item = _saat(s)
                if item:
                    item["muayene_yeri"] = (
                        str(my["muayeneYeri"]["adi"])
                        if isinstance(my.get("muayeneYeri"), dict)
                        and my["muayeneYeri"].get("adi")
                        else None
                    )
                    saatler.append(item)
        if saatler or ad:
            hekimler.append(
                {
                    "hekim": ad or None,
                    "hekim_id": str(hekim["mhrsHekimId"]) if hekim.get("mhrsHekimId") else None,
                    "saatler": saatler,
                }
            )
    return {"gun": str(raw["gun"]), "hekimler": hekimler}


def _aday(raw: Any) -> dict | None:
    """Arama sonucundaki bir adayı indirger — `aksiyon_id` slot çağrısının anahtarı."""
    if not isinstance(raw, dict):
        return None
    kurum = raw.get("kurum") if isinstance(raw.get("kurum"), dict) else {}
    klinik = raw.get("klinik") if isinstance(raw.get("klinik"), dict) else {}
    hekim = raw.get("hekim") if isinstance(raw.get("hekim"), dict) else {}
    aksiyon = raw.get("aksiyon") if isinstance(raw.get("aksiyon"), dict) else {}
    if not kurum.get("mhrsKurumId"):
        return None
    ad = " ".join(str(hekim[k]) for k in ("ad", "soyad") if hekim.get(k)).strip()
    out = {
        "kurum_id": str(kurum["mhrsKurumId"]),
        "kurum_adi": str(kurum["kurumAdi"]) if kurum.get("kurumAdi") else None,
        "ilce_id": str(kurum["mhrsIlceId"]) if kurum.get("mhrsIlceId") else None,
        "klinik_id": str(klinik["mhrsKlinikId"]) if klinik.get("mhrsKlinikId") else None,
        "klinik_adi": str(klinik["mhrsKlinikAdi"]) if klinik.get("mhrsKlinikAdi") else None,
        "cetvel_tipi": (
            str(klinik["lcetvelTipi"]) if klinik.get("lcetvelTipi") is not None else None
        ),
        "hekim": ad or None,
        "hekim_id": str(hekim["mhrsHekimId"]) if hekim.get("mhrsHekimId") else None,
        "aksiyon_id": str(aksiyon["id"]) if aksiyon.get("id") is not None else None,
        "en_erken": str(raw["baslangicZamani"]) if raw.get("baslangicZamani") else None,
    }
    return {k: v for k, v in out.items() if v is not None}


_NO_POLL = (
    "Bu tool'u DÖNGÜDE çağırmayın. MHRS aşırı sorguyu RNDS1010 ile karşılar ve "
    "reCAPTCHA ister; captcha çözülmediği için tekrar denemek yalnız eşiği "
    "derinleştirir ve kullanıcıyı online randevudan çıkarabilir."
)


def register(mcp: FastMCP) -> None:
    """MHRS arama/slot tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_search_institutions(
        clinic_id: str,
        province_id: str,
        district_id: str | None = None,
        institution_id: str | None = None,
        doctor_id: str | None = None,
        aksiyon_id: str | None = None,
    ) -> dict:
        """Randevu verilebilen kurum/klinik/hekim adaylarını arar — salt-okunur, YAZMAZ.

        Randevu zincirinin ilk adımı. Dönen her aday `aksiyon_id` taşır;
        `enabiz_mhrs_search_slots` onu ZORUNLU ister ve tahmin edilemez — bu yüzden
        slot araması doğrudan yapılamaz, önce buradan geçilir.

        - `clinic_id` / `province_id`: `enabiz_mhrs_list_clinics` / `list_provinces`'ten.
        - `district_id` / `institution_id` / `doctor_id`: verilmezse "farketmez".

        Gövdeli POST'tur ama okumadır; randevu ALMAZ.
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        body = {
            "aksiyonId": _id(aksiyon_id) if aksiyon_id else DEFAULT_AKSIYON_ID,
            "cinsiyet": CINSIYET,
            "mhrsHekimId": _id(doctor_id),
            "mhrsIlId": _id(province_id),
            "mhrsIlceId": _id(district_id),
            "mhrsKlinikId": _id(clinic_id),
            "mhrsKurumId": _id(institution_id),
            "muayeneYeriId": ANY_ID,
            "tumRandevular": False,
            "ekRandevu": True,
            "randevuZamaniList": [],
        }
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.post(ARAMA_PATH, json=body))

        if not isinstance(data, dict):
            return {"count": 0, "candidates": [], "note": _NO_POLL}
        adaylar: list[dict] = []
        for bucket in ("hastane", "semt", "alternatif"):
            for x in data.get(bucket) or []:
                a = _aday(x)
                if a:
                    a["grup"] = bucket
                    adaylar.append(a)
        return {"count": len(adaylar), "candidates": adaylar, "note": _NO_POLL}

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_search_slots(
        aksiyon_id: str,
        institution_id: str,
        clinic_id: str,
        province_id: str,
        district_id: str | None = None,
        doctor_id: str | None = None,
    ) -> dict:
        """Seçilen kurum/klinik için gün gün boş randevu saatlerini listeler — YAZMAZ.

        Argümanların hepsi `enabiz_mhrs_search_institutions` sonucundan gelir;
        özellikle `aksiyon_id` UYDURULMAZ.

        Dönen her saat bir `slot_id` taşır — randevu almak için
        `enabiz_mhrs_book_prepare(slot_id)` ile devam edin. Bu tool randevu ALMAZ.
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        body = {
            "aksiyonId": _id(aksiyon_id),
            "mhrsKurumId": _id(institution_id),
            "mhrsKlinikId": _id(clinic_id),
            "mhrsHekimId": _id(doctor_id),
            "mhrsIlId": _id(province_id),
            "mhrsIlceId": _id(district_id),
            "muayeneYeriId": ANY_ID,
            "cinsiyet": CINSIYET,
            "tumRandevular": False,
            "ekRandevu": True,
            "randevuZamaniList": [],
        }
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.post(SLOT_PATH, json=body))

        # Sunucu iki şekil kullanıyor: düz dizi ya da {responseData: [...]}.
        if isinstance(data, dict):
            data = data.get("responseData")
        gunler = [g for g in (_gun(x) for x in (data or [])) if g] if isinstance(data, list) else []
        return {"count": len(gunler), "days": gunler, "note": _NO_POLL}
