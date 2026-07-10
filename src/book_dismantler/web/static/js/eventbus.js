/**
 * 极简事件总线：替代散落的 addEventListener / dispatchEvent 模式。
 * 用于跨组件通信（如 store 变更后通知特定 UI 重新渲染）。
 *
 * 用法：
 *   const bus = window.bdBus;
 *   const off = bus.on('jobs:updated', (jobs) => { ... });
 *   bus.emit('jobs:updated', newJobs);
 *   off();
 */
(function (global) {
  "use strict";

  function createBus() {
    const listeners = new Map(); // event -> Set<fn>

    return {
      on(event, fn) {
        if (!listeners.has(event)) listeners.set(event, new Set());
        listeners.get(event).add(fn);
        return function off() {
          const set = listeners.get(event);
          if (set) set.delete(fn);
        };
      },
      off(event, fn) {
        const set = listeners.get(event);
        if (set) set.delete(fn);
      },
      emit(event, payload) {
        const set = listeners.get(event);
        if (!set) return;
        set.forEach(function (fn) {
          try {
            fn(payload);
          } catch (e) {
            console.error("bus listener error for", event, e);
          }
        });
      },
    };
  }

  global.bdBus = createBus();
  global.bdCreateBus = createBus;
})(window);
