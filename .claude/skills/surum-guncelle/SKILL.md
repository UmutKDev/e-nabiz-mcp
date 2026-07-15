---
name: surum-guncelle
description: Use after any feature/phase change (adding, removing, or renaming a tool or data area) to keep docs/STATUS.md, README.md tool counts and list, and the commit message consistent. Invoke as the final step of yeni-tool-ekle, or whenever tool/field counts change.
---

# Sürüm / STATUS güncelle

Bir feature/faz değişikliğinden sonra sayı ve doküman tutarlılığını sağlar. STATUS.md
feature commit'leriyle kilit-adımda tutulur, bayat bırakılmaz.

## Checklist

1. **Gerçek sayıları al.** Tool sayısını uydurma — kaynaktan doğrula:
   ```bash
   uv run pytest -q                         # önce yeşil olsun; test sayısını not al
   grep -rc "@mcp.tool" src/enabiz_mcp       # tool tanımlarını say (auth dahil)
   ```
2. **`docs/STATUS.md`:**
   - Üstteki `Son güncelleme:` tarihini bugüne çek.
   - "**N tool / M veri alanı**" sayılarını güncelle (özet paragrafı + durum tablosu).
   - İlgili satırın durumunu (🟢/🟡) ve varsa kayıt sayılarını güncelle.
3. **`README.md`:**
   - Başlıktaki tool sayısını (`## Tool'lar (N)`) ve "Durum" satırındaki
     "**N tool / M veri alanı**" ifadesini güncelle.
   - Yeni tool'u doğru kategori başlığı altında listeye ekle.
   - Salt-okunur / PDF metadata notları hâlâ doğru mu, kontrol et.
4. **Commit:** Conventional Commits, İngilizce type + Türkçe açıklama/gövde.
   - Gövdede **o anki gerçek test sayısını** yaz (sabit bir sayı ezberleme; `pytest`
     çıktısından al).
   - `!` yalnız gerçekten breaking değişiklikte.
   - Gövde şununla biter: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
5. **`docs/notes/decisions.md`** — yalnız gerçek bir mimari/yön kararı verildiyse, tarih
   damgalı bir ADR (D-numarası) ekle. Append-only; rutin değişiklikte dokunma.

## Kaçınılacaklar
- CLAUDE.md'ye sabit tool sayısı yazma — sayılar STATUS.md/README'de yaşar.
- Commit gövdesine geçmişten kopyalanmış eski test sayısını yazma.
- Sayıları elle tahmin etme; `grep`/`pytest` çıktısından doğrula.
