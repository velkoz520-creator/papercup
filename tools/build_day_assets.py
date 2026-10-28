# 猫猫 day 主题资产产线：切割 + 抠底 + 修瑕疵 + 导出
import numpy as np, os
from PIL import Image, ImageFilter
from collections import deque

SRC = r'C:\Users\94716\Desktop\papercup-ui\猫猫'
WEB = r'C:\Users\94716\projects\voice-call\packages\web-client\assets\day'
STG = r'C:\Users\94716\projects\voice-call\tools\day_stage'
os.makedirs(WEB, exist_ok=True)

def load(n): return Image.open(os.path.join(SRC, n)).convert('RGBA')
def save(im, n): im.save(os.path.join(WEB, n)); print(n, im.size)

s1, s2, sd = load('小组件1.png'), load('小组件2.png'), load('拨号页小组件.png')

# --- 简单切件 ---
save(s2.crop((20,14,560,246)),  'logo.png')
save(s2.crop((780,20,1070,270)),'cup.png')
save(s2.crop((415,530,705,740)),'cloudkitten.png')
save(s1.crop((322,566,1122,694)),'input-bar.png')
save(s1.crop((12,402,276,664)), 'note-keep.png')
save(sd.crop((1100,64,2124,276)), 'dial-bowx.png')
save(sd.crop((1132,288,2122,492)), 'dial-clipmic.png')

# --- 圆形按钮：框内出圈清零 ---
def circle_crop(im, box, name, r_shave=2):
    c = im.crop(box); w,h = c.size
    a = np.array(c); yy,xx = np.mgrid[0:h,0:w]
    r = min(w,h)/2 - r_shave
    out = (xx-w/2)**2 + (yy-h/2)**2 <= r*r
    a[~out] = 0; a[...,3] = np.where(out, a[...,3], 0)
    save(Image.fromarray(a), name)
circle_crop(s1,(544,104,760,324),'btn-mic.png')
circle_crop(s1,(772,104,994,324),'btn-end.png')

# --- K 气泡 / 她的胶囊 ---
save(s1.crop((350,382,1116,560)), 'bub-k.png')
save(s2.crop((40,520,425,612)),   'bub-you.png')

# --- 猫猫板：棋盘格抠底（边缘泛洪 + 只留最大连通体） ---
im = load('猫猫板.png'); a = np.array(im).astype(np.int16)
H,W = a.shape[:2]
mx = a[...,:3].max(2); mn = a[...,:3].min(2)
checker = (mx-mn < 14) & (mn > 150)          # 低饱和浅色 = 棋盘格
bg = np.zeros((H,W), bool); q = deque()
for x in range(W):
    for y in (0,H-1):
        if checker[y,x] and not bg[y,x]: bg[y,x]=True; q.append((y,x))
for y in range(H):
    for x in (0,W-1):
        if checker[y,x] and not bg[y,x]: bg[y,x]=True; q.append((y,x))
while q:
    cy,cx = q.popleft()
    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
        ny,nx = cy+dy,cx+dx
        if 0<=ny<H and 0<=nx<W and checker[ny,nx] and not bg[ny,nx]:
            bg[ny,nx]=True; q.append((ny,nx))
alpha = np.where(bg,0,255).astype(np.uint8)
# 只留最大连通体
lab = np.zeros((H,W), np.int32); cur=0; best=(0,0)
for y in range(H):
    for x in range(W):
        if alpha[y,x]>0 and lab[y,x]==0:
            cur+=1; sz=0; q=deque([(y,x)]); lab[y,x]=cur
            while q:
                cy,cx=q.popleft(); sz+=1
                for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                    ny,nx=cy+dy,cx+dx
                    if 0<=ny<H and 0<=nx<W and alpha[ny,nx]>0 and lab[ny,nx]==0:
                        lab[ny,nx]=cur; q.append((ny,nx))
            if sz>best[1]: best=(cur,sz)
alpha[lab!=best[0]]=0
out = np.array(im); out[...,3]=alpha
# 裁到内容 + 1px 羽化
ys,xs = np.where(alpha>0)
out = out[ys.min()-2:ys.max()+3, xs.min()-2:xs.max()+3]
img = Image.fromarray(out)
a2 = np.array(img); a2[...,3] = np.array(Image.fromarray(a2[...,3]).filter(ImageFilter.GaussianBlur(1)))
save(Image.fromarray(a2), 'card-bear.png')

# --- 动态小猫爪：白底抠底 ---
im = load('动态小猫爪.png'); a = np.array(im).astype(np.int16)
H,W = a.shape[:2]
mx = a[...,:3].max(2); mn = a[...,:3].min(2)
white = (mn > 240) & (mx-mn < 10)
bg = np.zeros((H,W), bool); q = deque()
for x in range(W):
    for y in (0,H-1):
        if white[y,x] and not bg[y,x]: bg[y,x]=True; q.append((y,x))
for y in range(H):
    for x in (0,W-1):
        if white[y,x] and not bg[y,x]: bg[y,x]=True; q.append((y,x))
while q:
    cy,cx = q.popleft()
    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
        ny,nx = cy+dy,cx+dx
        if 0<=ny<H and 0<=nx<W and white[ny,nx] and not bg[ny,nx]:
            bg[ny,nx]=True; q.append((ny,nx))
alpha = np.where(bg,0,255).astype(np.uint8)
ys,xs = np.where(alpha>0)
out = np.array(im); out[...,3]=alpha
out = out[max(0,ys.min()-1):ys.max()+2, max(0,xs.min()-1):xs.max()+2]
img = Image.fromarray(out)
img.thumbnail((480,480), Image.LANCZOS)
save(img, 'paw.png')

# --- 拨号条：去假光标（左半找孤立竖线，横向插值抹掉） ---
def decaret(im, name):
    a = np.array(im); h,w = a.shape[:2]
    g = a[...,:3].mean(2).astype(np.int16)
    region = g[:, int(w*0.08):int(w*0.30)]
    dev = np.abs(region - np.median(region, axis=1, keepdims=True)).sum(0)
    cand = np.where(dev > dev.max()*0.55)[0] if dev.max()>0 else []
    if len(cand):
        x0,x1 = cand.min()+int(w*0.08), cand.max()+int(w*0.08)
        if 2 <= x1-x0 <= 14:
            L,R = x0-4, x1+4
            for y in range(h):
                for c in range(4):
                    a[y,x0:x1+1,c] = np.linspace(a[y,L,c], a[y,R,c], x1-x0+1)
    save(Image.fromarray(a), name)
decaret(sd.crop((48,16,1012,270)), 'dial-search.png')
decaret(sd.crop((54,512,1044,698)), 'dial-lock.png')

# --- 背景转 webp ---
load('通话页背景.png').convert('RGB').save(os.path.join(WEB,'bg-call.webp'), quality=88)
load('拨号页背景.png').convert('RGB').save(os.path.join(WEB,'bg-dial.webp'), quality=88)
print('bg-call.webp / bg-dial.webp ok')

# --- 验货拼图 v2 ---
names = sorted(os.listdir(WEB))
imgs = [Image.open(os.path.join(WEB,n)) for n in names if n!='_contact.png']
cols, cw, ch, pad = 5, 300, 210, 26
rows = (len(imgs)+cols-1)//cols
sheet = Image.new('RGB',(cols*cw, rows*(ch+pad)),(238,205,220))
from PIL import ImageDraw
d = ImageDraw.Draw(sheet)
for i,(n,im) in enumerate(zip([x for x in names if x!='_contact.png'],imgs)):
    im2 = im.copy(); im2.thumbnail((cw-10,ch-10))
    x,y = (i%cols)*cw,(i//cols)*(ch+pad)
    try: sheet.paste(im2,(x+5,y+18),im2)
    except ValueError: sheet.paste(im2.convert('RGB'),(x+5,y+18))
    d.text((x+6,y+2), n, fill=(120,30,60))
sheet.save(os.path.join(STG,'_contact2.png'))
print('contact2 ok')
