// PDF 서재 - 업로드 자동 전송, 끌어다 놓기, 변환 중 새로고침, 삭제 확인
(function () {
  var input = document.getElementById("file-input");
  var form = document.getElementById("upload-form");
  if (input && form) {
    input.addEventListener("change", function () {
      if (input.files.length) form.submit();
    });
    // label[role=button]을 키보드로도 열 수 있게
    var label = form.querySelector("label");
    label.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });

    var depth = 0;
    document.addEventListener("dragenter", function (e) {
      if (!e.dataTransfer || ![].includes.call(e.dataTransfer.types, "Files")) return;
      depth++; document.body.classList.add("dragging");
    });
    document.addEventListener("dragleave", function () {
      depth = Math.max(0, depth - 1);
      if (!depth) document.body.classList.remove("dragging");
    });
    document.addEventListener("dragover", function (e) { e.preventDefault(); });
    document.addEventListener("drop", function (e) {
      e.preventDefault(); depth = 0; document.body.classList.remove("dragging");
      if (e.dataTransfer && e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        form.submit();
      }
    });
  }

  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.dataset.confirm)) e.preventDefault();
    });
  });

  if (document.body.hasAttribute("data-converting")) {
    setTimeout(function () { window.location.reload(); }, 2500);
  }
})();
