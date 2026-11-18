// 웹 리더 - 보기 설정, 목차/설정 패널, 읽던 위치 저장과 이어 읽기
(function () {
  var body = document.body, root = document.documentElement;
  var bookId = body.dataset.book, chapter = +body.dataset.chapter;
  var start = +body.dataset.start, span = +body.dataset.span, resume = +body.dataset.resume;

  /* ---------- 보기 설정 (이 브라우저에만 저장) ---------- */
  var settings = {};
  try { settings = JSON.parse(localStorage.getItem("ebook.reader") || "{}"); } catch (e) {}
  var systemDark = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
  var defaults = { theme: systemDark ? "dark" : "paper", font: "serif", size: 19, lh: "1.85" };
  function get(key) { return settings[key] != null ? String(settings[key]) : String(defaults[key]); }
  function save() { try { localStorage.setItem("ebook.reader", JSON.stringify(settings)); } catch (e) {} }

  function apply() {
    root.dataset.theme = get("theme");
    root.dataset.font = get("font");
    root.style.setProperty("--rfs", get("size") + "px");
    root.style.setProperty("--rlh", get("lh"));
    document.getElementById("size-out").textContent = get("size") + "px";
    document.querySelectorAll("[data-set]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(get(b.dataset.set) === b.dataset.value));
    });
  }
  document.querySelectorAll("[data-set]").forEach(function (b) {
    b.addEventListener("click", function () { settings[b.dataset.set] = b.dataset.value; save(); apply(); });
  });
  function step(delta) {
    settings.size = Math.min(30, Math.max(14, +get("size") + delta)); save(); apply();
  }
  document.getElementById("size-down").addEventListener("click", function () { step(-1); });
  document.getElementById("size-up").addEventListener("click", function () { step(1); });
  apply();

  /* ---------- 목차 서랍 / 설정 패널 ---------- */
  var toc = document.getElementById("toc"), set = document.getElementById("settings");
  var scrim = document.getElementById("scrim");
  var tocBtn = document.getElementById("toc-btn"), setBtn = document.getElementById("set-btn");
  function toggle(panel, btn, open) {
    panel.classList.toggle("open", open);
    panel.inert = !open;
    btn.setAttribute("aria-expanded", String(open));
  }
  function closeAll() {
    toggle(toc, tocBtn, false); toggle(set, setBtn, false); scrim.classList.remove("open");
  }
  tocBtn.addEventListener("click", function () {
    var open = !toc.classList.contains("open"); closeAll();
    if (open) { toggle(toc, tocBtn, true); scrim.classList.add("open"); var cur = toc.querySelector("[aria-current]"); if (cur) cur.scrollIntoView({ block: "center" }); }
  });
  setBtn.addEventListener("click", function () {
    var open = !set.classList.contains("open"); closeAll();
    if (open) { toggle(set, setBtn, true); scrim.classList.add("open"); }
  });
  scrim.addEventListener("click", closeAll);

  /* ---------- 키보드: 장 이동은 즉시 (애니메이션 없음) ---------- */
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { closeAll(); return; }
    if (e.altKey || e.ctrlKey || e.metaKey || /input|textarea|select/i.test(e.target.tagName)) return;
    var link = e.key === "ArrowLeft" ? document.querySelector("a[rel=prev]")
             : e.key === "ArrowRight" ? document.querySelector("a[rel=next]") : null;
    if (link) window.location.href = link.href;
  });

  /* ---------- 위 바: 내려 읽으면 숨김 ---------- */
  var bar = document.getElementById("bar"), lastY = window.scrollY;
  /* ---------- 진행률 저장 ---------- */
  var fill = document.getElementById("r-fill"), pct = document.getElementById("r-percent");
  var timer = null, lastSent = "";

  function ratio() {
    var range = document.documentElement.scrollHeight - window.innerHeight;
    return range <= 4 ? 1 : Math.min(1, Math.max(0, window.scrollY / range));
  }
  function payload() {
    var r = ratio();
    return JSON.stringify({ chapter: chapter, ratio: +r.toFixed(4), percent: +Math.min(100, start + span * r).toFixed(2) });
  }
  function show() {
    var p = Math.min(100, start + span * ratio());
    fill.style.setProperty("--p", (p / 100).toFixed(4));
    pct.textContent = Math.round(p) + "%";
  }
  function send(useBeacon) {
    var data = payload();
    if (data === lastSent) return;
    lastSent = data;
    var url = "/book/" + bookId + "/progress";
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([data], { type: "application/json" }));
    } else {
      fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: data, keepalive: true });
    }
  }
  window.addEventListener("scroll", function () {
    var y = window.scrollY;
    if (Math.abs(y - lastY) > 8) { bar.classList.toggle("hide", y > lastY && y > 120); lastY = y; }
    show();
    clearTimeout(timer); timer = setTimeout(function () { send(false); }, 1200);
  }, { passive: true });
  window.addEventListener("pagehide", function () { send(true); });
  document.addEventListener("visibilitychange", function () { if (document.hidden) send(true); });

  /* ---------- 이어 읽기: 그림이 다 불러와진 뒤 위치를 맞춘다 ---------- */
  window.addEventListener("load", function () {
    if (resume > 0 && resume < 1) {
      window.scrollTo(0, resume * (document.documentElement.scrollHeight - window.innerHeight));
    }
    show(); send(false);  // 장을 열었다는 것도 위치로 남긴다
  });
  show();
})();
