import sys
import types

cv2_stub = types.SimpleNamespace(VideoCapture=object, CAP_PROP_FPS=5, CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4)
torch_stub = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False, empty_cache=lambda: None))
ultralytics_stub = types.SimpleNamespace(YOLO=object)

sys.modules.setdefault("cv2", cv2_stub)
sys.modules.setdefault("torch", torch_stub)
sys.modules.setdefault("ultralytics", ultralytics_stub)

from backend.services.video_processor import VideoProcessor


def test_compute_crop_bounds_clamps_left_edge_once() -> None:
    """Negatif başlangıç tek bir clamp ile 0'a çekilmeli."""
    x1, x2 = VideoProcessor._compute_crop_bounds(center_x=20, crop_width=200, frame_width=1000)

    assert (x1, x2) == (0, 200)


def test_compute_crop_bounds_clamps_right_edge() -> None:
    x1, x2 = VideoProcessor._compute_crop_bounds(center_x=980, crop_width=200, frame_width=1000)

    assert (x1, x2) == (800, 1000)
