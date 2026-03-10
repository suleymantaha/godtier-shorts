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

# 4. Frontend'i başlat
echo "🎨 Frontend başlatılıyor..."
cd frontend
npm run dev &

# Süreçleri açık tut
wait
