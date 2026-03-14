#!/bin/bash

# Proje dizinine git (script'in bulunduğu yer)
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

echo "🚀 God-Tier Shorts başlatılıyor..."

# 1. Conda ortamını aktif et
# Eğer conda shell hook yüklü değilse init gerekebilir
source $(conda info --base)/etc/profile.d/conda.sh
conda activate godtier-shorts

# 2. Trap kur: Script kapatıldığında alt süreçleri de öldür
cleanup() {
    echo "Stopping all processes..."
    kill $(jobs -p)
    exit
}
trap cleanup SIGINT SIGTERM

# 3. Backend'i başlat
echo "📡 Backend başlatılıyor..."
python -m backend.main &
BACKEND_PID=$!

# Backend hazır olana kadar bekle (frontend ilk açılışta connection refused almasın)
API_PORT_VALUE="${API_PORT:-$(grep -E '^API_PORT=' .env 2>/dev/null | tail -n 1 | cut -d '=' -f2)}"
API_PORT_VALUE="${API_PORT_VALUE:-8000}"
HEALTH_URL="http://127.0.0.1:${API_PORT_VALUE}/docs"

echo "⏳ Backend hazır bekleniyor: ${HEALTH_URL}"
for i in $(seq 1 60); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
        echo "✅ Backend hazır."
        break
    fi
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
        echo "❌ Backend erken kapandı. Logları kontrol edin."
        exit 1
    fi
    sleep 1
done

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "❌ Backend 60 saniye içinde hazır olmadı."
    exit 1
fi

# 4. Frontend'i başlat
echo "🎨 Frontend başlatılıyor..."
cd frontend
npm run dev &

# Süreçleri açık tut
wait
