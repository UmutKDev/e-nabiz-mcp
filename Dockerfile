# syntax=docker/dockerfile:1.7
# ============================================================
# E-Nabız MCP — salt-okunur, stdio-only MCP sunucusu.
# Bu imaj ghcr.io'da HERKESE AÇIK yayımlanır.
#
# İmaj KOD taşır; PHI ve kimlik bilgisi TAŞIMAZ. Savunma ÇİFT katmanlı:
#   1) .dockerignore = allowlist (deny-all) → dosya context'e HİÇ girmez
#   2) aşağıdaki AÇIK COPY'ler → `COPY . .` ASLA kullanılmaz
# Katman DEĞİŞMEZLİĞİ: bir dosya bir kez katmana girerse sonradan
# `RUN rm` onu SİLMEZ (`docker save`/`docker history` ile çıkarılır).
# Tek doğru savunma: dosyanın context'e hiç girmemesi.
#
# Kimlik bilgileri ÇALIŞMA ZAMANINDA, mount edilen .env ile verilir;
# build'de ASLA (ARG/ENV `docker history`'de görünür) ve `-e`/`--env-file`
# ile ASLA (değerleri `docker inspect`te görünür — ölçüldü).
# ============================================================

FROM python:3.13-slim-bookworm AS builder

# uv'yi sürüme sabitle (`:latest` DEĞİL) — tekrarlanabilirlik uv'ye de bağlı.
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv

# UV_PYTHON_DOWNLOADS=0 → uv taban imajın yorumlayıcısını kullanır,
# katmana ikinci bir standalone CPython indirmez.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Katman 1 — yalnız bağımlılıklar; src/ değişince bu pahalı katman bozulmaz.
# README.md ZORUNLU BUILD GİRDİSİ: pyproject.toml `readme = "README.md"`
# → uv_build onu wheel METADATA'sı için açar. Yoksa build şu hatayla ölür:
#   failed to open file `.../README.md`: No such file or directory
# "Doküman runtime'da gereksiz" diye .dockerignore'dan SİLMEYİN.
COPY pyproject.toml uv.lock README.md .python-version ./

# --frozen : uv.lock bayatsa sessizce yeniden çözme, GÜRÜLTÜYLE patla.
#            Tüm runtime bağımlılıkları alt-sınırsız (fastmcp>=3.4.4 ...);
#            kilitsiz build aynı commit'ten farklı bağımlılık seti üretir →
#            bir HTML-scraper'da bu, sessiz parser davranış kaymasıdır.
# --no-dev : PEP 735 `dev` grubu (pytest+ruff) VARSAYILAN kurulur; bu bayrak
#            olmadan test araçları herkese açık imaja sızar.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --no-editable

COPY src ./src

# --no-editable ZORUNLU: uv.lock projeyi `source = { editable = "." }` kaydeder.
# Bayraksız .venv, /app/src'e geri işaret eden bir editable-finder içerir ve
# runtime stage'e kopyalandığında ImportError verir. Bu bayrak gerçek bir wheel
# kurar → .venv kendi kendine yeter ve src/ runtime imajına hiç girmez.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ------------------------------------------------------------
# Runtime — uv yok, kaynak yok, test yok. Yalnız .venv.
# Builder ile AYNI taban: .venv, o yorumlayıcının ABI'sine ve mutlak
# yollarına bağlıdır.
# ------------------------------------------------------------
FROM python:3.13-slim-bookworm

# image.source, paketi GHCR'de repoya otomatik bağlar (README + provenance).
# licenses artık beyan edilebilir: repoda LICENSE (MIT) ve pyproject'te
# `license = "MIT"` var. Bu etiket o iki kaynakla TUTARLI kalmalı — lisans
# değişirse üçünü birden değiştirin.
LABEL org.opencontainers.image.title="enabiz-mcp" \
      org.opencontainers.image.description="E-Nabız (T.C. Sağlık Bakanlığı KSS) için yerel, salt-okunur stdio MCP sunucusu" \
      org.opencontainers.image.source="https://github.com/UmutKDev/e-nabiz-mcp" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.documentation="https://github.com/UmutKDev/e-nabiz-mcp/blob/main/README.md"

# Root DEĞİL. PHI işleyen bir konteynerde uid 0, kodun dosyalara uyguladığı
# chmod 0600'ü anlamsızlaştırır.
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data \
 && chown app:app /data

COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Oturum + indirmeleri TEK bağlama noktasına sabitle.
#  1. Kullanıcı tek dizin bağlar; oturum kalıcı olur. Login insan-döngüde SMS
#     OTP'dir — kalıcılık olmadan her restart GERÇEK bir SMS yakar.
#  2. config.py'deki override dalı `Path.home()`dan ÖNCE döner → enabiz kod
#     yolunda Path.home() HİÇ çağrılmaz. Bu, konteyner rastgele bir uid ile
#     (`--user 1000:1000`, /etc/passwd kaydı yok) çalıştığında oluşacak
#     RuntimeError'ı ortadan kaldırır ve imajı uid'den bağımsız yapar.
ENV ENABIZ_SESSION_PATH=/data/session.json \
    ENABIZ_DOWNLOAD_DIR=/data/downloads

# Yukarıdaki override'lar sayesinde enabiz kodu HOME'a dokunmaz; yine de
# rastgele uid senaryosunda YAZILABİLİR bir HOME garantisi için /tmp.
# (distroless'ın /home/nonroot'u 0700'dür ve rastgele uid'de yazılamaz.)
# Buraya PHI yazılmaz.
ENV HOME=/tmp

# Transport'u stdio'ya ÇİVİLE: fastmcp ayarları FASTMCP_ önekini okur; ortamdan
# miras kalan bir FASTMCP_TRANSPORT=http bu sunucuyu sessizce HTTP dinleyicisine
# çevirebilirdi. Bu sunucu YALNIZ stdio'dur.
ENV FASTMCP_TRANSPORT=stdio

# Banner'ı kapat. Banner stdout'u BOZMUYOR (fastmcp `Console(stderr=True)`
# kullanır — ölçüldü), gerekçe stdout değil EGRESS: banner her açılışta
# pypi.org'a sürüm kontrolü isteği atar. PHI konteynerinde tek meşru egress
# enabiz.gov.tr:443 olmalı.
ENV FASTMCP_SHOW_SERVER_BANNER=false \
    FASTMCP_CHECK_FOR_UPDATES=off

USER app

# WORKDIR /app YÜK TAŞIR — silmeyin. İKİ AYRI mekanizma buna bakar ve bunlar
# AYNI ŞEY DEĞİLDİR (ikisini karıştırmak bu imajın en kolay bozulma yolu):
#
#  1. CWD gerçekten önemli olan yer: fastmcp'nin kendi Settings'i IMPORT
#     anında GÖRELİ bir ".env" dosyasını CWD'ye göre stat'ler. CWD geçilemez
#     bir dizinse (0700 + başka uid) sunucu daha başlamadan
#     `PermissionError: [Errno 13] Permission denied: '.env'` ile çöker.
#     /app 0755'tir → her uid traverse eder, stat temiz ENOENT döner.
#
#  2. CWD'nin önemli OLMADIĞI yer: kullanıcının `-v ./.env:/app/.env:ro` ile
#     bağladığı .env'i python-dotenv CWD sayesinde DEĞİL, VENV KONUMU
#     sayesinde bulur. find_dotenv() ÇAĞIRAN MODÜLÜN dosyasından yukarı yürür:
#     /app/.venv/lib/python3.13/site-packages/enabiz_mcp/config.py → … → /app
#     ve /app/.env'i orada bulur. CWD bu aramaya HİÇ girmez.
#
# SONUÇ: .env'i bulduran şey venv'in /app ALTINDA olmasıdır, WORKDIR değil.
# Venv'i /opt/venv'e taşırsanız WORKDIR /app dursa bile kimlik bilgileri
# SESSİZCE bulunamaz olur; hata ancak login'de "ENABIZ_TCKIMLIK ayarlı değil"
# diye yüzeye çıkar. Venv'i taşırsanız .env mount yolunu da taşıyın.
WORKDIR /app

# VOLUME BİLEREK YOK: `VOLUME /data`, kullanıcı -v vermeyi unutursa ANONİM bir
# volume yaratır; `--rm` onu siler → oturum yine kaybolur, üstelik yetim volume
# çöpü birikir. Kalıcılık açık `-v` ile sağlanır (README'deki run komutu).

# EXPOSE YOK, HEALTHCHECK YOK — bu sunucu hiçbir port dinlemez. MCP istemcisinin
# alt süreci olarak stdin/stdout'ta konuşur: `docker run -i` ŞART. `-i` olmadan
# stdin'de anında EOF görür ve derhal çıkar. `-d` ile ASLA çalıştırmayın.
ENTRYPOINT ["enabiz-mcp"]
