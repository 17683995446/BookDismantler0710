/**
 * 极简路由：管理 Tab 切换 + URL 同步 + 滚动位置记忆。
 *
 * 用法：
 *   Router.init({ onChange: (tab, prev) => { ... } });
 *   Router.navigate('home');
 *   Router.getCurrentTab();
 *
 * 支持 URL 参数：?tab=home/knowledge/jobs/settings
 * 支持 Hash 路由：#home / #knowledge / #jobs / #settings
 */
(function (global) {
  "use strict";

  var VALID_TABS = ["knowledge", "home", "jobs", "settings"];
  /* S1-BUG1: 默认 Tab 改为 home，符合用户预期 */
  var currentTab = "home";
  var onChange = null;
  var store = global.bdStore;

  /* S1-BUG6: 滚动位置记忆 — 每个Tab独立保存 */
  var scrollMemory = {};

  function getCurrentTab() {
    return currentTab;
  }

  function navigate(tab, opts) {
    if (VALID_TABS.indexOf(tab) === -1) return;
    opts = opts || {};
    var prev = currentTab;
    currentTab = tab;
    if (store) {
      store.setState({ activeTab: tab });
    }
    if (opts.syncUrl !== false) {
      syncUrl(tab);
    }
    if (!opts.silent && typeof onChange === "function") {
      onChange(tab, prev);
    }
    if (global.bdBus) {
      global.bdBus.emit("tab:changed", { tab: tab, prev: prev });
    }
  }

  function syncUrl(tab) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("tab", tab);
      /* 同时更新 hash，支持 #tab 直接访问 */
      url.hash = tab;
      window.history.pushState({}, "", url);
    } catch (e) {
      /* URL 同步失败不影响功能 */
    }
  }

  /* S1-BUG6: 保存当前Tab的滚动位置 */
  function saveScroll(tab) {
    try {
      scrollMemory[tab] = window.scrollY || 0;
    } catch (e) {
      /* 忽略 */
    }
  }

  /* S1-BUG6: 恢复指定Tab的滚动位置 */
  function restoreScroll(tab) {
    var pos = scrollMemory[tab];
    if (typeof pos === "number" && pos > 0) {
      try {
        window.scrollTo(0, pos);
      } catch (e) {
        /* 忽略 */
      }
    } else {
      /* 无记忆位置时回到顶部 */
      try {
        window.scrollTo(0, 0);
      } catch (e) {
        /* 忽略 */
      }
    }
  }

  /* S1-BUG2/3: 从URL读取初始tab（同时支持query参数和hash） */
  function readTabFromUrl() {
    try {
      /* 优先读取 hash */
      var hash = window.location.hash.replace("#", "");
      if (hash && VALID_TABS.indexOf(hash) !== -1) {
        return hash;
      }
      /* 其次读取 query 参数 */
      var params = new URLSearchParams(window.location.search);
      var tabParam = params.get("tab");
      if (tabParam && VALID_TABS.indexOf(tabParam) !== -1) {
        return tabParam;
      }
    } catch (e) {
      /* URL 解析失败使用默认 */
    }
    return null;
  }

  function init(opts) {
    opts = opts || {};
    onChange = opts.onChange || null;

    /* 从 URL 读取初始 tab */
    var urlTab = readTabFromUrl();
    if (urlTab) {
      currentTab = urlTab;
    }

    /* 响应浏览器前进/后退 */
    window.addEventListener("popstate", function () {
      var tab = readTabFromUrl();
      if (tab) {
        navigate(tab);
      }
    });

    /* S1-BUG2/3: 也监听 hashchange 事件（支持手动修改URL hash） */
    window.addEventListener("hashchange", function () {
      var tab = readTabFromUrl();
      if (tab && tab !== currentTab) {
        navigate(tab, { syncUrl: false });
      }
    });

    return currentTab;
  }

  global.Router = {
    init: init,
    navigate: navigate,
    getCurrentTab: getCurrentTab,
    saveScroll: saveScroll,
    restoreScroll: restoreScroll,
    VALID_TABS: VALID_TABS,
  };
})(window);
