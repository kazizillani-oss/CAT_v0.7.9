"""
Real-time 3D Atom, Electron, and Proton Simulation for CCT [BETA].
Uses terminal-based 3D projection and creative ASCII/ANSI design.
"""

import math
import random
import sys
import time
from . import theme
from . import keys
from .atomsim import ELEMENTS, resolve_element, SHELL_NAMES

# 3D Projection Constants
FOV = 250
CAMERA_Z = 5.0

def project_3d(x, y, z, width, height, scale=1.0):
    """Simple 3D to 2D perspective projection."""
    factor = FOV / (z + CAMERA_Z)
    x_2d = x * factor * scale * 2.0  # Terminal char aspect ratio correction
    y_2d = y * factor * scale
    return int(width // 2 + x_2d), int(height // 2 - y_2d)

def rotate_y(x, y, z, angle):
    """Rotate around Y axis."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return x * cos_a + z * sin_a, y, -x * sin_a + z * cos_a

def rotate_x(x, y, z, angle):
    """Rotate around X axis."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return x, y * cos_a - z * sin_a, y * sin_a + z * cos_a

def get_3d_graph_data(z_num, angle):
    """Generate 3D graph data points for a potential field or electron density."""
    points = []
    # Real-time calculation of potential field V(r) = -kZe^2/r
    k = 1.0  # simplified units
    for i in range(-12, 13, 2):
        for j in range(-12, 13, 2):
            x = i / 4.0
            y = j / 4.0
            r = math.sqrt(x*x + y*y)
            # Electrostatic potential calculation
            val = -k * z_num / (r + 0.8)
            # Add wave function interference simulation
            val += 0.3 * math.sin(r * 3 - angle * 1.5)
            points.append((x, val, y))
    return points

def calculate_consequences(z_num, shells):
    """Calculate physical consequences based on the atomic configuration."""
    # 1. Bohr Radius for the outermost shell
    n_max = len(shells)
    rn = 0.529 * (n_max**2) / z_num # in Angstroms
    
    # 2. Ionization Energy (simplified)
    ie = 13.6 * (z_num**2) / (n_max**2) # in eV
    
    # 3. Effective Nuclear Charge (Slater's rule approximation)
    s = 0
    if n_max > 1:
        s = sum(shells[:-1]) * 0.85 + (shells[-1]-1) * 0.35
    else:
        s = (shells[0]-1) * 0.3
    z_eff = z_num - s
    
    return [
        f"Outer Radius: {rn:.3f} \u00c5",
        f"Ionization E: {ie:.2f} eV",
        f"Z-effective: {z_eff:.2f} (Slater)"
    ]

def atom_simulation_3d(z_num, out=sys.stdout, max_frames=1000, frame_delay=0.05):
    if z_num not in ELEMENTS:
        print(theme.red(f"  No shell data for element Z={z_num} (supported: 1-36)."))
        return

    sym, name, shells, mass = ELEMENTS[z_num]
    neutrons = mass - z_num
    
    angle_y = 0.0
    angle_x = 0.2
    speed = 0.1
    paused = False
    show_graph = False
    
    width, height = 70, 26
    interactive = keys.stdin_is_interactive()

    theme.hide_cursor()
    try:
        theme.clear_screen()
        frame = 0
        while frame < max_frames:
            grid = [[" "] * width for _ in range(height)]
            
            # 1. Draw 3D Graph if enabled
            if show_graph:
                graph_pts = get_3d_graph_data(z_num, angle_y)
                for gx, gy, gz in graph_pts:
                    rx, ry, rz = rotate_y(gx, gy, gz, angle_y * 0.5)
                    rx, ry, rz = rotate_x(rx, ry, rz, angle_x)
                    px, py = project_3d(rx, ry, rz, width, height, scale=1.5)
                    if 0 <= px < width and 0 <= py < height:
                        grid[py][px] = theme.faint("\u00b7")

            # 2. Draw Nucleus (Protons + Neutrons)
            random.seed(z_num * 13)
            total_nucleons = z_num + neutrons
            for i in range(min(total_nucleons, 50)):
                # Random position in a sphere
                phi = random.uniform(0, 2 * math.pi)
                costheta = random.uniform(-1, 1)
                u = random.uniform(0, 1)
                theta = math.acos(costheta)
                r = 0.4 * (u ** (1/3))
                
                nx = r * math.sin(theta) * math.cos(phi)
                ny = r * math.sin(theta) * math.sin(phi)
                nz = r * math.cos(theta)
                
                # Rotate nucleus
                rx, ry, rz = rotate_y(nx, ny, nz, angle_y * 0.2)
                rx, ry, rz = rotate_x(rx, ry, rz, angle_x)
                px, py = project_3d(rx, ry, rz, width, height)
                
                if 0 <= px < width and 0 <= py < height:
                    is_proton = (i < z_num)
                    ch = "P" if is_proton else "n"
                    color = theme.red if is_proton else theme.dim
                    grid[py][px] = color(ch, bold=True)

            # 3. Draw Electrons in Shells
            for si, count in enumerate(shells):
                radius = (si + 1) * 1.2
                e_speed = 1.0 / (si + 1) ** 0.5
                for e in range(count):
                    phase = 2 * math.pi * e / count
                    # Orbit in XZ plane initially
                    ex = radius * math.cos(angle_y * e_speed + phase)
                    ez = radius * math.sin(angle_y * e_speed + phase)
                    ey = 0
                    
                    # Tilt orbits slightly for "3D" feel
                    tilt = (si * 0.4)
                    ex, ey, ez = rotate_x(ex, ey, ez, tilt)
                    
                    # Apply global rotation
                    rx, ry, rz = rotate_y(ex, ey, ez, angle_y)
                    rx, ry, rz = rotate_x(rx, ry, rz, angle_x)
                    
                    px, py = project_3d(rx, ry, rz, width, height)
                    if 0 <= px < width and 0 <= py < height:
                        grid[py][px] = theme.cyan("\u25cf", bold=True)

            # Render frame
            theme.cursor_home()
            consequences = calculate_consequences(z_num, shells)
            info = [
                theme.badge("BETA", theme.BG_WARN) + " " + theme.purple(f"█ {name} ({sym}) 3D SIMULATION █", bold=True),
                theme.dim(f"Z: {z_num} ┃ MASS: ≈{mass} ┃ NUCLEONS: {total_nucleons}"),
                theme.dim("REAL-TIME: ") + theme.green(" ┃ ".join(consequences)),
                theme.dim("STATUS: ") + theme.orange("QUANTUM POTENTIAL MAPPING" if show_graph else "STABLE ELECTRON CONFIG"),
                ""
            ]
            lines = ["".join(row) for row in grid]
            out.write(theme.panel(info + lines, title="3D ATOM SIM", color=theme.CYAN, width=width + 4))
            
            # Controls
            out.write("\n" + theme.faint(
                "  [q] quit  [space] pause  [g] toggle 3D graph  [+/-] speed  [arrows] rotate") + "\n")
            out.flush()

            if not paused:
                angle_y += speed
                frame += 1

            if not interactive:
                out.write(theme.dim(
                    "\n  (no interactive terminal detected — showing a single "
                    "frame instead of the live view)\n"))
                out.flush()
                break

            if keys.key_available():
                k = keys.read_key()
                if k == "q": break
                elif k == " ": paused = not paused
                elif k == "g": show_graph = not show_graph
                elif k == "+": speed = min(0.5, speed + 0.02)
                elif k == "-": speed = max(0.01, speed - 0.02)
                # Arrow keys and W/A/S/D for rotation
                elif k in ("w", "\x1b[A"): angle_x += 0.1
                elif k in ("s", "\x1b[B"): angle_x -= 0.1
                elif k in ("a", "\x1b[D"): angle_y -= 0.1
                elif k in ("d", "\x1b[C"): angle_y += 0.1

            time.sleep(frame_delay)
            
    finally:
        theme.show_cursor()
    print()
