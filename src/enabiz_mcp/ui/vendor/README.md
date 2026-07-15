@modelcontextprotocol/ext-apps — vendor edilmiş tarayıcı paketi

Kaynak : https://www.npmjs.com/package/@modelcontextprotocol/ext-apps
Sürüm  : 1.7.4
Dosya  : dist/src/app-with-deps.js  →  ext-apps.js
Lisans : MIT (ext-apps.LICENSE)

NEDEN VENDOR: widget iframe'inin CSP'si CDN'den import'u engelliyor
(paket blank render eder) ve privacy.md §1-2 dış egress yasaklıyor. Bu repoda
npm toolchain'i YOK ve olmayacak — bu bir JS VARLIĞI, JS toolchain'i değil.
Gerekçe: docs/notes/decisions.md D8.

GÜNCELLEME: npm pack @modelcontextprotocol/ext-apps@<sürüm> → tarball'dan
dist/src/app-with-deps.js'i buraya kopyala. ELLE DÜZENLEME — üretilmiş dosya.
export{…} → globalThis.ExtApps çevrimi çalışma zamanında bundle.py yapar.
