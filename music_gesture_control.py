# ====================================================================
# music_gesture_control.py - a hand-gesture music demo (webcam: move your
# hand to control sound). An experiment parked in this repo, separate from
# the form filler.
# ====================================================================
import cv2
import numpy as np
import math
import subprocess
import time
from collections import deque

# ==========================================
# CONFIGURATION
# ==========================================
# Hand Detection
MIN_HAND_AREA = 5000

# Gesture Thresholds
VOLUME_DIST_MIN = 50
VOLUME_DIST_MAX = 200
COOLDOWN_TIME = 2.0 # Seconds between triggers (Next)
PLAY_PAUSE_THRESH = 1.0 # Seconds to hold gesture to trigger

# Smoothing
VOLUME_HISTORY = deque(maxlen=5)

def run_applescript(script):
    """Runs an AppleScript command."""
    try:
        subprocess.run(['osascript', '-e', script], check=False)
    except Exception as e:
        print(f"Error running AppleScript: {e}")

def control_spotify(command, value=None):
    """Controls Spotify using AppleScript."""
    if command == "volume":
        # Value 0-100
        script = f'tell application "Spotify" to set sound volume to {int(value)}'
    elif command == "playpause":
        script = 'tell application "Spotify" to playpause'
    elif command == "next":
        script = 'tell application "Spotify" to next track'
    
    run_applescript(script)

def get_defects(contour):
    """Returns convexity defects and the hull."""
    hull_indices = cv2.convexHull(contour, returnPoints=False)
    hull_points = cv2.convexHull(contour, returnPoints=True)
    
    if len(hull_indices) > 3:
        defects = cv2.convexityDefects(contour, hull_indices)
        return defects, hull_points
    return None, hull_points

def count_fingers(contour, defects):
    """Counts fingers based on convexity defects."""
    if defects is None: return 0
    
    count = 0
    for i in range(defects.shape[0]):
        s, e, f, d = defects[i, 0]
        start = tuple(contour[s][0])
        end = tuple(contour[e][0])
        far = tuple(contour[f][0])
        
        # Triangle sides
        a = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
        b = math.sqrt((far[0] - start[0])**2 + (far[1] - start[1])**2)
        c = math.sqrt((end[0] - far[0])**2 + (end[1] - far[1])**2)
        
        # Cosine rule for angle
        angle = math.acos((b**2 + c**2 - a**2) / (2*b*c)) * 57
        
        # Ignore angles > 90 and very close points
        if angle <= 90 and d > 3000: # d is distance from hull
            count += 1
            
    return count + 1 # +1 because 4 gaps = 5 fingers

def draw_structural_mesh(frame, contour, defects, hull_points, centroid):
    """Draws a sci-fi style mesh on the hand."""
    cx, cy = centroid
    
    # 1. Draw Centroid
    cv2.circle(frame, (cx, cy), 8, (0, 255, 255), -1)
    
    # 2. Draw Hull (Outer Boundary)
    cv2.drawContours(frame, [hull_points], -1, (0, 255, 0), 2)
    
    # 3. Connect Centroid to Defects (Webbing)
    if defects is not None:
        for i in range(defects.shape[0]):
            s, e, f, d = defects[i, 0]
            far = tuple(contour[f][0])
            # Only draw deep defects
            if d > 3000:
                cv2.line(frame, (cx, cy), far, (255, 255, 0), 1)
                cv2.circle(frame, far, 4, (0, 0, 255), -1)

def main():
    cap = cv2.VideoCapture(0)
    
    # Calibration State
    calibrated = False
    roi_hist = None
    
    # Gesture State
    last_trigger_time = 0
    hand_state = "Open" # Open, Closed
    state_change_time = 0
    
    # Play/Pause Stability
    play_pause_start = 0
    
    print("Music Gesture Control Started.")
    print("1. Press 'c' to CALIBRATE skin color (Place hand in the green box).")
    print("2. Gestures:")
    print("   - Volume: 'L' shape (Thumb-Index distance).")
    print("   - Play/Pause: Two Hands (Hold for 1s).")
    print("   - Next Song: Open -> Close -> Open hand.")
    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        frame = cv2.flip(frame, 1)
        height, width = frame.shape[:2]
        
        # UI: Status Bar
        status_text = "Status: Idle"
        action_text = ""
        
        if not calibrated:
            # Draw Calibration Box
            cv2.rectangle(frame, (width//2 - 50, height//2 - 50), (width//2 + 50, height//2 + 50), (0, 255, 0), 2)
            cv2.putText(frame, "Place hand in box & press 'c'", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("Music Gesture Control", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                # Calibrate
                roi = frame[height//2 - 50:height//2 + 50, width//2 - 50:width//2 + 50]
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                roi_hist = cv2.calcHist([hsv_roi], [0, 1], None, [180, 256], [0, 180, 0, 256])
                cv2.normalize(roi_hist, roi_hist, 0, 255, cv2.NORM_MINMAX)
                calibrated = True
                print("Calibrated!")
            elif key == ord('q'):
                break
            continue

        # Processing
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        dst = cv2.calcBackProject([hsv], [0, 1], roi_hist, [0, 180, 0, 256], 1)
        
        # Smooth and Threshold
        disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cv2.filter2D(dst, -1, disc, dst)
        _, thresh = cv2.threshold(dst, 50, 255, 0)
        thresh = cv2.merge((thresh, thresh, thresh))
        
        # Find Contours (on single channel)
        thresh_gray = cv2.cvtColor(thresh, cv2.COLOR_BGR2GRAY)
        contours, _ = cv2.findContours(thresh_gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter large contours (Hands)
        hands = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > MIN_HAND_AREA:
                hands.append(cnt)
        
        # Sort by area
        hands.sort(key=cv2.contourArea, reverse=True)
        
        # ---------------------------
        # GESTURE LOGIC
        # ---------------------------
        current_time = time.time()
        
        if len(hands) >= 2:
            # Two Hands Detected -> Play/Pause
            status_text = "Status: Two Hands Detected"
            
            # Draw Bounding Boxes
            for h in hands[:2]:
                x, y, w, h_rect = cv2.boundingRect(h)
                cv2.rectangle(frame, (x, y), (x+w, y+h_rect), (0, 255, 255), 2)
                cv2.putText(frame, "Hand", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
            if play_pause_start == 0:
                play_pause_start = current_time
            
            # Check duration
            hold_time = current_time - play_pause_start
            progress = min(hold_time / PLAY_PAUSE_THRESH, 1.0)
            
            # Draw Progress Bar
            cv2.rectangle(frame, (width//2 - 100, height - 100), (width//2 + 100, height - 80), (50, 50, 50), -1)
            cv2.rectangle(frame, (width//2 - 100, height - 100), (int(width//2 - 100 + 200 * progress), height - 80), (0, 255, 255), -1)
            cv2.putText(frame, "Hold for Play/Pause", (width//2 - 80, height - 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            if hold_time > PLAY_PAUSE_THRESH and (current_time - last_trigger_time > COOLDOWN_TIME):
                print("Gesture: Play/Pause")
                control_spotify("playpause")
                last_trigger_time = current_time
                action_text = "ACTION: PLAY/PAUSE"
                play_pause_start = 0 # Reset

        elif len(hands) == 1:
            play_pause_start = 0 # Reset if only 1 hand
            
            hand = hands[0]
            x, y, w, h_rect = cv2.boundingRect(hand)
            cv2.rectangle(frame, (x, y), (x+w, y+h_rect), (0, 255, 0), 2)
            cv2.putText(frame, "Hand", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            # Calculate Centroid
            M = cv2.moments(hand)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx, cy = 0, 0
            
            defects, hull_points = get_defects(hand)
            fingers = count_fingers(hand, defects)
            
            # Draw Structural Mesh
            draw_structural_mesh(frame, hand, defects, hull_points, (cx, cy))
            
            # Volume (L-Shape / Pinch)
            if defects is not None and fingers <= 2:
                status_text = "Status: Volume Control"
                max_dist = 0
                p1, p2 = None, None
                
                for i in range(defects.shape[0]):
                    s, e, f, d = defects[i, 0]
                    start = tuple(hand[s][0])
                    end = tuple(hand[e][0])
                    dist = math.hypot(end[0] - start[0], end[1] - start[1])
                    
                    if dist > max_dist:
                        max_dist = dist
                        p1, p2 = start, end
                
                if p1 and max_dist > 50:
                    cv2.line(frame, p1, p2, (255, 0, 0), 2)
                    cv2.circle(frame, p1, 5, (255, 0, 0), -1)
                    cv2.circle(frame, p2, 5, (255, 0, 0), -1)
                    
                    # Map distance to volume
                    dist_clamped = max(VOLUME_DIST_MIN, min(max_dist, VOLUME_DIST_MAX))
                    vol = ((dist_clamped - VOLUME_DIST_MIN) / (VOLUME_DIST_MAX - VOLUME_DIST_MIN)) * 100
                    
                    # Smooth Volume
                    VOLUME_HISTORY.append(vol)
                    avg_vol = sum(VOLUME_HISTORY) / len(VOLUME_HISTORY)
                    
                    cv2.putText(frame, f"Vol: {int(avg_vol)}%", (x, y - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    control_spotify("volume", avg_vol)

            # Next Song (Open -> Close -> Open)
            new_state = "Unknown"
            if fingers >= 4:
                new_state = "Open"
                status_text = "Status: Open Hand"
            elif fingers <= 1:
                new_state = "Closed"
                status_text = "Status: Fist (Closed)"
            
            if new_state != "Unknown":
                if hand_state == "Open" and new_state == "Closed":
                    # Started closing
                    state_change_time = current_time
                    hand_state = "Closed"
                elif hand_state == "Closed" and new_state == "Open":
                    # Opened again
                    if current_time - state_change_time < 1.0: # Fast transition
                        if current_time - last_trigger_time > COOLDOWN_TIME:
                            print("Gesture: Next Song")
                            control_spotify("next")
                            last_trigger_time = current_time
                            action_text = "ACTION: NEXT SONG"
                    hand_state = "Open"
            
            cv2.putText(frame, f"Fingers: {fingers}", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        else:
            play_pause_start = 0 # Reset

        # Draw HUD
        cv2.rectangle(frame, (0, height-40), (width, height), (0, 0, 0), -1)
        cv2.putText(frame, status_text, (10, height-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        if action_text:
            cv2.putText(frame, action_text, (width - 250, height-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow("Music Gesture Control", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
