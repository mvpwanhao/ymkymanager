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

  /** 桌面端饼图右侧图例快照：窄屏复原与主题色合并用（避免旋转屏后残留在底部图例）。 */
  var pieLayoutBaseline =
    typeof WeakMap !== "undefined"
      ? new WeakMap()
      : {
          /* 极老环境兜底：单页仅一张饼图也够 */
          _m: {},
          has: function (gd) {
            return Object.prototype.hasOwnProperty.call(this._m, gd);
          },
          get: function (gd) {
            return this._m[gd];
          },
          set: function (gd, v) {
            this._m[gd] = v;
          },
        };

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

  /** 首张渲染时记入服务端饼图 layout，横屏/主题切换时用其还原 domain 与边距。 */
  function rememberPieBaselineIfNeeded(gd) {
    if (!(gd.closest && gd.closest(".plot-pie"))) return;
    if (pieLayoutBaseline.has(gd)) return;
    if (!gd._fullLayout || !gd.data || !gd.data[0] || gd.data[0].type !== "pie") return;
    try {
      var L = gd._fullLayout;
      var tr = gd.data[0];
      var dx = tr.domain && tr.domain.x;
      var dy = tr.domain && tr.domain.y;
      pieLayoutBaseline.set(gd, {
        margin: {
          l: L.margin.l,
          r: L.margin.r,
          t: L.margin.t,
          b: L.margin.b,
        },
        domainx: dx ? dx.slice() : [0.04, 0.7],
        domainy: dy ? dy.slice() : [0.06, 0.78],
        legTitle: legendTitleText(L),
      });
    } catch (e2) {}
  }

  var LEGEND_BG_CLEAR = {
    bgcolor: "rgba(0,0,0,0)",
    bordercolor: "rgba(0,0,0,0)",
    borderwidth: 0,
  };

  /** 与各矿产量占比饼图服务端图例对齐（直角宽屏）。 */
  function desktopPieLegend(fc, titleText) {
    return Object.assign({}, LEGEND_BG_CLEAR, {
      xref: "paper",
      x: 1,
      xanchor: "left",
      yref: "paper",
      y: 0.52,
      yanchor: "middle",
      itemwidth: 30,
      tracegroupgap: 2,
      font: { color: fc },
      title: {
        text: titleText || "煤矿",
        font: { color: fc, size: 12 },
      },
    });
  }

  function relayoutForTheme(gd) {
    if (typeof window.Plotly === "undefined" || !gd) return;
    if (!gd._fullLayout) return;
    var L = gd._fullLayout;
    rememberPieBaselineIfNeeded(gd);
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
    var inPie = gd.closest && gd.closest(".plot-pie");
    var hasLegend = L.showlegend !== false;
    var tracePatch = null;
    var traceIndices = null;

    if (inTrend && hasLegend) {
      var ltitle = legendTitleText(L);
      if (isNarrow()) {
        o.legend = Object.assign({}, LEGEND_BG_CLEAR, {
          font: { color: fc },
          orientation: "h",
          y: -0.18,
          yanchor: "top",
          x: 0.5,
          xanchor: "center",
          title: { text: ltitle, font: { color: fc, size: 12 } },
        });
        o.margin = { l: 48, r: 20, t: 20, b: 112 };
      } else {
        o.legend = Object.assign({}, LEGEND_BG_CLEAR, {
          font: { color: fc },
          orientation: "v",
          y: 1,
          yanchor: "top",
          x: 1.02,
          xanchor: "left",
          title: { text: ltitle, font: { color: fc, size: 12 } },
        });
        o.margin = { l: 52, r: 120, t: 24, b: 56 };
      }
    } else if (inPie && hasLegend && isNarrow()) {
      tracePatch = { domain: [{ x: [0.06, 0.94], y: [0.34, 0.86] }] };
      traceIndices = [0];
      var nt = legendTitleText(L);
      o.legend = Object.assign({}, LEGEND_BG_CLEAR, {
        font: { color: fc },
        orientation: "h",
        y: -0.02,
        yanchor: "top",
        x: 0.5,
        xanchor: "center",
        itemwidth: 30,
        tracegroupgap: 6,
        title: { text: nt, font: { color: fc, size: 12 } },
      });
      o.margin = { l: 10, r: 10, t: 70, b: 132 };
    } else if (inPie && hasLegend && !isNarrow() && pieLayoutBaseline.has(gd)) {
      tracePatch = (function () {
        var b = pieLayoutBaseline.get(gd);
        return { domain: [{ x: b.domainx.slice(), y: b.domainy.slice() }] };
      })();
      traceIndices = [0];
      var bp = pieLayoutBaseline.get(gd);
      var lt = bp.legTitle || legendTitleText(L);
      o.margin = Object.assign({}, bp.margin);
      o.legend = desktopPieLegend(fc, lt);
    } else {
      var leg = L.legend || {};
      var lf = Object.assign({}, leg.font || {});
      lf.color = fc;
      var legNext = Object.assign({}, leg, LEGEND_BG_CLEAR, { font: lf });
      if (leg.title && typeof leg.title === "object") {
        legNext.title = Object.assign({}, leg.title, {
          font: Object.assign({}, leg.title.font || {}, { color: fc }),
        });
      }
      o.legend = legNext;
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
    var anns = L.annotations;
    if (anns && anns.length) {
      for (var i = 0; i < anns.length; i++) {
        o["annotations[" + i + "].font.color"] = fc;
      }
    }
    try {
      if (
        tracePatch &&
        traceIndices &&
        traceIndices.length &&
        typeof window.Plotly.update === "function"
      ) {
        window.Plotly.update(gd, tracePatch, o, traceIndices);
      } else {
        window.Plotly.relayout(gd, o);
      }
    } catch (e) {
      try {
        window.Plotly.relayout(gd, o);
      } catch (e3) {}
    }
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
