/**
 * 确认对话框组件。
 * 通过 bdBus 触发显示：bus.emit('confirm:show', { title, message, onOk, ... })
 * 替代原生 confirm()，提供更佳的视觉一致性和可定制性。
 *
 * 设计原则：
 * - 单一职责：仅负责模态框的显示/隐藏与用户交互
 * - 依赖最小：仅依赖 bdBus 和 store
 * - 错误隔离：异常时仍能关闭模态框
 */
(function (global) {
  "use strict";

  const store = global.bdStore;
  const bus = global.bdBus;

  function showConfirm(options) {
    const opts = Object.assign(
      {
        title: "确认操作",
        message: "是否继续？",
        okText: "确认",
        cancelText: "取消",
        danger: false,
        onOk: null,
        onCancel: null,
      },
      options || {}
    );
    store.setState({
      confirmModal: {
        visible: true,
        title: opts.title,
        message: opts.message,
        okText: opts.okText,
        cancelText: opts.cancelText,
        danger: !!opts.danger,
        onOk: opts.onOk,
        onCancel: opts.onCancel,
      },
    });
  }

  function hideConfirm() {
    var cur = store.getState().confirmModal;
    store.setState({
      confirmModal: Object.assign({}, cur, { visible: false }),
    });
  }

  function handleOk() {
    var cur = store.getState().confirmModal;
    hideConfirm();
    if (typeof cur.onOk === "function") {
      try {
        cur.onOk();
      } catch (e) {
        console.error("confirm onOk error", e);
      }
    }
  }

  function handleCancel() {
    var cur = store.getState().confirmModal;
    hideConfirm();
    if (typeof cur.onCancel === "function") {
      try {
        cur.onCancel();
      } catch (e) {
        console.error("confirm onCancel error", e);
      }
    }
  }

  // 绑定到 DOM（在 app.js 初始化时调用）。
  // 使用 _bdBound 标志防重复绑定（兼容 app.js 中已存在的旧绑定）。
  function bindElements() {
    var modal = document.getElementById("confirm-modal");
    if (!modal) return;
    if (modal._bdBound) return; // 已绑定则跳过
    modal._bdBound = true;
    var okBtn = document.getElementById("confirm-modal-ok");
    var cancelBtn = document.getElementById("confirm-modal-cancel");
    var closeBtn = document.getElementById("confirm-modal-close");
    if (okBtn) okBtn.addEventListener("click", handleOk);
    if (cancelBtn) cancelBtn.addEventListener("click", handleCancel);
    if (closeBtn) closeBtn.addEventListener("click", handleCancel);

    // ESC 键关闭
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && store.getState().confirmModal.visible) {
        handleCancel();
      }
    });

    // 背景点击关闭
    modal.addEventListener("click", function (e) {
      if (e.target === modal) handleCancel();
    });
  }

  // 订阅 store：模态框可见性变化时同步 DOM
  store.subscribe(function (state) {
    var modal = document.getElementById("confirm-modal");
    if (!modal) return;
    var cm = state.confirmModal;
    if (cm.visible) {
      modal.classList.remove("hidden");
      var titleEl = document.getElementById("confirm-modal-title");
      var msgEl = document.getElementById("confirm-modal-message");
      var okEl = document.getElementById("confirm-modal-ok");
      var cancelEl = document.getElementById("confirm-modal-cancel");
      if (titleEl) titleEl.textContent = cm.title;
      if (msgEl) msgEl.textContent = cm.message;
      if (okEl) {
        okEl.textContent = cm.okText;
        okEl.classList.toggle("btn-danger", cm.danger);
      }
      if (cancelEl) cancelEl.textContent = cm.cancelText;
    } else {
      modal.classList.add("hidden");
    }
  });

  global.ConfirmModal = {
    show: showConfirm,
    hide: hideConfirm,
    bind: bindElements,
  };
})(window);
