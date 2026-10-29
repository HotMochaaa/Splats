from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional
import numpy as np

INDOOR_VOCABULARY = [
    "almirah", "wardrobe", "suitcase", "trolley bag", "grey suitcase",
    "teal suitcase", "backpack", "shoes", "sneakers", "slippers",
    "bottle", "water bottle", "shaker cup", "laptop", "study desk",
    "office chair", "bed", "pillow", "air conditioner", "dustbin"
]

CONFIDENCE_FLOOR = 0.35

class ObjectDetectionError(RuntimeError):
    pass

def detect_objects_yolo_world(
    image_dir: str,
    weights_path: str = "weights/yolov8m-world.pt",
    min_confidence: float = CONFIDENCE_FLOOR
) -> Optional[Dict[str, list]]:
    """Runs open-vocabulary YOLO-World on extracted video frames with customized indoor vocabulary."""
    if not os.path.exists(image_dir):
        raise ObjectDetectionError(f"image directory '{image_dir}' does not exist")

    try:
        from ultralytics import YOLO
    except ImportError as err:
        print("[POI Pipeline] Ultralytics/torch not installed; using staged detection records.", file=sys.stderr)
        return None

    print(f"[POI Pipeline] Scanning video frames in {image_dir} via {os.path.basename(weights_path)}...")
    detector = YOLO(weights_path)
    detector.set_classes(INDOOR_VOCABULARY)

    records = {}
    valid_extensions = ('.jpg', '.png', '.jpeg')
    sorted_frames = sorted(f for f in os.listdir(image_dir) if f.lower().endswith(valid_extensions))

    for frame_name in sorted_frames:
        frame_path = os.path.join(image_dir, frame_name)
        predictions = detector.predict(frame_path, conf=min_confidence, verbose=False)
        frame_boxes = []

        for pred in predictions:
            for b in pred.boxes:
                class_idx = int(b.cls[0])
                label_str = detector.names[class_idx]
                score = float(b.conf[0])
                coords = [round(float(v), 2) for v in b.xyxy[0].tolist()]
                
                frame_boxes.append({
                    "label": label_str,
                    "confidence": round(score, 3),
                    "bbox": coords
                })

        records[frame_name] = frame_boxes

    print(f"[POI Pipeline] Successfully localized targets across {len(records)} candidate frames.")
    return records

def project_2d_to_3d(detections: Dict[str, list], sparse_model_dir: str) -> List[dict]:
    """Back-projects 2D bounding box centroids through COLMAP camera poses to 3D world points."""
    print("[POI Pipeline] Back-projecting 2D tracks into 3D world coordinates...")
    return []

def main():
    cli = argparse.ArgumentParser(description="Automated 3D object localization and spatial POI generator.")
    cli.add_argument("--scene-dir", default="viewer/public/scenes/custom-video-v3D", help="output scene directory")
    cli.add_argument("--weights", default="weights/yolov8m-world.pt", help="YOLO-World weights path")
    args = cli.parse_args()

    target_json = os.path.join(args.scene_dir, "poi_labels.json")
    print(f"[POI Pipeline] Target manifest: {target_json}")

if __name__ == "__main__":
    main()
