import cv2
import numpy as np
import math
import time

# ==========================================
# CONFIGURATION
# ==========================================
# Color Tracking (Blue)
BLUE_LOWER = np.array([100, 50, 50])
BLUE_UPPER = np.array([130, 255, 255])

# 3D Engine
FOCAL_LENGTH = 600
CAMERA_Z = 5.0

# UI
HOVER_TIME_THRESH = 1.5 # Seconds to trigger selection

class Vector3:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

class Object3D:
    def __init__(self, type_name, position):
        self.type = type_name
        self.position = position # Vector3
        self.rotation = Vector3(0, 0, 0)
        self.scale = 1.0
        
        # Define vertices relative to center (0,0,0)
        if type_name == "Cube":
            s = 1.0
            self.vertices = [
                Vector3(-s, -s, -s), Vector3(s, -s, -s), Vector3(s, s, -s), Vector3(-s, s, -s), # Front
                Vector3(-s, -s, s), Vector3(s, -s, s), Vector3(s, s, s), Vector3(-s, s, s)      # Back
            ]
            self.edges = [
                (0,1), (1,2), (2,3), (3,0), # Front face
                (4,5), (5,6), (6,7), (7,4), # Back face
                (0,4), (1,5), (2,6), (3,7)  # Connecting lines
            ]
        elif type_name == "Pyramid":
            s = 1.0
            h = 1.5
            self.vertices = [
                Vector3(-s, 0, -s), Vector3(s, 0, -s), Vector3(s, 0, s), Vector3(-s, 0, s), # Base
                Vector3(0, -h, 0) # Tip
            ]
            self.edges = [
                (0,1), (1,2), (2,3), (3,0), # Base
                (0,4), (1,4), (2,4), (3,4)  # Sides
            ]

def project_point(v, width, height):
    """Projects 3D point to 2D screen coordinates"""
    # Simple perspective projection
    factor = FOCAL_LENGTH / (v.z + CAMERA_Z)
    x = int(v.x * factor + width / 2)
    y = int(v.y * factor + height / 2)
    return (x, y)

def rotate_point(v, angle_x, angle_y):
    """Rotates a point around X and Y axis"""
    # Rotate Y
    xz = complex(v.x, v.z)
    xz *= complex(math.cos(angle_y), math.sin(angle_y))
    rx, rz = xz.real, xz.imag
    
    # Rotate X
    yz = complex(v.y, rz)
    yz *= complex(math.cos(angle_x), math.sin(angle_x))
    ry, rz = yz.real, yz.imag
    
    return Vector3(rx, ry, rz)

def main():
    cap = cv2.VideoCapture(0)
    
    # State
    objects = []
    current_tool = "None" # None, Cube, Pyramid
    
    # Hover State
    hover_start_time = 0
    hover_target = None
    
    # Buttons
    buttons = [
        {"name": "Cube", "rect": (20, 50, 100, 50), "color": (0, 255, 0)},
        {"name": "Pyramid", "rect": (20, 120, 100, 50), "color": (0, 255, 255)},
        {"name": "Clear", "rect": (20, 190, 100, 50), "color": (0, 0, 255)}
    ]

    print("3D Gesture Modeler Started.")
    print("- Use a BLUE object as a cursor.")
    print("- Hover over buttons to select.")
    print("- Hover in center to place object.")
    print("- Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret: break
        
        frame = cv2.flip(frame, 1) # Mirror view
        height, width = frame.shape[:2]
        
        # 1. Track Cursor (Blue Object)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, BLUE_LOWER, BLUE_UPPER)
        mask = cv2.erode(mask, None, iterations=2)
        mask = cv2.dilate(mask, None, iterations=2)
        
        cnts, _ = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cursor_pos = None
        
        if len(cnts) > 0:
            c = max(cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            if radius > 10:
                cursor_pos = (int(x), int(y))
                cv2.circle(frame, cursor_pos, int(radius), (0, 255, 255), 2)
                cv2.circle(frame, cursor_pos, 5, (0, 0, 255), -1)

        # 2. UI Interaction
        is_hovering_ui = False
        if cursor_pos:
            cx, cy = cursor_pos
            
            # Check Buttons
            for btn in buttons:
                bx, by, bw, bh = btn["rect"]
                if bx < cx < bx + bw and by < cy < by + bh:
                    is_hovering_ui = True
                    if hover_target != btn["name"]:
                        hover_target = btn["name"]
                        hover_start_time = time.time()
                    
                    # Check Timer
                    elapsed = time.time() - hover_start_time
                    progress = min(elapsed / HOVER_TIME_THRESH, 1.0)
                    
                    # Draw Progress
                    cv2.rectangle(frame, (bx, by), (int(bx + bw * progress), by + bh), (255, 255, 255), -1)
                    
                    if elapsed >= HOVER_TIME_THRESH:
                        if btn["name"] == "Clear":
                            objects = []
                            current_tool = "None"
                        else:
                            current_tool = btn["name"]
                        hover_target = None # Reset
                        hover_start_time = 0
                
            # Check 3D Placement (if not hovering UI and tool selected)
            if not is_hovering_ui and current_tool != "None":
                if hover_target != "Place":
                    hover_target = "Place"
                    hover_start_time = time.time()
                
                elapsed = time.time() - hover_start_time
                
                # Draw Placement Progress at Cursor
                cv2.circle(frame, cursor_pos, 30, (255, 255, 255), 2)
                cv2.ellipse(frame, cursor_pos, (30, 30), 0, 0, 360 * (elapsed / HOVER_TIME_THRESH), (0, 255, 0), 4)
                
                if elapsed >= HOVER_TIME_THRESH:
                    # Place Object
                    # Map 2D cursor to 3D world (approximate Z=0 plane)
                    # x_screen = x_world * f / z_cam + w/2
                    # x_world = (x_screen - w/2) * z_cam / f
                    wx = (cx - width/2) * CAMERA_Z / FOCAL_LENGTH
                    wy = (cy - height/2) * CAMERA_Z / FOCAL_LENGTH
                    
                    objects.append(Object3D(current_tool, Vector3(wx, wy, 0)))
                    hover_target = None
                    hover_start_time = 0
            
            if not is_hovering_ui and hover_target != "Place":
                hover_target = None
                hover_start_time = 0

        # 3. Draw UI
        for btn in buttons:
            bx, by, bw, bh = btn["rect"]
            color = btn["color"]
            if current_tool == btn["name"]:
                color = (255, 255, 255) # Highlight selected
                
            cv2.rectangle(frame, (bx, by), (bx+bw, by+bh), color, 2)
            cv2.putText(frame, btn["name"], (bx+10, by+30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        # 4. Render 3D World
        # Auto-rotate world slightly for 3D effect
        world_rot_y = time.time() * 0.5
        
        for obj in objects:
            # Calculate world position relative to camera
            # (Simple: just move vertices)
            
            for edge in obj.edges:
                v1 = obj.vertices[edge[0]]
                v2 = obj.vertices[edge[1]]
                
                # Transform V1
                p1 = Vector3(v1.x + obj.position.x, v1.y + obj.position.y, v1.z + obj.position.z)
                # Rotate around center of object (optional) or world origin?
                # Let's rotate object around its own center for visual flair? 
                # No, let's rotate the whole world view
                
                p1 = rotate_point(p1, 0, world_rot_y)
                p2 = Vector3(v2.x + obj.position.x, v2.y + obj.position.y, v2.z + obj.position.z)
                p2 = rotate_point(p2, 0, world_rot_y)
                
                # Project
                pt1 = project_point(p1, width, height)
                pt2 = project_point(p2, width, height)
                
                cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

        cv2.imshow("3D Gesture Modeler", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
