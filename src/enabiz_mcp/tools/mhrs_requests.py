"""MHRS randevu TALEBİ — "yer açılırsa haber ver" (listeleme okuma, oluştur/sil YAZMA).

Aradığınız kriterlere randevu yoksa MHRS randevu vermez ama **talep** kabul eder:
uygun bir yer açılınca kullanıcıya haber verir. `enabiz_mhrs_search_institutions`
`RND4033` uyarısı döndürdüğünde (istenen kurumda yer yok, yalnız alternatif var) bu
akış devreye girer.

Talep bir **randevu DEĞİLDİR** — hiçbir slot tutmaz, 15 günlük branş yasağı riski
taşımaz. Ama sunucuda kalıcı bir kayıt oluşturur ve bildirim tetikler, o yüzden
yazmadır ve `confirm=True` ister.

**Bu iddia kanıtlandı** (bir güvenlik dayanağı olduğu için): MHRS eşleşme bulunca
otomatik randevu AÇMAZ; kullanıcıya bildirim gider, kullanıcı linkten "Onayla" derse
`randevu-ekle` çağrılır, "Reddet" derse `randevu-talep-eslesme-red`. Yani randevu
ancak kullanıcının onayıyla oluşur (`vatandas-85-chunk.js`; bkz. `docs/findings/mhrs.md`).
Canlı bir talebin `"Randevu oluşturuldu"` durumu, o talebin KARŞILANMIŞ hâlidir —
otomatik bir yazma değil.

Bundle'daki akış (vatandas-45-chunk.js):
    GET  yonetim/genel/mesaj/by-kodu/GNL2030   → onay metni
    POST kurum/randevu-talep  {lhatirlatmaSaatSecimi, mhrsHekimId, mhrsKlinikId,
                               mhrsKurumId, muayeneYeriId}

Bundle ayrıca `HATIRLATMA_SAAT_SECIMI` lookup'ını çeker ama sonucunu ATAR (bkz.
`HATIRLATMA_SAAT`) — arayüzde bildirim saati seçeneği yoktur.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..config import Config
from ..mhrs.auth import mhrs_session
from ..mhrs.client import api_client, unwrap
from ._common import auth_guarded
from .mhrs_slots import ANY_ID, _id, _mesaj

TALEP_PATH = "kurum/randevu-talep"
TALEP_SEARCH_PATH = "kurum/randevu-talep/search"
TALEP_DELETE_PATH = "kurum/randevu-talep/{talep_id}"
TALEP_RENEW_PATH = "kurum/randevu-talep/yenile/{talep_id}"

#: Her zaman `"1"` — bu bir varsayılan DEĞİL, tek değer. Kullanıcı doğruladı:
#: arayüzde bildirim saati seçeneği YOK.
#:
#: Bundle yanıltıcı: `HATIRLATMA_SAAT_SECIMI` lookup'ını GET'liyor ve sonucu `V`'ye
#: `saatList` diye geçiyor. Ama V onu ATIYOR — virgül operatörü:
#:     n = (e.saatList, N({lhatirlatmaSaatSecimi:"1"}, e.talepBodyData))
#: `e.saatList` hesaplanır ve değeri düşer; gövdeye giren sabit `"1"`'dir. Tüm
#: bundle'da `lhatirlatmaSaatSecimi` yalnız burada, yalnız bu değerle geçer.
#:
#: Yani o GET ölü koddur. "Lookup çekiliyorsa seçilebiliyordur" çıkarımı yapıldı ve
#: YANLIŞTI — çağrının varlığı, sonucunun kullanıldığı anlamına gelmez.
HATIRLATMA_SAAT = "1"


def _ad(raw: Any, *keys: str) -> str | None:
    """İç içe bir nesneden ilk dolu alanı `str` olarak alır."""
    if not isinstance(raw, dict):
        return None
    for k in keys:
        v = raw.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def _talep(raw: Any) -> dict | None:
    """Bir talep kaydını sözleşme alanlarına indirger."""
    if not isinstance(raw, dict) or raw.get("id") is None:
        return None
    durum = raw.get("randevuTalepDurumu")
    out = {
        "talep_id": str(raw["id"]),
        "kurum": _ad(raw.get("kurum"), "kurumAdi", "kurumKisaAdi"),
        "klinik": _ad(raw.get("klinik"), "mhrsKlinikAdi", "kisaAdi"),
        "hekim": " ".join(
            x
            for x in (_ad(raw.get("hekim"), "ad"), _ad(raw.get("hekim"), "soyad"))
            if x
        ).strip()
        or None,
        "muayene_yeri": _ad(raw.get("muayeneYeri"), "adi"),
        "gecerlilik_zamani": _ad(raw, "gecerlilikZamani"),
        "durum": _ad(durum, "valText") if isinstance(durum, dict) else None,
        # Sunucu bu iki kararı KENDİ veriyor — kendi kuralımızı uydurmuyoruz.
        "silinebilir": _ad(raw, "talepSilinebilir"),
        "yenilenebilir": _ad(raw, "yenilenebilir"),
    }
    return {k: v for k, v in out.items() if v is not None}


def register(mcp: FastMCP) -> None:
    """MHRS randevu talebi tool'larını kaydeder."""

    @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_list_requests() -> dict:
        """Açık randevu taleplerini listeler — salt-okunur.

        Talep = "bu kriterlere uygun randevu açılırsa haber ver". Randevu DEĞİLDİR.
        Her kayıt `talep_id` taşır (silmek için) ve sunucunun verdiği `silinebilir` /
        `yenilenebilir` bayraklarını.
        """
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt) as client:
            resp = client.get(TALEP_SEARCH_PATH)
            data = unwrap(resp)
        # Bundle `e.data.data.data` okuyor — liste zarfın `data`'sının İÇİNDE bir
        # `data` alanında; iki katlı. Düz dizi de gelebilir, ikisini de karşıla.
        ham = data.get("data") if isinstance(data, dict) else data
        items = [t for t in (_talep(x) for x in (ham or [])) if t] if isinstance(ham, list) else []
        return {"count": len(items), "requests": items}

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_create_request(
        clinic_id: str,
        institution_id: str,
        doctor_id: str | None = None,
        exam_place_id: str | None = None,
        confirm: bool = False,
    ) -> dict:
        """**Randevu TALEBİ oluşturur** — yer açılınca MHRS haber verir. `confirm=True` şart.

        Ne zaman: `enabiz_mhrs_search_institutions` `RND4033` uyarısı döndürdüğünde,
        yani istenen kurum/klinikte randevu yokken.

        Bu bir randevu DEĞİLDİR: slot tutmaz, 15 günlük branş yasağı riski taşımaz.
        Ama sunucuda kalıcı kayıt açar ve bildirim tetikler — o yüzden yazmadır.

        - `clinic_id` / `institution_id`: aramada kullandığınız id'ler.
        - `doctor_id` / `exam_place_id`: verilmezse "farketmez" (`-1`).
        - `confirm`: kullanıcı açıkça onaylamadan `True` GEÇMEYİN.

        **Belirli bir hekim için talep** (geçmiş randevudan tekrar akışı): `doctor_id`
        geçin — `enabiz_mhrs_rebook_criteria`'nın döndürdüğü id. Canlıda doğrulandı:
        talep hekim adıyla oluşuyor. `doctor_id` geçilmezse talep KURUM+KLİNİK
        geneline açılır ve herhangi bir hekimin boşluğu bildirim tetikler — sessizce
        farklı bir şey, o yüzden hangisinin istendiğini kullanıcıya sorun.
        """
        if not confirm:
            return {
                "error": "confirm_required",
                "message": (
                    "Talep oluşturulmadı. Kullanıcıya hangi kurum/klinik için talep "
                    "açılacağını gösterip onay alın, sonra confirm=True ile çağırın."
                ),
            }
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        body = {
            "lhatirlatmaSaatSecimi": HATIRLATMA_SAAT,
            "mhrsHekimId": _id(doctor_id),
            "mhrsKlinikId": _id(clinic_id),
            "mhrsKurumId": _id(institution_id),
            "muayeneYeriId": _id(exam_place_id),
        }
        with api_client(cfg, session.jwt, allow_write=True) as client:
            resp = client.post(TALEP_PATH, json=body)
            unwrap(resp)
            mesaj = None
            envelope = resp.json()
            if isinstance(envelope, dict):
                for w in (envelope.get("infos") or []) + (envelope.get("warnings") or []):
                    if isinstance(w, dict) and (m := _mesaj(w.get("mesaj"))):
                        mesaj = m
                        break
        out: dict = {"created": True}
        if mesaj:
            out["message"] = mesaj
        return out

    @mcp.tool(annotations={"readOnlyHint": False, "openWorldHint": True})
    @auth_guarded
    def enabiz_mhrs_delete_request(request_id: str, confirm: bool = False) -> dict:
        """Randevu talebini siler. `confirm=True` şart.

        - `request_id`: `enabiz_mhrs_list_requests`'ten gelen `talep_id`.
        """
        if not confirm:
            return {
                "error": "confirm_required",
                "message": "Talep silinmedi. Kullanıcıya gösterip onay alın, sonra confirm=True.",
            }
        cfg = Config.from_env()
        session = mhrs_session(cfg)
        with api_client(cfg, session.jwt, allow_write=True) as client:
            unwrap(client.delete(TALEP_DELETE_PATH.format(talep_id=request_id)))
        return {"deleted": True, "request_id": request_id}


__all__ = ["ANY_ID", "register"]
