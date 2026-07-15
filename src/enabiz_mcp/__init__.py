"""E-Nabız MCP paketi.

Burada bilinçli olarak `server` import EDİLMEZ. Edilseydi `from enabiz_mcp import
auth` gibi masum bir import bile tüm tool modüllerini + FastMCP'yi çekip 36 tool'u
kaydederdi (ölçüldü: +1260 modül) — `scripts/discover.py` bunu her koşuda yapıyordu.
Konsol giriş noktası doğrudan `enabiz_mcp.server:main`'i hedefler (pyproject.toml).
"""

from __future__ import annotations
