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

  var revealNodes = document.querySelectorAll(".hero-copy, .stat, .eyebrow, h2, .lede, .steps, .card, .sources li, .note, .recompute, .timeline li, .faq details, .chips, .close .wrap");
  if (!reduce && "IntersectionObserver" in window) {
    document.documentElement.classList.add("motion");
    var groups = new Map();
    revealNodes.forEach(function (node) {
      node.classList.add("reveal");
      var parent = node.parentElement;
      if (!groups.has(parent)) groups.set(parent, 0);
      var index = groups.get(parent);
      groups.set(parent, index + 1);
      node.style.transitionDelay = Math.min(index, 6) * 60 + "ms";
    });
    var seen = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        seen.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    revealNodes.forEach(function (node) { seen.observe(node); });
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
