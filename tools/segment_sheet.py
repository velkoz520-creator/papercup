# 组件表连通域分析：按 alpha 膨胀分簇，输出大件的包围盒（1/2 分辨率聚类防碎片）
import numpy as np, sys
from PIL import Image
from collections import deque

def blobs(alpha, scale=2, thr=12, gap=6):
    small = np.array(Image.fromarray(alpha).resize((alpha.shape[1]//scale, alpha.shape[0]//scale), Image.BILINEAR))
    mask = small > thr
    H, W = mask.shape
    # 膨胀：把 gap 像素内的邻域算连通（用最大池化近似）
    grown = mask.copy()
    for _ in range(gap):
        p = np.pad(grown, 1)
        grown = p[:-2,1:-1]|p[2:,1:-1]|p[1:-1,:-2]|p[1:-1,2:]|p[:-2,:-2]|p[:-2,2:]|p[2:,:-2]|p[2:,2:]|grown
    seen = np.zeros_like(grown, bool)
    out = []
    for y in range(H):
        for x in range(W):
            if grown[y,x] and not seen[y,x]:
                q = deque([(y,x)]); seen[y,x] = True
                ys, xs = [], []
                while q:
                    cy, cx = q.popleft()
                    if mask[cy,cx]: ys.append(cy); xs.append(cx)
                    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny, nx = cy+dy, cx+dx
                        if 0<=ny<H and 0<=nx<W and grown[ny,nx] and not seen[ny,nx]:
                            seen[ny,nx] = True; q.append((ny,nx))
                if not ys: continue
                y0,y1,x0,x1 = min(ys),max(ys),min(xs),max(xs)
                # 原图坐标，带 2px 余量
                out.append((x0*scale, y0*scale, (x1+1)*scale, (y1+1)*scale, (y1-y0+1)*(x1-x0+1)))
    out.sort(key=lambda b: -b[4])
    return out

for path in sys.argv[1:]:
    im = Image.open(path).convert('RGBA')
    a = np.array(im)[:,:,3]
    print(f'== {path.split(chr(92))[-1]} {im.size}')
    for i,(x0,y0,x1,y1,area) in enumerate([b for b in blobs(a) if b[4] > 1200][:22]):
        print(f'  #{i}: ({x0},{y0})-({x1},{y1}) w={x1-x0} h={y1-y0}')
