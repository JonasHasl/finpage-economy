(() => {
  "use strict";

  const selector = "#algo-trend-canvas";
  const mounted = new WeakSet();
  const palette = {
    grid: "rgba(82, 107, 128, 0.16)",
    areaTop: "rgba(4, 120, 87, 0.18)",
    areaBottom: "rgba(3, 105, 161, 0.02)",
    lineStart: "rgba(3, 105, 161, 0.88)",
    lineEnd: "rgba(4, 120, 87, 0.98)",
    glow: "rgba(4, 120, 87, 0.34)",
    point: "rgba(4, 120, 87, 0.98)",
    pointGlow: "rgba(4, 120, 87, 0.48)",
  };
  const levels = [
    0.10, 0.16, 0.13, 0.24, 0.30, 0.27, 0.39, 0.45,
    0.41, 0.54, 0.60, 0.57, 0.70, 0.77, 0.83, 0.94,
  ];

  const easeOutCubic = (value) => 1 - Math.pow(1 - value, 3);

  function tracedPoints(points, progress) {
    if (progress >= 1) return points;
    const scaled = Math.max(0, progress) * (points.length - 1);
    const whole = Math.floor(scaled);
    const result = points.slice(0, whole + 1);
    if (whole < points.length - 1) {
      const amount = scaled - whole;
      const start = points[whole];
      const end = points[whole + 1];
      result.push({
        x: start.x + (end.x - start.x) * amount,
        y: start.y + (end.y - start.y) * amount,
      });
    }
    return result;
  }

  function curvePath(context, points) {
    if (!points.length) return;
    context.moveTo(points[0].x, points[0].y);
    for (let index = 1; index < points.length - 1; index += 1) {
      const midpointX = (points[index].x + points[index + 1].x) / 2;
      const midpointY = (points[index].y + points[index + 1].y) / 2;
      context.quadraticCurveTo(points[index].x, points[index].y, midpointX, midpointY);
    }
    if (points.length > 1) {
      const last = points[points.length - 1];
      context.lineTo(last.x, last.y);
    }
  }

  function mount(canvas) {
    if (mounted.has(canvas)) return;
    mounted.add(canvas);

    const context = canvas.getContext("2d");
    if (!context) return;

    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const state = {
      width: 0,
      height: 0,
      ratio: Math.min(window.devicePixelRatio || 1, 2),
      startedAt: performance.now(),
      frame: null,
    };

    function resize() {
      const bounds = canvas.getBoundingClientRect();
      state.width = Math.max(1, bounds.width);
      state.height = Math.max(1, bounds.height);
      state.ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(state.width * state.ratio);
      canvas.height = Math.round(state.height * state.ratio);
      context.setTransform(state.ratio, 0, 0, state.ratio, 0, 0);
      draw(performance.now());
    }

    function draw(now) {
      const { width, height } = state;
      if (!width || !height) return;

      context.setTransform(state.ratio, 0, 0, state.ratio, 0, 0);
      context.clearRect(0, 0, width, height);

      context.save();
      context.strokeStyle = palette.grid;
      context.lineWidth = 1;
      for (const fraction of [0.25, 0.5, 0.75]) {
        const y = Math.round(height * fraction) + 0.5;
        context.beginPath();
        context.moveTo(0, y);
        context.lineTo(width, y);
        context.stroke();
      }
      context.restore();

      const reducedMotion = motionPreference.matches;
      const elapsed = Math.max(0, now - state.startedAt);
      const drawProgress = reducedMotion ? 1 : easeOutCubic(Math.min(1, elapsed / 1800));
      const horizontalPadding = Math.max(6, width * 0.012);
      const verticalPadding = Math.max(5, height * 0.08);
      const usableWidth = width - horizontalPadding * 2;
      const usableHeight = height - verticalPadding * 2;
      const points = levels.map((level, index) => {
        const wave = reducedMotion ? 0 : Math.sin(now / 900 + index * 0.72) * height * 0.012;
        return {
          x: horizontalPadding + (usableWidth * index) / (levels.length - 1),
          y: height - verticalPadding - level * usableHeight + wave,
        };
      });
      const visiblePoints = tracedPoints(points, drawProgress);
      if (visiblePoints.length < 2) return;

      const first = visiblePoints[0];
      const last = visiblePoints[visiblePoints.length - 1];

      context.save();
      context.beginPath();
      curvePath(context, visiblePoints);
      context.lineTo(last.x, height);
      context.lineTo(first.x, height);
      context.closePath();
      const area = context.createLinearGradient(0, 0, 0, height);
      area.addColorStop(0, palette.areaTop);
      area.addColorStop(1, palette.areaBottom);
      context.fillStyle = area;
      context.fill();
      context.restore();

      context.save();
      context.beginPath();
      curvePath(context, visiblePoints);
      const stroke = context.createLinearGradient(0, 0, width, 0);
      stroke.addColorStop(0, palette.lineStart);
      stroke.addColorStop(1, palette.lineEnd);
      context.strokeStyle = stroke;
      context.lineWidth = 2.4;
      context.lineCap = "round";
      context.lineJoin = "round";
      context.shadowColor = palette.glow;
      context.shadowBlur = 9;
      context.stroke();
      context.restore();

      const pulse = reducedMotion ? 1 : 1 + Math.sin(now / 330) * 0.22;
      context.save();
      context.beginPath();
      context.arc(last.x, last.y, 4.2 * pulse, 0, Math.PI * 2);
      context.fillStyle = palette.point;
      context.shadowColor = palette.pointGlow;
      context.shadowBlur = 12;
      context.fill();
      context.restore();
    }

    function animate(now) {
      if (!canvas.isConnected) {
        resizeObserver.disconnect();
        motionPreference.removeEventListener("change", restartForMotionPreference);
        state.frame = null;
        return;
      }
      draw(now);
      state.frame = window.requestAnimationFrame(animate);
    }

    function restartForMotionPreference() {
      if (state.frame !== null) {
        window.cancelAnimationFrame(state.frame);
        state.frame = null;
      }
      state.startedAt = performance.now() - (motionPreference.matches ? 1800 : 0);
      if (motionPreference.matches) {
        draw(performance.now());
      } else {
        state.frame = window.requestAnimationFrame(animate);
      }
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(canvas);
    motionPreference.addEventListener("change", restartForMotionPreference);
    resize();
    restartForMotionPreference();
  }

  function scan(root = document) {
    if (root.matches && root.matches(selector)) mount(root);
    if (root.querySelectorAll) root.querySelectorAll(selector).forEach(mount);
  }

  const observer = new MutationObserver((records) => {
    records.forEach((record) => record.addedNodes.forEach((node) => {
      if (node.nodeType === Node.ELEMENT_NODE) scan(node);
    }));
  });

  function start() {
    scan();
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
