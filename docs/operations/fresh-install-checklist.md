# Fresh Install Checklist

Yeni bir makinede kuruluma baslamadan once su referanslari hedefleyin:

- Python `3.13.x`
- Node.js `22.x`
- npm `10.x`

Repo icindeki pin dosyalari:

- `.python-version`
- `.nvmrc`

## 1. Sistem bagimliliklari

Kurulu ve `PATH` icinde oldugunu dogrulayin:

- `ffmpeg`
- `yt-dlp`

GPU kullanacaksaniz:

- NVIDIA driver + CUDA runtime
- `nvidia-smi` komutu calisiyor olmali

Not:

- GPU yoksa uygulama tamamen bozulmaz.
- YOLO tarafi CPU fallback yapar.
- NVENC yoksa ffmpeg `libx264` fallback yapar.
- Sadece isleme suresi belirgin sekilde artar.

## 2. Repo kurulumu

```bash
git clone https://github.com/suleymantaha/godtier-shorts.git
cd godtier-shorts

pip install -r requirements.txt
cd frontend && npm ci
cd ..
```

## 3. Ortam degiskenleri

```bash
cp .env.example .env
```

En azindan su alanlari dogru olmali:

- `VITE_CLERK_PUBLISHABLE_KEY`
- `CLERK_ISSUER_URL`
- `CLERK_AUDIENCE`
- `VITE_CLERK_JWT_TEMPLATE`
- `SOCIAL_ENCRYPTION_SECRET`

Opsiyonel ama sosyal yayin icin gerekli:

- `POSTIZ_API_BASE_URL`
- `SOCIAL_CONNECTION_MODE=managed`
- `PUBLIC_APP_URL`

Yalniz tek kullanicili lokal dev fallback icin:

- `POSTIZ_API_KEY`
- `ALLOW_ENV_POSTIZ_API_KEY_FALLBACK=1`

Detayli env rehberi:

- [api-key-setup.md](/home/arch/godtier-shorts/docs/api-key-setup.md)
- [clerk-auth-setup.md](/home/arch/godtier-shorts/docs/clerk-auth-setup.md)
- [postiz-global-oauth-standard.md](/home/arch/godtier-shorts/docs/operations/postiz-global-oauth-standard.md)

## 4. Kurulum sonrasi dogrulama

```bash
python scripts/check_toolchain.py
python scripts/check_runtime_config.py
python scripts/check_system_deps.py
bash scripts/verify.sh
```

Beklenen sonuc:

- toolchain check gecer
- runtime config check gecer
- system deps check icinde `ffmpeg` ve `yt-dlp` `ok` doner
- GPU zorunlu ortamda `python scripts/check_system_deps.py --require-gpu` de gecer
- NVENC zorunlu ortamda `python scripts/check_system_deps.py --require-nvenc` de gecer
- frontend lint/test/build gecer
- backend testleri gecer

## 5. Ilk calistirma

```bash
./run.sh
```

Kontrol edin:

- Frontend: `http://localhost:5173`
- Backend docs: `http://127.0.0.1:8000/docs`
- GPU zorunlu ortamda `REQUIRE_CUDA_FOR_APP=1 ./run.sh` ile startup fail-fast çalışmalı
- NVENC zorunlu ortamda `REQUIRE_NVENC_FOR_APP=1 ./run.sh` ve gerekirse `REQUIRE_NVENC_FOR_BURN=1` ile subtitle burn fallback kapatılmalı
- Linux ortaminda Vite `ENOSPC` watcher limitine takilirsa `./run.sh` frontend'i otomatik olarak polling fallback ile açmalı

## 5.1 ENOSPC watcher hatasi notu

Belirti:

- Frontend startup sirasinda `ENOSPC: System limit for number of file watchers reached`

Mevcut repo davranisi:

- `./run.sh` native watch ile dener
- `ENOSPC` gorurse frontend'i otomatik polling mode ile yeniden baslatir
- Polling fallback icin `CHOKIDAR_USEPOLLING=1` ve varsayilan `CHOKIDAR_INTERVAL=300` kullanilir

Isterseniz kalici sistem ayari da yapabilirsiniz:

```bash
echo fs.inotify.max_user_watches=524288 | sudo tee /etc/sysctl.d/99-godtier-shorts.conf
echo fs.inotify.max_user_instances=1024 | sudo tee -a /etc/sysctl.d/99-godtier-shorts.conf
echo fs.inotify.max_queued_events=32768 | sudo tee -a /etc/sysctl.d/99-godtier-shorts.conf
sudo sysctl --system
```

## 6. Kirmadan tasinabilir kurulum icin notlar

- Pyre/Pyright config dosyalari artik makineye ozel absolute path kullanmamalidir.
- Yeni makinede farkli conda/venv yolu kullanacaksaniz repo dosyasini degistirmeyin; local wrapper veya shell env kullanin.
- `bash scripts/verify.sh` gecmeden uygulamayi deploy etmeyin.
- Codex/sandbox icinde `torch.cuda` veya `nvidia-smi` yalanci negatif verebilir; son karar gerçek host shell veya app startup probe sonucudur.
