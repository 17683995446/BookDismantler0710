/**
 * 轻量级错误边界：包裹每个 Tab 渲染，捕获渲染异常。
 *
 * 用法：
 *   const safeRender = ErrorBoundary.wrap(renderKnowledge, { fallback: "renderEmpty" });
 *   safeRender();
 *
 * 设计原则：
 * - 仅捕获同步渲染异常，异步异常通过全局 onerror 处理
 * - 降级 UI：显示错误提示 + 重新加载按钮
 * - 错误上报：未来可对接 sentry 等
 */
(function (global) {
  "use strict";

  function wrap(fn, opts) {
    opts = opts || {};
    return function safeRender() {
      try {
        var result = fn.apply(this, arguments);
        return result;
      } catch (e) {
        console.error("Render error:", e, "(fallback:", opts.fallback || "none", ")");
        if (typeof opts.onError === "function") {
          try {
            opts.onError(e);
          } catch (_) {
            /* 忽略降级函数自身的错误 */
          }
        }
        if (typeof opts.fallback === "function") {
          try {
            return opts.fallback(e);
          } catch (fallbackErr) {
            console.error("Fallback also failed:", fallbackErr);
            return renderHardError(e);
          }
        }
        return renderHardError(e);
      }
    };
  }

  function renderHardError(err) {
    return (
      '<div class="error-boundary">' +
      '<div class="error-boundary-icon">⚠️</div>' +
      '<p class="error-boundary-title">页面加载出错</p>' +
      '<p class="error-boundary-desc">' +
      (err && err.message ? err.message : "未知错误") +
      "</p>" +
      '<button class="btn btn-primary" type="button" onclick="location.reload()">重新加载</button>' +
      "</div>"
    );
  }

  // 全局异步错误兜底
  if (typeof window !== "undefined") {
    window.addEventListener("error", function (e) {
      console.error("Window error:", e.error || e.message);
    });
    window.addEventListener("unhandledrejection", function (e) {
      console.error("Unhandled promise rejection:", e.reason);
    });
  }

  global.ErrorBoundary = { wrap: wrap, renderHardError: renderHardError };
})(window);
