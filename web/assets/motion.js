/* Scroll reveal, card tilt, magnetic primary buttons, hero light. No libraries. */
(function () {
  if (location.hash) {
    var jumped = document.querySelector(location.hash);
    if (jumped) jumped.scrollIntoView();
  }

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]still=1/.test(location.search);
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  var pill = document.querySelector(".nav-links .pill");
  var nav = document.getElementById("site-nav");
  if (pill && nav && fine) {
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

  if (!reduce && fine) {
    document.querySelectorAll(".tilt, .card, .stage").forEach(function (card) {
      card.addEventListener("pointermove", function (event) {
        var rect = card.getBoundingClientRect();
        var px = (event.clientX - rect.left) / rect.width - 0.5;
        var py = (event.clientY - rect.top) / rect.height - 0.5;
        var lift = card.classList.contains("stage") ? 5 : 3.5;
        card.style.transform = "perspective(900px) rotateX(" + (-py * lift).toFixed(2) + "deg) rotateY(" + (px * lift).toFixed(2) + "deg)";
        card.style.boxShadow = (px * 18).toFixed(1) + "px " + (py * 14).toFixed(1) + "px 36px -18px rgba(238, 249, 75, 0.28)";
      });
      card.addEventListener("pointerleave", function () {
        card.style.transform = "";
        card.style.boxShadow = "";
      });
    });

    document.querySelectorAll("a.btn.yellow").forEach(function (btn) {
      btn.addEventListener("pointermove", function (event) {
        var rect = btn.getBoundingClientRect();
        var x = event.clientX - (rect.left + rect.width / 2);
        var y = event.clientY - (rect.top + rect.height / 2);
        btn.style.transform = "translate(" + (x * 0.22).toFixed(1) + "px," + (y * 0.28).toFixed(1) + "px)";
      });
      btn.addEventListener("pointerleave", function () { btn.style.transform = ""; });
    });
  }

  var glow = document.getElementById("hero-glow");
  var hero = document.querySelector(".hero");
  if (glow && hero && !reduce && fine) {
    var tx = 0.72;
    var ty = 0.28;
    var cx = 0.72;
    var cy = 0.28;
    var raf = 0;
    function tick() {
      cx += (tx - cx) * 0.055;
      cy += (ty - cy) * 0.055;
      glow.style.left = (cx * 100).toFixed(2) + "%";
      glow.style.top = (cy * 100).toFixed(2) + "%";
      if (Math.abs(tx - cx) + Math.abs(ty - cy) > 0.0015) raf = requestAnimationFrame(tick);
      else raf = 0;
    }
    hero.addEventListener("pointermove", function (event) {
      var rect = hero.getBoundingClientRect();
      tx = (event.clientX - rect.left) / rect.width;
      ty = (event.clientY - rect.top) / rect.height;
      if (!raf) raf = requestAnimationFrame(tick);
    });
  }

  var revealNodes = document.querySelectorAll(".sec-top, .sec-head, .card, .step, .tilt, .acc-item, .timeline li, .close, .stat, .note, .tabs, canvas.dither, .kv");
  if (!reduce && "IntersectionObserver" in window) {
    document.documentElement.classList.add("motion");
    var groups = new Map();
    revealNodes.forEach(function (node) {
      node.classList.add("reveal");
      var parent = node.parentElement;
      if (!groups.has(parent)) groups.set(parent, 0);
      var index = groups.get(parent);
      groups.set(parent, index + 1);
      node.style.transitionDelay = Math.min(index, 7) * 70 + "ms";
    });
    var seen = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        seen.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.08 });
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
