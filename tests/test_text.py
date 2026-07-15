"""Türkçe büyük/küçük harf katlama testleri.

Portal verisi TÜMÜ BÜYÜK HARF gelir; `str.lower()` Türkçe için yanlıştır ve
filtreleri sessizce yanlış-negatife düşürür. Bkz. `enabiz_mcp._text`.
"""

from __future__ import annotations

import pytest

from enabiz_mcp._text import tr_contains, tr_lower


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("İSTANBUL", "istanbul"),  # İ → i (str.lower() 'i̇' üretir: i + U+0307)
        ("HASTALIKLARI", "hastalıkları"),  # I → ı (str.lower() ASCII 'i' üretir)
        ("İÇ HASTALIKLARI", "iç hastalıkları"),  # ikisi bir arada
        ("ŞEHİR HASTANESİ", "şehir hastanesi"),
        ("BURSA OSMANGAZİ", "bursa osmangazi"),
        ("şehir", "şehir"),  # zaten küçük → değişmez
        ("ÇĞÖŞÜ", "çğöşü"),  # bunları str.lower() zaten doğru yapar
    ],
)
def test_tr_lower(raw, expected):
    assert tr_lower(raw) == expected


def test_str_lower_is_wrong_for_turkish():
    """Düzelttiğimiz hatanın kendisi — regresyon olursa burası anlamını yitirir."""
    assert "İ".lower() != "i"  # iki kod noktası: i + U+0307
    assert len("İ".lower()) == 2
    assert "I".lower() == "i"  # 'ı' olmalıydı
    assert "istanbul" not in "İSTANBUL".lower()
    assert "istanbul" in tr_lower("İSTANBUL")


def test_tr_contains_none_and_empty():
    assert tr_contains("x", None) is False
    assert tr_contains("x", "") is False
    assert tr_contains("", "ŞEHİR") is True  # boş dize her yerde geçer


def test_tr_contains_both_sides_folded():
    """Sorgu da veri de katlanmalı — yalnız birini katlamak eşleşmeyi düzeltmez."""
    assert tr_contains("İç Hastalıkları", "İÇ HASTALIKLARI")
    assert tr_contains("iç hastalıkları", "İÇ HASTALIKLARI")
    assert tr_contains("ŞEHİR", "şehir hastanesi")
