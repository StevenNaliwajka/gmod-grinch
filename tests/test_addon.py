"""Checks for the Burrito Grinch player model addon.  Run: python3 -m unittest discover tests"""
import json, os, re, struct, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'source', 'scripts'))
from mdlbones import read_bones  # noqa: E402

LUA = open(os.path.join(ROOT, 'lua', 'autorun', 'burrito_grinch.lua')).read()
MODEL = re.search(r'local MODEL\s*=\s*"([^"]+)"', LUA).group(1)
HANDS = re.search(r'local HANDS\s*=\s*"([^"]+)"', LUA).group(1)


def textures(mdl):
    d = open(mdl, 'rb').read()
    n, idx = struct.unpack_from('<ii', d, 204)
    out = []
    for i in range(n):
        o = idx + i * 64
        s = o + struct.unpack_from('<i', d, o)[0]
        out.append(d[s:d.index(b'\0', s)].decode())
    return out


class Addon(unittest.TestCase):
    def test_every_menu_entry_has_a_picture(self):
        # the player model picker shows spawnicons/<model>.png; a model without one is a grey box
        entries = re.findall(r'list\.Set\("PlayerOptionsModel",\s*\w+,\s*(\w+)\)', LUA)
        self.assertTrue(entries, 'no PlayerOptionsModel entries found')
        for var in entries:
            path = re.search(r'local %s\s*=\s*"([^"]+)"' % var, LUA).group(1)
            png = os.path.join(ROOT, 'materials', 'spawnicons', path[:-4] + '.png')
            self.assertTrue(os.path.isfile(png), 'no picture for ' + path)
            head = open(png, 'rb').read(24)
            self.assertEqual(head[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', head[16:24]), (64, 64))

    def test_model_files_ship(self):
        for m in (MODEL, HANDS):
            for ext in ('.mdl', '.vvd', '.dx90.vtx'):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, m[:-4] + ext)), m[:-4] + ext)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, MODEL[:-4] + '.phy')), 'player model needs a ragdoll')

    def test_every_material_ships(self):
        for m in (MODEL, HANDS):
            for t in textures(os.path.join(ROOT, m)):
                base = os.path.join(ROOT, 'materials', 'models', 'player', 'burrito', 'grinch_ultimatum', t)
                self.assertTrue(os.path.isfile(base + '.vmt'), t + '.vmt')
                self.assertTrue(os.path.isfile(base + '.vtf'), t + '.vtf')

    def test_skeleton_is_stock_valvebiped(self):
        # GMod's animations only fit if the bind pose is the stock citizen's, bone for bone
        ref = json.load(open(os.path.join(ROOT, 'source', 'data', 'skeleton.json')))[:56]
        got = read_bones(os.path.join(ROOT, MODEL))
        self.assertEqual([b['name'] for b in got], [b['name'] for b in ref])
        for a, b in zip(got, ref):
            for p, q in zip(a['pos'], b['pos']):
                self.assertAlmostEqual(p, q, places=3, msg=a['name'])

    def test_hands_skeleton_is_stock_c_arms(self):
        ref = {b['name']: b for b in json.load(open(os.path.join(ROOT, 'source', 'data', 'carms_skeleton.json')))}
        for b in read_bones(os.path.join(ROOT, HANDS)):
            for p, q in zip(b['pos'], ref[b['name']]['pos']):
                self.assertAlmostEqual(p, q, places=3, msg=b['name'])


if __name__ == '__main__':
    unittest.main()
