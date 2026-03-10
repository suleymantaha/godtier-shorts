"""
backend/config.py
=================
Projenin tek hakikat kaynağı (single source of truth).
Tüm klasör yolları ve sabitler buradan yönetilir.
Bir yolu değiştirmek istersen, sadece bu dosyayı düzenle.
"""
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Temel dizinler
# ---------------------------------------------------------------------------

# Bu dosyanın bulunduğu yer: godtier-shorts/backend/
BACKEND_DIR = Path(__file__).parent

# Proje kökü: godtier-shorts/
ROOT = BACKEND_DIR.parent

# Tüm runtime artifact'ları için merkezi alan (gitignored)
WORKSPACE = ROOT / "workspace"

# Alt dizinler
DOWNLOADS_DIR = WORKSPACE / "downloads"
TEMP_DIR      = WORKSPACE / "temp"
OUTPUTS_DIR   = WORKSPACE / "outputs"     # Genel çıktılar (opsiyonel/eski)
METADATA_DIR  = WORKSPACE / "metadata"
LOGS_DIR      = WORKSPACE / "logs"
PROJECTS_DIR  = WORKSPACE / "projects"    # Yeni proje tabanlı yapı

# ---------------------------------------------------------------------------
# Yol Yardımcıları (Path traversal güvenliği)
# ---------------------------------------------------------------------------

def sanitize_project_name(project_name: str) -> str:
    """Path traversal önleme: sadece güvenli karakterlere izin verir."""
    if not project_name or not project_name.strip():
        raise ValueError("Proje adı boş olamaz")
    if ".." in project_name or "/" in project_name or "\\" in project_name:
        raise ValueError("Geçersiz proje adı: path traversal karakterleri yasak")
    safe = re.sub(r"[^\w\-]", "", project_name)
    if not safe or len(safe) > 100:
        raise ValueError("Geçersiz proje adı")
    return safe


def sanitize_clip_name(clip_name: str) -> str:
    """Path traversal önleme: sadece güvenli dosya adına izin verir."""
    if not clip_name or not clip_name.strip():
        raise ValueError("Klip adı boş olamaz")
    if ".." in clip_name or "/" in clip_name or "\\" in clip_name:
        raise ValueError("Geçersiz klip adı: path traversal karakterleri yasak")
    base = Path(clip_name).name
    if not base or len(base) > 200:
        raise ValueError("Geçersiz klip adı")
    return base


def get_project_dir(project_name: str) -> Path:
    """Proje klasör yolunu döner (path traversal korumalı)."""
    safe_name = sanitize_project_name(project_name)
    pdir = PROJECTS_DIR / safe_name
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir


def get_project_path(project_name: str, *parts: str) -> Path:
    """Proje içinde klasör oluşturmadan güvenli bir path döner."""
    safe_name = sanitize_project_name(project_name)
    return PROJECTS_DIR / safe_name / Path(*parts)


class ProjectPaths:
    """Bir projenin içindeki tüm kritik dosyaları yönetir (path traversal korumalı)."""
    def __init__(self, project_name: str):
        self.root = get_project_dir(project_name)  # sanitize_project_name içeride çağrılır
        self.master_video = self.root / "master.mp4"
        self.master_audio = self.root / "master.wav"
        self.transcript   = self.root / "transcript.json"
        self.viral_meta   = self.root / "viral.json"
        self.outputs      = self.root / "shorts"
        self.outputs.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Önemli dosyalar (Geriye dönük uyumluluk için varsayılanlar)
# ---------------------------------------------------------------------------

MASTER_VIDEO     = DOWNLOADS_DIR / "master_video.mp4"
MASTER_AUDIO     = DOWNLOADS_DIR / "master_audio.wav"
VIDEO_METADATA   = METADATA_DIR  / "video_metadata.json"
VIDEO_HASH       = METADATA_DIR  / "video_hash.sha256"
VIRAL_SEGMENTS   = METADATA_DIR  / "viral_segments.json"

# ---------------------------------------------------------------------------
# AI Model dosyaları
# ---------------------------------------------------------------------------

YOLO_MODEL_PATH = ROOT / "yolo11x.pt"
MODELS_DIR      = ROOT / "models"

# ---------------------------------------------------------------------------
# Sunucu ayarları
# ---------------------------------------------------------------------------

API_HOST = "0.0.0.0"
API_PORT = 8000
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
]

# Upload limitleri (5GB)
UPLOAD_MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024
MAX_UPLOAD_BYTES = UPLOAD_MAX_FILE_SIZE  # Alias

# ---------------------------------------------------------------------------
# Workspace klasörlerini oluştur (import sırasında garantile)
# ---------------------------------------------------------------------------

def ensure_workspace() -> None:
    """Workspace alt klasörlerinin var olduğunu garanti eder."""
    for d in (DOWNLOADS_DIR, TEMP_DIR, OUTPUTS_DIR, METADATA_DIR, LOGS_DIR, PROJECTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

ensure_workspace()
