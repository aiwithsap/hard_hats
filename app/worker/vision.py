"""Vision module for YOLO inference (worker version)."""

from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np
from ultralytics import YOLO

from .config import config

# Detection class IDs from the Construction-Hazard-Detection-YOLO11 model
CLASS_HARDHAT = 0
CLASS_MASK = 1
CLASS_NO_HARDHAT = 2
CLASS_NO_MASK = 3
CLASS_NO_SAFETY_VEST = 4
CLASS_PERSON = 5
CLASS_SAFETY_CONE = 6
CLASS_SAFETY_VEST = 7
CLASS_MACHINERY = 8
CLASS_UTILITY_POLE = 9
CLASS_VEHICLE = 10

CLASS_NAMES = {
    CLASS_HARDHAT: "Hardhat",
    CLASS_MASK: "Mask",
    CLASS_NO_HARDHAT: "NO-Hardhat",
    CLASS_NO_MASK: "NO-Mask",
    CLASS_NO_SAFETY_VEST: "NO-Safety Vest",
    CLASS_PERSON: "Person",
    CLASS_SAFETY_CONE: "Safety Cone",
    CLASS_SAFETY_VEST: "Safety Vest",
    CLASS_MACHINERY: "Machinery",
    CLASS_UTILITY_POLE: "Utility Pole",
    CLASS_VEHICLE: "Vehicle",
}

# Colors (BGR format for OpenCV)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_YELLOW = (0, 255, 255)
COLOR_BLUE = (255, 0, 0)
COLOR_WHITE = (255, 255, 255)


_model: Optional[YOLO] = None


def load_model(weights_path: str = config.WEIGHTS_PATH) -> YOLO:
    """Load YOLO model from weights file."""
    global _model
    if _model is None:
        print(f"[VISION] Loading YOLO model from: {weights_path}")
        _model = YOLO(weights_path)
    return _model


def get_model() -> YOLO:
    """Get the loaded model."""
    if _model is None:
        return load_model()
    return _model


def infer(
    model: YOLO,
    frame: np.ndarray,
    conf: float = config.DEFAULT_CONF,
    imgsz: int = config.DEFAULT_IMGSZ,
) -> List[Dict[str, Any]]:
    """
    Run inference on a frame and return detections.

    Returns:
        List of detection dicts with keys: box, class_id, class_name, confidence
    """
    results = model.predict(frame, conf=conf, imgsz=imgsz, verbose=False)

    detections = []
    if results and len(results) > 0:
        result = results[0]
        boxes = result.boxes

        for i in range(len(boxes)):
            box = boxes.xyxy[i].cpu().numpy().astype(int)
            class_id = int(boxes.cls[i].cpu().numpy())
            confidence = float(boxes.conf[i].cpu().numpy())

            detections.append({
                "box": tuple(box),
                "class_id": class_id,
                "class_name": CLASS_NAMES.get(class_id, f"class_{class_id}"),
                "confidence": confidence,
            })

    return detections


def head_region(box: Tuple[int, int, int, int], frac: float = 0.30) -> Tuple[int, int, int, int]:
    """Compute the head region (top portion) of a person bounding box."""
    x1, y1, x2, y2 = box
    height = y2 - y1
    head_height = int(height * frac)
    return (x1, y1, x2, y1 + head_height)


def box_overlap(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Compute IoU between two boxes."""
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2

    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)

    if xi2 <= xi1 or yi2 <= yi1:
        return 0.0

    inter_area = (xi2 - xi1) * (yi2 - yi1)
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0

    return inter_area / union_area


def point_in_polygon(point: Tuple[int, int], polygon: List[Tuple[int, int]]) -> bool:
    """Check if a point is inside a polygon."""
    polygon_np = np.array(polygon, dtype=np.int32)
    result = cv2.pointPolygonTest(polygon_np, point, False)
    return result >= 0


def get_centroid(box: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """Get the centroid of a bounding box."""
    x1, y1, x2, y2 = box
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def draw_box(
    frame: np.ndarray,
    box: Tuple[int, int, int, int],
    color: Tuple[int, int, int],
    label: str = "",
    thickness: int = 2,
) -> np.ndarray:
    """Draw a bounding box with optional label on frame."""
    x1, y1, x2, y2 = box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

    if label:
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 1
        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, font_thickness)
        cv2.rectangle(frame, (x1, y1 - text_h - 10), (x1 + text_w + 4, y1), color, -1)
        cv2.putText(frame, label, (x1 + 2, y1 - 5), font, font_scale, COLOR_WHITE, font_thickness)

    return frame


def draw_polygon(
    frame: np.ndarray,
    polygon: List[Tuple[int, int]],
    color: Tuple[int, int, int] = COLOR_BLUE,
    alpha: float = 0.3,
) -> np.ndarray:
    """Draw a semi-transparent polygon on frame."""
    overlay = frame.copy()
    pts = np.array(polygon, dtype=np.int32)
    cv2.fillPoly(overlay, [pts], color)
    cv2.polylines(frame, [pts], True, color, 2)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    return frame


def annotate_ppe(frame: np.ndarray, detections: List[Dict[str, Any]]) -> np.ndarray:
    """Annotate frame for PPE compliance mode."""
    persons = [d for d in detections if d["class_id"] == CLASS_PERSON]
    hardhats = [d for d in detections if d["class_id"] == CLASS_HARDHAT]
    no_hardhats = [d for d in detections if d["class_id"] == CLASS_NO_HARDHAT]
    safety_vests = [d for d in detections if d["class_id"] == CLASS_SAFETY_VEST]
    no_safety_vests = [d for d in detections if d["class_id"] == CLASS_NO_SAFETY_VEST]

    for person in persons:
        person_box = person["box"]
        head_box = head_region(person_box, frac=0.30)

        has_no_hardhat = any(box_overlap(head_box, d["box"]) > 0.1 for d in no_hardhats)
        has_hardhat = any(box_overlap(head_box, d["box"]) > 0.1 for d in hardhats)
        has_no_vest = any(box_overlap(person_box, d["box"]) > 0.1 for d in no_safety_vests)
        has_vest = any(box_overlap(person_box, d["box"]) > 0.1 for d in safety_vests)

        violations = []
        compliant = []

        if has_no_hardhat:
            violations.append("NO HAT")
        elif has_hardhat:
            compliant.append("HAT")

        if has_no_vest:
            violations.append("NO VEST")
        elif has_vest:
            compliant.append("VEST")

        if violations:
            color = COLOR_RED
            label = ", ".join(violations)
        elif compliant:
            color = COLOR_GREEN
            label = ", ".join(compliant)
        else:
            color = COLOR_YELLOW
            label = "?"

        frame = draw_box(frame, person_box, color, label)

    return frame


def annotate_zone(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    polygon: List[Tuple[int, int]],
) -> np.ndarray:
    """Annotate frame for zone violation mode."""
    frame = draw_polygon(frame, polygon, COLOR_BLUE, alpha=0.2)
    persons = [d for d in detections if d["class_id"] == CLASS_PERSON]

    for person in persons:
        centroid = get_centroid(person["box"])
        in_zone = point_in_polygon(centroid, polygon)

        if in_zone:
            color = COLOR_RED
            label = "VIOLATION"
        else:
            color = COLOR_GREEN
            label = "OK"

        frame = draw_box(frame, person["box"], color, label)
        cv2.circle(frame, centroid, 5, color, -1)

    return frame


def annotate_frame(
    frame: np.ndarray,
    detections: List[Dict[str, Any]],
    mode: str = "ppe",
    polygon: Optional[List[Tuple[int, int]]] = None,
) -> np.ndarray:
    """Annotate frame based on detection mode."""
    if mode == "ppe":
        return annotate_ppe(frame, detections)
    elif mode == "zone":
        if polygon is None:
            polygon = [(100, 100), (500, 100), (500, 400), (100, 400)]
        return annotate_zone(frame, detections, polygon)
    else:
        return annotate_ppe(frame, detections)
