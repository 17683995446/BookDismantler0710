/**
 * 空状态组件。
 * 统一展示"无数据/无任务/无选择"等空场景。
 *
 * 用法：
 *   EmptyState.render(target, { icon, title, desc, actionText, onAction });
 */
(function (global) {
  "use strict";

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function render(target, opts) {
    var el = typeof target === "string" ? document.getElementById(target) : target;
    if (!el) return;
    var o = Object.assign(
      {
        icon: "📭",
        title: "暂无内容",
        desc: "",
        actionText: "",
        onAction: null,
        size: "lg", // 'sm' | 'lg'
      },
      opts || {}
    );
    var html =
      '<div class="empty-state empty-state-' + escapeHtml(o.size) + '">' +
      '<div class="empty-state-icon">' + escapeHtml(o.icon) + "</div>" +
      '<p class="empty-state-title">' + escapeHtml(o.title) + "</p>";
    if (o.desc) {
      html += '<p class="empty-state-desc">' + escapeHtml(o.desc) + "</p>";
    }
    if (o.actionText && typeof o.onAction === "function") {
      html +=
        '<button class="btn btn-primary btn-large" type="button" data-empty-action>' +
        escapeHtml(o.actionText) +
        "</button>";
    }
    html += "</div>";
    el.innerHTML = html;
    var btn = el.querySelector("[data-empty-action]");
    if (btn && typeof o.onAction === "function") {
      btn.addEventListener("click", o.onAction);
    }
  }

  global.EmptyState = { render: render };
})(window);
