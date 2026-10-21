// The Zählwerk counter: the page already shows the last reading (each drum strip's `dN` class);
// this script reveals the play button and, on a click, steps through the years the page lists
// in `data-series` ("2018:1640 2019:1612 …", read from velometer's all.csv when the site was
// built). It stores nothing and loads nothing.
(function () {
  "use strict";
  var counter = document.getElementById("counter");
  var play = document.getElementById("play");
  var live = document.getElementById("reading");
  if (!counter || !play || !live) return;
  var series = counter.dataset.series.trim().split(/\s+/).map(function (pair) {
    var p = pair.split(":");
    return [Number(p[0]), Number(p[1])];
  });
  if (series.length < 2) return;
  var number = new Intl.NumberFormat("de-DE");

  function setter(id) {
    var strips = Array.prototype.slice.call(document.querySelectorAll("#" + id + " .strip"));
    return function (value) {
      var digits = String(value).padStart(strips.length, "0").slice(-strips.length);
      strips.forEach(function (s, i) { s.className = "strip d" + digits[i]; });
    };
  }
  var setKm = setter("km-drums");
  var setYear = setter("yr-drums");

  function show(i) {
    setKm(series[i][1]);
    setYear(series[i][0]);
    live.textContent = "Berlin " + series[i][0] + ": " + number.format(series[i][1]) + " km";
  }

  var timer = null;
  play.hidden = false;
  play.addEventListener("click", function () {
    clearTimeout(timer);
    var i = 0;
    (function step() {
      show(i);
      i += 1;
      if (i < series.length) timer = setTimeout(step, 750);
    })();
  });
})();
