# ====================================================================
# face_mesh_generator.py - a webcam face-mesh demo (draws the MediaPipe
# face wireframe on your video). An experiment parked in this repo,
# separate from the form filler.
# ====================================================================
import cv2
import numpy as np

def generate_face_mesh():
    # Initialize Face Detector (Haar Cascade)
    # This is built-in to OpenCV
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # Initialize Facemark (LBF)
    facemark = cv2.face.createFacemarkLBF()
    
    try:
        facemark.loadModel("lbfmodel.yaml")
    except cv2.error:
        print("Error: Could not load lbfmodel.yaml. Ensure it is in the same directory.")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open video capture.")
        return

    print("Face Landmark Generator Started. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        if len(faces) > 0:
            # Find landmarks
            ok, landmarks = facemark.fit(frame, faces)
            
            if ok:
                for marks in landmarks:
                    # marks is a list of (x, y) points
                    # Draw points
                    for (x, y) in marks[0]:
                        cv2.circle(frame, (int(x), int(y)), 2, (0, 255, 0), -1)
                    
                    # Draw connections (Mesh-like visualization)
                    # 68 points mapping:
                    # 0-16: Jaw
                    # 17-21: Right Eyebrow
                    # 22-26: Left Eyebrow
                    # 27-35: Nose
                    # 36-41: Right Eye
                    # 42-47: Left Eye
                    # 48-67: Mouth
                    
                    pts = marks[0].astype(np.int32)
                    
                    # Jaw
                    cv2.polylines(frame, [pts[0:17]], False, (255, 255, 255), 1)
                    # Eyebrows
                    cv2.polylines(frame, [pts[17:22]], False, (255, 255, 255), 1)
                    cv2.polylines(frame, [pts[22:27]], False, (255, 255, 255), 1)
                    # Nose
                    cv2.polylines(frame, [pts[27:31]], False, (255, 255, 255), 1)
                    cv2.polylines(frame, [pts[31:36]], False, (255, 255, 255), 1)
                    # Eyes
                    cv2.polylines(frame, [pts[36:42]], True, (255, 255, 255), 1)
                    cv2.polylines(frame, [pts[42:48]], True, (255, 255, 255), 1)
                    # Mouth
                    cv2.polylines(frame, [pts[48:60]], True, (255, 255, 255), 1)
                    cv2.polylines(frame, [pts[60:68]], True, (255, 255, 255), 1)

        # Display
        cv2.imshow('Face Landmark Generator', frame)

        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    generate_face_mesh()

