---
name: yeni-parser-ekle
description: Use when writing or refactoring an HTML→model parser in src/enabiz_mcp/parsers.py — the standard table skeleton, the exact-id/no-fallback rule, _rows()/_cell()/_text() helpers, string-only values, the independent out_of_range safety check, and the tr_lower slug trap. Invoke this whenever touching parsing logic.
---

# Yeni parser ekle

`parsers.py` saf HTML→Pydantic model katmanıdır (yan etkisiz). Kırmızı çizgi:
**sessizce yanlış eşlenmiş kayıt, boş sonuçtan kötüdür** — emin değilsen `[]` dön.

## Standart tablo iskeleti

`parse_insurance` (`parsers.py:1119-1139`) kanonik örnek:

```python
def parse_<domain>(html: str) -> list[<Model>]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#tbl<Xxx>")        # SADECE tam id — `or` YOK
    out: list[<Model>] = []
    if table is None:
        return out                               # eksik id → boş; tahmin yok
    for tr in _rows(table):                       # tbody VEYA th'siz tr'ler
        tds = [_text(td) for td in tr.find_all("td")]
        if len(tds) < N or not any(tds[:N]):     # N = gerçek kolon sayısının ALTINDA taban
            continue
        out.append(<Model>(
            date=_cell(tds, 0) or "",             # gerekli str alan → `or ""`
            field2=_cell(tds, 1),                 # opsiyonel alan → çıplak _cell
        ))
    return out
```

## Kurallar

- **Tabloyu yalnız tam id ile seç.** `select_one("#id") or soup.find("table")` ASLA —
  `a074eee`'de tam bu silindi (eksik id'de nav tablosunu sağlık modeline eşliyordu).
  `tests/test_parser_robustness.py:28-39` bunu kilitler.
- **Satırları `_rows(table)` ile gez** (`parsers.py:168-169`), `table.select("tbody tr")`
  DEĞİL — sonrakisi tbody'siz tablolarda `[]` döner. `parse_prescriptions` bu yüzden
  düzeltildi (`a074eee`).
- **Satır guard'ı** `if len(tds) < N or not any(tds[:N]): continue`. `N` gerçek kolon
  sayısının **altında** bir tabandır — hiçbir gerçek satırı düşürmemek için; tam kolon
  sayısına "sıkılaştırma".
- **Hücreye `_cell(tds, i)`** (uç geçildiyse `None`, `""`→`None`), **metne `_text(el)`**
  (`get_text(" ", strip=True)`). Gerekli str alanına `_cell(tds, 0) or ""`.
- **Her değer `str`/`str | None`.** Sayı/doz/kutu/tarih int/float/bool'a çevrilmez —
  model sözleşmesi bu (`box_count: str | None` `:334`).
- **Pydantic model:** `BaseModel`, tek satır Türkçe docstring; alan adı İngilizce
  snake_case, `Field(description=...)` Türkçe; opsiyonel `str | None = Field(default=None,
  …)`, gerekli `str = Field(…)`.

## Özel durumlar

- **Çok-tablolu sayfa:** modül-seviye `(table_id, slug)` tuple'ı tanımla, üstünde döngü,
  slug'ı her kayda bas (`_ALLERGY_TABLES` `:577-581`). Slug DEĞERLERİ ASCII Türkçe
  (`ilac`, `tani`, `deri`, `diger`).
- **`tr_lower` tuzağı:** `tr_lower`/`tr_contains` yalnız Türkçe **portal metnine**,
  karşılaştırmanın iki tarafına. Parser'ın atadığı ASCII slug'a ASLA —
  `tr_lower("DIGER")=="dığer"` ve eşleşme sessizce kaçar. Slug filtresinde düz `.lower()`.
- **onclick token'ı:** modül-seviye derlenmiş `_XXX_RE` + `_row_token(tr, RE)` ile çek.
  Token, virgül/tırnak içerebilen kolonla (ör. ICD kodları) aynı çağrıdaysa regex'i
  **son tırnaklı argümana** çapala (`_HASTALIK_TOKEN_RE` `:622-625`).
- **Kart-grid sayfa:** `_rows`/tablo-id yerine CSS class seçici (`soup.select(".xCardList")`
  + kart içi `.select_one(".class")`) — radyoloji `:238-261`, ziyaret `:843-861`.
- **Serbest-metin/bilinmeyen yapı** detay yanıtı: yapılandırılmış parser yerine
  `html_to_text()` (`:264-273`).
- **Dönüş tipi:** `list[dict]`/`dict` dönenler her instance'a `.model_dump()`; `list[Model]`
  dönen instance'ı doğrudan ekler.
- **`out_of_range` (lab):** sunucunun `status`'undan BAĞIMSIZ, `_compute_out_of_range`
  (`:434-464`) ile. Muhafazakâr — çözülemezse `None`, asla yanlış `False`. `_num`
  `"nan"/"inf"` reddeder (`float()` kabul ederdi; `:417-431`).
- **PII yok:** TCKN/e-posta/telefon emit etme (`Profile` bunları bilerek dışlar).

## Sanksiyonlu istisna
`parse_prescriptions` (`:130-146`) `tds`'i bilerek doğrudan indeksler (onclick regex için
ham `<td>` gerekli). Standart "hep `_cell` kullan" kuralı standart iskelete özgüdür,
mutlak değildir.

## Test
Sentetik fixture (`tests/fixtures/<domain>_sample.html`, `<!-- SENTETİK -->`, PHI yok) +
`test_parser_robustness.py` deseninde nav-only ve tbody'siz vakalar. `uv run pytest`.
