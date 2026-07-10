/**
 * Book Dismantler · 工具函数模块
 *
 * 提供 DOM 快捷方法、格式化、转义等通用工具。
 * 通过 window.BD_Utils 命名空间暴露，供 app.js 使用。
 */
(function () {
    "use strict";

    /* ===================== DOM 快捷方法 ===================== */
    function $(id) { return document.getElementById(id); }

    function on(target, evt, handler) {
        if (target) target.addEventListener(evt, handler);
    }

    /* ===================== 辅助函数 ===================== */

    /** 弹出 Toast 通知（type: success/error/info）。 */
    function showToast(message, type) {
        var toast = $("toast");
        if (!toast) return;
        toast.textContent = message == null ? "" : String(message);
        toast.className = "toast " + (type || "info");
        toast.classList.remove("hidden");
        clearTimeout(toast._timer);
        toast._timer = setTimeout(function () {
            toast.classList.add("hidden");
        }, 3200);
    }

    /** 友好地格式化文件大小。 */
    function formatSize(bytes) {
        if (bytes == null || isNaN(bytes)) return "-";
        var n = Number(bytes);
        if (n < 1024) return n + " B";
        if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
        if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
        return (n / 1073741824).toFixed(2) + " GB";
    }

    /** 任务状态码 -> 中文文本。 */
    function statusText(status) {
        var map = {
            pending: "等待中",
            running: "执行中",
            done: "已完成",
            failed: "失败",
            cancelled: "已取消",
            reconciled: "已完成",  /* C2: 后端 reconciled 状态映射为用户友好文案 */
            completed: "已完成"
        };
        return map[status] || status || "未知";
    }

    function statusClass(status) {
        return "status-" + (status || "pending");
    }

    /** HTML 转义，防止注入。 */
    function escapeHtml(text) {
        if (text == null) return "";
        var div = document.createElement("div");
        div.textContent = String(text);
        return div.innerHTML;
    }

    /** 属性值转义。 */
    function escapeAttr(text) {
        return String(text == null ? "" : text)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    /** ISO 时间字符串 -> 本地可读时间。 */
    function formatTime(isoString) {
        if (!isoString) return "-";
        var d = new Date(isoString);
        if (isNaN(d.getTime())) return String(isoString);
        var pad = function (n) { return n < 10 ? "0" + n : "" + n; };
        return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
            " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
    }

    function formatDuration(seconds) {
        if (seconds == null || isNaN(seconds)) return "-";
        var s = Number(seconds);
        if (s < 1) return s.toFixed(1) + " 秒";
        if (s < 60) return Math.round(s) + " 秒";
        var m = Math.floor(s / 60);
        var r = Math.round(s % 60);
        if (m < 60) return m + " 分 " + r + " 秒";
        var h = Math.floor(m / 60);
        return h + " 时 " + (m % 60) + " 分";
    }

    function fileIcon(filename) {
        var name = (filename || "").toLowerCase();
        if (name.indexOf("知识图谱") >= 0 || name.indexOf("graph") >= 0) return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="5" cy="6" r="2.5" fill="currentColor"/><circle cx="19" cy="6" r="2.5" fill="currentColor"/><circle cx="12" cy="14" r="3" fill="currentColor" opacity=".8"/><circle cx="6" cy="20" r="2" fill="currentColor" opacity=".6"/><circle cx="18" cy="20" r="2" fill="currentColor" opacity=".6"/><path d="M7 7l3 6M17 7l-3 6M10 16l-3 3M14 16l3 3M7 6h10" stroke="currentColor" stroke-width="1.2" opacity=".4"/></svg>';
        if (name.indexOf(".html") >= 0) return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5z" fill="currentColor" opacity=".8"/><path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" opacity=".4"/></svg>';
        if (name.indexOf(".md") >= 0) return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M3 3h18v18H3z" stroke="currentColor" stroke-width="2" opacity=".4"/><path d="M7 14l3-3 3 2 4-5" stroke="currentColor" stroke-width="2" fill="none"/></svg>';
        if (name.indexOf(".org") >= 0) return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="2" opacity=".4"/><path d="M7 8h10M7 12h10M7 16h6" stroke="currentColor" stroke-width="2"/></svg>';
        if (name.indexOf(".json") >= 0) return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M8 3H6a2 2 0 00-2 2v4a2 2 0 01-2 2 2 2 0 012 2v4a2 2 0 002 2h2M16 3h2a2 2 0 012 2v4a2 2 0 002 2 2 2 0 00-2 2v4a2 2 0 01-2 2h-2" stroke="currentColor" stroke-width="2"/></svg>';
        return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M4 4h16v16H4z" stroke="currentColor" stroke-width="2"/></svg>';
    }

    /* ===================== E6: 节流/防抖 ===================== */

    /** 防抖：连续调用只执行最后一次。用于搜索框输入。 */
    function debounce(fn, wait) {
        var timer = null;
        var debounced = function () {
            var ctx = this;
            var args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function () {
                fn.apply(ctx, args);
                timer = null;
            }, wait || 200);
        };
        debounced.cancel = function () { clearTimeout(timer); timer = null; };
        return debounced;
    }

    /** 节流：固定间隔最多执行一次。用于滚动/resize。 */
    function throttle(fn, wait) {
        var last = 0;
        var timer = null;
        return function () {
            var ctx = this;
            var args = arguments;
            var now = Date.now();
            if (now - last >= (wait || 100)) {
                last = now;
                fn.apply(ctx, args);
            } else {
                clearTimeout(timer);
                timer = setTimeout(function () {
                    last = Date.now();
                    fn.apply(ctx, args);
                }, wait - (now - last));
            }
        };
    }

    /* ===================== 暴露命名空间 ===================== */
    window.BD_Utils = {
        $: $,
        on: on,
        showToast: showToast,
        formatSize: formatSize,
        statusText: statusText,
        statusClass: statusClass,
        escapeHtml: escapeHtml,
        escapeAttr: escapeAttr,
        formatTime: formatTime,
        formatDuration: formatDuration,
        fileIcon: fileIcon,
        debounce: debounce,
        throttle: throttle
    };
})();
