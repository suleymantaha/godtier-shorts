import sys
import types

cv2_stub = types.SimpleNamespace(
    VideoCapture=object,
    CAP_PROP_FPS=5,
    CAP_PROP_FRAME_WIDTH=3,
    CAP_PROP_FRAME_HEIGHT=4,
    resize=lambda frame, size, *args, **kwargs: frame
)
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


def test_compute_crop_bounds_soft_boundary_damping() -> None:
    """Sınır marjini sınırları aştığında cubic spline damping uygulanmalı."""
    # crop_width = 200, frame_width = 1000
    # min_x = 100, max_x = 900
    # margin = 200 * 0.05 = 10.0 pixels
    # boundary zone: [100, 110] ve [890, 900]
    
    # 1. Marjinden uzak durum: Damping uygulanmamalı
    x1, x2 = VideoProcessor._compute_crop_bounds(center_x=500, crop_width=200, frame_width=1000)
    assert (x1, x2) == (400, 600)
    
    # 2. Sol sınır damping marjininde: center_x = 105 (t = 0.5)
    # g(0.5) = -0.125 + 0.5 = 0.375
    # mapped center = 100 + 10 * 0.375 = 103.75
    # x1 = int(103.75 - 100) = 3
    # x2 = 203
    x1_left, x2_left = VideoProcessor._compute_crop_bounds(center_x=105, crop_width=200, frame_width=1000)
    assert x1_left == 3
    assert x2_left == 203
    
    # 3. Sağ sınır damping marjininde: center_x = 895 (t = 0.5)
    # mapped center = 900 - 10 * 0.375 = 896.25
    # x1 = int(896.25 - 100) = 796
    # x2 = 996
    x1_right, x2_right = VideoProcessor._compute_crop_bounds(center_x=895, crop_width=200, frame_width=1000)
    assert x1_right == 796
    assert x2_right == 996
