/* Scroll reveal, card tilt, one-time counters. No libraries. */
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
    document.querySelectorAll("a.btn.yellow").forEach(function (btn) {
      btn.addEventListener("pointermove", function (event) {
        var rect = btn.getBoundingClientRect();
        var x = event.clientX - (rect.left + rect.width / 2);
        var y = event.clientY - (rect.top + rect.height / 2);
        btn.style.transform = "translate(" + (x * 0.22).toFixed(1) + "px," + (y * 0.28).toFixed(1) + "px)";
      });
      btn.addEventListener("pointerleave", function () { btn.style.transform = ""; });
    });
    document.querySelectorAll(".card").forEach(function (card) {
      card.addEventListener("pointermove", function (event) {
        var rect = card.getBoundingClientRect();
        var px = (event.clientX - rect.left) / rect.width - 0.5;
        var py = (event.clientY - rect.top) / rect.height - 0.5;
        card.style.transform = "perspective(900px) rotateX(" + (-py * 3.5).toFixed(2) + "deg) rotateY(" + (px * 3.5).toFixed(2) + "deg)";
        card.style.boxShadow = (px * 16).toFixed(1) + "px " + (py * 12).toFixed(1) + "px 32px -18px rgba(212, 227, 106, 0.22)";
      });
      card.addEventListener("pointerleave", function () {
        card.style.transform = "";
        card.style.boxShadow = "";
      });
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
      var limit = window.innerHeight * 1.15;
      revealNodes.forEach(function (node) {
        if (node.classList.contains("in")) return;
        if (node.getBoundingClientRect().top < limit) show(node);
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
    window.addEventListener("scroll", function () { sweep(); armIdle(); }, { passive: true });
    armIdle();
  }

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
    }, { threshold: 0.6 });
    once.observe(el);
  }
  document.querySelectorAll("[data-count]").forEach(function (el) {
    arm(el, function () { count(el); });
  });
})();
