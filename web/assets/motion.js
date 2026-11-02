/* Tile field, halftone shield, hover pill, card tilt, counters. No libraries. */
(function () {
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]still=1/.test(location.search);
  var hidden = document.hidden;

  function lerp(a, b, t) { return a + (b - a) * t; }
  function hue(t) {
    var stops = [[46, 94, 88], [124, 255, 91], [238, 249, 75], [46, 94, 88]];
    var x = ((t % 1) + 1) % 1 * (stops.length - 1);
    var i = Math.floor(x);
    var f = x - i;
    var a = stops[i];
    var b = stops[Math.min(i + 1, stops.length - 1)];
    return "rgb(" + Math.round(lerp(a[0], b[0], f)) + "," + Math.round(lerp(a[1], b[1], f)) + "," + Math.round(lerp(a[2], b[2], f)) + ")";
  }
  function fit(canvas, dprCap) {
    var dpr = Math.min(window.devicePixelRatio || 1, dprCap || 1.25);
    var w = canvas.clientWidth;
    var h = canvas.clientHeight;
    if (!w || !h) return null;
    var pw = Math.round(w * dpr);
    var ph = Math.round(h * dpr);
    if (canvas.width !== pw || canvas.height !== ph) {
      canvas.width = pw;
      canvas.height = ph;
    }
    var ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: w, h: h };
  }
  function onScreen(el, cb) {
    if (!("IntersectionObserver" in window)) { cb(true); return; }
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { cb(entry.isIntersecting); });
    }, { rootMargin: "80px" });
    obs.observe(el);
  }

  function makeTiles(canvas, opts) {
    if (!canvas) return function () {};
    var cells = [];
    var builtFor = "";
    function rebuild(w, h) {
      var key = w + "x" + h;
      if (key === builtFor) return;
      builtFor = key;
      cells = [];
      var size = opts.size;
      var gap = opts.gap;
      var step = size + gap;
      var cols = Math.ceil(w / step) + 1;
      var rows = Math.ceil(h / step) + 1;
      for (var y = 0; y < rows; y++) {
        for (var x = 0; x < cols; x++) {
          cells.push({
            x: x * step + (y % 2 ? step * 0.5 : 0),
            y: y * step,
            on: Math.random() > 0.45,
            next: performance.now() + 400 + Math.random() * 2200
          });
        }
      }
    }
    var alive = true;
    onScreen(canvas, function (v) { alive = v; });
    function draw(now) {
      var box = fit(canvas, 1.25);
      if (!box) return;
      rebuild(box.w, box.h);
      var ctx = box.ctx;
      ctx.clearRect(0, 0, box.w, box.h);
      var color = hue(now / 14000);
      var i;
      for (i = 0; i < cells.length; i++) {
        var cell = cells[i];
        if (!reduce && alive && now > cell.next) {
          cell.on = !cell.on;
          cell.next = now + 1000 + Math.random() * 2000;
        }
        var fade = opts.fade ? cell.x / box.w : 1;
        ctx.globalAlpha = cell.on ? 0.18 + fade * 0.72 : 0.05;
        ctx.fillStyle = cell.on ? color : "#2a2b26";
        ctx.fillRect(cell.x, cell.y, opts.size, opts.size);
      }
      ctx.globalAlpha = 1;
    }
    return draw;
  }

  var shieldMask = null;
  var shieldKey = "";
  function shieldDots(w, h) {
    var key = w + "x" + h;
    if (shieldMask && shieldKey === key) return shieldMask;
    shieldKey = key;
    var off = document.createElement("canvas");
    off.width = Math.round(w);
    off.height = Math.round(h);
    var g = off.getContext("2d");
    g.fillStyle = "#fff";
    g.beginPath();
    g.moveTo(w * 0.5, h * 0.06);
    g.lineTo(w * 0.84, h * 0.2);
    g.lineTo(w * 0.78, h * 0.55);
    g.quadraticCurveTo(w * 0.5, h * 0.96, w * 0.22, h * 0.55);
    g.lineTo(w * 0.16, h * 0.2);
    g.closePath();
    g.fill();
    var data = g.getImageData(0, 0, off.width, off.height).data;
    var dots = [];
    var step = 5;
    for (var y = 0; y < off.height; y += step) {
      for (var x = 0; x < off.width; x += step) {
        if (data[(y * off.width + x) * 4 + 3] > 128) {
          var nx = x / off.width;
          var ny = y / off.height;
          var light = Math.max(0.25, 1 - (nx * 0.55 + ny * 0.35));
          dots.push([x / off.width, y / off.height, light]);
        }
      }
    }
    shieldMask = dots;
    return dots;
  }

  function drawShield(canvas, now, spin) {
    var box = fit(canvas, 1.5);
    if (!box) return;
    var ctx = box.ctx;
    ctx.clearRect(0, 0, box.w, box.h);
    var dots = shieldDots(Math.round(box.w), Math.round(box.h));
    var color = hue(now / 14000);
    ctx.save();
    ctx.translate(box.w / 2, box.h / 2);
    ctx.rotate(spin);
    ctx.translate(-box.w / 2, -box.h / 2);
    ctx.fillStyle = color;
    for (var i = 0; i < dots.length; i++) {
      var d = dots[i];
      var s = 1.4 + d[2] * 2.4;
      ctx.globalAlpha = 0.35 + d[2] * 0.65;
      ctx.fillRect(d[0] * box.w - s / 2, d[1] * box.h - s / 2, s, s);
    }
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  function drawPile(canvas, now) {
    var box = fit(canvas, 1.25);
    if (!box) return;
    var ctx = box.ctx;
    var w = box.w;
    var h = box.h;
    ctx.clearRect(0, 0, w, h);
    var horizon = h * 0.62;
    var grad = ctx.createLinearGradient(0, horizon, 0, h);
    grad.addColorStop(0, "rgba(239,238,236,0.16)");
    grad.addColorStop(1, "rgba(239,238,236,0)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, horizon, w, h - horizon);
    ctx.strokeStyle = "rgba(239,238,236,0.35)";
    ctx.beginPath();
    ctx.moveTo(0, horizon);
    ctx.lineTo(w, horizon);
    ctx.stroke();
    var spots = [0.18, 0.34, 0.5, 0.66, 0.82];
    for (var i = 0; i < spots.length; i++) {
      var bob = reduce ? 0 : Math.sin(now / 900 + i) * 4;
      var cx = spots[i] * w;
      var cy = horizon - 46 + (i % 2) * 10 + bob;
      paintBadge(ctx, cx, cy, 34 + (i === 2 ? 10 : 0), hue((now / 14000) + i * 0.08), false);
      ctx.save();
      ctx.translate(cx, horizon + (horizon - cy) * 0.55);
      ctx.scale(1, -0.45);
      ctx.globalAlpha = 0.28;
      paintBadge(ctx, 0, 0, 34 + (i === 2 ? 10 : 0), hue((now / 14000) + i * 0.08), true);
      ctx.restore();
    }
  }

  function paintBadge(ctx, x, y, s, color, flat) {
    ctx.save();
    ctx.translate(x, y);
    ctx.beginPath();
    ctx.moveTo(0, -s);
    ctx.lineTo(s * 0.78, -s * 0.62);
    ctx.lineTo(s * 0.62, s * 0.28);
    ctx.quadraticCurveTo(0, s * 1.05, -s * 0.62, s * 0.28);
    ctx.lineTo(-s * 0.78, -s * 0.62);
    ctx.closePath();
    if (!flat) {
      var g = ctx.createLinearGradient(-s, -s, s, s);
      g.addColorStop(0, "#efeeec");
      g.addColorStop(0.45, color);
      g.addColorStop(1, "#1f3b3a");
      ctx.fillStyle = g;
    } else {
      ctx.fillStyle = color;
    }
    ctx.fill();
    ctx.restore();
  }

  var hero = document.querySelector(".hero");
  var tiles = document.getElementById("hero-tiles");
  var shield = document.getElementById("shield");
  var slot = document.getElementById("shield-slot");
  var cta = document.getElementById("cta-tiles");
  var pile = document.getElementById("badge-pile");
  var drawHeroTiles = makeTiles(tiles, { size: 26, gap: 7, fade: true });
  var drawCtaTiles = makeTiles(cta, { size: 18, gap: 6, fade: false });
  var heroOn = true;
  var ctaOn = false;
  var pileOn = false;
  if (hero) onScreen(hero, function (v) { heroOn = v; });
  if (cta) onScreen(cta, function (v) { ctaOn = v; });
  if (pile) onScreen(pile, function (v) { pileOn = v; });
  document.addEventListener("visibilitychange", function () { hidden = document.hidden; });

  var tiltX = 0;
  var tiltY = 0;
  if (hero && slot && !reduce) {
    hero.addEventListener("pointermove", function (event) {
      var rect = hero.getBoundingClientRect();
      tiltX = (event.clientX - rect.left) / rect.width - 0.5;
      tiltY = (event.clientY - rect.top) / rect.height - 0.5;
      slot.style.transform = "rotateY(" + (tiltX * 14).toFixed(2) + "deg) rotateX(" + (-tiltY * 10).toFixed(2) + "deg)";
    });
    hero.addEventListener("pointerleave", function () {
      tiltX = 0;
      tiltY = 0;
      slot.style.transform = "";
    });
  }

  var last = 0;
  function loop(now) {
    if (!hidden) {
      if (heroOn && (reduce || now - last > 32)) {
        drawHeroTiles(now);
        if (shield) drawShield(shield, now, reduce ? 0 : Math.sin(now / 1800) * 0.08);
      }
      if (ctaOn) drawCtaTiles(now);
      if (pileOn && (reduce || now - last > 32)) drawPile(pile, now);
      last = now;
    }
    if (!reduce) requestAnimationFrame(loop);
  }
  requestAnimationFrame(function (now) {
    loop(now);
    if (reduce) {
      drawHeroTiles(now);
      if (shield) drawShield(shield, now, 0);
      drawCtaTiles(now);
      drawPile(pile, now);
    }
  });
  window.addEventListener("resize", function () {
    shieldMask = null;
    if (tiles) tiles.width = 0;
    if (cta) cta.width = 0;
  });

  var pill = document.querySelector(".nav-links .pill");
  var nav = document.getElementById("site-nav");
  if (pill && nav && window.matchMedia("(hover: hover)").matches) {
    nav.addEventListener("pointerover", function (event) {
      var link = event.target.closest ? event.target.closest("a") : null;
      if (!link || !nav.contains(link)) return;
      var nb = nav.getBoundingClientRect();
      var ab = link.getBoundingClientRect();
      pill.style.opacity = "1";
      pill.style.width = ab.width + "px";
      pill.style.height = ab.height + "px";
      pill.style.transform = "translate(" + (ab.left - nb.left) + "px," + (ab.top - nb.top) + "px)";
    });
    nav.addEventListener("pointerleave", function () { pill.style.opacity = "0"; });
  }

  if (!reduce && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    document.querySelectorAll(".bento .tilt, .stage").forEach(function (card) {
      card.addEventListener("pointermove", function (event) {
        var rect = card.getBoundingClientRect();
        var px = (event.clientX - rect.left) / rect.width - 0.5;
        var py = (event.clientY - rect.top) / rect.height - 0.5;
        card.style.transform = "perspective(700px) rotateX(" + (-py * 6).toFixed(2) + "deg) rotateY(" + (px * 8).toFixed(2) + "deg) scale(1.015)";
        var iso = card.querySelector(".iso");
        if (iso) iso.style.transform = "rotateX(" + (-py * 16).toFixed(2) + "deg) rotateY(" + (px * 18).toFixed(2) + "deg) translateZ(18px)";
      });
      card.addEventListener("pointerleave", function () {
        card.style.transform = "";
        var iso = card.querySelector(".iso");
        if (iso) iso.style.transform = "";
      });
    });
  }

  if (!reduce) document.documentElement.classList.add("motion");
  var revealNodes = document.querySelectorAll(".sec-head, .card, .step, .bento, .acc, .timeline li, .close");
  if (!reduce && "IntersectionObserver" in window) {
    revealNodes.forEach(function (node) { node.classList.add("reveal"); });
    var seen = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        seen.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    revealNodes.forEach(function (node) { seen.observe(node); });
  }

  function count(el) {
    var target = Number(el.getAttribute("data-count"));
    if (!target && target !== 0) return;
    if (reduce) { el.textContent = String(target); return; }
    var start = performance.now();
    function tick(now) {
      var p = Math.min(1, (now - start) / 880);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(target * eased));
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  function countGroup(nodes) {
    if (reduce) {
      nodes.forEach(function (el) { el.textContent = el.getAttribute("data-count"); });
      return;
    }
    var start = performance.now();
    function tick(now) {
      var p = Math.min(1, (now - start) / 880);
      var eased = 1 - Math.pow(1 - p, 3);
      nodes.forEach(function (el) {
        el.textContent = String(Math.round(Number(el.getAttribute("data-count")) * eased));
      });
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  var counters = Array.prototype.filter.call(document.querySelectorAll("[data-count]"), function (el) {
    return !el.parentElement || !el.parentElement.classList.contains("ratio");
  });
  var ratios = document.querySelectorAll(".ratio");
  function arm(el, fn) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    var once = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        fn();
        once.disconnect();
      });
    }, { threshold: 0.5 });
    once.observe(el);
  }
  counters.forEach(function (el) { arm(el, function () { count(el); }); });
  ratios.forEach(function (box) {
    arm(box, function () { countGroup(box.querySelectorAll("[data-count]")); });
  });
})();
