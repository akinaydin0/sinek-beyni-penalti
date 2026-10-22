"""Bir şutun GERÇEK spike raster'ını 1080x1920 video (ya da PNG dizisi) olarak çizer.

Kaynak yalnızca kick.py'nin kaydettiği npz: her çizgi, modelde o nöronun attığı
bir spike'tır (zamanı 0.1 ms çözünürlükte). Uydurma parıltı, sahte veri, HUD yok.

Satırlar: sola döndüren 5 nöron (DNa01_L, DNa02_L, DNb05_L, DNg13_L, DNb06_R),
sağa döndüren 5 nöron (aynaları) ve ileri sürüş (oDN1 L/R).
Oynatma çizgisi soldan sağa ilerler; spike, oynatma çizgisi geçince belirir
(ilk 40 ms biyolojik zaman sarı, sonra beyaz). 1 s beyin zamanı varsayılan olarak
4 s'ye yayılır (4x yavaş; altta yazar), sonda 1 s durur.

Kullanım:
  .venv/bin/python -I raster.py --npz ../veri/beyin_raster/prova_beyin_kararlari/kick_01.npz
        [--out ../cikti/raster_prova_kick_01.mp4] [--png-dir DİZİN] [--slow 4] [--fps 60] [--no-text]
"""
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ortam  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

W, H = 1080, 1920
INK = (11, 11, 13)
WHITE = (255, 255, 255)
GREY = (220, 221, 222)
DIM = (120, 121, 124)
LINE = (42, 42, 42)
YELLOW = (255, 242, 0)
FONT_DIR = ortam.BEYIN / 'indirilen' / 'fonts'

SOL = ['DNa01_L', 'DNa02_L', 'DNb05_L', 'DNg13_L', 'DNb06_R']
SAG = ['DNa01_R', 'DNa02_R', 'DNb05_R', 'DNg13_R', 'DNb06_L']
ILERI = ['oDN1_L', 'oDN1_R']

X0, X1 = 270, 1010          # raster alanı (1000 ms)
ROW_H = 72
TICK_H = 50
TICK_W = 3
FLASH_S = 0.040


def font(ad, px):
    return ImageFont.truetype(str(FONT_DIR / f'JetBrainsMono-{ad}.ttf'), px)


def yerlesim(odn1=True):
    """Satır y merkezleri ve grup başlıkları."""
    y = 300
    rows, heads = {}, []
    gruplar = [('SOLA DÖNDÜREN', SOL), ('SAĞA DÖNDÜREN', SAG)] + ([('İLERİ SÜRÜŞ', ILERI)] if odn1 else [])
    for baslik, adlar in gruplar:
        heads.append((baslik, y))
        y += 48
        for a in adlar:
            rows[a] = y + ROW_H // 2
            y += ROW_H
        y += 46
    return rows, heads, y


def etiket(a):
    tip, s = a.split('_')
    return f'{tip} {s}'


def tx(t_s, t_run):
    return X0 + (X1 - X0) * (t_s / t_run)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--npz', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--png-dir', default=None)
    ap.add_argument('--slow', type=float, default=4.0)
    ap.add_argument('--fps', type=int, default=60)
    ap.add_argument('--hold', type=float, default=1.0)
    ap.add_argument('--no-text', action='store_true')
    ap.add_argument('--no-odn1', action='store_true')
    a = ap.parse_args()

    src = Path(a.npz).resolve()
    d = np.load(src, allow_pickle=False)
    labels = [str(x) for x in d['readout_labels']]
    t_run = float(d['t_run_s'])
    prova = bool(d['prova'])
    seed = int(d['trial_seed'])
    spikes = {lab: np.sort(d['ro_t'][d['ro_label_idx'] == k]) for k, lab in enumerate(labels)}
    rows, heads, y_end = yerlesim(not a.no_odn1)

    # sabit katman
    base = Image.new('RGB', (W, H), INK)
    dr = ImageDraw.Draw(base)
    f_lab, f_head, f_small, f_cnt = font('Bold', 30), font('Bold', 26), font('Regular', 24), font('ExtraBold', 64)
    for lab, yc in rows.items():
        dr.line([(X0, yc + TICK_H // 2), (X1, yc + TICK_H // 2)], fill=LINE, width=2)
        if not a.no_text:
            dr.text((X0 - 24, yc), etiket(lab), font=f_lab, fill=GREY, anchor='rm')
    if not a.no_text:
        for baslik, y in heads:
            dr.text((60, y + 10), baslik, font=f_head, fill=DIM, anchor='lm')
        ya = y_end - 20
        for ms, anc in ((0, 'lt'), (500, 'mt'), (1000, 'rt')):
            x = tx(ms / 1000 * t_run, t_run)
            dr.line([(x, ya - 14), (x, ya - 2)], fill=DIM, width=2)
            dr.text((x, ya + 6), f'{ms} ms', font=f_small, fill=DIM, anchor=anc)
        dr.text((W // 2, H - 280), 'FlyWire v783 · Shiu et al. 2024 LIF', font=f_small, fill=DIM, anchor='mm')
        dr.text((W // 2, H - 244), f'seed {seed} · 1 s beyin zamanı, {a.slow:g}x yavaş', font=f_small, fill=DIM, anchor='mm')
        if prova:
            dr.text((W // 2, 200), 'PROVA', font=f_head, fill=DIM, anchor='mm')

    n_main = int(round(t_run * a.slow * a.fps))
    n_hold = int(round(a.hold * a.fps))
    out = Path(a.out).resolve() if a.out else (ortam.CIKTI / f'raster_{src.parent.name}_{src.stem}.mp4')
    out.parent.mkdir(parents=True, exist_ok=True)
    png_dir = Path(a.png_dir).resolve() if a.png_dir else None
    if png_dir:
        png_dir.mkdir(parents=True, exist_ok=True)
    ff = None
    if not png_dir:
        ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                               '-s', f'{W}x{H}', '-r', str(a.fps), '-i', '-', '-c:v', 'libx264', '-preset', 'slow',
                               '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out)],
                              stdin=subprocess.PIPE)
    ycnt = y_end + 70
    for fi in range(n_main + n_hold):
        t_now = min(t_run, (fi + 1) / (a.slow * a.fps))  # bu kareye kadar geçen beyin zamanı
        im = base.copy()
        g = ImageDraw.Draw(im)
        for lab, yc in rows.items():
            s = spikes.get(lab, np.array([]))
            s = s[s <= t_now]
            for t in s:
                x = tx(t, t_run)
                col = YELLOW if (t_now - t) < FLASH_S and fi < n_main else WHITE
                g.rectangle([x - TICK_W / 2, yc - TICK_H / 2, x + TICK_W / 2, yc + TICK_H / 2], fill=col)
        if fi < n_main:
            xp = tx(t_now, t_run)
            g.line([(xp, rows[SOL[0]] - TICK_H), (xp, y_end - 40)], fill=DIM, width=2)
        if not a.no_text:
            nl = sum(int((spikes[k] <= t_now).sum()) for k in SOL)
            nr = sum(int((spikes[k] <= t_now).sum()) for k in SAG)
            done = fi >= n_main
            cl = YELLOW if done and nl > nr else WHITE
            cr = YELLOW if done and nr > nl else WHITE
            g.text((X0, ycnt), f'SOL {nl}', font=f_cnt, fill=cl, anchor='lm')
            g.text((X1, ycnt), f'SAĞ {nr}', font=f_cnt, fill=cr, anchor='rm')
        if png_dir:
            im.save(png_dir / f'{fi:05d}.png')
        else:
            ff.stdin.write(im.tobytes())
    if ff:
        ff.stdin.close()
        ff.wait()
    meta = {
        'source_npz': str(src.relative_to(ortam.PROJE)) if src.is_relative_to(ortam.PROJE) else str(src),
        'source_npz_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
        'trial_seed': seed, 'prova': prova, 'steer': float(d['steer']), 'decision_ms': int(d['decision_ms']),
        'fps': a.fps, 'slow_factor': a.slow, 'frames_main': n_main, 'frames_hold': n_hold,
        'frame_rule': 'frame f shows every spike with t <= (f+1)/(slow*fps) s of brain time',
        'spike_counts': {k: int(len(v)) for k, v in spikes.items()},
        'output': str(png_dir if png_dir else out),
    }
    side = (png_dir / 'meta.json') if png_dir else out.with_suffix('.json')
    side.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
    print('yazıldı:', meta['output'])


if __name__ == '__main__':
    main()
