import cv2
import os
from datetime import datetime


CAPTURE_FOLDER = "captures"


def capture_object(camera_index=0):
    os.makedirs(CAPTURE_FOLDER, exist_ok=True)

    camera = cv2.VideoCapture(camera_index)

    if not camera.isOpened():
        raise RuntimeError("Could not open webcam.")

    print("Camera opened.")
    print("Hold an object in front of the camera.")
    print("SPACE = capture")
    print("ESC = cancel")

    saved_path = None

    while True:
        success, frame = camera.read()

        if not success:
            print("Could not read webcam frame.")
            break

        # Instructions displayed on camera window
        cv2.putText(
            frame,
            "SPACE = Scan Object | ESC = Cancel",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.imshow("Object Scanner", frame)

        key = cv2.waitKey(1) & 0xFF

        # ESC
        if key == 27:
            break

        # SPACE
        if key == 32:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            saved_path = os.path.join(
                CAPTURE_FOLDER,
                f"scan_{timestamp}.jpg"
            )

            cv2.imwrite(saved_path, frame)

            print(f"Saved image: {saved_path}")
            break

    camera.release()
    cv2.destroyAllWindows()

    return saved_path


if __name__ == "__main__":
    capture_object()