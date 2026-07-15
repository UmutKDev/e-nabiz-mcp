"""Widget kolon şemaları — saf veri, I/O yok, FastMCP bağımlılığı yok.

Parser'lar her değeri `str`/`str | None` olarak çıkarır (CLAUDE.md); model
alanları hangi kolonun başlık, hangisinin not olduğunu SÖYLEMEZ. O bilgi burada
durur ve widget'ı sürer.

D6: `key` alanları ASCII/İngilizce (model alan adlarıyla birebir), `label` ve
`values` Türkçe (kullanıcıya görünen metin).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

#: Bir kolonun widget'taki görsel rolü. Kronoloji düzeninde:
#:   date  → zaman omurgasındaki tik (domain başına TAM BİR tane)
#:   title → satırın birincil satırı
#:   chip  → küçük, versal, çerçeveli etiket (RENKSİZ — bkz. table.html renk notu)
#:   note  → ikincil, sönük satır
#:   meta  → üçüncül, satır-içi ayrıntı
Role = Literal["date", "title", "chip", "note", "meta"]

#: Jenerik zaman-omurgalı tablo — kronolojik liste alanlarının varsayılan widget'ı.
#: Burada durur (registry'de değil) çünkü hem `tools/*` hem `ui/*` okur; registry
#: `tools/*`'ı import ettiği için oradan okumak döngü kurar.
TABLE_URI = "ui://enabiz/table.html"


@dataclass(frozen=True)
class Column:
    """Tek bir model alanının widget'ta nasıl görüneceği."""

    key: str
    label: str
    role: Role = "meta"
    #: Slug → Türkçe görünen ad (yalnız `chip` rolü için anlamlı).
    #: Parser'ın atadığı ASCII slug'lar burada Türkçeleşir; `tr_lower` BURAYA
    #: GİRMEZ — slug zaten ASCII (CLAUDE.md: `tr_lower("DIGER")=="dığer"`).
    values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainSchema:
    """Bir veri alanının widget sözleşmesi."""

    #: Widget başlığı (Türkçe, kullanıcıya görünür).
    title: str
    columns: tuple[Column, ...]
    #: Kayıt yokken gösterilecek metin. Boş liste bir HATA DEĞİL: e-Nabız yalnız
    #: hastanelerin bildirdiğini tutar. Kullanıcı bunu bilmezse boşluğu arıza sanır.
    empty_text: str = "Bu alanda kayıt bulunamadı."
    #: Bu alanı render eden widget. Tool'un `resource_uri`'si ve kaynak kaydı AYNI
    #: buradan okur — iki yerde yazılsaydı biri kayınca widget sessizce boş açılırdı.
    widget_uri: str = TABLE_URI


ALLERGIES = DomainSchema(
    title="Alerjiler",
    columns=(
        Column(key="date", label="Tarih", role="date"),
        Column(
            key="category",
            label="Tür",
            role="chip",
            values={"ilac": "İlaç", "tani": "Tanı", "deri": "Deri testi"},
        ),
        Column(key="drug_name", label="İlaç", role="title"),
        Column(key="allergy_type", label="Alerji türü", role="meta"),
        Column(key="symptoms", label="Belirtiler", role="note"),
    ),
    empty_text=(
        "Alerji kaydı bulunamadı. E-Nabız yalnız sağlık kuruluşlarının bildirdiği kayıtları tutar."
    ),
)
