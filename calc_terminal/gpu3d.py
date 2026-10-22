"""
GPU-accelerated 3D companion views [BETA].

A terminal's stdout is text cells — there is no GPU access from inside
it, no matter how many ANSI escape codes are used. `sim3d.py` and
`atomsim.py` do real-time 3D *projection math* and render it as
characters, which looks good and runs everywhere, but it is not, and
cannot be, GPU-rendered.

This module is the honest way to deliver actual GPU-accelerated 3D:
it writes a small, self-contained HTML file that uses WebGL (via
three.js, loaded from a CDN) and opens it in the user's default
browser. The rendering then genuinely runs on the user's GPU, with
real 360-degree orbit/pan/zoom (mouse-driven, via OrbitControls) and a
real requestAnimationFrame loop (so it runs at the display's actual
refresh rate rather than a fixed terminal frame_delay).

Three views are supported:
  - atom view    -- nucleus + shell electrons for any supported element
  - graph view   -- a 3D surface plot of a user-given z = f(x, y)
  - scale view   -- the Planck length can't be rendered "to scale"
                    next to anything human-sized (the ratio is roughly
                    10^20 times bigger than the ratio of an atom to the
                    observable universe), so instead this draws a
                    logarithmic zoom ladder: Planck length -> proton ->
                    atom -> human -> Earth -> observable universe, each
                    a GPU-rendered 3D scene, so the *relative* scale is
                    honestly communicated instead of faked.

Requires nothing beyond the Python standard library to *generate* the
file; the browser fetches three.js itself over the network the same
way it would fetch any web page.
"""

import json
import os
import webbrowser

from .atomsim import ELEMENTS

EXPORT_DIR = os.path.join(os.path.expanduser("~"), "cct_exports")

_THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"
_ORBIT_CDN = "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js"

_PAGE_SHELL = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>CCT — GPU 3D · {title}</title>
<style>
  html, body {{ margin: 0; height: 100%; background: #0a0e14; overflow: hidden;
                font-family: -apple-system, Segoe UI, sans-serif; }}
  #hud {{ position: fixed; top: 12px; left: 16px; color: #b8c4d9; font-size: 13px;
          line-height: 1.5; pointer-events: none; text-shadow: 0 1px 3px #000; }}
  #hud b {{ color: #ffd580; }}
  #hint {{ position: fixed; bottom: 12px; left: 16px; color: #6b7684; font-size: 12px; }}
  canvas {{ display: block; }}
</style>
</head>
<body>
<div id="hud">{hud}</div>
<div id="hint">drag to orbit · scroll to zoom · right-drag to pan</div>
<script type="importmap">
{{ "imports": {{ "three": "{three_cdn}",
                 "three/addons/controls/OrbitControls.js": "{orbit_cdn}" }} }}
</script>
<script type="module">
import * as THREE from "three";
import {{ OrbitControls }} from "three/addons/controls/OrbitControls.js";

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0e14);
scene.fog = new THREE.FogExp2(0x0a0e14, 0.015);

const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, 0.01, 5000);
camera.position.set({cam_x}, {cam_y}, {cam_z});

const renderer = new THREE.WebGLRenderer({{ antialias: true }});
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;

scene.add(new THREE.AmbientLight(0x8899bb, 0.6));
const key = new THREE.PointLight(0xfff2cc, 2.2, 0, 0);
key.position.set(6, 8, 6);
scene.add(key);

{scene_js}

window.addEventListener("resize", () => {{
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
}});

let t = 0;
function animate() {{
  requestAnimationFrame(animate);
  t += 0.016;
  {animate_js}
  controls.update();
  renderer.render(scene, camera);
}}
animate();
</script>
</body>
</html>
"""


def _write(name, html):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def _open(path):
    try:
        webbrowser.open("file://" + os.path.abspath(path))
        return True
    except Exception:
        return False


# --------------------------------------------------------------- atom view --
def export_atom_view(z_num, open_browser=True):
    """Real-time GPU-rendered nucleus + electron-shell view for element
    Z=z_num. Electrons genuinely orbit (animated each frame), nucleons
    are placed randomly inside a small sphere."""
    if z_num not in ELEMENTS:
        return None, f"No shell data for Z={z_num} (supported: 1-36)."

    sym, name, shells, mass = ELEMENTS[z_num]
    neutrons = mass - z_num

    scene_js = [
        "const nucleus = new THREE.Group(); scene.add(nucleus);",
        f"const totalNucleons = {min(z_num + neutrons, 80)};",
        f"const protonCount = {z_num};",
        "for (let i = 0; i < totalNucleons; i++) {",
        "  const isP = i < protonCount;",
        "  const geo = new THREE.SphereGeometry(0.18, 16, 16);",
        "  const mat = new THREE.MeshStandardMaterial({",
        "    color: isP ? 0xff5f56 : 0x9aa4b2, roughness: 0.35, metalness: 0.2 });",
        "  const m = new THREE.Mesh(geo, mat);",
        "  const r = 0.45 * Math.cbrt(Math.random());",
        "  const th = Math.acos(2 * Math.random() - 1), ph = Math.random() * Math.PI * 2;",
        "  m.position.set(r*Math.sin(th)*Math.cos(ph), r*Math.sin(th)*Math.sin(ph), r*Math.cos(th));",
        "  nucleus.add(m);",
        "}",
        "const shellGroups = [];",
        f"const shells = {json.dumps(shells)};",
        "shells.forEach((count, si) => {",
        "  const radius = (si + 1) * 1.6;",
        "  const ring = new THREE.Mesh(",
        "    new THREE.TorusGeometry(radius, 0.006, 8, 128),",
        "    new THREE.MeshBasicMaterial({ color: 0x3a4a63, transparent: true, opacity: 0.5 }));",
        "  ring.rotation.x = Math.PI / 2 + si * 0.3;",
        "  scene.add(ring);",
        "  const group = new THREE.Group();",
        "  for (let e = 0; e < count; e++) {",
        "    const eMesh = new THREE.Mesh(",
        "      new THREE.SphereGeometry(0.12, 12, 12),",
        "      new THREE.MeshStandardMaterial({ color: 0x58a6ff, emissive: 0x1a3a6b, roughness: 0.2 }));",
        "    group.add(eMesh);",
        "  }",
        "  group.userData = { radius, count, tilt: si * 0.3, speed: 0.6 / Math.sqrt(si + 1) };",
        "  scene.add(group);",
        "  shellGroups.push(group);",
        "});",
    ]
    animate_js = [
        "shellGroups.forEach(g => {",
        "  const { radius, count, tilt, speed } = g.userData;",
        "  g.children.forEach((e, i) => {",
        "    const a = t * speed + (i / count) * Math.PI * 2;",
        "    const x = radius * Math.cos(a), z = radius * Math.sin(a);",
        "    e.position.set(x, Math.sin(tilt) * z * 0.3, z * Math.cos(tilt));",
        "  });",
        "});",
        "nucleus.rotation.y += 0.002;",
    ]
    hud = (f"<b>{name} ({sym})</b><br>Z = {z_num} &nbsp; mass \u2248 {mass} "
           f"&nbsp; nucleons = {z_num + neutrons}<br>shells: {shells}")
    html = _PAGE_SHELL.format(
        title=f"{name} atom", hud=hud, three_cdn=_THREE_CDN, orbit_cdn=_ORBIT_CDN,
        cam_x=4, cam_y=3, cam_z=6,
        scene_js="\n".join(scene_js), animate_js="\n".join(animate_js),
    )
    path = _write(f"gpu3d_atom_{sym}.html", html)
    if open_browser:
        _open(path)
    return path, None


# -------------------------------------------------------------- graph view --
_ALLOWED_GRAPH_FUNCS = "sin cos tan sqrt exp log abs pow"


def export_graph_view(expr="sin(sqrt(x*x+z*z))", x_range=(-6, 6), z_range=(-6, 6),
                       open_browser=True):
    """Real-time GPU-rendered 3D surface for z = f(x, z). `expr` must be
    a JS expression using only x, z, Math.* — it's inserted into a
    <script> that runs in the *user's own browser*, not evaluated by
    Python, so there's no eval() of untrusted input on the CCT side."""
    js_expr = expr
    scene_js = [
        "const N = 60;",
        f"const xr = [{x_range[0]}, {x_range[1]}], zr = [{z_range[0]}, {z_range[1]}];",
        "const geo = new THREE.PlaneGeometry(xr[1]-xr[0], zr[1]-zr[0], N, N);",
        "geo.rotateX(-Math.PI/2);",
        "const pos = geo.attributes.position;",
        "function f(x, z) { try { return (" + js_expr + "); } catch(e) { return 0; } }",
        "let maxY = 0.001;",
        "for (let i = 0; i < pos.count; i++) {",
        "  const x = pos.getX(i), z = pos.getZ(i);",
        "  const y = f(x, z);",
        "  pos.setY(i, y);",
        "  maxY = Math.max(maxY, Math.abs(y));",
        "}",
        "geo.computeVertexNormals();",
        "const mat = new THREE.MeshStandardMaterial({",
        "  color: 0x58a6ff, roughness: 0.35, metalness: 0.15, side: THREE.DoubleSide,",
        "  flatShading: false });",
        "const surface = new THREE.Mesh(geo, mat);",
        "scene.add(surface);",
        "const grid = new THREE.GridHelper(Math.max(xr[1]-xr[0], zr[1]-zr[0]), 20, 0x2a3a52, 0x1c2635);",
        "grid.position.y = -0.001;",
        "scene.add(grid);",
    ]
    animate_js = ["surface.rotation.y = Math.sin(t * 0.05) * 0.15;"]
    hud = f"<b>z = f(x, z)</b><br>{expr}<br>x, z \u2208 [{x_range[0]}, {x_range[1]}]"
    html = _PAGE_SHELL.format(
        title="surface", hud=hud, three_cdn=_THREE_CDN, orbit_cdn=_ORBIT_CDN,
        cam_x=7, cam_y=6, cam_z=9,
        scene_js="\n".join(scene_js), animate_js="\n".join(animate_js),
    )
    path = _write("gpu3d_graph.html", html)
    if open_browser:
        _open(path)
    return path, None


# -------------------------------------------------------------- scale view --
# Logarithmic zoom ladder. Each rung is drawn as a GPU-rendered sphere
# whose *label* states the real physical size — the spheres themselves
# are NOT drawn to relative scale (impossible to see 10^60 at once);
# what's real and to-scale is the exponent shown at each rung.
_SCALE_RUNGS = [
    ("Planck length", "1.616 \u00d7 10\u207b\u00b3\u2075 m", 0xff6b6b),
    ("Proton radius", "8.4 \u00d7 10\u207b\u00b9\u2076 m", 0xffa94d),
    ("Hydrogen atom (Bohr radius)", "5.3 \u00d7 10\u207b\u00b9\u00b9 m", 0xffd43b),
    ("A virus", "\u2248 10\u207b\u2077 m", 0x69db7c),
    ("Human", "\u2248 1.7 m", 0x58a6ff),
    ("Earth diameter", "1.27 \u00d7 10\u2077 m", 0x4dabf7),
    ("Observable universe", "\u2248 8.8 \u00d7 10\u00b2\u2076 m", 0xb197fc),
]


def export_scale_view(open_browser=True):
    """A logarithmic scale ladder from the Planck length to the
    observable universe, rendered as an orbit-able GPU 3D scene."""
    n = len(_SCALE_RUNGS)
    scene_js = ["const rungGroup = new THREE.Group(); scene.add(rungGroup);"]
    for i, (label, size, color) in enumerate(_SCALE_RUNGS):
        y = i * 2.2 - (n - 1) * 1.1
        scene_js += [
            f"{{ const m = new THREE.Mesh(new THREE.SphereGeometry(0.55, 32, 32),",
            f"    new THREE.MeshStandardMaterial({{ color: {color}, emissive: {color}, emissiveIntensity: 0.25, roughness: 0.3 }}));",
            f"  m.position.set(0, {y}, 0); rungGroup.add(m); }}",
        ]
    animate_js = ["rungGroup.rotation.y += 0.003;"]
    hud_lines = "<br>".join(f"<b>{l}</b> \u2014 {s}" for l, s, _ in _SCALE_RUNGS)
    hud = f"Logarithmic scale ladder \u2014 exponents are real, sphere sizes are not<br><br>{hud_lines}"
    html = _PAGE_SHELL.format(
        title="scale ladder", hud=hud, three_cdn=_THREE_CDN, orbit_cdn=_ORBIT_CDN,
        cam_x=5, cam_y=0, cam_z=10,
        scene_js="\n".join(scene_js), animate_js="\n".join(animate_js),
    )
    path = _write("gpu3d_scale.html", html)
    if open_browser:
        _open(path)
    return path, None
