"""MHRS randevu listeleri (salt-okunur).

`tools/appointments.py` ile FARKI: o, e-Nabız'ın `/Home/Randevularim` HTML tablosunu
okur — randevu verisinin ÇIKTISI. Bu modül MHRS API'sinin kendisini okur ve
`hastaRandevuNumarasi` (hrn) döndürür; hrn iptalin anahtarıdır ve HTML tablosunda yok.

Aksiyon uçları (`iptal-et/{hrn}`, `randevu-ozellik/gizle/{hrn}`) KULLANILMAZ —
iptal Faz 3'te, iki-adımlı onayla gelir.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..config import Config
from ..mhrs.auth import mhrs_session
from ..mhrs.client import api_client, unwrap
from ._common import apply_limit, auth_guarded

UPCOMING_PATH = "kurum/randevu/yaklasan-randevularim"
HISTORY_PATH = "kurum/randevu/randevu-gecmisi"


def _text(value: Any) -> str | None:
    """Skaler bir alanı `str | None`'a indirger — ev kuralı: sayıya çevirme."""
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value)


def _zaman(raw: Any) -> dict:
    """`randevuBaslangicZamaniStr` gibi parçalı zaman nesnesini düzleştirir.

    MHRS zamanı hem ham (`randevuBaslangicZamani`) hem parçalanmış
    (`{tarih, gun, saat, zaman}`) gönderiyor. Parçalıyı taşıyoruz: sunucunun kendi
    biçimlendirmesi, bizim tarih ayrıştırma tahminimizden güvenilir.
    """
    if not isinstance(raw, dict):
        return {}
    keys = ("tarih", "gun", "saat", "zaman")
    return {k: _text(raw.get(k)) for k in keys if raw.get(k) is not None}


def _hekim(raw: dict) -> str | None:
    """Hekim adını birleştirir — uca göre alan adı DEĞİŞİR.

    `yaklasan-randevularim` / `randevu-gecmisi` hekimi PARÇALI verir
    (`mhrsHekimAd` + `mhrsHekimSoyad`); `randevu-arsiv` ise tek alanda
    (`hekimAdSoyad`). Bu, canlı doğrulamada yakalandı: parser yalnız `hekimAdSoyad`
    arıyordu ve hekim adı SESSİZCE düşüyordu — sunucu veriyi döndürüyor, kayıt
    "geçerli" görünüyor, yalnız bir alan eksik. Boş-sonuç invaryantı bu sınıfı
    yakalamaz; ancak canlı alan adı karşılaştırması yakalar.
    """
    birlesik = _text(raw.get("hekimAdSoyad"))
    if birlesik:
        return birlesik
    parts = [_text(raw.get("mhrsHekimAd")), _text(raw.get("mhrsHekimSoyad"))]
    ad = " ".join(p for p in parts if p).strip()
    return ad or None


def _appointment(raw: Any) -> dict | None:
    """Bir MHRS randevu DTO'sunu sözleşme alanlarına indirger.

    Beklenen anahtar yoksa `None` — sessiz yanlış-eşleme yerine boş sonuç
    (invaryant #2). `hastaRandevuNumarasi` zorunlu sayılır: onsuz kayıt bir randevu
    değildir ve Faz 3'te iptal edilemez.
    """
    if not isinstance(raw, dict):
        return None
    hrn = _text(raw.get("hastaRandevuNumarasi"))
    if hrn is None:
        return None

    durum = raw.get("randevuKayitDurumu")
    gecmis_durum = raw.get("randevuGecmisiRandevuDurumu")
    out: dict = {
        "hrn": hrn,
        "kurum_adi": _text(raw.get("kurumAdi")),
        "ana_kurum_adi": _text(raw.get("anaKurumAdi")),
        "klinik_adi": _text(raw.get("mhrsKlinikAdi")) or _text(raw.get("klinikAdi")),
        "hekim": _hekim(raw),
        "muayene_yeri": _text(raw.get("muayeneYeriAdi")),
        "randevu_turu": _text(raw.get("randevuTuruAdi")),
        "baslangic": _zaman(raw.get("randevuBaslangicZamaniStr")),
        "bitis": _zaman(raw.get("randevuBitisZamaniStr")),
        # `ek` = fazla mesai slotu, `shmMi` = sağlıklı hayat merkezi randevusu.
        "ek_slot": _text(raw.get("ek")),
        "shm_mi": _text(raw.get("shmMi")),
        # Faz 3'ün ihtiyacı: sunucu bu randevunun iptal edilebilir OLUP OLMADIĞINI
        # kendisi söylüyor. Kendi kuralımızı uydurmak yerine sunucuya soruyoruz.
        "iptal_edilebilir": _text(raw.get("iptalEdilebilirMi")),
        "iptal_son_zaman": _text(raw.get("iptalGecerlilikZamani")),
    }
    if isinstance(durum, dict):
        out["kayit_durumu"] = _text(durum.get("valText"))
    if isinstance(gecmis_durum, dict):
        out["randevu_durumu"] = _text(gecmis_durum.get("valText"))
    return {k: v for k, v in out.items() if v not in (None, {})}


def _bucket(data: Any, key: str) -> list[dict]:
    """Zarf içindeki bir DTO listesini randevulara çevirir; yoksa `[]`."""
    if not isinstance(data, dict):
        return []
    return [a for a in (_appointment(x) for x in data.get(key) or []) if a]


def register(mcp: FastMCP) -> None:
    """MHRS randevu listesi tool'larını verilen FastMCP örneğine kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_list_upcoming(limit: int | None = None) -> dict:
        """Yaklaşan MHRS randevularını listeler — salt-okunur.

        Her randevu `hrn` (hasta randevu numarası) taşır; iptal için gereken
        anahtar budur ve e-Nabız'ın HTML tablosunda bulunmaz.

        Bu tool randevu ALMAZ ve İPTAL ETMEZ. Kimlikli oturum gerektirir.

        - `limit`: en fazla kaç kayıt (varsayılan 50; `0` = sınırsız).
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.get(UPCOMING_PATH))
        items, env = apply_limit(_bucket(data, "aktifRandevuDtoList"), limit)
        return {**env, "appointments": items}

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_list_history(
        start_date: str | None = None,
        limit: int | None = None,
    ) -> dict:
        """Geçmiş MHRS randevularını listeler — salt-okunur.

        - `start_date`: `GG.AA.YYYY`. Verilmezse MHRS'nin varsayılan penceresi.
        - `limit`: en fazla kaç kayıt (varsayılan 50; `0` = sınırsız).

        Gizlenmiş randevular ayrı bir listede gelir ve `hidden_count` ile yalnız
        SAYISI bildirilir — kullanıcı onları kasten gizlemiş; içeriklerini modele
        açmak o kararı geri alır.
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        params = {"baslangicTarihi": start_date} if start_date else None
        with api_client(cfg, session.jwt) as client:
            data = unwrap(client.get(HISTORY_PATH, params=params))
        past = _bucket(data, "gecmisRandevuDtoList")
        items, env = apply_limit(past, limit)
        return {
            **env,
            "appointments": items,
            "hidden_count": len(_bucket(data, "gizliRandevuGecmisiDtoList")),
        }
