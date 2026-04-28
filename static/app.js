/*!
 * Copyright (c) 2026-2027 宛皓 (Wan Hao). All rights reserved.
 * 本文件为「云煤矿业产销量管理系统」的组成部分。
 * 仅授予云南云煤矿业开发有限公司及其关联方在内部业务系统中使用；
 * 未经著作权人书面同意，禁止复制、反编译、转售或二次发行。详见根目录 LICENSE。
 */
(function () {
  (function setupTheme() {
    var STORAGE_KEY = "ymky-theme";
    function getPref() {
      try {
        return localStorage.getItem(STORAGE_KEY) || "system";
      } catch (e) {
        return "system";
      }
    }
    function resolveMode(pref) {
      if (pref === "dark") return "dark";
      if (pref === "light") return "light";
      if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
      }
      return "light";
    }
    function applyTheme(pref) {
      var p = pref;
      if (p === undefined || p === null) {
        p = getPref();
      } else {
        try {
          localStorage.setItem(STORAGE_KEY, p);
        } catch (e) {}
      }
      var mode = resolveMode(p);
      document.documentElement.setAttribute("data-color-mode", mode);
      document.documentElement.setAttribute("data-theme-pref", p);
      var sel = document.getElementById("themeSelect");
      if (sel) sel.value = p;
      var meta = document.getElementById("meta-theme-color");
      if (meta) meta.setAttribute("content", mode === "dark" ? "#121316" : "#0062a8");
      try {
        window.dispatchEvent(new CustomEvent("ymky-theme", { detail: { mode: mode, pref: p } }));
      } catch (e) {}
    }
    function onSystemColorChange() {
      if (getPref() === "system") applyTheme("system");
    }
    document.addEventListener("DOMContentLoaded", function () {
      applyTheme(getPref());
      var sel = document.getElementById("themeSelect");
      if (sel) {
        sel.addEventListener("change", function () {
          applyTheme(sel.value);
        });
      }
      var mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq.addEventListener) mq.addEventListener("change", onSystemColorChange);
      else if (mq.addListener) mq.addListener(onSystemColorChange);
    });
  })();

  function pad(n) { return String(n).padStart(2, "0"); }

  function tick() {
    var els = document.querySelectorAll("#clock, #clock-foot");
    if (!els.length) return;
    var fmt = new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      hour12: false,
    });
    var text = "北京时间 " + fmt.format(new Date());
    els.forEach(function (el) { el.textContent = text; });
  }
  tick();
  setInterval(tick, 1000);

  /* data-loading：防重复提交；disabled 推迟到下一 tick，避免漏掉 submitter 的 name/value */
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.matches("[data-loading]")) return;
    if (form._submitting) { ev.preventDefault(); return; }
    form._submitting = true;
    var btns = form.querySelectorAll("button[type=submit]");
    btns.forEach(function (b) {
      if (b.dataset._origText === undefined) b.dataset._origText = b.textContent;
      b.setAttribute("aria-busy", "true");
      if (b === document.activeElement || ev.submitter === b) {
        b.textContent = "处理中…";
      }
    });
    setTimeout(function () {
      btns.forEach(function (b) { b.disabled = true; });
    }, 0);
    setTimeout(function () {
      form._submitting = false;
      btns.forEach(function (b) {
        b.disabled = false;
        b.removeAttribute("aria-busy");
        if (b.dataset._origText !== undefined) b.textContent = b.dataset._origText;
      });
    }, 8000);
  }, true);

  /* number：值为 0 时 focus 全选 */
  document.addEventListener("focusin", function (ev) {
    var t = ev.target;
    if (t && t.tagName === "INPUT" && t.type === "number") {
      if (parseFloat(t.value) === 0) {
        try { t.select(); } catch (_) {}
      }
    }
  });

  /* data-confirm-leave：离开前若表单已改则 confirm */
  function snapshotForm(form) {
    var snap = Object.create(null);
    form.querySelectorAll("input, select, textarea").forEach(function (el) {
      if (!el.name) return;
      var t = (el.type || el.tagName).toLowerCase();
      if (t === "submit" || t === "button" || t === "hidden") return;
      snap[el.name + "::" + t] = el.value;
    });
    form._initialSnap = snap;
  }
  function isFormDirty(form) {
    var snap = form && form._initialSnap;
    if (!snap) return false;
    var dirty = false;
    form.querySelectorAll("input, select, textarea").forEach(function (el) {
      if (!el.name) return;
      var t = (el.type || el.tagName).toLowerCase();
      if (t === "submit" || t === "button" || t === "hidden") return;
      var key = el.name + "::" + t;
      if (key in snap && snap[key] !== el.value) dirty = true;
    });
    return dirty;
  }
  function snapshotAll() {
    document.querySelectorAll("form").forEach(snapshotForm);
  }
  if (document.readyState !== "loading") snapshotAll();
  else document.addEventListener("DOMContentLoaded", snapshotAll);

  document.addEventListener("click", function (ev) {
    var el = ev.target && ev.target.closest && ev.target.closest("[data-confirm-leave]");
    if (!el) return;
    var form = (el.form) || el.closest("form");
    var dirty = form ? isFormDirty(form) : false;
    if (!dirty) {
      var anyDirty = false;
      document.querySelectorAll("form").forEach(function (f) {
        if (isFormDirty(f)) anyDirty = true;
      });
      dirty = anyDirty;
    }
    if (!dirty) return;
    var msg = el.getAttribute("data-confirm-leave") || "尚未提交，确认离开吗？";
    if (!window.confirm(msg)) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
    }
  }, true);

  /* 移动端侧栏抽屉；≥1024px 由 CSS 保持静态栏 */
  (function setupNavDrawer() {
    var toggle = document.getElementById("navToggle");
    var sidebar = document.getElementById("sidebarNav");
    var backdrop = document.getElementById("navBackdrop");
    if (!toggle || !sidebar) return;

    function isDesktop() {
      return window.matchMedia("(min-width: 1024px)").matches;
    }
    function open() {
      if (isDesktop()) return;
      sidebar.classList.add("is-open");
      sidebar.setAttribute("aria-hidden", "false");
      if (backdrop) {
        backdrop.hidden = false;
        requestAnimationFrame(function () { backdrop.classList.add("is-open"); });
      }
      toggle.setAttribute("aria-expanded", "true");
      toggle.setAttribute("aria-label", "关闭功能菜单");
      document.body.classList.add("nav-open");
    }
    function close() {
      sidebar.classList.remove("is-open");
      sidebar.setAttribute("aria-hidden", "true");
      if (backdrop) {
        backdrop.classList.remove("is-open");
        setTimeout(function () { backdrop.hidden = true; }, 240);
      }
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "打开功能菜单");
      document.body.classList.remove("nav-open");
    }
    function toggleOpen() {
      if (sidebar.classList.contains("is-open")) close();
      else open();
    }

    var lastFire = 0;
    function onActivate(ev) {
      var now = Date.now();
      if (now - lastFire < 250) return;
      lastFire = now;
      ev.preventDefault();
      toggleOpen();
    }
    toggle.addEventListener("click", onActivate);
    toggle.addEventListener("touchend", onActivate, { passive: false });
    if (backdrop) {
      backdrop.addEventListener("click", close);
      backdrop.addEventListener("touchend", function (ev) {
        ev.preventDefault();
        close();
      }, { passive: false });
    }
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && sidebar.classList.contains("is-open")) close();
    });
    sidebar.addEventListener("click", function (ev) {
      var a = ev.target && ev.target.closest && ev.target.closest("a");
      if (a) close();
    });
    window.addEventListener("resize", function () {
      if (isDesktop() && sidebar.classList.contains("is-open")) close();
    });
  })();

  /* /health 探测；可见性控制轮询频率 */
  (function setupNetStatus() {
    var pill = document.getElementById("net-status");
    if (!pill) return;
    var dotEl = pill.querySelector(".net-dot");
    var labelEl = pill.querySelector(".net-label");

    var INTERVAL_OK   = 20000;
    var INTERVAL_WARN = 10000;
    var INTERVAL_FAIL = 5000;
    var INTERVAL_MAX_BACKOFF = 30000;
    var FETCH_TIMEOUT = 4000;
    var THRESHOLD_FAIR = 300;
    var THRESHOLD_SLOW = 1000;

    var timer = null;
    var inflight = null;
    var consecutiveFails = 0;

    function fmtClock(d) {
      function p(n) { return String(n).padStart(2, "0"); }
      return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
    }
    function setState(state, text, rtt) {
      pill.dataset.state = state;
      if (labelEl) labelEl.textContent = text;
      var when = fmtClock(new Date());
      var rttPart = (rtt == null) ? "" : (" · 延迟 " + Math.round(rtt) + " ms");
      pill.title = "上次检测 " + when + rttPart;
    }

    function schedule(ms) {
      if (timer) { clearTimeout(timer); timer = null; }
      if (document.hidden) return;
      timer = setTimeout(check, ms);
    }

    function onSuccess(rtt) {
      consecutiveFails = 0;
      if (rtt < THRESHOLD_FAIR) {
        setState("good", "网络畅通", rtt);
        schedule(INTERVAL_OK);
      } else if (rtt < THRESHOLD_SLOW) {
        setState("fair", "略有延迟", rtt);
        schedule(INTERVAL_OK);
      } else {
        setState("slow", "网络拥堵", rtt);
        schedule(INTERVAL_WARN);
      }
    }
    function onFailure() {
      consecutiveFails += 1;
      setState("offline", "连不上服务", null);
      var ms = consecutiveFails <= 3
        ? INTERVAL_FAIL
        : Math.min(INTERVAL_FAIL * Math.pow(2, consecutiveFails - 3), INTERVAL_MAX_BACKOFF);
      schedule(ms);
    }

    function check() {
      /* 不依赖 navigator.onLine：部分手机在 WiFi 下会误报为 false，导致永远红灯 */
      if (inflight) { try { inflight.abort(); } catch (_) {} }
      var ctrl = (typeof AbortController !== "undefined") ? new AbortController() : null;
      inflight = ctrl;
      var timeoutId = setTimeout(function () {
        if (ctrl) { try { ctrl.abort(); } catch (_) {} }
      }, FETCH_TIMEOUT);
      var t0 = (performance && performance.now) ? performance.now() : Date.now();
      var url = "/health?t=" + Math.floor(t0);
      var opts = { method: "GET", cache: "no-store", credentials: "same-origin" };
      if (ctrl) opts.signal = ctrl.signal;
      fetch(url, opts).then(function (resp) {
        clearTimeout(timeoutId);
        inflight = null;
        var rtt = ((performance && performance.now) ? performance.now() : Date.now()) - t0;
        if (!resp.ok) { onFailure(); return; }
        onSuccess(rtt);
      }).catch(function () {
        clearTimeout(timeoutId);
        inflight = null;
        onFailure();
      });
    }

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) {
        if (timer) { clearTimeout(timer); timer = null; }
      } else {
        check();
      }
    });
    window.addEventListener("online",  function () { check(); });
    window.addEventListener("offline", function () { onFailure(); });
    window.addEventListener("pageshow", function () { check(); });

    check();
  })();
})();
