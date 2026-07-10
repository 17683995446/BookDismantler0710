/**
 * 极简状态管理：单例 store + 订阅模式。
 * 替代散落的全局变量和直接 DOM 状态。
 *
 * 用法：
 *   const store = window.bdStore;
 *   const tab = store.getState().activeTab;
 *   store.subscribe((state) => { ... });
 *   store.setState({ activeTab: 'home' });
 */
(function (global) {
  "use strict";

  const initialState = {
    /* S1-BUG1: 默认 Tab 改为 home，与 router 默认值保持一致 */
    activeTab: "home",
    selectedJobId: "",
    jobs: [],
    knowledgeModel: null,
    samples: [],
    providers: [],
    settings: null,
    loading: false,
    confirmModal: {
      visible: false,
      title: "",
      message: "",
      okText: "确认",
      cancelText: "取消",
      onOk: null,
      onCancel: null,
    },
  };

  function createStore(initial) {
    let state = Object.assign({}, initial);
    const listeners = new Set();

    return {
      getState() {
        return state;
      },
      setState(partial) {
        const next =
          typeof partial === "function" ? partial(state) : Object.assign({}, state, partial);
        if (next === state) return;
        const prev = state;
        state = next;
        listeners.forEach(function (fn) {
          try {
            fn(state, prev);
          } catch (e) {
            /* 单个 listener 异常不影响其他 */
            console.error("store listener error", e);
          }
        });
      },
      subscribe(fn) {
        listeners.add(fn);
        return function unsubscribe() {
          listeners.delete(fn);
        };
      },
    };
  }

  global.bdStore = createStore(initialState);
  global.bdCreateStore = createStore;
})(window);
