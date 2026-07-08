"""Generate a perfect single-page sandbox PDF for TDD testing.

Creates data/test_sandbox.pdf with known clean text so we can
validate the full extraction pipeline deterministically.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fitz  # PyMuPDF


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "test_sandbox.pdf")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    doc = fitz.open()
    page = doc.new_page()

    # Insert clean, predictable text that mirrors a real academic paper
    page.insert_text(
        fitz.Point(72, 72),  # 1-inch margin
        (
            "A Sandbox Study of 3D YOLO and Anomaly Detection\n"
            "By John Doe and Jane Smith\n"
            "Published in 2026 at Sandbox Journal of Robotics\n"
            "\n"
            "Abstract:\n"
            "This paper presents a simplified 3D YOLO anomaly detection framework.\n"
            "\n"
            "Introduction:\n"
            "Our framework focuses on spatial anomaly detection in industrial environments.\n"
            "It uses a 3D YOLO-based architecture with real-time video processing.\n"
            "However, it has one major limitation that affects real-world deployment.\n"
            "\n"
            "Method:\n"
            "We employ a custom 3D convolutional backbone with YOLO-style detection heads.\n"
            "The model is trained on synthetic anomaly data with mixed results.\n"
            "\n"
            "Conclusion:\n"
            "The limitation is that the model requires high lighting conditions\n"
            "to avoid false alarms. Future work should address this constraint.\n"
            "\n"
            "References:\n"
            "[1] Redmon et al., YOLOv3, 2018.\n"
            "[2] Doe et al., 3D Convolutions for Video, 2020.\n"
        ),
        fontsize=11,
        fontname="helv",
    )

    doc.save(OUTPUT_PATH)
    doc.close()
    print(f"Sandbox PDF written: {OUTPUT_PATH}")
    print(f"Pages: 1")
    print("Text preview:")
    print("  A Sandbox Study of 3D YOLO and Anomaly Detection")
    print("  By John Doe and Jane Smith")
    print("  Published in 2026 at Sandbox Journal of Robotics")
    print("  Limitation: requires high lighting conditions to avoid false alarms")


if __name__ == "__main__":
    main()