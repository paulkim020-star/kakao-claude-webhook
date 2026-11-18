// 웹 리더 - 책갈피, 밑줄(형광펜), 메모. 내용은 모두 textContent로만 그린다 (HTML로 해석하지 않는다).
(function () {
  var api = window.readerApi;
  if (!api) return;
  var body = document.body, bookId = body.dataset.book, chapter = +body.dataset.chapter;
  var chapterBody = document.getElementById("chapter-body");
  var selBar = document.getElementById("sel-bar"), pop = document.getElementById("note-pop");
  var panel = document.getElementById("notes-panel"), notesBtn = document.getElementById("notes-btn");
  var list = document.getElementById("notes-list"), emptyHint = document.getElementById("notes-empty");
  var toastEl = document.getElementById("toast"), bmBtn = document.getElementById("bm-btn");
  var quote = document.getElementById("note-quote"), area = document.getElementById("note-text");
  var titles = Array.prototype.map.call(document.querySelectorAll("#toc a"), function (a) { return a.textContent.trim(); });
  var base = "/book/" + bookId + "/notes";
  var notes = [], popNote = null, popColor = "yellow", toastTimer = null;
  var COLOR_NAME = { yellow: "노랑", green: "초록", pink: "분홍" };

  function request(method, url, data) {
    return fetch(url, {
      method: method, headers: { "Content-Type": "application/json" },
      body: data ? JSON.stringify(data) : undefined,
    }).then(function (res) {
      if (!res.ok) throw new Error(res.status);
      return res.status === 204 ? null : res.json();
    });
  }
  function toast(message) {
    toastEl.textContent = message; toastEl.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2200);
  }
  function failed() { toast("저장하지 못했습니다. 잠시 뒤에 다시 해 주세요."); }

  /* ---------- 글자 위치(장 본문 기준)와 칠하기 ---------- */
  function offsetOf(node, off) {
    var r = document.createRange(); r.setStart(chapterBody, 0); r.setEnd(node, off);
    return r.toString().length;
  }
  function textNodes() {
    var walker = document.createTreeWalker(chapterBody, NodeFilter.SHOW_TEXT), out = [], n;
    while ((n = walker.nextNode())) out.push(n);
    return out;
  }
  function markClass(n) { return "hl hl-" + n.color + (n.note ? " has-note" : ""); }

  function applyMark(n) {
    var pos = 0;
    textNodes().forEach(function (node) {
      var s = pos, e = pos + node.data.length; pos = e;
      var from = Math.max(n.start, s), to = Math.min(n.end, e);
      if (from >= to || !/\S/.test(node.data)) return;   // 공백뿐인 조각은 칠하지 않는다 (표 안에 빈 칸이 생길 수 있다)
      var mid = from > s ? node.splitText(from - s) : node;
      if (to < e) mid.splitText(to - from);
      var mark = document.createElement("mark");
      mark.className = markClass(n); mark.dataset.id = n.id;
      mid.parentNode.insertBefore(mark, mid); mark.appendChild(mid);
    });
  }
  function marksOf(id) { return chapterBody.querySelectorAll('mark[data-id="' + id + '"]'); }
  function removeMarks(id) {
    marksOf(id).forEach(function (m) {
      var parent = m.parentNode;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m);
    });
    chapterBody.normalize();
  }
  function restyle(n) { marksOf(n.id).forEach(function (m) { m.className = markClass(n); }); }
  function byId(id) { return notes.filter(function (n) { return n.id === id; })[0]; }

  /* ---------- 글을 고르면 뜨는 막대 ---------- */
  function selection() {
    var sel = window.getSelection();
    if (!sel.rangeCount || sel.isCollapsed) return null;
    var range = sel.getRangeAt(0);
    if (!chapterBody.contains(range.startContainer) || !chapterBody.contains(range.endContainer)) return null;
    var raw = range.toString(), text = raw.trim();
    if (!text) return null;
    var lead = raw.length - raw.replace(/^\s+/, "").length, trail = raw.length - raw.replace(/\s+$/, "").length;
    var start = offsetOf(range.startContainer, range.startOffset) + lead;
    var end = offsetOf(range.endContainer, range.endOffset) - trail;
    return { start: start, end: end, text: text, rect: range.getBoundingClientRect() };
  }
  function overlaps(s) {
    return notes.some(function (n) { return n.kind === "highlight" && n.chapter === chapter && s.start < n.end && s.end > n.start; });
  }
  function hideSel() { selBar.hidden = true; }
  function showSel() {
    var s = selection();
    if (!s || pop.classList.contains("open")) { hideSel(); return; }
    selBar.hidden = false;
    var w = selBar.offsetWidth, x = s.rect.left + s.rect.width / 2 - w / 2;
    x = Math.max(8, Math.min(window.innerWidth - w - 8, x));
    var y = s.rect.top - selBar.offsetHeight - 8;
    if (y < 64) y = s.rect.bottom + 10;
    selBar.style.left = x + "px"; selBar.style.top = y + "px";
  }
  var selTimer = null;
  document.addEventListener("selectionchange", function () { clearTimeout(selTimer); selTimer = setTimeout(showSel, 140); });
  selBar.addEventListener("pointerdown", function (e) { e.preventDefault(); });   // 누르는 동안 글자 선택 유지
  selBar.addEventListener("mousedown", function (e) { e.preventDefault(); });

  selBar.addEventListener("click", function (e) {
    var btn = e.target.closest("button");
    if (!btn) return;
    var s = selection();
    if (!s) return;
    if (s.end - s.start > 2000) { toast("한 번에 2,000자까지 표시할 수 있습니다."); return; }
    if (overlaps(s)) { toast("이미 표시한 부분과 겹칩니다."); return; }
    var color = btn.dataset.color || "yellow", withMemo = "memo" in btn.dataset;
    request("POST", base, { kind: "highlight", chapter: chapter, start: s.start, end: s.end, text: s.text, color: color })
      .then(function (n) {
        notes.push(n); window.getSelection().removeAllRanges(); hideSel();
        applyMark(n); renderList();
        if (withMemo) openPop(n);
      }).catch(failed);
  });

  /* ---------- 메모 창 ---------- */
  function setPopColor(color) {
    popColor = color;
    pop.querySelectorAll("[data-pop-color]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.popColor === color));
    });
  }
  function openPop(n) {
    var mark = marksOf(n.id)[0];
    if (!mark) return;
    api.closeAll();
    popNote = n;
    quote.textContent = n.text.length > 80 ? n.text.slice(0, 80) + "…" : n.text;
    area.value = n.note; setPopColor(n.color);
    var rect = mark.getClientRects()[0], w = Math.min(340, window.innerWidth - 16);
    var left = Math.max(8, Math.min(window.innerWidth - w - 8, rect.left));
    pop.style.cssText = "left:" + left + "px;top:0;right:auto;width:" + w + "px";
    pop.classList.add("open"); pop.inert = false;
    var h = pop.offsetHeight, top = rect.bottom + 8;       // 실제 높이를 재서 화면 안에 놓는다
    if (top + h > window.innerHeight - 8) top = rect.top - h - 8;
    pop.style.top = Math.max(64, Math.min(top, window.innerHeight - h - 8)) + "px";
    area.focus({ preventScroll: true });
  }
  function closePop() { pop.classList.remove("open"); pop.inert = true; popNote = null; }

  pop.addEventListener("click", function (e) {
    var c = e.target.closest("[data-pop-color]");
    if (c) setPopColor(c.dataset.popColor);
  });
  document.getElementById("note-save").addEventListener("click", function () {
    var n = popNote; if (!n) return;
    request("PATCH", base + "/" + n.id, { note: area.value.trim(), color: popColor })
      .then(function (updated) {
        Object.assign(n, updated); restyle(n); renderList(); closePop(); toast("저장했습니다.");
      }).catch(failed);
  });
  document.getElementById("note-del").addEventListener("click", function () {
    var n = popNote; if (!n) return;
    request("DELETE", base + "/" + n.id).then(function () { dropNote(n); closePop(); toast("밑줄을 지웠습니다."); }).catch(failed);
  });
  function dropNote(n) {
    notes = notes.filter(function (x) { return x.id !== n.id; });
    if (n.kind === "highlight") removeMarks(n.id);
    renderList();
  }
  chapterBody.addEventListener("click", function (e) {   // 칠한 글을 누르면 메모 창
    var mark = e.target.closest("mark");
    if (!mark || String(window.getSelection())) return;
    var n = byId(+mark.dataset.id);
    if (n) openPop(n);
  });
  document.addEventListener("pointerdown", function (e) {   // 바깥을 누르면 닫는다
    if (pop.classList.contains("open") && !pop.contains(e.target) && !e.target.closest("mark")) closePop();
  }, true);

  /* ---------- 책갈피 ---------- */
  bmBtn.addEventListener("click", function () {
    var r = api.ratio();
    var near = notes.filter(function (n) { return n.kind === "bookmark" && n.chapter === chapter && Math.abs(n.ratio - r) < 0.02; })[0];
    if (near) {
      request("DELETE", base + "/" + near.id).then(function () { dropNote(near); toast("책갈피를 뺐습니다."); }).catch(failed);
    } else {
      request("POST", base, { kind: "bookmark", chapter: chapter, ratio: +r.toFixed(4), text: api.visibleText() })
        .then(function (n) { notes.push(n); renderList(); toast("책갈피를 꽂았습니다."); }).catch(failed);
    }
  });

  /* ---------- 메모 서랍: 장별 목록 ---------- */
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function sorted() {
    return notes.slice().sort(function (a, b) {
      return a.chapter - b.chapter || (a.kind === "highlight" ? a.start : 0) - (b.kind === "highlight" ? b.start : 0) || a.ratio - b.ratio || a.id - b.id;
    });
  }
  function renderList() {
    list.textContent = "";
    emptyHint.hidden = notes.length > 0;
    var last = -1;
    sorted().forEach(function (n) {
      if (n.chapter !== last) {
        last = n.chapter;
        list.appendChild(el("h3", "note-group", (n.chapter + 1) + "장" + (titles[n.chapter] ? " · " + titles[n.chapter] : "")));
      }
      var item = el("div", "note-item");
      var open = el("button", "note-open");
      open.type = "button";
      open.appendChild(el("span", "note-tag", n.kind === "bookmark" ? "책갈피" : "밑줄 · " + COLOR_NAME[n.color]));
      if (n.text) open.appendChild(el("span", "note-text hl-edge-" + (n.kind === "highlight" ? n.color : "none"), n.text));
      if (n.note) open.appendChild(el("span", "note-memo", n.note));
      open.addEventListener("click", function () { openNote(n); });
      var del = el("button", "link-btn danger note-del", "지우기");
      del.type = "button";
      del.setAttribute("aria-label", (n.kind === "bookmark" ? "책갈피" : "밑줄") + " 지우기");
      del.addEventListener("click", function () {
        request("DELETE", base + "/" + n.id).then(function () { dropNote(n); }).catch(failed);
      });
      item.appendChild(open); item.appendChild(del); list.appendChild(item);
    });
  }
  function openNote(n) {
    if (n.chapter !== chapter) {
      window.location.href = "/book/" + bookId + "/read?c=" + n.chapter + (n.kind === "highlight" ? "&n=" + n.id : "&r=" + n.ratio);
      return;
    }
    api.closeAll();
    if (n.kind === "highlight") { var m = marksOf(n.id)[0]; if (m) api.jumpTo(m); }
    else api.goRatio(n.ratio);
  }
  notesBtn.addEventListener("click", function () {
    if (panel.classList.contains("open")) api.closePanel(panel, notesBtn);
    else api.openPanel(panel, notesBtn);
  });
  document.addEventListener("reader:closeall", function () {
    panel.classList.remove("open"); panel.inert = true; notesBtn.setAttribute("aria-expanded", "false");
    closePop(); hideSel();
  });

  /* ---------- 시작: 저장된 기록을 불러와 칠한다 ---------- */
  var wanted = new URLSearchParams(window.location.search).get("n");
  function jumpWanted() {
    if (!wanted) return;
    var m = marksOf(wanted)[0];
    if (m) api.jumpTo(m);
  }
  fetch(base).then(function (res) { return res.ok ? res.json() : []; }).then(function (all) {
    notes = all;
    notes.filter(function (n) { return n.kind === "highlight" && n.chapter === chapter; }).forEach(applyMark);
    renderList(); jumpWanted();
  }).catch(function () {});
  window.addEventListener("load", jumpWanted);   // 그림이 다 뜬 뒤 위치가 바뀌면 한 번 더 맞춘다
})();
