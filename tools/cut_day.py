# 猫猫组件表 -> 命名散件（粗切，验货后再精修）
from PIL import Image
import os
SRC = r'C:\Users\94716\Desktop\papercup-ui\猫猫'
OUT = r'C:\Users\94716\projects\voice-call\tools\day_stage'
s1 = Image.open(os.path.join(SRC,'小组件1.png')).convert('RGBA')
s2 = Image.open(os.path.join(SRC,'小组件2.png')).convert('RGBA')
sd = Image.open(os.path.join(SRC,'拨号页小组件.png')).convert('RGBA')

cuts = [
 (s1,'btn_mic',   (544,104,760,324)),
 (s1,'btn_end',   (772,104,994,324)),
 (s1,'input_bar', (322,566,1122,694)),
 (s1,'note_keep', (12,402,276,664)),
 (s1,'k_bubble',  (328,410,1096,548)),
 (s1,'bear_baked',(52,30,530,386)),      # 带字的熊耳卡，仅参考勿用
 (s2,'logo',      (20,14,560,246)),
 (s2,'cup_string',(780,20,1070,270)),
 (s2,'bar_plain', (20,500,430,740)),
 (s2,'bar_tail2', (16,596,436,722)),
 (sd,'dial_search',(48,16,1012,270)),
 (sd,'dial_heart', (48,286,1044,500)),
 (sd,'dial_lock',  (54,512,1044,698)),
 (sd,'dial_bowx',  (1100,64,2124,276)),
 (sd,'dial_clipmic',(1132,288,2122,492)),
 (sd,'dial_cal',   (1146,530,1514,698)),
 (sd,'dial_img',   (1582,528,1710,668)),
 (sd,'dial_add',   (1752,534,1888,690)),
 (sd,'dial_paw',   (1932,508,2132,700)),
]
for im,name,box in cuts:
    im.crop(box).save(os.path.join(OUT, name+'.png'))
    print(name, box, f'{box[2]-box[0]}x{box[3]-box[1]}')

# 验货拼图：缩到宽300贴网格
names = [n for _,n,_, in [(a,b,c) for a,b,c in cuts]]
imgs = [Image.open(os.path.join(OUT,n+'.png')) for n in names]
cols = 5; cw, ch, pad = 300, 220, 26
rows = (len(imgs)+cols-1)//cols
sheet = Image.new('RGBA',(cols*cw, rows*(ch+pad)),(40,40,60,255))
from PIL import ImageDraw
d = ImageDraw.Draw(sheet)
for i,(n,im) in enumerate(zip(names,imgs)):
    im2 = im.copy(); im2.thumbnail((cw-10, ch-10))
    x,y = (i%cols)*cw, (i//cols)*(ch+pad)
    sheet.paste(im2,(x+5,y+18),im2)
    d.text((x+6,y+2), f'{i}:{n}', fill=(255,255,160,255))
sheet.convert('RGB').save(os.path.join(OUT,'_contact.png'))
print('contact sheet ->', os.path.join(OUT,'_contact.png'))
