// 웹 리더 - 보기 설정(스크롤/쪽 넘김), 목차·설정 패널, 읽던 위치 저장과 이어 읽기
(function () {
  var body = document.body, root = document.documentElement;
  var bookId = body.dataset.book, chapter = +body.dataset.chapter;
  var start = +body.dataset.start, span = +body.dataset.span, resume = +body.dataset.resume;
  var stage = document.getElementById("stage"), prose = document.getElementById("prose");
  var bar = document.getElementById("bar"), pageno = document.getElementById("pageno");
  var total = +body.dataset.total;

  /* ---------- 보기 설정 (이 브라우저에만 저장) ---------- */
  var settings = {};
  try { settings = JSON.parse(localStorage.getItem("ebook.reader") || "{}"); } catch (e) {}
  var systemDark = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
  var defaults = { theme: systemDark ? "dark" : "paper", font: "serif", size: 19, lh: "1.85", mode: "scroll" };
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

  /* ---------- 위치: 스크롤은 스크롤 비율, 쪽 넘김은 쪽 번호로 센다 ---------- */
  var paged = false, page = 0, pages = 1, step = 0, GAP = 48;

  function scrollRatio() {
    var range = document.documentElement.scrollHeight - window.innerHeight;
    return range <= 4 ? 1 : Math.min(1, Math.max(0, window.scrollY / range));
  }
  function ratio() { return paged ? (pages <= 1 ? 1 : page / (pages - 1)) : scrollRatio(); }

  function layout(r) {   // 쪽 나누기: 본문 폭을 정하고 쪽 수를 센 뒤 r 위치의 쪽으로 간다
    var cs = getComputedStyle(stage);
    var inner = stage.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    var pw = Math.floor(Math.min(inner, parseFloat(getComputedStyle(prose).fontSize) * 38));
    stage.style.setProperty("--pw", pw + "px");
    prose.style.transform = "none";
    step = pw + GAP;
    pages = Math.max(1, Math.round((prose.scrollWidth + GAP) / step));
    goPage(Math.round(r * (pages - 1)), false);
  }
  function relayout() { if (paged) layout(ratio()); }

  function goPage(n, animate) {
    page = Math.min(pages - 1, Math.max(0, n));
    prose.style.transition = animate && !reduced ? "transform 160ms cubic-bezier(0.23, 1, 0.32, 1)" : "none";
    prose.style.transform = "translateX(" + (-page * step) + "px)";
    pageno.textContent = "장 " + (chapter + 1) + "/" + total + " · " + (page + 1) + "/" + pages + "쪽";
    show(); schedule();
  }
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function chapterLink(rel, atEnd) {
    var a = document.querySelector("a[rel=" + rel + "]");
    return a ? a.href + (atEnd ? "&r=1" : "") : null;
  }
  function turn(dir, animate) {
    var target = page + dir;
    if (target >= 0 && target < pages) { goPage(target, animate); return; }
    var link = dir > 0 ? chapterLink("next", false) : chapterLink("prev", true);
    if (link) window.location.href = link;
  }

  function setMode(mode, r) {
    paged = mode === "page";
    body.classList.toggle("paged", paged);
    pageno.hidden = !paged;
    bar.classList.remove("hide");
    if (paged) {
      prose.querySelectorAll("img").forEach(function (img) { img.loading = "eager"; });
      window.scrollTo(0, 0);
      layout(r);
    } else {
      prose.style.transform = ""; prose.style.transition = ""; stage.style.removeProperty("--pw");
      window.scrollTo(0, r * (document.documentElement.scrollHeight - window.innerHeight));
      show();
    }
  }

  document.querySelectorAll("[data-set]").forEach(function (b) {
    b.addEventListener("click", function () {
      var r = ratio();
      settings[b.dataset.set] = b.dataset.value; save(); apply();
      if (b.dataset.set === "mode") setMode(get("mode"), r); else if (paged) layout(r);
    });
  });
  function step2(delta) {
    var r = ratio();
    settings.size = Math.min(30, Math.max(14, +get("size") + delta)); save(); apply();
    if (paged) layout(r);
  }
  document.getElementById("size-down").addEventListener("click", function () { step2(-1); });
  document.getElementById("size-up").addEventListener("click", function () { step2(1); });
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
    document.dispatchEvent(new Event("reader:closeall"));
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

  /* ---------- 키보드: 쪽/장 이동은 즉시 (애니메이션 없음) ---------- */
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { closeAll(); return; }
    if (e.altKey || e.ctrlKey || e.metaKey || /input|textarea|select|button/i.test(e.target.tagName)) return;
    if (document.querySelector(".popover.open, .drawer.open")) return;
    if (paged) {
      if (e.key === "ArrowRight" || e.key === "PageDown" || (e.key === " " && !e.shiftKey)) { e.preventDefault(); turn(1, false); }
      else if (e.key === "ArrowLeft" || e.key === "PageUp" || (e.key === " " && e.shiftKey)) { e.preventDefault(); turn(-1, false); }
      return;
    }
    var link = e.key === "ArrowLeft" ? chapterLink("prev", false) : e.key === "ArrowRight" ? chapterLink("next", false) : null;
    if (link) window.location.href = link;
  });

  /* ---------- 쪽 넘김: 화면 좌우 탭, 좌우 스와이프, 가운데 탭은 위 바 ---------- */
  var down = null;
  stage.addEventListener("pointerdown", function (e) { down = paged ? { x: e.clientX, y: e.clientY, t: Date.now() } : null; });
  stage.addEventListener("pointerup", function (e) {
    if (!paged || !down) return;
    var dx = e.clientX - down.x, dy = e.clientY - down.y, dt = Date.now() - down.t;
    down = null;
    if (String(window.getSelection())) return;           // 글자를 고르는 중에는 넘기지 않는다
    if (Math.abs(dx) > 50 && Math.abs(dx) > 1.5 * Math.abs(dy)) { turn(dx < 0 ? 1 : -1, true); return; }
    if (Math.abs(dx) < 10 && Math.abs(dy) < 10 && dt < 350 && !e.target.closest("a, button, mark")) {
      var x = e.clientX / window.innerWidth;
      if (x < 0.3) turn(-1, true); else if (x > 0.7) turn(1, true); else bar.classList.toggle("hide");
    }
  });

  /* ---------- 진행률 저장 ---------- */
  var fill = document.getElementById("r-fill"), pct = document.getElementById("r-percent");
  var timer = null, lastSent = "", lastY = window.scrollY;

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
  function schedule() { clearTimeout(timer); timer = setTimeout(function () { send(false); }, 1200); }

  window.addEventListener("scroll", function () {
    if (paged) return;
    var y = window.scrollY;
    if (Math.abs(y - lastY) > 8) { bar.classList.toggle("hide", y > lastY && y > 120); lastY = y; }
    show(); schedule();
  }, { passive: true });
  window.addEventListener("pagehide", function () { send(true); });
  document.addEventListener("visibilitychange", function () { if (document.hidden) send(true); });

  var resizeTimer = null;
  window.addEventListener("resize", function () { clearTimeout(resizeTimer); resizeTimer = setTimeout(relayout, 150); });

  /* ---------- 시작: 그림이 다 불러와진 뒤 위치를 맞춘다 ---------- */
  function visibleText() {   // 지금 화면 맨 위의 글 (책갈피 설명용)
    var r = paged ? stage.getBoundingClientRect() : { left: 0, right: window.innerWidth, top: 70, bottom: window.innerHeight };
    var blocks = prose.querySelectorAll("#chapter-body p, #chapter-body h1, #chapter-body h2, #chapter-body h3, #chapter-body li, #chapter-body td");
    for (var i = 0; i < blocks.length; i++) {
      var rects = blocks[i].getClientRects();
      for (var k = 0; k < rects.length; k++) {
        var q = rects[k];
        if (q.right > r.left && q.left < r.right && q.bottom > r.top + 4 && q.top < r.bottom) {
          var text = blocks[i].textContent.replace(/\s+/g, " ").trim();
          if (text) return text.slice(0, 60);
        }
      }
    }
    return "";
  }
  window.readerApi = {   // 책갈피·메모 스크립트(notes.js)가 쓰는 연결부
    get paged() { return paged; },
    chapter: chapter, ratio: ratio, visibleText: visibleText, closeAll: closeAll, scrim: scrim,
    openPanel: function (panel, btn) { closeAll(); toggle(panel, btn, true); scrim.classList.add("open"); },
    closePanel: function (panel, btn) { toggle(panel, btn, false); scrim.classList.remove("open"); },
    goRatio: function (r) {
      if (paged) goPage(Math.round(r * (pages - 1)), false);
      else window.scrollTo(0, r * (document.documentElement.scrollHeight - window.innerHeight));
    },
    jumpTo: function (el) {   // 글 조각이 있는 자리로 (스크롤은 가운데로, 쪽 넘김은 그 쪽으로)
      if (!paged) { el.scrollIntoView({ block: "center" }); return; }
      var rect = el.getClientRects()[0];
      goPage(Math.floor((rect.left - prose.getBoundingClientRect().left) / step + 0.001), false);
    },
  };
  if (get("mode") === "page") setMode("page", resume);
  window.addEventListener("load", function () {
    if (paged) layout(resume > 0 ? resume : 0);
    else if (resume > 0) window.scrollTo(0, resume * (document.documentElement.scrollHeight - window.innerHeight));
    show(); send(false);   // 장을 열었다는 것도 위치로 남긴다
  });
  show();
})();
