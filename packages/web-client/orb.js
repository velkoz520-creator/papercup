/* Papercup Crystal Orb FX —— 闻序《Crystal Orb Animation Spec v1》JS 层（锁版）
   幅度/速度参数全部以 spec 为准，改动画请改 docs/ORB-ANIMATION-SPEC.md 先过审。 */
(function () {
  'use strict';
  var STATE_MAP = { listening: 'listening', user_speaking: 'listening', thinking: 'thinking', speaking: 'speaking' };
  var GLINT_IDLE = [2500, 7000], GLINT_HOT = [800, 2800];
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var state = 'idle', glintTimer = null, tickTimer = null, startAt = 0;

  function scene() { return document.querySelector('.orb-scene'); }

  function fireGlint() {
    if (reduceMotion) return;
    var list = document.querySelectorAll('.glint');
    if (!list.length) return;
    var el = list[Math.floor(Math.random() * list.length)];
    el.classList.remove('flash');
    void el.offsetWidth;              /* reflow 重启动画（spec §5） */
    el.classList.add('flash');
  }

  function scheduleGlint() {
    clearTimeout(glintTimer);
    var range = state === 'speaking' ? GLINT_HOT : GLINT_IDLE;
    glintTimer = setTimeout(function () {
      fireGlint();
      scheduleGlint();
    }, range[0] + Math.random() * (range[1] - range[0]));
  }

  /* 音量 → CSS 变量（spec §3：球最多膨胀 2.5%，不抽搐） */
  function setLevel(v) {
    var s = scene(); if (!s) return;
    var n = Math.max(0, Math.min(1, v || 0));
    s.style.setProperty('--orb-level', n.toFixed(3));
    if (state === 'speaking') s.style.setProperty('--voice-glow', n.toFixed(3));
  }

  function setState(m) {
    state = STATE_MAP[m] || (m === 'idle' ? 'idle' : state);
    var s = scene();
    if (s) {
      s.dataset.state = state;
      if (state !== 'speaking') s.style.setProperty('--voice-glow', '0');
    }
    scheduleGlint();
  }

  /* 通话计时（概念图 03:28 那一颗） */
  function tick() {
    var el = document.getElementById('duration'); if (!el) return;
    var t = Math.max(0, Math.floor((Date.now() - startAt) / 1000));
    var h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
    el.textContent = (h ? h + ':' + String(m).padStart(2, '0') : String(m)) + ':' + String(s).padStart(2, '0');
  }
  function startTimer() { stopTimer(); startAt = Date.now(); tickTimer = setInterval(tick, 1000); tick(); }
  function stopTimer() { if (tickTimer) clearInterval(tickTimer); tickTimer = null; }

  window.OrbFX = { setState: setState, setLevel: setLevel, startTimer: startTimer, stopTimer: stopTimer, fireGlint: fireGlint };
  scheduleGlint();
})();
