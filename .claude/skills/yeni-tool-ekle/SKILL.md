---
name: yeni-tool-ekle
description: Use when adding a new read-only E-Nabız MCP tool (a new data endpoint surfaced as enabiz_* ) to this repo — walks endpoint→parser→tool module→server registration→fixture+test→docs, end to end. Covers the read-only invariant, readOnlyHint policy, and the two-file server registration trap.
---

# Yeni tool ekle (uçtan uca)

Yeni bir salt-okunur E-Nabız veri ucunu `enabiz_*` tool'u olarak ekler. Her adımı bir
task'a çevir ve sırayla ilerle. Kırmızı çizgi: **hiçbir yazma/mutasyon ucu çağrılmaz**
(bkz. `CLAUDE.md` invaryant #1).

## Checklist

1. **Endpoint'i doğrula.** Ucun GET/POST yolu, param adları ve dönen kabın (tablo id /
   CSS class) `docs/findings/discovery-report.md` veya `docs/findings/endpoints.md`'de
   var mı? Yoksa **`endpoint-kesfet` skill'ini** çalıştır — uydurma endpoint yazma.

2. **Parser yaz.** `parsers.py`'ye ekle. Deseni **`yeni-parser-ekle` skill'i** anlatır:
   tam tablo id (fallback yok), `_rows()`/`_cell()`, değerler `str`, Pydantic model
   (İngilizce alan adı + Türkçe `description`).

3. **Tool modülü oluştur** — `src/enabiz_mcp/tools/<domain>.py`. `tools/allergies.py`'yi
   birebir örnek al:
   ```python
   from fastmcp import FastMCP
   from .. import auth
   from ..config import Config
   from ..parsers import parse_<domain>
   from ._common import apply_limit, auth_guarded

   PAGE = "/Home/<Endpoint>"

   def register(mcp: FastMCP) -> None:
       @mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
       @auth_guarded
       def enabiz_list_<domain>(limit: int | None = None) -> dict:
           """<Türkçe açıklama>. Salt-okunur; oturum gerektirir."""
           cfg = Config.from_env()
           with auth.session_scope(cfg) as client:
               html = client.get(PAGE).text
               if 'name="TCKimlikNo"' in html:
                   raise auth.AuthRequired("Oturum düşmüş görünüyor.")
               items = parse_<domain>(html)
           items, env = apply_limit(items, limit)
           return {**env, "<domain>": [i.model_dump() for i in items]}
   ```
   - Decorator sırası: `@mcp.tool` **dış**, `@auth_guarded` **iç**.
   - Elle try/except yazma — `auth_guarded` `AuthRequired`'ı `{"error":"auth_required",…}`
     sözlüğüne çevirir.
   - Liste zarfını `apply_limit` üretir: `limit` varsayılan 50, `0`=sınırsız, dönen
     `count`/`total`/`truncated` (`tools/_common.py:17-32`).
   - `readOnlyHint`: yalnız uzak portal mutasyonu varsa `False`. Yerel dosya yazan ya da
     ağ probu yapan tool bile `True` kalır (bkz. `download`, `session_status`).

4. **`server.py`'de kaydet — İKİ düzenleme, ikisi de şart:**
   - `from .tools import (...)` bloğuna (`server.py:14-33`) modülü **alfabetik** ekle.
   - Doğru grup yorumunun altında `<domain>.register(mcp)` çağır (`server.py:91-116`).
   - `register()` çağrısını unutursan tool **sessizce hiç yüklenmez** — hata da vermez.

5. **Sentetik fixture + test.**
   - `tests/fixtures/<domain>_sample.html` — **PHI yok**, en üstte `<!-- SENTETİK -->`
     yorumu; parser'ın beklediği tam tablo id'sini ve birkaç uydurma satır içerir.
   - Test dosyası: fixture'ı `conftest.fixture_html("<domain>_sample")` ile yükle.
   - **Liste tool'u için smoke kapsamı:** tool adı `enabiz_list_*` OLMALI **ve** modül
     `tests/test_tools_smoke.py` içindeki `_MODULES` tuple'ına eklenmeli. İkisi birden
     olmazsa tool **sıfır smoke kapsamı** alır (`>=` sayı assertion'ı yalnız var olan
     lister kaybolursa tetiklenir, yenisini yakalamaz).
   - Parser robustness: `tests/test_parser_robustness.py` desenini izle — nav-only sayfa
     `[]` dönmeli; tablo tbody'siz de gelse satırlar okunmalı.

6. **Doğrula.** `uv run pytest && uv run ruff check`. İkisi de yeşil olmadan bitmiş sayma.

7. **Dokümanı güncelle.** `surum-guncelle` skill'ini çalıştır (STATUS.md/README sayıları,
   tool listesi, commit trailer).

## Kaçınılacaklar
- Yeni tool'a `readOnlyHint: False` verme — yalnız login tool'ları yan etkili.
- Yeni tool'u `server.py` içine inline yazma; auth tool'ları dışında hepsi `register()`
  closure'ı olur.
- Endpoint'e emin değilken tahminle POST/GET seçme — keşif raporundan doğrula.
