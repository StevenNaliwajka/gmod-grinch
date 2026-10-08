# Build the Grinch's Ultimatum dancing Grinch around the GMod ValveBiped skeleton.
# Run: blender -b --python build_grinch.py -- <skeleton.json> <out.blend>
# Units: Source units, same axes as the compiled male_07 (character faces -Y, +X = character's left).
import bpy, bmesh, json, math, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
SKEL, OUT = argv[0], argv[1]
bones = json.load(open(SKEL))
B = {b['name'].replace('ValveBiped.', ''): Vector(b['wt']) for b in bones}

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)

# ---------------------------------------------------------------- materials
COLORS = {
    'grinch_skin':   (0.42, 0.86, 0.20),
    'grinch_fur':    (0.82, 0.90, 0.16),
    'grinch_eye':    (0.97, 0.90, 0.30),
    'grinch_pupil':  (0.10, 0.08, 0.05),
    'grinch_brow':   (0.70, 0.36, 0.10),
    'grinch_lips':   (0.78, 0.42, 0.68),
    'grinch_shirt':  (0.95, 0.95, 0.93),
    'grinch_jacket': (0.17, 0.17, 0.18),
    'grinch_lapel':  (0.42, 0.42, 0.44),
    'grinch_jeans':  (0.16, 0.30, 0.66),
    'grinch_belt':   (0.45, 0.26, 0.12),
    'grinch_buckle': (0.72, 0.70, 0.62),
    'grinch_shoe':   (0.22, 0.14, 0.09),
    'grinch_sole':   (0.85, 0.83, 0.78),
    'grinch_outline':(0.02, 0.02, 0.02),
}
MATS = {}
for name, c in COLORS.items():
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*[x ** 2.2 for x in c], 1)
    p.inputs['Roughness'].default_value = 0.8
    if name == 'grinch_outline':
        m.use_backface_culling = True
    m.use_fake_user = True
    MATS[name] = m

PARTS = []  # (object, allowed bones)

def finish(bm, name, mat, allowed, subsurf=1, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    me.materials.append(MATS[mat])
    if subsurf:
        md = ob.modifiers.new('sub', 'SUBSURF')
        md.levels = subsurf
        md.render_levels = subsurf
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier='sub')
    for p in ob.data.polygons:
        p.use_smooth = smooth
    PARTS.append((ob, allowed))
    return ob

def frames(path):
    """parallel-transport frames along a polyline"""
    T = []
    for i in range(len(path)):
        a = path[max(i - 1, 0)]; b = path[min(i + 1, len(path) - 1)]
        T.append((b - a).normalized())
    up = Vector((0, -1, 0)) if abs(T[0].y) < 0.9 else Vector((0, 0, 1))
    N = [(up - T[0] * up.dot(T[0])).normalized()]
    for i in range(1, len(T)):
        n = N[-1] - T[i] * N[-1].dot(T[i])
        if n.length < 1e-6:
            n = N[-1]
        N.append(n.normalized())
    return T, N

def tube(name, mat, pts, allowed, seg=12, cap0=True, cap1=True, subsurf=1, twist_up=None, gap=None):
    """pts: list of (center Vector, rx, ry) or (center, rx, ry_front, ry_back).
    rx is along frame binormal, ry along frame normal ('front' = +normal side).
    gap: function(i) -> half angle (rad) of an opening centred on the +normal direction (for an open jacket)."""
    path = [p[0] for p in pts]
    T, N = frames(path)
    if twist_up is not None:
        N = [(twist_up - t * twist_up.dot(t)).normalized() for t in T]
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        c, rx = p[0], p[1]
        ryf = p[2]; ryb = p[3] if len(p) > 3 else p[2]
        bn = T[i].cross(N[i]).normalized()
        ring = []
        g = gap(i) if gap else 0
        for k in range(seg + (1 if g else 0)):
            if g:
                a = g + (2 * math.pi - 2 * g) * k / seg
            else:
                a = 2 * math.pi * k / seg
            ca, sa = math.cos(a), math.sin(a)
            ry = ryf if ca > 0 else ryb
            v = c + N[i] * (ca * ry) + bn * (sa * rx)
            ring.append(bm.verts.new(v))
        rings.append(ring)
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        n = len(r0)
        rng = range(n - 1) if gap else range(n)
        for k in rng:
            bm.faces.new((r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]))
    if not gap:
        for ring, cap, flip in ((rings[0], cap0, True), (rings[-1], cap1, False)):
            if cap:
                c = bm.verts.new(sum((v.co for v in ring), Vector()) / len(ring))
                n = len(ring)
                for k in range(n):
                    f = (ring[k], ring[(k + 1) % n], c) if not flip else (ring[(k + 1) % n], ring[k], c)
                    bm.faces.new(f)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(bm, name, mat, allowed, subsurf)

def blob(name, mat, center, radii, allowed, rot=(0, 0, 0), seg=16, ring=10, cut=None, subsurf=0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1)
    R = Matrix.LocRotScale(center, None, None) @ \
        (Matrix.Rotation(rot[2], 4, 'Z') @ Matrix.Rotation(rot[1], 4, 'Y') @ Matrix.Rotation(rot[0], 4, 'X')) @ \
        Matrix.Diagonal((*radii, 1))
    if cut is not None:  # keep only the part of the unit sphere with z > cut (a lid)
        for v in bm.verts:
            if v.co.z < cut:
                v.co.z = cut
    bmesh.ops.transform(bm, matrix=R, verts=bm.verts)
    return finish(bm, name, mat, allowed, subsurf)

def lerp(a, b, t):
    return a + (b - a) * t

V = Vector
HEAD = ['Bip01_Head1']
NECK = ['Bip01_Neck1', 'Bip01_Head1', 'Bip01_Spine4']
TORSO = ['Bip01_Pelvis', 'Bip01_Spine', 'Bip01_Spine1', 'Bip01_Spine2', 'Bip01_Spine4', 'Bip01_Neck1',
         'Bip01_L_Clavicle', 'Bip01_R_Clavicle', 'Bip01_L_UpperArm', 'Bip01_R_UpperArm']

# ---------------------------------------------------------------- head
# rings: (z, centre y, rx, ry front, ry back)
head_rings = [
    (59.6, 2.6, 2.3, 2.3, 2.3),
    (61.6, 2.2, 2.2, 2.2, 2.2),
    (63.0, 1.2, 2.6, 2.8, 2.5),
    (63.7, -0.2, 3.3, 4.2, 2.9),
    (64.6, -0.6, 3.9, 4.9, 3.3),
    (65.7, -0.7, 4.25, 5.1, 3.6),
    (66.9, -0.5, 4.15, 4.8, 3.8),
    (68.2, -0.2, 3.95, 4.35, 3.9),
    (69.5, 0.0, 3.75, 4.15, 3.9),
    (70.9, 0.2, 3.4, 3.75, 3.7),
    (72.3, 0.4, 2.8, 3.0, 3.1),
    (73.4, 0.6, 1.9, 2.0, 2.1),
    (74.0, 0.7, 0.6, 0.6, 0.6),
]
pts = [(V((0, y, z)), rx, ryf, ryb) for z, y, rx, ryf, ryb in head_rings]
tube('head', 'grinch_skin', pts, NECK, seg=20, twist_up=V((0, -1, 0)), subsurf=2)

def face_y(x, z):
    """front surface y of the head at (x, z)"""
    for i in range(len(head_rings) - 1):
        z0, z1 = head_rings[i][0], head_rings[i + 1][0]
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            y = lerp(head_rings[i][1], head_rings[i + 1][1], t)
            rx = lerp(head_rings[i][2], head_rings[i + 1][2], t)
            ry = lerp(head_rings[i][3], head_rings[i + 1][3], t)
            return y - ry * math.sqrt(max(0.0, 1 - (x / rx) ** 2))
    return 0

# eyes: yellow almonds, heavy green upper lids (smug), small pupils glancing to the side
for s in (1, -1):
    ex, ez = 1.75 * s, 68.4
    ey = face_y(ex, ez) + 0.35
    yaw = -0.33 * s
    blob(f'eye_{s}', 'grinch_eye', V((ex, ey, ez)), (1.5, 0.6, 0.92), HEAD, rot=(0, 0, yaw))
    blob(f'lid_{s}', 'grinch_skin', V((ex, ey + 0.08, ez + 0.05)), (1.62, 0.74, 1.02), HEAD,
         rot=(0.3, 0.05 * s, yaw), cut=0.3)
    px = ex + 0.35 - (0.25 * s)
    blob(f'pupil_{s}', 'grinch_pupil', V((px, ey - 0.5, ez - 0.3)), (0.34, 0.14, 0.36), HEAD,
         rot=(0, 0, yaw), seg=10, ring=6)
    # brow: thick orange-brown arc, inner end low (scheming)
    bpts = []
    for k in range(6):
        t = k / 5
        x = s * lerp(0.45, 3.25, t)
        z = lerp(69.45, 70.15, t) + 0.55 * math.sin(t * math.pi)
        bpts.append((V((x, face_y(x, z) + 0.15, z)), lerp(0.42, 0.22, t), 0.3))
    tube(f'brow_{s}', 'grinch_brow', bpts, HEAD, seg=8, twist_up=V((0, -1, 0)))

# nose bump + nostrils
blob('nose', 'grinch_skin', V((0, face_y(0, 66.8) + 0.25, 66.8)), (0.9, 0.7, 0.65), HEAD)
for s in (1, -1):
    blob(f'nostril_{s}', 'grinch_pupil', V((0.42 * s, face_y(0.42, 66.45) - 0.12, 66.45)), (0.17, 0.1, 0.12), HEAD,
         seg=8, ring=6)
# smirk: pink-purple lips, curling up on the character's left
lpts = []
for k in range(9):
    t = k / 8
    x = lerp(-1.7, 1.9, t)
    z = 65.15 + 0.55 * t * t - 0.12 * math.sin(t * math.pi)
    lpts.append((V((x, face_y(x, z) + 0.1, z)), lerp(0.34, 0.2, abs(t - 0.45) * 1.6), 0.24))
tube('lips', 'grinch_lips', lpts, HEAD, seg=8, twist_up=V((0, -1, 0)))
# cheek/chin creases for the Grinch muzzle
for s in (1, -1):
    blob(f'cheek_{s}', 'grinch_skin', V((2.5 * s, face_y(2.5, 65.9) + 0.55, 65.9)), (1.2, 0.8, 1.0), HEAD)
blob('chin', 'grinch_skin', V((0.1, face_y(0, 64.0) + 0.6, 64.0)), (1.5, 0.9, 0.8), HEAD)

# flame-like tufts on top of the head
tufts = [
    [(V((0.0, 0.6, 73.4)), 1.35), (V((0.35, 0.55, 75.8)), 1.05), (V((-0.25, 0.7, 78.2)), 0.75),
     (V((0.45, 0.95, 80.4)), 0.42), (V((1.1, 1.2, 82.0)), 0.06)],
    [(V((1.4, 0.5, 72.9)), 1.0), (V((2.45, 0.55, 74.9)), 0.75), (V((2.75, 0.75, 77.0)), 0.42),
     (V((2.35, 1.0, 78.6)), 0.06)],
    [(V((-1.4, 0.5, 72.9)), 1.0), (V((-2.6, 0.6, 74.6)), 0.7), (V((-3.3, 0.85, 76.3)), 0.38),
     (V((-3.2, 1.1, 77.7)), 0.05)],
    [(V((0.6, 1.9, 72.9)), 0.9), (V((1.0, 2.9, 74.6)), 0.55), (V((0.6, 3.6, 76.0)), 0.05)],
]
for i, t in enumerate(tufts):
    tube(f'tuft_{i}', 'grinch_skin', [(c, r, r * 0.8) for c, r in t], HEAD, seg=10, cap1=False)
# little side spikes (ears of fur)
for s in (1, -1):
    tube(f'earfur_{s}', 'grinch_skin', [(V((3.6 * s, 0.9, 69.6)), 0.7, 0.5), (V((4.6 * s, 1.1, 70.9)), 0.35, 0.3),
                                        (V((5.0 * s, 1.3, 71.9)), 0.04, 0.04)], HEAD, seg=8, cap1=False)

# ---------------------------------------------------------------- neck fur (yellow-green ruff)
bm = bmesh.new()
n = 26
top, mid, bot = [], [], []
for k in range(n):
    a = 2 * math.pi * k / n
    ca, sa = math.cos(a), math.sin(a)
    front = max(0.0, -ca) ** 1.5
    top.append(bm.verts.new(V((2.45 * sa, 2.1 + 2.45 * ca, 62.9 - 0.8 * front))))
    rm = 3.3 + 1.2 * front
    mid.append(bm.verts.new(V((rm * sa, 2.2 + rm * ca, 60.9 - 1.6 * front))))
    spike = (1.4 + 3.8 * front) * (1.0 if k % 2 == 0 else 0.45)
    r = 3.6 + 1.7 * front
    bot.append(bm.verts.new(V((r * sa, 2.2 + r * ca, 60.4 - 1.4 * front - spike))))
for k in range(n):
    bm.faces.new((top[k], top[(k + 1) % n], mid[(k + 1) % n], mid[k]))
    bm.faces.new((mid[k], mid[(k + 1) % n], bot[(k + 1) % n], bot[k]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
fur = finish(bm, 'neckfur', 'grinch_fur', ['Bip01_Neck1', 'Bip01_Spine4'], subsurf=0, smooth=False)
sm = fur.modifiers.new('sol', 'SOLIDIFY'); sm.thickness = 0.35; sm.offset = 0
bpy.context.view_layer.objects.active = fur; bpy.ops.object.modifier_apply(modifier='sol')

# ---------------------------------------------------------------- torso: shirt and open jacket
shirt_rings = [  # z, cy, rx, ry front, ry back
    (38.6, 0.6, 6.6, 4.1, 4.3),
    (43.0, 0.9, 6.3, 4.0, 4.3),
    (48.0, 1.2, 6.8, 4.4, 4.6),
    (53.0, 1.5, 7.4, 4.8, 4.8),
    (57.0, 1.9, 7.3, 4.5, 4.5),
    (59.6, 2.3, 5.4, 3.5, 3.6),
    (61.2, 2.5, 3.0, 2.6, 2.6),
]
tube('shirt', 'grinch_shirt', [(V((0, y, z)), rx, f, b) for z, y, rx, f, b in shirt_rings], TORSO, seg=20,
     twist_up=V((0, -1, 0)), cap1=False)

jk = [  # the jacket hangs a little below the belt and is boxier
    (35.6, 0.5, 7.9, 5.4, 5.3),
    (38.6, 0.6, 7.6, 5.2, 5.1),
    (43.0, 0.9, 7.2, 5.0, 5.0),
    (48.0, 1.2, 7.6, 5.3, 5.3),
    (53.0, 1.5, 8.3, 5.6, 5.5),
    (57.0, 1.9, 8.3, 5.2, 5.2),
    (59.8, 2.3, 6.2, 4.0, 4.2),
    (61.4, 2.5, 4.0, 3.3, 3.4),
]
gaps = [0.95, 0.92, 0.85, 0.78, 0.66, 0.52, 0.48, 0.55]
jacket = tube('jacket', 'grinch_jacket', [(V((0, y, z)), rx, f, b) for z, y, rx, f, b in jk], TORSO, seg=22,
              twist_up=V((0, -1, 0)), gap=lambda i: gaps[i], subsurf=1)
sm = jacket.modifiers.new('sol', 'SOLIDIFY'); sm.thickness = 0.45; sm.offset = -1
bpy.context.view_layer.objects.active = jacket; bpy.ops.object.modifier_apply(modifier='sol')

# raised collar behind the neck
cpts = []
for k in range(9):
    a = math.radians(lerp(-120, 120, k / 8))
    cpts.append(V((4.1 * math.sin(a), 2.6 + 3.4 * math.cos(a) * -1, 61.0)))
bm = bmesh.new()
lo = [bm.verts.new(p) for p in cpts]
hi = [bm.verts.new(V((p.x * 1.18, 2.6 + (p.y - 2.6) * 1.2, 63.4))) for p in cpts]
for k in range(len(lo) - 1):
    bm.faces.new((lo[k], lo[k + 1], hi[k + 1], hi[k]))
col = finish(bm, 'collar', 'grinch_jacket', ['Bip01_Spine4', 'Bip01_Neck1'], subsurf=1)
sm = col.modifiers.new('sol', 'SOLIDIFY'); sm.thickness = 0.4
bpy.context.view_layer.objects.active = col; bpy.ops.object.modifier_apply(modifier='sol')

# lapels: lighter grey flaps folded out along the opening
for s in (1, -1):
    bm = bmesh.new()
    def jpt(z, ang_off):
        # point on jacket surface near the opening at height z
        for i in range(len(jk) - 1):
            if jk[i][0] <= z <= jk[i + 1][0]:
                t = (z - jk[i][0]) / (jk[i + 1][0] - jk[i][0]); break
        g = lerp(gaps[i], gaps[i + 1], t) + ang_off
        y = lerp(jk[i][1], jk[i + 1][1], t); rx = lerp(jk[i][2], jk[i + 1][2], t); f = lerp(jk[i][3], jk[i + 1][3], t)
        return V((s * rx * math.sin(g), y - f * math.cos(g) - 0.25, z))
    a = [bm.verts.new(jpt(z, 0.0)) for z in (48.5, 52.0, 55.5, 58.5, 60.6)]
    b = [bm.verts.new(jpt(z, w)) for z, w in ((48.5, 0.05), (52.0, 0.35), (55.5, 0.55), (58.5, 0.45), (60.6, 0.3))]
    for k in range(4):
        f = bm.faces.new((a[k], a[k + 1], b[k + 1], b[k]) if s > 0 else (b[k], b[k + 1], a[k + 1], a[k]))
    lap = finish(bm, f'lapel_{s}', 'grinch_lapel', TORSO, subsurf=1)
    sm = lap.modifiers.new('sol', 'SOLIDIFY'); sm.thickness = 0.25
    bpy.context.view_layer.objects.active = lap; bpy.ops.object.modifier_apply(modifier='sol')

# sleeves
for s, side in ((1, 'L'), (-1, 'R')):
    sh = B[f'Bip01_{side}_UpperArm']; el = B[f'Bip01_{side}_Forearm']; wr = B[f'Bip01_{side}_Hand']
    start = V((5.6 * s, 2.0, 59.3))
    pts = [(start, 2.9, 2.9), (lerp(sh, el, 0.15), 2.85, 2.8), (lerp(sh, el, 0.6), 2.6, 2.55),
           (el, 2.45, 2.4), (lerp(el, wr, 0.5), 2.3, 2.25), (lerp(el, wr, 0.88), 2.25, 2.2),
           (lerp(el, wr, 0.93), 2.05, 2.0)]
    sl = tube(f'sleeve_{side}', 'grinch_jacket', pts, ['Bip01_' + side + '_' + x for x in ('Clavicle', 'UpperArm', 'Forearm', 'Hand')] + ['Bip01_Spine4'],
              seg=14, cap0=True, cap1=False)

# ---------------------------------------------------------------- hands with long claws
for s, side in ((1, 'L'), (-1, 'R')):
    hb = B[f'Bip01_{side}_Hand']
    knuck = (B[f'Bip01_{side}_Finger1'] + B[f'Bip01_{side}_Finger4']) / 2
    al = [f'Bip01_{side}_Hand', f'Bip01_{side}_Forearm']
    wrist0 = lerp(B[f'Bip01_{side}_Forearm'], hb, 0.86)
    tube(f'wrist_{side}', 'grinch_skin', [(wrist0, 1.35, 1.2), (hb, 1.3, 1.1)], al, seg=12, cap0=True)
    # palm: wide across the fingers, thin through the hand
    d = (knuck - hb).normalized()
    across = (B[f'Bip01_{side}_Finger4'] - B[f'Bip01_{side}_Finger1']).normalized()
    pal = [(hb, 1.35, 0.85), (lerp(hb, knuck, 0.55), 1.75, 0.8), (knuck, 1.75, 0.7)]
    tube(f'palm_{side}', 'grinch_skin', pal, al, seg=12, twist_up=d.cross(across).normalized())
    for f in range(5):
        c = [B[f'Bip01_{side}_Finger{f}'], B[f'Bip01_{side}_Finger{f}1'], B[f'Bip01_{side}_Finger{f}2']]
        tip = c[2] + (c[2] - c[1]).normalized() * (1.5 if f else 1.2)
        claw = tip + (c[2] - c[1]).normalized() * 0.8
        names = [f'Bip01_{side}_Finger{f}', f'Bip01_{side}_Finger{f}1', f'Bip01_{side}_Finger{f}2', f'Bip01_{side}_Hand']
        r = 0.5 if f else 0.55
        tube(f'finger_{side}{f}', 'grinch_skin',
             [(c[0], r, r), (c[1], r * 0.92, r * 0.88), (c[2], r * 0.82, r * 0.78), (tip, r * 0.6, r * 0.55),
              (claw, 0.06, 0.06)], names, seg=8, cap1=False)

# ---------------------------------------------------------------- jeans, belt, shoes
LEG = lambda side: [f'Bip01_{side}_Thigh', f'Bip01_{side}_Calf', f'Bip01_{side}_Foot', 'Bip01_Pelvis']
hip = [(36.0, 0.4, 6.7, 4.4, 4.6), (38.6, 0.5, 6.9, 4.4, 4.6), (41.6, 0.7, 6.8, 4.3, 4.5)]
tube('jeans_hip', 'grinch_jeans', [(V((0, y, z)), rx, f, b) for z, y, rx, f, b in hip],
     ['Bip01_Pelvis', 'Bip01_Spine', 'Bip01_L_Thigh', 'Bip01_R_Thigh'], seg=20, twist_up=V((0, -1, 0)))
for s, side in ((1, 'L'), (-1, 'R')):
    th, ca, ft = B[f'Bip01_{side}_Thigh'], B[f'Bip01_{side}_Calf'], B[f'Bip01_{side}_Foot']
    th2 = V((th.x * 0.95, th.y + 0.6, 37.5))
    pts = [(th2, 3.9, 3.8), (lerp(th, ca, 0.45), 3.4, 3.4), (ca, 2.95, 2.95), (lerp(ca, ft, 0.5), 2.85, 2.85),
           (lerp(ca, ft, 0.85), 3.05, 3.1), (V((ft.x, ft.y, 2.6)), 3.15, 3.2)]
    tube(f'jeans_{side}', 'grinch_jeans', pts, LEG(side), seg=16, twist_up=V((0, -1, 0)), cap1=False)
    # shoes
    toe = B[f'Bip01_{side}_Toe0']
    sp = [(V((ft.x, ft.y + 1.6, 1.9)), 1.95, 1.9), (V((ft.x, ft.y - 0.6, 1.9)), 2.2, 2.0),
          (V((toe.x, toe.y, 1.7)), 2.15, 1.7), (V((toe.x, toe.y - 2.4, 1.5)), 1.75, 1.3)]
    sh = tube(f'shoe_{side}', 'grinch_shoe', sp, [f'Bip01_{side}_Foot', f'Bip01_{side}_Toe0', f'Bip01_{side}_Calf'],
              seg=14, twist_up=V((0, 0, 1)))
    for v in sh.data.vertices:
        v.co.z = max(v.co.z, 0.55)
    tube(f'ankle_{side}', 'grinch_shoe', [(V((ft.x, ft.y + 0.8, 5.2)), 2.05, 2.1), (V((ft.x, ft.y + 0.6, 2.3)), 2.1, 2.2)],
         [f'Bip01_{side}_Foot', f'Bip01_{side}_Calf'], seg=14)
    sole = tube(f'sole_{side}', 'grinch_sole', [(V((ft.x, ft.y + 3.4, 0.55)), 2.0, 0.55),
                                               (V((ft.x, ft.y + 0.2, 0.55)), 2.2, 0.6),
                                               (V((toe.x, toe.y - 2.0, 0.6)), 1.85, 0.55),
                                               (V((toe.x, toe.y - 3.8, 0.75)), 0.9, 0.4)],
                [f'Bip01_{side}_Foot', f'Bip01_{side}_Toe0'], seg=10, twist_up=V((0, 0, 1)))
    for v in sole.data.vertices:
        v.co.z = max(v.co.z, 0.0)

belt = [(39.9, 0.55, 7.05, 4.6, 4.8), (41.3, 0.65, 7.0, 4.55, 4.75)]
tube('belt', 'grinch_belt', [(V((0, y, z)), rx, f, b) for z, y, rx, f, b in belt],
     ['Bip01_Pelvis', 'Bip01_Spine'], seg=20, twist_up=V((0, -1, 0)), subsurf=0)
blob('buckle', 'grinch_buckle', V((0, 0.55 - 4.65, 40.6)), (1.0, 0.25, 0.75), ['Bip01_Pelvis'], seg=8, ring=4)

# ---------------------------------------------------------------- outline shells (inverted hull) for the cartoon look
OUTLINE_SKIP = {'pupil_1', 'pupil_-1', 'nostril_1', 'nostril_-1'}
for ob, _ in PARTS:
    ob['outline'] = 0.0 if ob.name in OUTLINE_SKIP else (0.09 if ob.name.startswith(('eye', 'lid', 'brow', 'lips', 'finger', 'nose', 'cheek', 'chin', 'buckle')) else 0.16)
    ob['allowed'] = json.dumps(PARTS[[p[0] for p in PARTS].index(ob)][1])

# ---------------------------------------------------------------- weighting helper armature (only used to compute weights here)
SKIP = {'ValveBiped.forward', 'ValveBiped.Anim_Attachment_RH', 'ValveBiped.Anim_Attachment_LH'}
segs = {}
for i, b in enumerate(bones[:56]):
    if b['name'] in SKIP:
        continue
    kids = [c for c in bones[:56] if c['parent'] == i and c['name'] not in SKIP]
    h = Vector(b['wt'])
    if kids:
        t = sum((Vector(k['wt']) for k in kids), Vector()) / len(kids)
    else:
        p = Vector(bones[b['parent']]['wt'])
        t = h + (h - p).normalized() * (3 if 'Finger' in b['name'] else 4)
    if 'Hand' in b['name'] and 'Finger' not in b['name']:
        side = 'L' if '_L_' in b['name'] else 'R'
        t = (B[f'Bip01_{side}_Finger1'] + B[f'Bip01_{side}_Finger4']) / 2
    if b['name'].endswith('Head1'):
        t = h + Vector((0, -0.5, 9))
    segs[b['name'].replace('ValveBiped.', '')] = (h, t)

def segdist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.dot(ab), 1e-9)))
    return (p - (a + ab * t)).length

for ob, allowed in PARTS:
    for g in list(ob.vertex_groups):
        ob.vertex_groups.remove(g)
    groups = {n: ob.vertex_groups.new(name='ValveBiped.' + n) for n in allowed}
    for v in ob.data.vertices:
        ds = sorted((segdist(v.co, *segs[n]), n) for n in allowed)
        best = ds[:3]
        d0 = best[0][0]
        ws = [(n, 1.0 / (max(d, 0.05) ** 4)) for d, n in best if d < d0 + 2.5]
        tot = sum(w for _, w in ws)
        for n, w in ws:
            if w / tot > 0.02:
                groups[n].add([v.index], w / tot, 'REPLACE')

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('BUILT', len(PARTS), 'parts', sum(len(o.data.polygons) for o, _ in PARTS), 'faces')
