/* Scroll reveal, cursor, magnets, counters. Native scroll stays intact. */
(function () {
  if (location.hash) {
    var jumped = document.querySelector(location.hash);
    if (jumped) jumped.scrollIntoView();
  }

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]still=1/.test(location.search);
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var narrow = window.matchMedia("(max-width: 767px)").matches;
  if (reduce) document.documentElement.classList.add("reduce");

  var pill = document.querySelector(".nav-links .pill");
  var nav = document.getElementById("site-nav");
  if (pill && nav && fine && !reduce) {
    nav.addEventListener("pointerover", function (event) {
      var link = event.target.closest ? event.target.closest("a") : null;
      if (!link || !nav.contains(link) || link.closest("[hidden]")) return;
      var nb = nav.getBoundingClientRect();
      var ab = link.getBoundingClientRect();
      pill.style.opacity = "1";
      pill.style.width = ab.width + "px";
      pill.style.height = ab.height + "px";
      pill.style.transform = "translate(" + (ab.left - nb.left) + "px," + (ab.top - nb.top) + "px)";
    });
    nav.addEventListener("pointerleave", function () { pill.style.opacity = "0"; });
  }

  var header = document.querySelector(".site-header");
  var lastY = window.scrollY;
  if (header) {
    var peek = document.createElement("div");
    peek.className = "nav-peek";
    peek.setAttribute("aria-hidden", "true");
    document.body.appendChild(peek);
    peek.addEventListener("pointerenter", function () { header.classList.remove("nav-hide"); });
    header.addEventListener("pointerenter", function () { header.classList.remove("nav-hide"); });
    window.addEventListener("pointermove", function (event) {
      if (event.clientY < 28) header.classList.remove("nav-hide");
    }, { passive: true });
  }
  function syncSteps() {
    var how = document.getElementById("how");
    if (!how) return;
    var steps = how.querySelectorAll(".step");
    var row = how.querySelector(".steps");
    var rect = how.getBoundingClientRect();
    var vh = window.innerHeight || 1;
    var p = (vh * 0.62 - rect.top) / Math.max(1, rect.height);
    var clamped = Math.max(0, Math.min(1, p));
    if (row) row.style.setProperty("--p", clamped.toFixed(4));
    var on = p > -0.02 && p < 1.02;
    var idx = Math.min(steps.length - 1, Math.max(0, Math.floor(clamped * steps.length)));
    steps.forEach(function (step, i) {
      step.classList.toggle("is-on", on && i === idx);
    });
  }
  window.addEventListener("scroll", function () {
    var y = window.scrollY;
    var open = nav && nav.classList.contains("open");
    if (header && !reduce && !open) {
      if (y < 32) header.classList.remove("nav-hide");
      else if (y > lastY + 6) header.classList.add("nav-hide");
      else if (y < lastY - 6) header.classList.remove("nav-hide");
    } else if (header && (reduce || open)) {
      header.classList.remove("nav-hide");
    }
    lastY = y;
    syncSteps();
  }, { passive: true });
  syncSteps();

  var pointer = { x: window.innerWidth / 2, y: window.innerHeight / 2, inside: false };
  var cursorOn = false;
  var cursor;
  var dot;
  var ring;
  var tag;
  var ringPos = { x: pointer.x, y: pointer.y, s: 1 };
  var dotPos = { x: pointer.x, y: pointer.y };
  if (cursorOn) {
    cursor = document.createElement("div");
    cursor.className = "ax-cursor";
    cursor.setAttribute("aria-hidden", "true");
    cursor.innerHTML = "<div class=\"ring\"></div><div class=\"dot\"></div><div class=\"tag\"></div>";
    document.body.appendChild(cursor);
    ring = cursor.querySelector(".ring");
    dot = cursor.querySelector(".dot");
    tag = cursor.querySelector(".tag");
  }

  var magnets = [];
  if (false) {
    magnets = Array.prototype.map.call(document.querySelectorAll("a.btn, .nav-links a"), function (el) {
      return { el: el, x: 0, y: 0 };
    });
  }

  function magnetTarget(m) {
    var rect = m.el.getBoundingClientRect();
    var dx = pointer.x - (rect.left + rect.width / 2);
    var dy = pointer.y - (rect.top + rect.height / 2);
    var dist = Math.hypot(dx, dy);
    if (dist > 90) return { x: 0, y: 0, near: false };
    var pull = 1 - dist / 90;
    return { x: dx * 0.28 * pull, y: dy * 0.28 * pull, near: true };
  }

  var magRaf = 0;
  function stepMagnets() {
    magRaf = 0;
    var moving = false;
    magnets.forEach(function (m) {
      var goal = pointer.inside ? magnetTarget(m) : { x: 0, y: 0, near: false };
      m.x += (goal.x - m.x) * 0.18;
      m.y += (goal.y - m.y) * 0.18;
      var pressed = m.el.classList.contains("is-pressed") ? 0.97 : 1;
      if (Math.abs(m.x) + Math.abs(m.y) > 0.35 || m.el.classList.contains("is-pressed")) {
        m.el.style.transition = "none";
        m.el.style.transform = "translate(" + m.x.toFixed(2) + "px," + m.y.toFixed(2) + "px) scale(" + pressed + ")";
        moving = true;
      } else if (m.el.style.transform) {
        m.el.style.transition = "transform 0.6s cubic-bezier(0.34, 1.45, 0.64, 1)";
        m.el.style.transform = "";
        window.setTimeout(function () { m.el.style.transition = ""; }, 650);
        moving = true;
      }
    });
    if (cursorOn && cursor) {
      dotPos.x += (pointer.x - dotPos.x) * 0.45;
      dotPos.y += (pointer.y - dotPos.y) * 0.45;
      ringPos.x += (pointer.x - ringPos.x) * 0.18;
      ringPos.y += (pointer.y - ringPos.y) * 0.18;
      var overLink = false;
      var el = document.elementFromPoint(pointer.x, pointer.y);
      if (el && el.closest) overLink = !!el.closest("a, button, summary, .card");
      var drag = document.body.dataset.axCursor === "drag";
      var goalS = drag ? 1.35 : (overLink ? 1.18 : 1);
      ringPos.s += (goalS - ringPos.s) * 0.18;
      cursor.style.transform = "translate(" + ringPos.x.toFixed(1) + "px," + ringPos.y.toFixed(1) + "px)";
      dot.style.transform = "translate(" + (dotPos.x - ringPos.x).toFixed(1) + "px," + (dotPos.y - ringPos.y).toFixed(1) + "px)";
      ring.style.transform = "scale(" + ringPos.s.toFixed(3) + ")";
      var label = drag ? "[ DRAG ]" : (overLink ? "[ VIEW ]" : "");
      if (tag.textContent !== label) tag.textContent = label;
      if (Math.abs(pointer.x - ringPos.x) + Math.abs(pointer.y - ringPos.y) > 0.4 || Math.abs(goalS - ringPos.s) > 0.01) moving = true;
    }
    if (moving) magRaf = requestAnimationFrame(stepMagnets);
  }
  function wake() {
    if (!magRaf && (magnets.length || cursorOn)) magRaf = requestAnimationFrame(stepMagnets);
  }

  if (cursorOn || magnets.length) {
    window.addEventListener("pointermove", function (event) {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.inside = true;
      if (cursorOn) document.body.classList.add("has-ax-cursor");
      wake();
    }, { passive: true });
    window.addEventListener("pointerleave", function () {
      pointer.inside = false;
      document.body.classList.remove("has-ax-cursor");
      wake();
    });
  }

  document.addEventListener("pointerdown", function (event) {
    var btn = event.target.closest ? event.target.closest(".btn, .nav-links a, button") : null;
    if (btn) btn.classList.add("is-pressed");
    wake();
  });
  document.addEventListener("pointerup", function () {
    document.querySelectorAll(".is-pressed").forEach(function (el) { el.classList.remove("is-pressed"); });
    wake();
  });

  if (false) {
    document.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("pointermove", function (event) {
        var rect = card.getBoundingClientRect();
        var px = (event.clientX - rect.left) / rect.width - 0.5;
        var py = (event.clientY - rect.top) / rect.height - 0.5;
        card.style.transition = "none";
        card.style.setProperty("--mx", ((event.clientX - rect.left) / rect.width * 100).toFixed(1) + "%");
        card.style.setProperty("--my", ((event.clientY - rect.top) / rect.height * 100).toFixed(1) + "%");
        card.style.transform = "perspective(900px) rotateX(" + (-py * 5).toFixed(2) + "deg) rotateY(" + (px * 5).toFixed(2) + "deg)";
        card.style.boxShadow = (px * 18).toFixed(1) + "px " + (py * 14).toFixed(1) + "px 36px -18px rgba(238, 249, 75, 0.22)";
      });
      card.addEventListener("pointerleave", function () {
        card.style.transition = "transform 0.55s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.55s ease";
        card.style.transform = "";
        card.style.boxShadow = "";
      });
    });
  }

  var revealSelector = ".hero-copy, .stat, .sec-top, h2, .lede, .card, .sources li, .note, .recompute, .timeline li, .faq details, .chips, .close .hero-actions";
  var revealNodes = Array.prototype.filter.call(document.querySelectorAll(revealSelector), function (node) {
    return !(node.parentElement && node.parentElement.closest(revealSelector));
  });
  if (!reduce && revealNodes.length && "IntersectionObserver" in window) {
    document.documentElement.classList.add("motion");
    var groups = new Map();
    revealNodes.forEach(function (node) {
      node.setAttribute("data-reveal", "");
      node.classList.add("reveal");
      var parent = node.parentElement;
      var index = groups.get(parent) || 0;
      groups.set(parent, index + 1);
      node.style.transitionDelay = Math.min(index, 2) * 40 + "ms";
    });
    function show(node) {
      if (node.classList.contains("in")) return;
      node.classList.add("in");
      var steps = node.closest(".steps");
      if (steps) steps.classList.add("line-in");
    }
    function sweep() {
      var vh = window.innerHeight;
      revealNodes.forEach(function (node) {
        var rect = node.getBoundingClientRect();
        var onScreen = rect.bottom > 0 && rect.top < vh * 1.15;
        if (onScreen) {
          node.classList.remove("out");
          show(node);
        } else if (rect.bottom < -12 && node.classList.contains("in")) {
          node.classList.add("out");
        }
      });
    }
    var idle = 0;
    function armIdle() {
      window.clearTimeout(idle);
      idle = window.setTimeout(function () { revealNodes.forEach(show); }, 1500);
    }
    var seen = new IntersectionObserver(function () { sweep(); }, {
      rootMargin: "0px 0px 15% 0px",
      threshold: 0
    });
    revealNodes.forEach(function (node) { seen.observe(node); });
    sweep();
    var sweepScheduled = false;
    function scheduleSweep() {
      if (!sweepScheduled) {
        sweepScheduled = true;
        requestAnimationFrame(function () {
          sweep();
          sweepScheduled = false;
        });
      }
      armIdle();
    }
    window.addEventListener("scroll", scheduleSweep, { passive: true });
    armIdle();
  } else {
    document.documentElement.classList.add("intro-go");
  }

  window.setTimeout(function () {
    document.documentElement.classList.add("intro-go");
  }, 2800);

  function count(el) {
    var target = Number(el.getAttribute("data-count"));
    if (!target && target !== 0) return;
    if (reduce) { el.textContent = String(target); return; }
    var start = performance.now();
    function tick(now) {
      var p = Math.min(1, (now - start) / 900);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = String(Math.round(target * eased));
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  function arm(el, fn) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    var once = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        fn();
        once.disconnect();
      });
    }, { threshold: 0.4 });
    once.observe(el);
  }
  document.querySelectorAll("[data-count]").forEach(function (el) {
    arm(el, function () { count(el); });
  });

  if (!reduce) {
    document.querySelectorAll(".bracket, .idx, .eyebrow").forEach(function (el) {
      arm(el, function () { decode(el); });
    });
    document.addEventListener("axv:lang", function () {
      document.querySelectorAll(".bracket, .idx, .eyebrow").forEach(function (el) {
        el._decode = (el._decode || 0) + 1;
      });
    });
  }

  function decode(el) {
    var finalText = el.textContent || "";
    if (!finalText || finalText.length > 42) return;
    var token = (el._decode || 0) + 1;
    el._decode = token;
    var glyphs = "AXVIGIL0123456789";
    var start = performance.now();
    var dur = Math.min(480, 16 * finalText.length + 140);
    function tick(now) {
      if (el._decode !== token) return;
      var p = Math.min(1, (now - start) / dur);
      var lock = Math.floor(p * finalText.length);
      var out = "";
      for (var i = 0; i < finalText.length; i++) {
        var ch = finalText.charAt(i);
        if (p >= 1 || i < lock || " []:/_·-".indexOf(ch) !== -1) out += ch;
        else out += glyphs.charAt((i * 3 + Math.floor(p * 9)) % glyphs.length);
      }
      el.textContent = p >= 1 ? finalText : out;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
})();
