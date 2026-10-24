import json

from camera import capture_object
from analyzer import analyze_object


def main():
    print("Starting scanner...")

    image_path = capture_object()

    if image_path is None:
        print("Scan cancelled.")
        return

    print()
    print(f"Captured: {image_path}")
    print("Analyzing object...")
    print()

    result = analyze_object(image_path)

    print("=== OBJECT ANALYSIS ===")
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()