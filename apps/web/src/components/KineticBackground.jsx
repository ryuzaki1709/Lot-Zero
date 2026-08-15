import React, { useEffect, useRef } from 'react';

/**
 * Interactive dot-field background.
 * Desktop: dots brighten emerald and lean away from the cursor, with a slow-fading wake.
 * Touch/idle: a phantom point drifts along a Lissajous path so the field is always alive.
 * Non-interactive layer — pointer-events: none, reduced-motion aware, pauses off-tab.
 */
export function KineticBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const ctx = canvas.getContext('2d');
    let raf = 0;
    let running = true;

    const SPACING = 25;
    const RADIUS = 190;
    const BASE_ALPHA = 0.10;
    const MAX_ALPHA = 0.55;
    const MAX_SHIFT = 9;
    const ACCENT = '0, 220, 130';
    const WHITE = '196, 226, 210';
    const IDLE_AFTER = 2600; // ms without input before the phantom takes over

    let dpr = 1;
    let cols = 0;
    let rows = 0;
    let lastInput = 0;
    const pointer = { x: -9999, y: -9999 };
    const phantom = { x: 0, y: 0 };
    let energy = new Float32Array(0);

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      cols = Math.ceil(window.innerWidth / SPACING) + 1;
      rows = Math.ceil(window.innerHeight / SPACING) + 1;
      energy = new Float32Array(cols * rows);
    };

    const onPointer = (e) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
      lastInput = performance.now();
    };

    const onTouch = (e) => {
      if (e.touches && e.touches[0]) {
        pointer.x = e.touches[0].clientX;
        pointer.y = e.touches[0].clientY;
        lastInput = performance.now();
      }
    };

    const onLeave = () => {
      pointer.x = -9999;
      pointer.y = -9999;
    };

    const draw = (t) => {
      if (!running) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

      // Choose the active influence point: real pointer, or a drifting phantom.
      const idle = t - lastInput > IDLE_AFTER || pointer.x === -9999;
      let fx;
      let fy;
      if (idle && !reduceMotion) {
        // Lissajous drift across the viewport — slow, organic, never repeats visibly.
        phantom.x = window.innerWidth * (0.5 + 0.42 * Math.sin(t * 0.00011 + 1.3));
        phantom.y = window.innerHeight * (0.5 + 0.40 * Math.sin(t * 0.000151));
        fx = phantom.x;
        fy = phantom.y;
      } else {
        fx = pointer.x;
        fy = pointer.y;
      }
      const reach = idle ? RADIUS * 1.25 : RADIUS;
      const strength = idle ? 0.7 : 1; // phantom is softer than a real hand

      for (let iy = 0; iy < rows; iy++) {
        for (let ix = 0; ix < cols; ix++) {
          const px = ix * SPACING;
          const py = iy * SPACING;
          const idx = iy * cols + ix;

          let target = 0;
          let ox = 0;
          let oy = 0;

          if (!reduceMotion) {
            const dx = px - fx;
            const dy = py - fy;
            const dist = Math.hypot(dx, dy);
            if (dist < reach) {
              const falloff = 1 - dist / reach;
              target = falloff * falloff * strength;
              const push = MAX_SHIFT * target;
              const inv = dist === 0 ? 0 : 1 / dist;
              ox = dx * inv * push;
              oy = dy * inv * push;
            }
          }

          const e0 = energy[idx];
          energy[idx] = target > e0 ? e0 + (target - e0) * 0.35 : e0 + (target - e0) * 0.05;
          const e = energy[idx];

          const shimmer = reduceMotion
            ? 0
            : 0.03 * (1 + Math.sin(t * 0.0004 + px * 0.012 + py * 0.014));

          const alpha = BASE_ALPHA + shimmer + (MAX_ALPHA - BASE_ALPHA) * e;
          const size = 1.15 + 1.1 * e;
          const color = e > 0.06 ? ACCENT : WHITE;

          ctx.fillStyle = `rgba(${color}, ${alpha})`;
          ctx.beginPath();
          ctx.arc(px + ox, py + oy, size, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      raf = requestAnimationFrame(draw);
    };

    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else {
        running = true;
        raf = requestAnimationFrame(draw);
      }
    };

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onPointer, { passive: true });
    window.addEventListener('touchmove', onTouch, { passive: true });
    window.addEventListener('touchstart', onTouch, { passive: true });
    window.addEventListener('mouseout', onLeave);
    document.addEventListener('visibilitychange', onVisibility);
    raf = requestAnimationFrame(draw);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onPointer);
      window.removeEventListener('touchmove', onTouch);
      window.removeEventListener('touchstart', onTouch);
      window.removeEventListener('mouseout', onLeave);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }}
    />
  );
}
