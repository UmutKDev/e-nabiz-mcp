"""Domain kaydı — hangi veri alanı hangi fetch'e, şemaya ve widget'a bağlı.

Tek doğruluk kaynağı: `enabiz_ui_data` veriyi buradan çeker, `resources.py`
widget URI'lerini buradan doğrular, tool'lar `resource_uri`'yi buradan alır.
Üç yerde ayrı ayrı yazılsaydı biri kayınca widget SESSİZCE boş açılırdı
(invaryant #2: sessiz yanlış-eşleme boş sonuçtan kötüdür).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..tools.allergies import fetch_allergies
from . import schema


@dataclass(frozen=True)
class Domain:
    """Bir veri alanının ucu: nasıl çekilir, nasıl görünür, nerede render edilir."""

    name: str
    schema: schema.DomainSchema
    #: Model nesnesi listesi döner (`list[BaseModel]`). Zarflama/`model_dump`
    #: çağıranın işi — bkz. `tools/allergies.py:fetch_allergies`.
    fetch: Callable[..., list[Any]]


#: Kayıtlı alanlar. Faz 0 yalnız `allergies` — desen kanıtlanmadan yayılmıyor.
DOMAINS: dict[str, Domain] = {
    "allergies": Domain(
        name="allergies",
        schema=schema.ALLERGIES,
        fetch=fetch_allergies,
    ),
}


def get(name: str) -> Domain | None:
    """Alanı ada göre döner; yoksa `None` — çağıran hata sözlüğü üretir."""
    return DOMAINS.get(name)


def widget_uris() -> set[str]:
    """Kayıtlı alanların işaret ettiği tüm widget URI'leri."""
    return {d.schema.widget_uri for d in DOMAINS.values()}
