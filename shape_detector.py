# ====================================================================
# shape_detector.py - a shape-recognition demo (webcam detects drawn or
# held shapes). An experiment parked in this repo, separate from the form
# filler.
# ====================================================================
import cv2
import numpy as np

# ==========================================
# PARAMETERS & CONFIGURATION
# ==========================================
# HSV Color Ranges (Hue: 0-180, Sat: 0-255, Val: 0-255)
# Adjust these if colors are not detected correctly.
# Red wraps around 0/180.
RED_LOWER1 = np.array([0, 50, 50])
RED_UPPER1 = np.array([10, 255, 255])
RED_LOWER2 = np.array([170, 50, 50])
RED_UPPER2 = np.array([180, 255, 255])

BLUE_LOWER = np.array([100, 50, 50])
BLUE_UPPER = np.array([130, 255, 255])

# Black detection threshold (Value channel < 80)
BLACK_VAL_THRESH = 80

# Depth Estimation Constants
# Focal Length: Depends on the camera. 600 is a good default for webcams.
# Known Width: Real-world width of the object in cm.
FOCAL_LENGTH = 600 
KNOWN_WIDTH_SMALL = 5.0   # cm (Ring/Triangle/Square)
KNOWN_WIDTH_BLIMP = 30.0  # cm (Blimp)

def nothing(x):
    """Callback function for trackbars (does nothing)"""
    pass

def get_color(img_hsv, contour):
    """
    Determines the color (Red, Blue, Black, or Unknown) of the object inside the contour.
    Uses the HSV color space.
    """
    mask = np.zeros(img_hsv.shape[:2], dtype=np.uint8)
    cv2.drawContours(mask, [contour], -1, 255, -1)
    
    # Calculate mean HSV inside the contour
    mean_val = cv2.mean(img_hsv, mask=mask)
    hue = mean_val[0]
    sat = mean_val[1]
    val = mean_val[2]

    # Check for Black (Low Value)
    if val < BLACK_VAL_THRESH:
        return "Black"

    # Check for Red (Two ranges because it wraps around 0)
    if (hue >= 0 and hue <= 10) or (hue >= 170 and hue <= 180):
        return "Red"
    
    # Check for Blue
    elif hue >= 100 and hue <= 130:
        return "Blue"
    
    return "Unknown"

def estimate_depth(width_px, is_blimp=False):
    """
    Estimates distance based on object width in pixels.
    Formula: Distance = (KnownWidth * FocalLength) / ApparentWidth
    """
    if is_blimp:
        known_width = KNOWN_WIDTH_BLIMP
    else:
        known_width = KNOWN_WIDTH_SMALL
        
    if width_px == 0: return 0
    return (known_width * FOCAL_LENGTH) / width_px

def draw_radar(objects, frame_width, frame_height):
    """
    Draws a top-down 'Radar' view of detected objects.
    X-axis: Horizontal position relative to camera center.
    Y-axis (on radar): Depth (Z).
    """
    radar_size = 400
    radar = np.zeros((radar_size, radar_size, 3), dtype=np.uint8)
    
    # Draw grid lines
    cv2.line(radar, (radar_size//2, 0), (radar_size//2, radar_size), (50, 50, 50), 1)
    cv2.line(radar, (0, radar_size - 50), (radar_size, radar_size - 50), (50, 50, 50), 1) # Camera line
    
    # Camera position
    cv2.circle(radar, (radar_size//2, radar_size - 50), 5, (255, 255, 255), -1)
    cv2.putText(radar, "Cam", (radar_size//2 - 15, radar_size - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    max_depth = 200 # cm, max range for radar
    scale_x = 0.5 # Scale factor for X position

    for obj in objects:
        label, color_name, x_cam, z_depth = obj
        
        # Map X (pixels) to Radar X
        x_offset = x_cam - (frame_width // 2)
        radar_x = int((radar_size // 2) + (x_offset * scale_x))
        
        # Map Z (cm) to Radar Y
        radar_y = int((radar_size - 50) - (z_depth * (radar_size - 50) / max_depth))
        
        # Clamp values
        radar_x = max(0, min(radar_size - 1, radar_x))
        radar_y = max(0, min(radar_size - 1, radar_y))
        
        # Color
        color = (200, 200, 200)
        if color_name == "Red": color = (0, 0, 255)
        elif color_name == "Blue": color = (255, 0, 0)
        elif color_name == "Black": color = (100, 100, 100)
        
        # Draw dot
        cv2.circle(radar, (radar_x, radar_y), 6, color, -1)
        cv2.putText(radar, f"{label} {int(z_depth)}cm", (radar_x + 8, radar_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    return radar

def detect_shapes():
    # Initialize video capture
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open video capture.")
        return

    # Create Settings Window
    cv2.namedWindow('Settings')
    # Trackbars for tuning
    cv2.createTrackbar('Min Area', 'Settings', 1000, 10000, nothing) # Filter small noise
    cv2.createTrackbar('Canny Low', 'Settings', 50, 255, nothing)    # Edge detection low thresh
    cv2.createTrackbar('Canny High', 'Settings', 150, 255, nothing)  # Edge detection high thresh
    cv2.createTrackbar('Circularity', 'Settings', 70, 100, nothing)  # Circle strictness (0-100 -> 0.0-1.0)

    print("Shape Detection Started. Adjust 'Settings' to tune detection.")
    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
            
        height, width = frame.shape[:2]

        # Get Trackbar Values
        min_area = cv2.getTrackbarPos('Min Area', 'Settings')
        canny_low = cv2.getTrackbarPos('Canny Low', 'Settings')
        canny_high = cv2.getTrackbarPos('Canny High', 'Settings')
        circularity_thresh = cv2.getTrackbarPos('Circularity', 'Settings') / 100.0

        # Preprocessing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Edge detection with tunable thresholds
        edges = cv2.Canny(blur, canny_low, canny_high)
        
        # Morphological Operations
        kernel = np.ones((5, 5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_objects = [] # Store for radar

        for contour in contours:
            area = cv2.contourArea(contour)
            # Filter small contours using Trackbar value
            if area < min_area: continue

            hull = cv2.convexHull(contour)
            epsilon = 0.04 * cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, epsilon, True)
            
            x, y, w, h = cv2.boundingRect(approx)
            shape_name = "Unknown"
            color_name = get_color(hsv, contour)
            
            # Shape Classification
            num_vertices = len(approx)
            is_blimp = False

            if num_vertices == 3:
                shape_name = "Triangle"
            elif num_vertices == 4:
                aspect_ratio = float(w) / h
                if 0.9 <= aspect_ratio <= 1.1:
                    shape_name = "Square"
                else:
                    # Strict filtering: Ignore rectangles or irregular quadrilaterals
                    shape_name = "Unknown" 
            else:
                # Circular check
                perimeter = cv2.arcLength(hull, True)
                if perimeter == 0: continue
                hull_area = cv2.contourArea(hull)
                circularity = 4 * np.pi * hull_area / (perimeter * perimeter)
                
                # Use Trackbar value for circularity
                if circularity > circularity_thresh:
                    # Blimp vs Ring Logic
                    if area > 10000 and color_name == "Blue":
                        shape_name = "Blimp"
                        is_blimp = True
                    else:
                        shape_name = "Ring"

            # Strict Filter: Only process if it is one of our target shapes
            if shape_name in ["Triangle", "Square", "Ring", "Blimp"]:
                depth_val = estimate_depth(w, is_blimp)
                
                # Center coordinates
                cx = x + w // 2
                cy = y + h // 2
                
                # Add to list for radar
                detected_objects.append((shape_name, color_name, cx, depth_val))
                
                # Draw
                label = f"{color_name} {shape_name}"
                depth_label = f"Z:{int(depth_val)}cm"
                
                cv2.drawContours(frame, [hull], -1, (0, 255, 0), 2)
                cv2.putText(frame, label, (x, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(frame, depth_label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Draw Radar
        radar_view = draw_radar(detected_objects, width, height)
        
        # Show windows
        cv2.imshow('Shape Detector', frame)
        cv2.imshow('Radar Map', radar_view)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    detect_shapes()
