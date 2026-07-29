#!/usr/bin/env python3
"""
BiSlide Vertical Scan Pattern Animation
Creates an animated GIF showing the zigzag vertical scanning pattern
"""

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle, Circle
import numpy as np

# Scan parameters
NUM_SCANS = 20
WIDTH_MM = 30
HEIGHT_MM = 150
SPEED = 50  # mm per frame for animation

# Calculate positions
x_step = WIDTH_MM / NUM_SCANS

def generate_scan_path():
    """Generate the complete scan path as a list of (x, y) points."""
    path = [(0, 0)]  # Start at origin
    current_x = 0
    current_y = 0
    
    for i in range(NUM_SCANS):
        # Alternate between down and up
        if i % 2 == 0:
            # Scan DOWN
            path.append((current_x, HEIGHT_MM))
            current_y = HEIGHT_MM
            
            # Move RIGHT (if not last segment)
            if i < NUM_SCANS - 1:
                current_x += x_step
                path.append((current_x, current_y))
        else:
            # Scan UP
            path.append((current_x, 0))
            current_y = 0
            
            # Move RIGHT (if not last segment)
            if i < NUM_SCANS - 1:
                current_x += x_step
                path.append((current_x, current_y))
    
    return path

def interpolate_path(waypoints, speed):
    """Interpolate between waypoints for smooth animation."""
    full_path = []
    
    for i in range(len(waypoints) - 1):
        x1, y1 = waypoints[i]
        x2, y2 = waypoints[i + 1]
        
        distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        num_steps = max(int(distance / speed), 2)
        
        for j in range(num_steps):
            t = j / num_steps
            x = x1 + t * (x2 - x1)
            y = y1 + t * (y2 - y1)
            full_path.append((x, y))
    
    full_path.append(waypoints[-1])  # Add final point
    return full_path

# Generate paths
waypoints = generate_scan_path()
full_path = interpolate_path(waypoints, SPEED)

# Create figure
fig, ax = plt.subplots(figsize=(10, 8))
ax.set_xlim(-10, WIDTH_MM + 10)
ax.set_ylim(-10, HEIGHT_MM + 10)
ax.set_aspect('equal')
ax.grid(True, alpha=0.3, linestyle='--')
ax.set_xlabel('X Position (mm)', fontsize=12)
ax.set_ylabel('Y Position (mm)', fontsize=12)
ax.set_title('BiSlide Vertical Scan Pattern', fontsize=14, fontweight='bold')

# Draw scan area boundary
scan_area = Rectangle((0, 0), WIDTH_MM, HEIGHT_MM, 
                       fill=False, edgecolor='black', linewidth=2, linestyle='--')
ax.add_patch(scan_area)

# Initialize plot elements
trail_line, = ax.plot([], [], 'b-', linewidth=1.5, alpha=0.6, label='Scan path')
current_pos = Circle((0, 0), 2, color='red', zorder=5, label='Current position')
ax.add_patch(current_pos)

# Waypoint markers
waypoint_x = [w[0] for w in waypoints]
waypoint_y = [w[1] for w in waypoints]
ax.plot(waypoint_x, waypoint_y, 'go', markersize=6, alpha=0.5, label='Waypoints', zorder=3)

# Text annotations
info_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, 
                    verticalalignment='top', fontsize=10,
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

segment_text = ax.text(0.02, 0.88, '', transform=ax.transAxes,
                       verticalalignment='top', fontsize=10,
                       bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

ax.legend(loc='upper right', fontsize=10)

# Animation data
trail_x = []
trail_y = []
current_segment = 0
segment_starts = [0]
for i in range(len(waypoints) - 1):
    x1, y1 = waypoints[i]
    x2, y2 = waypoints[i + 1]
    distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    num_steps = max(int(distance / SPEED), 2)
    segment_starts.append(segment_starts[-1] + num_steps)

def init():
    trail_line.set_data([], [])
    current_pos.center = (0, 0)
    info_text.set_text('')
    segment_text.set_text('')
    return trail_line, current_pos, info_text, segment_text

def animate(frame):
    global trail_x, trail_y, current_segment
    
    if frame >= len(full_path):
        frame = len(full_path) - 1
    
    x, y = full_path[frame]
    
    # Update trail
    trail_x.append(x)
    trail_y.append(y)
    trail_line.set_data(trail_x, trail_y)
    
    # Update current position
    current_pos.center = (x, y)
    
    # Determine current segment
    for i, start_idx in enumerate(segment_starts[:-1]):
        if segment_starts[i] <= frame < segment_starts[i + 1]:
            current_segment = i
            break
    
    # Update info text
    progress = (frame / len(full_path)) * 100
    info_text.set_text(f'Position: ({x:.1f}, {y:.1f}) mm\nProgress: {progress:.1f}%')
    
    # Update segment info
    if current_segment < len(waypoints) - 1:
        seg_num = (current_segment // 2) + 1
        direction = "DOWN" if current_segment % 2 == 0 else "UP/RIGHT"
        if current_segment % 2 == 1 and current_segment < len(waypoints) - 2:
            direction = "UP"
        elif current_segment % 2 == 0 and current_segment > 0:
            direction = "RIGHT" if waypoints[current_segment][0] != waypoints[current_segment + 1][0] else "DOWN"
        
        # Determine actual direction
        if current_segment < len(waypoints) - 1:
            x1, y1 = waypoints[current_segment]
            x2, y2 = waypoints[current_segment + 1]
            if abs(x2 - x1) < 0.1:  # Vertical movement
                direction = "DOWN" if y2 > y1 else "UP"
            else:  # Horizontal movement
                direction = "RIGHT"
        
        segment_text.set_text(f'Segment: {seg_num}/{NUM_SCANS}\nDirection: {direction}')
    
    return trail_line, current_pos, info_text, segment_text

# Create animation
anim = animation.FuncAnimation(fig, animate, init_func=init,
                             frames=len(full_path), interval=50,
                             blit=True, repeat=True)

# Save as GIF
print("Generating animation...")
Writer = animation.writers['ffmpeg']
writer = Writer(fps=20, metadata=dict(artist='BiSlide Scanner'), bitrate=1800)
anim.save('bislide_scan_pattern.mp4', writer=writer, dpi=100)
print(f"Animation saved as 'bislide_scan_pattern.mp4'")
print(f"Total waypoints: {len(waypoints)}")
print(f"Total frames: {len(full_path)}")
print(f"Scan area: {WIDTH_MM} × {HEIGHT_MM} mm")
print(f"Number of vertical scans: {NUM_SCANS}")

# Display the animation
plt.tight_layout()
plt.show()
