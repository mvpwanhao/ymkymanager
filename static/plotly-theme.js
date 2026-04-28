/*!
 * Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
 * 本文件为「云煤矿业产销量管理系统」的组成部分。
 * 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
 * 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE.
 */
/* Plotly 布局随 data-color-mode、视口宽度（日产量趋势图例）与主题切换 */
(function () {
  var NARROW_PX = 720;
  var resizeTimer = null;

  function isDark() {
    return document.documentElement.getAttribute("data-color-mode") === "dark";
  }

  function isNarrow() {
    return typeof window !== "undefined" && window.innerWidth <= NARROW_PX;
  }

  /* 与 dashboard_data._PLOT_COLORWAY 同步 */
  var COLORWAYS = {
    light: [
      "#2563eb", "#ea580c", "#16a34a", "#dc2626", "#7c3aed", "#0d9488", "#db2777", "#ca8a04",
      "#4f46e5", "#059669", "#e11d48", "#b45309",
    ],
    dark: [
      "#60a5fa", "#fb923c", "#4ade80", "#f87171", "#c4b5fd", "#2dd4bf", "#f472b6", "#fbbf24",
      "#a5b4fc", "#34d399", "#fb7185", "#fcd34d",
    ],
  };

  function legendTitleText(L) {
    try {
      var t = L.legend && L.legend.title;
      if (t && t.text) return t.text;
    } catch (e) {}
    return "煤矿";
  }

  function relayoutForTheme(gd) {
    if (typeof window.Plotly === "undefined" || !gd) return;
    if (!gd._fullLayout) return;
    var L = gd._fullLayout;
    var d = isDark();
    var fc = d ? "#eceef3" : "#111318";
    var o = d
      ? {
          paper_bgcolor: "#1e232e",
          plot_bgcolor: "#1e232e",
          font: { color: "#eceef3" },
          colorway: COLORWAYS.dark,
        }
      : {
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          font: { color: "#111318" },
          colorway: COLORWAYS.light,
        };

    var inTrend = gd.closest && gd.closest(".plot-trend");
    var hasLegend = L.showlegend !== false;
    if (inTrend && hasLegend) {
      var ltitle = legendTitleText(L);
      if (isNarrow()) {
        o.legend = {
          font: { color: fc },
          orientation: "h",
          y: -0.18,
          yanchor: "top",
          x: 0.5,
          xanchor: "center",
          title: { text: ltitle, font: { color: fc, size: 12 } },
        };
        o.margin = { l: 48, r: 20, t: 20, b: 112 };
      } else {
        o.legend = {
          font: { color: fc },
          orientation: "v",
          y: 1,
          yanchor: "top",
          x: 1.02,
          xanchor: "left",
          title: { text: ltitle, font: { color: fc, size: 12 } },
        };
        o.margin = { l: 52, r: 120, t: 24, b: 56 };
      }
    } else {
      o.legend = { font: { color: fc } };
    }

    if (L.title) o["title.font.color"] = d ? "#eceef3" : "#111318";
    if (L.xaxis) {
      o["xaxis.color"] = d ? "#b5bcc8" : "#647088";
      o["xaxis.gridcolor"] = d ? "#343c4c" : "#e2e6ed";
      o["xaxis.zerolinecolor"] = d ? "#4a5568" : "#c9d0db";
    }
    if (L.yaxis) {
      o["yaxis.color"] = d ? "#b5bcc8" : "#647088";
      o["yaxis.gridcolor"] = d ? "#343c4c" : "#e2e6ed";
      o["yaxis.zerolinecolor"] = d ? "#4a5568" : "#c9d0db";
    }
    if (L.scene) {
      o["scene.xaxis.color"] = d ? "#b5bcc8" : "#647088";
      o["scene.yaxis.color"] = d ? "#b5bcc8" : "#647088";
      o["scene.zaxis.color"] = d ? "#b5bcc8" : "#647088";
    }
    try {
      window.Plotly.relayout(gd, o);
    } catch (e) {}
  }

  function applyToAll() {
    if (typeof window.Plotly === "undefined") return;
    var nodes = document.querySelectorAll(".plotly-graph-div");
    for (var i = 0; i < nodes.length; i++) {
      var gd = nodes[i];
      if (gd._fullLayout) relayoutForTheme(gd);
    }
  }

  function schedule() {
    applyToAll();
    [80, 250, 600, 1200, 2000].forEach(function (ms) {
      setTimeout(applyToAll, ms);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule);
  } else {
    schedule();
  }
  window.addEventListener("ymky-theme", function () {
    setTimeout(applyToAll, 0);
  });
  window.addEventListener("resize", function () {
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(applyToAll, 150);
  });
})();
