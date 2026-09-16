# Crystal Orb Animation Spec v1（锁版）

> 作者：闻序 · 2026-09-15 交付，天天转交
> 状态：**v1 锁死**。Jester 可优化实现方式，**不允许擅自提高动画幅度和速度**。
> 后续总 UI 施工文档原样并入本规范。

## 总原则

> **位置变化 ≤ 6px；尺寸变化 ≤ 2.5%；常驻 glow 低强度；高亮只短暂出现。**

目标体感：盯着它几秒后才发现"诶，它一直在呼吸"，而不是打开网页第一秒"这球怎么在蹦迪"。
所有动画不得同时满功率跑。

## DOM 分层（5 层）

```html
<div class="orb-scene" data-state="listening">
  <div class="orb-ripple"></div>

  <div class="orbit orbit-back">
    <!-- SVG 椭圆轨道 + 水晶珠 -->
  </div>

  <div class="orb-float">
    <img class="orb-core" src="crystal-orb.webp" />
    <div class="orb-inner-glow"></div>
    <i class="glint glint-a"></i>
    <i class="glint glint-b"></i>
    <i class="glint glint-c"></i>
  </div>

  <div class="orbit orbit-front"></div>
</div>
```

**关键：浮动和音量缩放不抢同一个 transform。** `.orb-float` 负责上下漂，
`.orb-core` 负责 scale。JS 不得直接写 `element.style.transform`。

## 1. 整颗球：非常慢的失重悬浮

```css
@keyframes orbFloat {
  0%, 100% { transform: translate3d(0, 0, 0); }
  35%      { transform: translate3d(1px, -5px, 0); }
  70%      { transform: translate3d(-1px, 2px, 0); }
}
.orb-float { animation: orbFloat 6.8s ease-in-out infinite; }
```

## 2. 基础呼吸：光在呼吸，不是放大缩小

刻意不改 scale——scale 留给实时音量。

```css
@keyframes orbBreathe {
  0%, 100% {
    filter: brightness(1)
            drop-shadow(0 0 8px rgba(190,220,255,.20))
            drop-shadow(0 0 22px rgba(120,165,255,.10));
  }
  50% {
    filter: brightness(1.06)
            drop-shadow(0 0 12px rgba(210,235,255,.32))
            drop-shadow(0 0 32px rgba(135,175,255,.18));
  }
}
.orb-core {
  animation: orbBreathe 4.8s ease-in-out infinite;
  will-change: transform, filter;
}
```

## 3. 实时音量：CSS variable，封顶 2.5%

```css
.orb-core {
  transform: scale(calc(1 + var(--orb-level, 0) * .025));
  transition: transform 80ms linear;
}
```

```js
function setOrbLevel(level) {
  const normalized = Math.min(1, Math.max(0, level));
  orb.style.setProperty('--orb-level', normalized);
}
```

## 4. 水环：真前后遮挡轨道，禁止旋转球体 PNG

一顺一逆，周期故意不同（永不同步）：

```css
@keyframes orbitDriftA {
  from { transform: rotateZ(-8deg) rotateX(68deg) rotate(0deg); }
  to   { transform: rotateZ(-8deg) rotateX(68deg) rotate(360deg); }
}
@keyframes orbitDriftB {
  from { transform: rotateZ(52deg) rotateX(72deg) rotate(360deg); }
  to   { transform: rotateZ(52deg) rotateX(72deg) rotate(0deg); }
}
.orbit-a { animation: orbitDriftA 22s linear infinite; }
.orbit-b { animation: orbitDriftB 31s linear infinite; }
```

珠子作为 `.orbit` 的 child 固定在 SVG/path 上，父轨道转它自然跟着走。
**不要自己另写绕圈算法。**

```css
@keyframes crystalTwinkle {
  0%, 72%, 100% { filter: brightness(.95); }
  78% {
    filter: brightness(1.45)
            drop-shadow(0 0 6px rgba(230,245,255,.8));
  }
}
.crystal-bead { animation: crystalTwinkle 5.7s ease-in-out infinite; }
/* 不同珠子不同 animation-delay: -1.3s / -3.8s，不要一起闪 */
```

## 5. bling：随机折射星芒

星芒是 CSS/SVG 小十字，不跟固定循环走：

```css
@keyframes refractFlash {
  0%   { opacity: 0; transform: scale(.25) rotate(0deg); }
  35%  { opacity: 1; transform: scale(1) rotate(12deg); }
  100% { opacity: 0; transform: scale(1.35) rotate(22deg); }
}
.glint.flash { animation: refractFlash 720ms ease-out forwards; }
```

```js
function triggerRandomGlint() {
  const glints = [...document.querySelectorAll('.glint')];
  const el = glints[Math.floor(Math.random() * glints.length)];
  el.classList.remove('flash');
  void el.offsetWidth;           // reflow 重启动画
  el.classList.add('flash');
}
```

**不要 `setInterval(1000)`。** 每次结束后随机等 2.5–7 秒（speaking 时 0.8–2.8 秒）。

## 状态机（data-state）

```css
.orb-scene[data-state="listening"] { --glow-power: .75; }
.orb-scene[data-state="thinking"]  { --glow-power: 1;   }
.orb-scene[data-state="speaking"]  { --glow-power: 1.35; }
```

后端映射：CallState `listening/user_speaking → listening`、
`k_thinking → thinking`、`k_speaking → speaking`（Jester 注）。

### Listening：轻微涟漪（只要一圈淡波纹，不要雷达扫描）

```css
@keyframes listeningRipple {
  0%          { opacity: .22; transform: scale(.88); }
  70%, 100%   { opacity: 0;   transform: scale(1.14); }
}
[data-state="listening"] .orb-ripple {
  animation: listeningRipple 2.8s ease-out infinite;
}
```

### Thinking：内部柔光聚集（光往花心收，不要三个 loading 点）

```css
@keyframes thinkingGather {
  0%, 100% { opacity: .22; transform: scale(1.08); filter: blur(18px); }
  50%      { opacity: .48; transform: scale(.82);  filter: blur(10px); }
}
[data-state="thinking"] .orb-inner-glow {
  animation: thinkingGather 2.4s ease-in-out infinite;
}
```

### Speaking：不换动画，把现有世界"唤醒"

- 轨道速度：`22s / 31s → 15s / 21s`
- 呼吸光增强 15–25%
- glint 间隔：`2.5–7s → 0.8–2.8s`
- `himLevel` 接入：

```js
const level = Math.min(1, himLevel);
scene.style.setProperty('--orb-level', level);
scene.style.setProperty('--voice-glow', level);
```

```css
[data-state="speaking"] .orb-core {
  filter:
    brightness(calc(1.05 + var(--voice-glow) * .12))
    drop-shadow(0 0 calc(12px + var(--voice-glow) * 12px) rgba(205,230,255,.38));
}
```

K 声音越响，球越亮一点、稍微膨胀一点、折射更明显一点，**但永远不抽搐**。

## prefers-reduced-motion

```css
@media (prefers-reduced-motion: reduce) {
  .orb-float, .orb-core, .orbit,
  .orb-ripple, .orb-inner-glow, .crystal-bead {
    animation: none !important;
  }
  .orb-core {
    transition: filter .2s ease;
    transform: none !important;
  }
}
```

## 施工附注（Jester 实施层，不改动幅度/速度）

1. 轨道珠远端变暗：与轨道周期同相位的亮度/透明度曲线（远端 ≈0.45），纯 CSS。
2. filter 呼吸的性能兜底：真机掉帧时改用预渲染发光层 + opacity 呼吸（合成器友好），视觉等价。
3. speaking 提速时 animation-duration 变更会产生微小珠位跳变（慢轨道 + 暗珠，不可见级别），接受，不引入交叉渐隐复杂度。
