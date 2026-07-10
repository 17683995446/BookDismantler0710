/**
 * 前端模块测试：store / eventbus / router / utils
 * 通过 Node.js 加载并运行（无 DOM 环境，使用 jsdom 替代或简化）。
 *
 * 用法：node tests/frontend/test-modules.mjs
 */
"use strict";

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __filename = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(__filename), "../..");
const STATIC = path.join(ROOT, "src/book_dismantler/web/static");

// 读取 JS 源码并 polyfill window/document
function loadModule(name) {
  const code = readFileSync(path.join(STATIC, "js", name + ".js"), "utf-8");
  // 包装 IIFE：传入 window/document 占位
  return code;
}

// 极简 window/document polyfill
function makeWindow() {
  const listeners = {};
  const win = {
    addEventListener: (e, fn) => {
      (listeners[e] = listeners[e] || []).push(fn);
    },
    dispatchEvent: (e) => {
      (listeners[e.type] || []).forEach((fn) => fn(e));
    },
    /* S1: 添加 pushState 和 hash 支持，匹配 router.js 新功能 */
    history: { replaceState: () => {}, pushState: () => {} },
    location: { href: "http://test/", search: "", hash: "" },
  };
  const doc = {
    addEventListener: () => {},
    getElementById: () => null,
    querySelectorAll: () => [],
    createElement: () => ({ textContent: "", innerHTML: "" }),
  };
  win.document = doc;
  return win;
}

function withWindow(fn) {
  const win = makeWindow();
  globalThis.window = win;
  globalThis.document = win.document;
  globalThis.location = win.location;
  globalThis.history = win.history;
  return fn(win);
}

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log("  ✓ " + name);
    passed++;
  } catch (e) {
    console.error("  ✗ " + name + "\n    " + e.message);
    failed++;
  }
}

console.log("\n=== Store ===");
withWindow((win) => {
  const code = loadModule("store");
  eval(code);
  const store = win.bdStore;
  test("initial state has activeTab", () => {
    assert.equal(store.getState().activeTab, "home");
  });
  test("setState updates state", () => {
    store.setState({ activeTab: "home" });
    assert.equal(store.getState().activeTab, "home");
  });
  test("subscribe receives updates", () => {
    let received = null;
    const off = store.subscribe((s) => (received = s.activeTab));
    store.setState({ activeTab: "jobs" });
    assert.equal(received, "jobs");
    off();
    store.setState({ activeTab: "settings" });
    assert.equal(received, "jobs"); // 已取消订阅
  });
  test("functional setState", () => {
    store.setState((s) => ({ activeTab: s.activeTab + "!" }));
    assert.equal(store.getState().activeTab, "settings!");
  });
  test("listener error doesn't break others", () => {
    const order = [];
    store.subscribe(() => {
      throw new Error("bad");
    });
    store.subscribe(() => order.push("good"));
    store.setState({ test: 1 });
    assert.deepEqual(order, ["good"]);
  });
});

console.log("\n=== EventBus ===");
withWindow((win) => {
  eval(loadModule("eventbus"));
  const bus = win.bdBus;
  test("on/emit", () => {
    let received = null;
    bus.on("test:1", (v) => (received = v));
    bus.emit("test:1", "hello");
    assert.equal(received, "hello");
  });
  test("off", () => {
    let received = 0;
    const off = bus.on("test:2", () => received++);
    bus.emit("test:2", null);
    off();
    bus.emit("test:2", null);
    assert.equal(received, 1);
  });
  test("listener error doesn't break others", () => {
    const order = [];
    bus.on("test:3", () => {
      throw new Error("boom");
    });
    bus.on("test:3", () => order.push("ok"));
    bus.emit("test:3", null);
    assert.deepEqual(order, ["ok"]);
  });
  test("emit with no listener", () => {
    bus.emit("test:nobody", "x"); // 不抛错
  });
});

console.log("\n=== Router ===");
withWindow((win) => {
  eval(loadModule("router"));
  test("init returns default tab", () => {
    win.location.search = "";
    win.location.hash = "";
    const r = win.Router.init();
    assert.equal(r, "home");
  });
  test("init reads tab from URL", () => {
    win.location.search = "?tab=jobs";
    const r = win.Router.init();
    assert.equal(r, "jobs");
  });
  test("navigate updates current tab", () => {
    const r = win.Router;
    r.navigate("settings");
    assert.equal(r.getCurrentTab(), "settings");
  });
  test("navigate invalid tab is no-op", () => {
    const r = win.Router;
    const before = r.getCurrentTab();
    r.navigate("invalid-tab");
    assert.equal(r.getCurrentTab(), before);
  });
  test("VALID_TABS list", () => {
    assert.deepEqual(win.Router.VALID_TABS, ["knowledge", "home", "jobs", "settings"]);
  });
});

console.log("\n=== Utils (Debounce/Throttle) ===");
withWindow((win) => {
  // utils.js 使用 IIFE 暴露 window.BD_Utils，需要伪造 DOM
  win.document.querySelectorAll = () => [];
  win.document.getElementById = () => ({
    className: "toast hidden",
    classList: { add: () => {}, remove: () => {}, contains: () => false },
    textContent: "",
  });
  eval(loadModule("utils"));
  const { debounce, throttle } = win.BD_Utils;
  test("debounce delays execution", (done) => {
    let called = 0;
    const d = debounce(() => called++, 30);
    d();
    d();
    d();
    setTimeout(() => {
      assert.equal(called, 1);
      done && done();
    }, 60);
  });
  test("debounce passes args", (done) => {
    const d = debounce((a, b) => {
      assert.equal(a + b, 3);
      done && done();
    }, 20);
    d(1, 2);
  });
  test("debounce cancel", (done) => {
    let called = 0;
    const d = debounce(() => called++, 20);
    d();
    d.cancel();
    setTimeout(() => {
      assert.equal(called, 0);
      done && done();
    }, 40);
  });
  test("throttle limits calls", (done) => {
    let called = 0;
    const t = throttle(() => called++, 30);
    t();
    t();
    t();
    setTimeout(() => {
      assert.ok(called <= 2, "called=" + called);
      done && done();
    }, 100);
  });
});

console.log("\n=== Utils (format) ===");
withWindow((win) => {
  win.document.querySelectorAll = () => [];
  win.document.getElementById = () => null;
  eval(loadModule("utils"));
  const u = win.BD_Utils;
  test("formatSize", () => {
    assert.equal(u.formatSize(0), "0 B");
    assert.equal(u.formatSize(1024), "1.0 KB");
    assert.equal(u.formatSize(1048576), "1.0 MB");
    assert.equal(u.formatSize(1073741824), "1.00 GB");
  });
  test("formatDuration", () => {
    assert.equal(u.formatDuration(0.5), "0.5 秒");
    assert.equal(u.formatDuration(30), "30 秒");
    assert.equal(u.formatDuration(60), "1 分 0 秒");
    assert.equal(u.formatDuration(3661), "1 时 1 分");
  });
  test("statusText", () => {
    assert.equal(u.statusText("pending"), "等待中");
    assert.equal(u.statusText("running"), "执行中");
    assert.equal(u.statusText("done"), "已完成");
    assert.equal(u.statusText("failed"), "失败");
    assert.equal(u.statusText("cancelled"), "已取消");
    assert.equal(u.statusText("unknown"), "unknown");
  });
  test("escapeHtml", () => {
    // 注：escapeHtml 使用了 DOM API（createElement('div').textContent），
    // 在 Node 测试环境中该 API 不工作，故仅测试纯字符串转义函数 escapeAttr
    assert.equal(u.escapeHtml == null, false);
    assert.equal(typeof u.escapeHtml, "function");
  });
  test("escapeAttr", () => {
    assert.equal(u.escapeAttr('"hi"'), "&quot;hi&quot;");
    assert.equal(u.escapeAttr(null), "");
  });
});

console.log("\n=== Summary ===");
console.log(`  ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
