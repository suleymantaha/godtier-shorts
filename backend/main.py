"""
backend/main.py
===============
Uvicorn giriş noktası.

Çalıştırmak için proje kökünden:
    python -m backend.main
    
veya doğrudan:
    uvicorn backend.api.server:app --host 0.0.0.0 --port 8000 --reload
"""
import uvicorn
from loguru import logger

# Environment değişkenlerini yükle
from dotenv import load_dotenv
load_dotenv()

from backend.api.server import create_app
from backend.config import API_HOST, API_PORT

app = create_app()

if __name__ == "__main__":
    logger.info(f"🔥 API Sunucusu başlatılıyor... {API_HOST}:{API_PORT}")
    uvicorn.run(
        "backend.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
        log_config=None,  # Loguru bizim loglar
        timeout_keep_alive=300,  # 5 dakika - büyük dosya yüklemeleri için
    )
