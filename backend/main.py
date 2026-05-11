"""
backend/main.py
===============
Uvicorn giriş noktası.

Çalıştırmak için proje kökünden:
    python -m backend.main
    
veya doğrudan:
    uvicorn backend.api.server:app --host 0.0.0.0 --port 8000 --reload
"""
import os

# Windows CTranslate2/CUDA DLL Deadlock (Donma) Cözümleri
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.path.exists(torch_lib):
        os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
except ImportError:
    pass

# GPU probe davranisini tum calistirma yollarinda hizala.
os.environ.setdefault("PYTORCH_NVML_BASED_CUDA_CHECK", "1")
os.environ.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")
# Windows VAD/OpenMP Deadlock (Donma) Cözümleri
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import uvicorn
from loguru import logger

# Environment değişkenlerini yükle
from backend.core.runtime_env import load_runtime_env
load_runtime_env()

from backend.api.server import create_app
from backend.config import API_HOST, API_PORT, YOLO_MODEL_PATH
from backend.services.social.crypto import sanitize_managed_postiz_env_fallback

sanitize_managed_postiz_env_fallback(logger.warning)

app = create_app()

if __name__ == "__main__":
    logger.info(f"🔥 API Sunucusu başlatılıyor... {API_HOST}:{API_PORT}")
    logger.info("🎯 Etkin YOLO modeli: {}", YOLO_MODEL_PATH)
    uvicorn.run(
        "backend.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_config=None,  # Loguru bizim loglar
        timeout_keep_alive=300,  # 5 dakika - büyük dosya yüklemeleri için
    )
