/* Square Bayer dissolve between dark and light bands. No animation. */
(function () {
  var bayer = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5]
  ];
  function paint(canvas) {
    var from = canvas.dataset.from;
    var to = canvas.dataset.to;
    var size = 8;
    var w = canvas.clientWidth;
    var h = canvas.clientHeight;
    if (!w || !h) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    var ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = from;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = to;
    var rows = Math.ceil(h / size);
    var cols = Math.ceil(w / size);
    for (var y = 0; y < rows; y++) {
      var thresh = ((y + 0.5) / rows) * 16;
      for (var x = 0; x < cols; x++) {
        if (bayer[y % 4][x % 4] < thresh) ctx.fillRect(x * size, y * size, size, size);
      }
    }
  }
  function paintAll() {
    document.querySelectorAll("canvas.dither").forEach(paint);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", paintAll);
  else paintAll();
  var timer = 0;
  window.addEventListener("resize", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(paintAll, 80);
  });
})();
