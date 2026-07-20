/*!
 * Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
 * 本文件为「云煤矿业产销量管理系统」的组成部分。
 * 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
 * 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
 */
(function () {
  "use strict";

  var MIN_WIDTH = 50;

  function makeResizable(table) {
    var headers = table.querySelectorAll("thead th");
    if (!headers.length) return;

    for (var i = 0; i < headers.length; i++) {
      (function (th, colIndex) {
        var handle = document.createElement("div");
        handle.className = "col-resize-handle";
        th.appendChild(handle);

        handle.addEventListener("mousedown", function (e) {
          e.preventDefault();
          e.stopPropagation();

          var startX = e.clientX;
          var startWidth = th.offsetWidth;
          var nth = "nth-child(" + (colIndex + 1) + ")";
          var cells = table.querySelectorAll("tbody td:" + nth);
          var headCells = table.querySelectorAll("thead th:" + nth);

          function onMove(ev) {
            var w = Math.max(MIN_WIDTH, startWidth + (ev.clientX - startX));
            var wPx = w + "px";
            for (var i = 0; i < headCells.length; i++) {
              headCells[i].style.width = wPx;
              headCells[i].style.minWidth = wPx;
            }
            for (var j = 0; j < cells.length; j++) {
              cells[j].style.width = wPx;
              cells[j].style.minWidth = wPx;
            }
          }

          function onUp() {
            document.removeEventListener("mousemove", onMove);
            document.removeEventListener("mouseup", onUp);
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            handle.classList.remove("col-resize-handle--active");
          }

          document.body.style.cursor = "col-resize";
          document.body.style.userSelect = "none";
          handle.classList.add("col-resize-handle--active");
          document.addEventListener("mousemove", onMove);
          document.addEventListener("mouseup", onUp);
        });
      })(headers[i], i);
    }
  }

  function init() {
    var tables = document.querySelectorAll(".data-table");
    for (var i = 0; i < tables.length; i++) {
      if (tables[i].dataset.resizable) continue;
      tables[i].dataset.resizable = "1";
      makeResizable(tables[i]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
