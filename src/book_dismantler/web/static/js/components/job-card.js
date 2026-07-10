/**
 * 任务卡片组件：渲染单个任务的摘要、操作按钮。
 *
 * 用法：
 *   JobCard.render(cardEl, job, callbacks);
 *   callbacks: { onCancel, onDelete, onView, onClick }
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

  function formatDuration(seconds) {
    if (seconds == null) return null;
    if (seconds < 1) return seconds.toFixed(1) + " 秒";
    if (seconds < 60) return Math.round(seconds) + " 秒";
    var m = Math.floor(seconds / 60);
    var s = Math.round(seconds % 60);
    return m + " 分 " + s + " 秒";
  }

  function buildMetaPills(job) {
    var parts = [];
    if (job.provider) parts.push(escapeHtml(job.provider));
    if (job.duration_seconds != null) {
      var dur = formatDuration(job.duration_seconds);
      if (dur) parts.push("⏱ " + dur);
    }
    var count = job.artifact_count || 0;
    var countClass = count === 0 ? " job-meta-empty" : "";
    parts.push(
      '<span class="job-meta-pill' + countClass + '">📦 ' + count + " 产物</span>"
    );
    return '<span class="job-meta-pill">' + parts.join("</span><span class=\"job-meta-pill\">") + "</span>";
  }

  function buildActions(job) {
    var html = "";
    if (job.status === "pending" || job.status === "running") {
      html +=
        '<button class="btn btn-sm btn-secondary" data-action="cancel" data-job-id="' +
        escapeHtml(job.job_id) +
        '">取消</button>';
    } else if (job.status === "done") {
      html +=
        '<button class="btn btn-sm btn-primary" data-action="view" data-job-id="' +
        escapeHtml(job.job_id) +
        '" aria-label="查看产物">查看产物</button>';
      html +=
        '<button class="btn btn-sm btn-danger" data-action="delete" data-job-id="' +
        escapeHtml(job.job_id) +
        '">删除</button>';
    } else {
      html +=
        '<button class="btn btn-sm btn-danger" data-action="delete" data-job-id="' +
        escapeHtml(job.job_id) +
        '">删除</button>';
    }
    return html;
  }

  function render(target, job, cb) {
    var el = typeof target === "string" ? document.getElementById(target) : target;
    if (!el || !job) return;
    cb = cb || {};
    var statusClass = "status-" + (job.status || "pending");
    var statusText = {
      pending: "等待中",
      running: "运行中",
      done: "已完成",
      failed: "失败",
      cancelled: "已取消",
    }[job.status || "pending"] || job.status;

    var html =
      '<div class="job-item' +
      (job.status === "done" ? " job-item-clickable" : "") +
      '" data-job-id="' +
      escapeHtml(job.job_id) +
      '">' +
      '<div class="job-card-body">' +
      '<div class="job-title-row">' +
      '<span class="job-title">' +
      escapeHtml(job.book_title || job.book_filename || "未命名任务") +
      "</span>" +
      '<span class="status-badge ' +
      statusClass +
      '">' +
      escapeHtml(statusText) +
      "</span>" +
      "</div>" +
      '<div class="job-meta">' +
      buildMetaPills(job) +
      "</div>";

    // 进度条（仅运行中/等待中显示）
    if (job.status === "running" || job.status === "pending") {
      var pct = Math.max(0, Math.min(100, job.progress || 0));
      html +=
        '<div class="progress-bar" role="progressbar" aria-valuenow="' +
        pct +
        '" aria-valuemin="0" aria-valuemax="100">' +
        '<div class="progress-fill" style="width:' +
        pct +
        '%"></div></div>';
      if (job.current_step) {
        html += '<div class="job-step">' + escapeHtml(job.current_step) + "</div>";
      }
    }

    html += "</div>"; // .job-card-body
    html += '<div class="job-actions">' + buildActions(job) + "</div>";
    html += "</div>"; // .job-item

    el.innerHTML = html;

    // 绑定事件
    el.querySelectorAll("[data-action]").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        var action = btn.dataset.action;
        if (action === "cancel" && cb.onCancel) cb.onCancel(job.job_id);
        else if (action === "delete" && cb.onDelete) cb.onDelete(job.job_id);
        else if (action === "view" && cb.onView) cb.onView(job.job_id);
      });
    });
    if (cb.onClick && job.status === "done") {
      el.querySelector(".job-item").addEventListener("click", function () {
        cb.onClick(job.job_id);
      });
    }
  }

  global.JobCard = { render: render, formatDuration: formatDuration };
})(window);
