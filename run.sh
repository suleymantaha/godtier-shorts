#!/bin/bash

# Proje dizinine git (script'in bulunduğu yer)
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

TODAY="$(date +%F)"
RUNTIME_LOG_DIR="$PROJECT_ROOT/workspace/logs"
mkdir -p "$RUNTIME_LOG_DIR"
BACKEND_LOG="$RUNTIME_LOG_DIR/backend_dev_${TODAY}.log"
FRONTEND_LOG="$RUNTIME_LOG_DIR/frontend_dev_${TODAY}.log"
TAIL_STARTUP_LOGS="${TAIL_STARTUP_LOGS:-0}"

echo "🚀 God-Tier Shorts başlatılıyor..."

# 1. Conda ortamını aktif et
# Eğer conda shell hook yüklü değilse init gerekebilir
source $(conda info --base)/etc/profile.d/conda.sh
conda activate godtier-shorts
export PYTORCH_NVML_BASED_CUDA_CHECK="${PYTORCH_NVML_BASED_CUDA_CHECK:-1}"
export CUDA_DEVICE_ORDER="${CUDA_DEVICE_ORDER:-PCI_BUS_ID}"
export LOG_ACCELERATOR_STATUS_ON_STARTUP="${LOG_ACCELERATOR_STATUS_ON_STARTUP:-1}"

if [[ "${REQUIRE_CUDA_FOR_APP:-0}" == "1" || "${REQUIRE_NVENC_FOR_APP:-0}" == "1" ]]; then
    echo "🧪 GPU/NVENC önkontrolü çalıştırılıyor..."
    python scripts/check_system_deps.py $( [[ "${REQUIRE_NVENC_FOR_APP:-0}" == "1" ]] && printf '%s' '--require-nvenc' || printf '%s' '--require-gpu' )
fi

# 2. Trap kur: Script kapatıldığında alt süreçleri de öldür
cleanup() {
    echo "Stopping all processes..."
    jobs -pr | xargs -r kill 2>/dev/null || true
    if [[ -n "$FRONTEND_TAIL_PID" ]] && kill -0 "$FRONTEND_TAIL_PID" >/dev/null 2>&1; then
        kill "$FRONTEND_TAIL_PID" 2>/dev/null || true
    fi
    exit
}
trap cleanup SIGINT SIGTERM

read_inotify_limit() {
    local key="$1"
    local path="/proc/sys/fs/inotify/${key}"
    if [[ -r "$path" ]]; then
        cat "$path"
    else
        echo "n/a"
    fi
}

# 3. Backend'i başlat
echo "📡 Backend başlatılıyor..."
: > "$BACKEND_LOG"
python -m backend.main >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "📝 Backend log: $BACKEND_LOG"

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
        tail -n 40 "$BACKEND_LOG" 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "❌ Backend 60 saniye içinde hazır olmadı."
    tail -n 40 "$BACKEND_LOG" 2>/dev/null || true
    exit 1
fi

# 4. Frontend'i başlat
echo "🎨 Frontend başlatılıyor..."
cd frontend

FRONTEND_POLLING_MODE=0
FRONTEND_TAIL_PID=""
FRONTEND_PID=""
INOTIFY_WATCHES="$(read_inotify_limit max_user_watches)"
INOTIFY_INSTANCES="$(read_inotify_limit max_user_instances)"
INOTIFY_QUEUE="$(read_inotify_limit max_queued_events)"

echo "👀 inotify limits: watches=${INOTIFY_WATCHES} instances=${INOTIFY_INSTANCES} queue=${INOTIFY_QUEUE}"
echo "📝 Frontend log: $FRONTEND_LOG"

start_frontend_dev() {
    local mode_label="$1"
    shift

    : > "$FRONTEND_LOG"
    echo "🧭 Frontend dev server başlatılıyor (${mode_label})..."
    (
        "$@" npm run dev >"$FRONTEND_LOG" 2>&1
    ) &
    FRONTEND_PID=$!
}

tail_frontend_log() {
    if [[ ! "$TAIL_STARTUP_LOGS" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
        return
    fi

    if [[ -n "$FRONTEND_TAIL_PID" ]] && kill -0 "$FRONTEND_TAIL_PID" >/dev/null 2>&1; then
        return
    fi

    tail -n +1 -f "$FRONTEND_LOG" 2>/dev/null &
    FRONTEND_TAIL_PID=$!
}

wait_for_frontend_boot() {
    local deadline_seconds="${1:-8}"
    for _ in $(seq 1 "$deadline_seconds"); do
        if ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
            return 1
        fi

        if grep -qE 'Local:|ready in' "$FRONTEND_LOG"; then
            return 0
        fi

        sleep 1
    done

    kill -0 "$FRONTEND_PID" >/dev/null 2>&1
}

start_frontend_with_fallback() {
    if [[ "${CHOKIDAR_USEPOLLING:-0}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
        FRONTEND_POLLING_MODE=1
        start_frontend_dev "polling (env override)" env \
            CHOKIDAR_USEPOLLING="${CHOKIDAR_USEPOLLING}" \
            CHOKIDAR_INTERVAL="${CHOKIDAR_INTERVAL:-300}"
        if ! wait_for_frontend_boot 8; then
            echo "❌ Frontend polling mode ile de başlatılamadı."
            tail -n 60 "$FRONTEND_LOG" 2>/dev/null || true
            exit 1
        fi
        tail_frontend_log
        echo "✅ Frontend polling mode aktif."
        return
    fi

    start_frontend_dev "native watch" env
    if wait_for_frontend_boot 8; then
        tail_frontend_log
        echo "✅ Frontend native watch ile hazır."
        return
    fi

    if grep -q "ENOSPC: System limit for number of file watchers reached" "$FRONTEND_LOG"; then
        FRONTEND_POLLING_MODE=1
        echo "⚠️ Native watch ENOSPC nedeniyle açılamadı. Polling fallback aktif ediliyor."
        echo "ℹ️ İsterseniz kalıcı çözüm için fs.inotify limitlerini yükseltebilirsiniz."
        start_frontend_dev "polling fallback" env \
            CHOKIDAR_USEPOLLING=1 \
            CHOKIDAR_INTERVAL="${CHOKIDAR_INTERVAL:-300}"
        if ! wait_for_frontend_boot 12; then
            echo "❌ Frontend polling fallback ile de başlatılamadı."
            tail -n 60 "$FRONTEND_LOG" 2>/dev/null || true
            exit 1
        fi
        tail_frontend_log
        echo "✅ Frontend polling mode aktif."
        return
    fi

    echo "❌ Frontend başlatılamadı."
    tail -n 60 "$FRONTEND_LOG" 2>/dev/null || true
    exit 1
}

start_frontend_with_fallback
FRONTEND_LOCAL_URL="$(grep -m1 'Local:' "$FRONTEND_LOG" | sed 's/.*Local:[[:space:]]*//')"
if [[ -n "$FRONTEND_LOCAL_URL" ]]; then
    echo "🌐 Frontend URL: $FRONTEND_LOCAL_URL"
fi
echo "🌐 Backend Docs: $HEALTH_URL"
if [[ "$TAIL_STARTUP_LOGS" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
    echo "📜 Canlı frontend log takibi aktif."
else
    echo "📜 Terminal temiz modda. Canlı log için: TAIL_STARTUP_LOGS=1 ./run.sh"
fi

# Süreçleri açık tut
wait -n "$BACKEND_PID" "$FRONTEND_PID"
cleanup
