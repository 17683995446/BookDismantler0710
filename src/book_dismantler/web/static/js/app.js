/**
 * Book Dismantler 前端交互逻辑。
 *
 * 纯 vanilla JS（IIFE），通过 fetch() 与 FastAPI 后端通信。
 * 功能：标签切换、示例书籍、拖拽上传、任务创建、实时轮询、
 *       任务列表/操作、产物预览模态框、知识浏览器、设置、暗色模式、Toast。
 *
 * TODO(#138): 本文件中仍存在较多内联 style（如 job-actions / progress-bar /
 *   concept-meta 等），属于历史遗留的代码质量问题。后续应统一迁移到 CSS
 *   class（如 .btn-md / .btn-block / .job-meta 等工具类），减少 JS 中拼装
 *   内联样式，提升可维护性与主题一致性。本次仅做局部修复，未做大规模重构。
 */
(function () {
    "use strict";

    /* ===================== 常量 ===================== */
    var API_BASE = "/api";
    var POLL_INTERVAL = 3000;
    var THEME_KEY = "bd-theme";

    var TABS = [
        { id: "knowledge", label: "知识" },
        { id: "home", label: "首页" },
        { id: "jobs", label: "任务" },
        { id: "settings", label: "设置" }
    ];

    var PROVIDERS = [
        { value: "openai", label: "OpenAI" },
        { value: "deepseek", label: "DeepSeek" },
        { value: "gemini", label: "Gemini" },
        { value: "ollama", label: "Ollama" },
        { value: "siliconflow", label: "硅基流动" }
    ];

    /* D3: Provider 默认模型建议 */
    var PROVIDER_MODELS = {
        openai: "gpt-4o-mini",
        deepseek: "deepseek-chat",
        gemini: "gemini-1.5-flash",
        ollama: "llama3.1",
        siliconflow: "deepseek-ai/DeepSeek-V3"
    };

    /* D3: Provider 提示信息 */
    var PROVIDER_HINTS = {
        ollama: "需确保本地 Ollama 服务已启动（默认 http://localhost:11434）",
        openai: "API Key 以 sk- 开头",
        deepseek: "前往 platform.deepseek.com 获取 API Key",
        gemini: "前往 ai.google.dev 获取 API Key",
        siliconflow: "前往 siliconflow.cn 获取 API Key"
    };

    /* #114: 将 provider 原始值（如 "openai"）映射为友好名称（如 "OpenAI"）。
       PROVIDERS 数组以 value 字段作为键，未命中时回退为原始值。 */
    function providerLabel(key) {
        var p = PROVIDERS.find(function (x) { return x.value === key; });
        return p ? p.label : key;
    }

    /* ===================== 运行时状态 ===================== */
    var state = {
        activeTab: "home",  /* S1-BUG1: 默认 Tab 改为 home */
        currentBookId: null,
        currentBookTitle: "",
        currentJobId: null,
        polls: {},        // jobId -> intervalId
        jobsCache: [],
        lastKnowledge: null /* #118: 缓存最近一次加载的知识模型，避免写入巨大 DOM 属性 */
    };

    /* ===================== 模块别名（从 utils.js / api.js 引入） ===================== */
    var $ = window.BD_Utils.$;
    var on = window.BD_Utils.on;
    var showToast = window.BD_Utils.showToast;
    var formatSize = window.BD_Utils.formatSize;
    var statusText = window.BD_Utils.statusText;
    var statusClass = window.BD_Utils.statusClass;
    var escapeHtml = window.BD_Utils.escapeHtml;
    var escapeAttr = window.BD_Utils.escapeAttr;
    var formatTime = window.BD_Utils.formatTime;
    var formatDuration = window.BD_Utils.formatDuration;
    var fileIcon = window.BD_Utils.fileIcon;
    var debounce = window.BD_Utils.debounce; /* #116: 用于过滤输入防抖 */

    var apiGet = window.BD_API.get;
    var apiPost = window.BD_API.post;
    var apiPut = window.BD_API.put;
    var apiDelete = window.BD_API.delete;
    var API_BASE = window.BD_API.BASE;

    /* ===================== 布局：注入样式 / 导航 / 面板 / 模态框 ===================== */
    function ensureLayout() {
        /* ---- 导航：重建为 4 个标签（保留 ARIA tab 语义） ---- */
        var nav = document.querySelector(".header-nav");
        if (nav) {
            if (!nav.hasAttribute("role")) nav.setAttribute("role", "tablist");
            nav.innerHTML = TABS.map(function (t, i) {
                return '<a id="tablink-' + t.id + '" href="#" class="nav-link' + (i === 0 ? " active" : "") +
                    '" data-tab="' + t.id + '" role="tab" aria-selected="' + (i === 0 ? "true" : "false") +
                    '" aria-controls="tab-' + t.id + '">' + t.label + "</a>";
            }).join("");
        }

        /* ---- 主题切换按钮 ---- */
        var header = document.querySelector(".app-header");
        if (header && !$("theme-toggle")) {
            var btn = document.createElement("button");
            btn.id = "theme-toggle";
            btn.className = "theme-toggle";
            btn.type = "button";
            btn.innerHTML = '<span id="theme-icon">🌙</span><span id="theme-label">深色</span>';
            header.appendChild(btn);
        }

        var main = document.querySelector(".app-main") || document.body;

        /* ---- 首页面板：复用原上传面板 ---- */
        var uploadPanel = $("tab-upload");
        if (uploadPanel) uploadPanel.id = "tab-home";

        /* ---- 设置面板：复用原配置面板 ---- */
        var configPanel = $("tab-config");
        if (configPanel) configPanel.id = "tab-settings";

        /* ---- 知识面板：新建 ---- */
        if (!$("tab-knowledge")) {
            var k = document.createElement("section");
            k.id = "tab-knowledge";
            k.className = "tab-panel";
            k.innerHTML =
                '<div class="card">' +
                '<div class="card-header"><h2>知识浏览器</h2></div>' +
                '<p class="hint-text">选择一个已完成的拆书任务，自动浏览其知识模型。</p>' +
                '<div class="form-group">' +
                '<label for="knowledge-job-select">选择任务</label>' +
                '<select id="knowledge-job-select" class="form-control"><option value="">-- 请选择 --</option></select>' +
                "</div>" +
                '<button id="load-knowledge-btn" class="btn btn-secondary btn-sm" type="button">加载</button>' +
                "</div>" +
                '<div id="knowledge-content"></div>';
            main.appendChild(k);
        }

        /* ---- 设置表单：插入到设置面板顶部 ---- */
        var settingsPanel = $("tab-settings");
        if (settingsPanel && !$("settings-form-card")) {
            var formCard = document.createElement("div");
            formCard.id = "settings-form-card";
            formCard.className = "card";
            formCard.innerHTML =
                '<h2>运行时设置</h2>' +
                '<p class="hint-text">更新默认 Provider、模型与 API Key（运行时生效，不会写入 .env 文件）。</p>' +
                '<div class="form-group">' +
                '<label for="settings-provider">默认 Provider</label>' +
                '<select id="settings-provider" class="form-control">' +
                '<option value="">-- 使用默认 --</option>' +
                PROVIDERS.map(function (p) {
                    return '<option value="' + p.value + '">' + p.label + "</option>";
                }).join("") +
                "</select>" +
                /* D3: Provider 提示 */
                '<p class="form-hint" id="provider-hint" style="display:none;"></p>' +
                "</div>" +
                '<div class="form-group">' +
                '<label for="settings-apikey">API Key</label>' +
                '<p class="form-hint">将覆盖所选 Provider 的 Key，留空则使用默认</p>' +
                '<div class="input-with-toggle">' +
                '<input type="password" id="settings-apikey" class="form-control" placeholder="sk-..." autocomplete="off">' +
                '<button type="button" class="input-toggle-btn" id="apikey-toggle" aria-label="显示或隐藏 API Key" aria-pressed="false">👁</button>' +
                "</div>" +
                "</div>" +
                '<div class="form-group">' +
                '<label for="settings-model">默认模型</label>' +
                '<input type="text" id="settings-model" class="form-control" placeholder="如 gpt-4o-mini">' +
                "</div>" +
                '<button id="save-settings-btn" class="btn btn-primary settings-save-btn" type="button">保存设置</button>' +
                '<div id="settings-status" style="margin-top:12px;"></div>';
            settingsPanel.insertBefore(formCard, settingsPanel.firstChild);
        }

        /* ---- 产物预览模态框 ---- */
        if (!$("preview-modal")) {
            var modal = document.createElement("div");
            modal.id = "preview-modal";
            modal.className = "modal hidden";
            modal.innerHTML =
                '<div class="modal-overlay" id="modal-overlay"></div>' +
                '<div class="modal-content">' +
                '<div class="modal-header">' +
                '<h3 id="modal-title">预览</h3>' +
                '<div class="job-actions">' +
                '<a id="modal-download" class="btn btn-sm btn-secondary" href="#" download>下载</a>' +
                '<button id="modal-close" class="btn btn-sm btn-secondary" type="button">关闭</button>' +
                "</div></div>" +
                '<div id="modal-body" class="modal-body"></div>' +
                "</div>";
            document.body.appendChild(modal);
        }

        /* ---- Toast 兜底 ---- */
        if (!$("toast")) {
            var t = document.createElement("div");
            t.id = "toast";
            t.className = "toast hidden";
            document.body.appendChild(t);
        }
    }

    /* ===================== 标签切换 ===================== */
    function switchTab(tab) {
        /* S1-BUG6: 保存当前Tab滚动位置 */
        if (window.Router && typeof Router.saveScroll === "function") {
            Router.saveScroll(state.activeTab);
        }

        /* P0-12: 切换 tab 时关闭所有 Modal/抽屉，防止 body.overflow 泄漏 */
        if (typeof closeCreateJobModal === "function") closeCreateJobModal();
        if (typeof closeMobileMenu === "function") closeMobileMenu();
        /* 关闭预览/设置/确认 Modal */
        var modals = document.querySelectorAll(".modal-overlay:not(.hidden), .modal:not(.hidden)");
        modals.forEach(function (m) {
            m.classList.add("hidden");
            m.setAttribute("aria-hidden", "true");
        });
        document.body.style.overflow = "";

        state.activeTab = tab;
        document.querySelectorAll(".nav-link").forEach(function (l) {
            var isActive = l.dataset.tab === tab;
            l.classList.toggle("active", isActive);
            /* 同步 ARIA tab 选中状态 */
            if (l.hasAttribute("role")) {
                l.setAttribute("aria-selected", isActive ? "true" : "false");
            }
        });
        /* 同步底部导航栏 active 状态 */
        document.querySelectorAll(".bottom-nav-item").forEach(function (l) {
            l.classList.toggle("active", l.dataset.tab === tab);
        });
        document.querySelectorAll(".tab-panel").forEach(function (p) {
            p.classList.remove("active");
        });
        var panel = $("tab-" + tab);
        if (panel) panel.classList.add("active");

        if (tab === "jobs") loadJobs();
        if (tab === "knowledge") refreshKnowledgeJobs();
        /* settings 标签页由内联脚本（index.html）的 loadSettings 处理，
           避免重复 API 请求和 UI 冲突 */

        /* S1-BUG6: 恢复目标Tab滚动位置（使用requestAnimationFrame确保DOM已更新） */
        if (window.Router && typeof Router.restoreScroll === "function") {
            requestAnimationFrame(function () {
                Router.restoreScroll(tab);
            });
        }
    }

    /* ===================== B1: 移动端汉堡菜单抽屉 ===================== */
    function initMobileMenu() {
        var toggle = $("mobile-menu-toggle");
        var drawer = $("mobile-menu-drawer");
        if (!toggle || !drawer) return;

        /* F1: 移动端不再截断品牌名，使用 CSS 自适应字号 */

        on(toggle, "click", function (e) {
            e.preventDefault();
            if (drawer.classList.contains("is-open")) {
                closeMobileMenu();
            } else {
                openMobileMenu();
            }
        });

        /* 点击遮罩或关闭按钮关闭 */
        drawer.querySelectorAll("[data-close-mobile-menu]").forEach(function (el) {
            on(el, "click", closeMobileMenu);
        });

        /* 抽屉内的 tab 切换完成后自动关闭（沿用 document click 委托，此处仅监听关闭） */
        on(drawer, "click", function (e) {
            var link = e.target.closest("[data-tab]");
            if (link) {
                /* 切换激活态到抽屉内的对应项 */
                var links = drawer.querySelectorAll(".nav-link");
                for (var i = 0; i < links.length; i++) {
                    links[i].classList.remove("active");
                    links[i].setAttribute("aria-selected", "false");
                }
                link.classList.add("active");
                link.setAttribute("aria-selected", "true");
                /* 关闭抽屉 */
                setTimeout(closeMobileMenu, 120);
            }
        });

        /* 抽屉内搜索框：与 header 搜索框同步逻辑（此处仅占位，搜索功能由原 header-search 接管时该输入框为辅助） */
        var mobileSearch = $("mobile-search-input");
        if (mobileSearch) {
            on(mobileSearch, "input", function () {
                var mainSearch = $("header-search-input");
                if (mainSearch) {
                    mainSearch.value = mobileSearch.value;
                    mainSearch.dispatchEvent(new Event("input", { bubbles: true }));
                }
            });
        }
    }

    function openMobileMenu() {
        var drawer = $("mobile-menu-drawer");
        var toggle = $("mobile-menu-toggle");
        if (!drawer) return;
        drawer.removeAttribute("hidden");
        /* 强制 reflow 让 transition 生效 */
        void drawer.offsetWidth;
        drawer.classList.add("is-open");
        if (toggle) {
            toggle.setAttribute("aria-expanded", "true");
            toggle.setAttribute("aria-label", "关闭菜单");
        }
        /* 阻止 body 滚动 */
        document.body.style.overflow = "hidden";
    }

    function closeMobileMenu() {
        var drawer = $("mobile-menu-drawer");
        var toggle = $("mobile-menu-toggle");
        if (!drawer || !drawer.classList.contains("is-open")) return;
        drawer.classList.remove("is-open");
        if (toggle) {
            toggle.setAttribute("aria-expanded", "false");
            toggle.setAttribute("aria-label", "打开菜单");
        }
        document.body.style.overflow = "";
        /* 动画结束后再隐藏 */
        setTimeout(function () {
            if (drawer && !drawer.classList.contains("is-open")) {
                drawer.setAttribute("hidden", "");
            }
        }, 240);
    }

    /* ===================== E5: 任务页下拉刷新手势（移动端） ===================== */
    function initPullToRefresh() {
        var tabJobs = $("tab-jobs");
        if (!tabJobs) return;
        /* 仅在触屏设备启用 */
        if (!("ontouchstart" in window)) return;

        var startY = 0;
        var pulling = false;
        var threshold = 60; /* 下拉超过 60px 触发刷新 */
        var indicator = null;

        function ensureIndicator() {
            if (indicator) return indicator;
            indicator = document.createElement("div");
            indicator.className = "ptr-indicator";
            indicator.setAttribute("aria-hidden", "true");
            indicator.textContent = "↓ 下拉刷新";
            tabJobs.insertBefore(indicator, tabJobs.firstChild);
            return indicator;
        }

        on(tabJobs, "touchstart", function (e) {
            /* 仅当任务页可见且在顶部时启用 */
            if (state.activeTab !== "jobs") return;
            if (window.scrollY > 0 && document.documentElement.scrollTop > 0) return;
            if (e.touches.length !== 1) return;
            startY = e.touches[0].clientY;
            pulling = true;
        }, { passive: true });

        on(tabJobs, "touchmove", function (e) {
            if (!pulling) return;
            var dy = e.touches[0].clientY - startY;
            if (dy <= 0) {
                if (indicator) indicator.style.transform = "";
                return;
            }
            var ind = ensureIndicator();
            var distance = Math.min(dy * 0.5, threshold * 1.5);
            ind.style.transform = "translateY(" + distance + "px)";
            ind.style.opacity = String(Math.min(dy / threshold, 1));
            ind.textContent = dy >= threshold ? "↑ 释放刷新" : "↓ 下拉刷新";
        }, { passive: true });

        on(tabJobs, "touchend", function () {
            if (!pulling) return;
            pulling = false;
            var ind = indicator;
            if (!ind) return;
            var reached = parseFloat(ind.style.opacity || "0") >= 1;
            ind.style.transform = "";
            ind.style.opacity = "0";
            if (reached) {
                ind.textContent = "⟳ 刷新中…";
                ind.style.opacity = "1";
                var btn = $("refresh-jobs-btn");
                if (btn) btn.disabled = true;
                loadJobs().finally(function () {
                    if (btn) btn.disabled = false;
                    setTimeout(function () { ind.style.opacity = "0"; }, 400);
                });
            }
        }, { passive: true });
    }

    /* ===================== E6: 触摸反馈涟漪 ===================== */
    function initRipple() {
        if (!("ontouchstart" in window) && !window.matchMedia("(pointer: coarse)").matches) return;
        on(document, "pointerdown", function (e) {
            var target = e.target.closest(".btn, .sample-book-card, .job-item, .km-subtab, .nav-link");
            if (!target) return;
            var rect = target.getBoundingClientRect();
            var ripple = document.createElement("span");
            ripple.className = "ripple";
            var size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + "px";
            ripple.style.left = (e.clientX - rect.left - size / 2) + "px";
            ripple.style.top = (e.clientY - rect.top - size / 2) + "px";
            /* 防止 ripple 溢出 */
            var prevPos = getComputedStyle(target).position;
            if (prevPos === "static") target.style.position = "relative";
            var prevOverflow = getComputedStyle(target).overflow;
            if (prevOverflow === "visible") target.style.overflow = "hidden";
            target.appendChild(ripple);
            setTimeout(function () {
                if (ripple.parentNode) ripple.parentNode.removeChild(ripple);
            }, 600);
        }, { passive: true });
    }

    /* ===================== 暗色模式 ===================== */
    function initTheme() {
        /* 优先使用已保存的主题；无保存时保持 HTML 内联脚本设置的 data-theme（已处理 prefers-color-scheme） */
        var saved = null;
        try { saved = localStorage.getItem(THEME_KEY); } catch (e) {}
        if (saved === "dark" || saved === "light") {
            applyTheme(saved);
        } else {
            /* 无保存主题，同步当前 data-theme 属性到 applyTheme 的副作用 */
            var cur = document.documentElement.getAttribute("data-theme") || "light";
            applyTheme(cur);
        }
        on($("theme-toggle"), "click", toggleTheme);
        /* E3: 未手动设置主题时跟随系统 prefers-color-scheme 变化 */
        if (window.matchMedia && !saved) {
            try {
                window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
                    var curSaved = null;
                    try { curSaved = localStorage.getItem(THEME_KEY); } catch (e2) {}
                    if (!curSaved) applyTheme(e.matches ? "dark" : "light");
                });
            } catch (e3) {}
        }
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        /* HTML 使用 .theme-icon-moon / .theme-icon-sun 双图标，由 CSS 控制显隐；
           此处仅做兼容性更新（若存在 app.js 回退创建的 #theme-icon/#theme-label） */
        var icon = $("theme-icon");
        var label = $("theme-label");
        if (theme === "dark") {
            if (icon) icon.textContent = "☀️";
            if (label) label.textContent = "浅色";
        } else {
            if (icon) icon.textContent = "🌙";
            if (label) label.textContent = "深色";
        }
    }

    function toggleTheme() {
        var cur = document.documentElement.getAttribute("data-theme") || "light";
        var next = cur === "dark" ? "light" : "dark";
        applyTheme(next);
        try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
    }

    /* ===================== 通用确认对话框 ===================== */
    /* 替代原生 confirm()，提供移动端友好的模态确认体验 */
    var confirmResolve_ = null;
    function showConfirmDialog(message, opts) {
        opts = opts || {};
        var modal = $("confirm-modal");
        var msgEl = $("confirm-modal-message");
        var okBtn = $("confirm-modal-ok");
        var cancelBtn = $("confirm-modal-cancel");
        var titleEl = $("confirm-modal-title");
        if (!modal || !msgEl || !okBtn || !cancelBtn) {
            /* 降级：组件不存在时回退到原生 confirm */
            return Promise.resolve(confirm(message));
        }
        if (titleEl && opts.title) titleEl.textContent = opts.title;
        msgEl.textContent = message;
        okBtn.textContent = opts.okText || "确认删除";
        /* #131: 用 .btn-md 工具类统一中等尺寸，替代内联样式 */
        okBtn.className = "btn btn-md " + (opts.okClass || "btn-danger");
        cancelBtn.className = "btn btn-md btn-secondary";

        modal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
        /* #90: 打开确认对话框时启用焦点陷阱 */
        trapFocus(modal);

        return new Promise(function (resolve) {
            confirmResolve_ = resolve;
            /* 先移除旧监听再绑定，防止重复 */
            okBtn.onclick = function () {
                closeModal_();
                resolve(true);
            };
            cancelBtn.onclick = function () {
                closeModal_();
                resolve(false);
            };
        });
    }
    function closeModal_() {
        var modal = $("confirm-modal");
        if (modal) modal.classList.add("hidden");
        document.body.style.overflow = "";
        /* #90: 关闭确认对话框时释放焦点陷阱并恢复焦点 */
        releaseFocusTrap();
        confirmResolve_ = null;
    }

    /* ===================== 示例书籍 ===================== */
    /**
     * D6: 根据书名关键词分类，用于差异化色标。
     * 规则：技术关键词→tech、生活/烹饪→life、学习/工作→study。
     */
    function classifyBook(title) {
        var t = (title || "").toLowerCase();
        /* 注意：先匹配 learning 再匹配 tech，避免"深度工作"被错分到 tech */
        var lifeKw = ["烹饪", "美食", "生活", "艺术", "旅行", "文学", "情感", "人际", "恋爱", "心理"];
        var learningKw = ["工作", "学习", "方法", "思维", "认知", "专注", "效率", "成长", "刻意", "练习", "自我"];
        var techKw = ["ai", "人工智能", "智能", "编程", "代码", "数据", "算法", "机器", "网络", "系统", "技术"];
        if (lifeKw.some(function (k) { return t.indexOf(k) !== -1; })) return "life";
        if (learningKw.some(function (k) { return t.indexOf(k) !== -1; })) return "learning";
        if (techKw.some(function (k) { return t.indexOf(k) !== -1; })) return "tech";
        return "default";
    }

    async function loadSamples() {
        var list = $("sample-books-list");
        if (!list) return;
        list.innerHTML = '<p class="placeholder-text">加载中...</p>';
        try {
            var data = await apiGet("/books/samples");
            renderSamples((data && data.samples) || []);
        } catch (err) {
            list.innerHTML = '<p class="placeholder-text">加载示例书籍失败</p>';
            showToast(err.message, "error");
        }
    }

    function renderSamples(samples) {
        var list = $("sample-books-list");
        if (!samples.length) {
            list.innerHTML = '<p class="placeholder-text">暂无示例书籍</p>';
            return;
        }
        list.innerHTML = samples.map(function (book) {
            var title = (book.filename || "").replace(/\.[^.]+$/, "");
            var icon = '<svg width="32" height="32" viewBox="0 0 24 24" fill="none"><path d="M6 2h8l4 4v16a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5"/><path d="M14 2v4h4" stroke="currentColor" stroke-width="1.5"/><path d="M8 12h8M8 16h6" stroke="currentColor" stroke-width="1.5"/></svg>';
            /* D6: 分类色标（科技/生活/学习） */
            var cat = classifyBook(title);
            /* E4: 分类辅助 icon（色盲用户可区分）：科技=芯片，学习=书本，生活=餐叉 */
            var catIcon = "";
            if (cat === "tech") {
                /* D5: 简化芯片图标为 2 条电路线条，提升小尺寸识别度 */
                catIcon = '<svg class="cat-aux-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-label="科技类"><rect x="7" y="7" width="10" height="10" rx="1" stroke="currentColor" stroke-width="2"/><path d="M10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
            } else if (cat === "learning") {
                catIcon = '<svg class="cat-aux-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-label="学习类"><path d="M4 4h6a3 3 0 013 3v13a2 2 0 00-2-2H4z" stroke="currentColor" stroke-width="2"/><path d="M20 4h-6a3 3 0 00-3 3v13a2 2 0 012-2h7z" stroke="currentColor" stroke-width="2"/></svg>';
            } else {
                catIcon = '<svg class="cat-aux-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-label="生活类"><path d="M6 3v8a3 3 0 003 3v7M9 3v3M12 3v8a3 3 0 003 3v7M15 3c2 0 3 2 3 5s-1 5-3 5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
            }
            return '<div class="sample-book-card" data-book-id="' + escapeAttr(title) + '" data-book-title="' + escapeAttr(title) + '" role="button" tabindex="0">' +
                '<span class="sample-book-icon sample-book-icon--' + cat + '">' + icon + "</span>" +
                '<div class="sample-book-info">' +
                '<span class="sample-book-title">' + escapeHtml(title) + ' <span class="cat-aux">' + catIcon + "</span></span>" +
                '<span class="sample-book-meta">' + (book.format || "").toUpperCase() + "</span>" +
                "</div></div>";
        }).join("");
        list.querySelectorAll(".sample-book-card").forEach(function (card) {
            on(card, "click", function () {
                selectBook(card.dataset.bookId, card.dataset.bookTitle);
            });
            on(card, "keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    selectBook(card.dataset.bookId, card.dataset.bookTitle);
                }
            });
        });
    }

    /* ===================== 文件上传 ===================== */
    function setupUpload() {
        var dropZone = $("drop-zone");
        var fileInput = $("file-input");
        var browseBtn = $("browse-btn");

        on(browseBtn, "click", function (e) {
            e.stopPropagation();
            if (fileInput) fileInput.click();
        });
        on(dropZone, "click", function () {
            if (fileInput) fileInput.click();
        });
        on(fileInput, "change", function () {
            if (fileInput.files && fileInput.files.length) uploadFile(fileInput.files[0]);
            fileInput.value = "";
        });
        on(dropZone, "dragover", function (e) {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
        on(dropZone, "dragleave", function () {
            dropZone.classList.remove("dragover");
        });
        on(dropZone, "drop", function (e) {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files.length) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });
    }

    async function uploadFile(file) {
        /* 防止重复上传 */
        if (state.uploading) return;
        var validExts = [".pdf", ".epub"];
        var dot = file.name.lastIndexOf(".");
        var ext = dot >= 0 ? file.name.substring(dot).toLowerCase() : "";
        if (validExts.indexOf(ext) < 0) {
            showToast("仅支持 PDF / EPUB 格式", "error");
            return;
        }
        /* 客户端文件大小校验（50MB） */
        if (file.size > 50 * 1024 * 1024) {
            showToast("文件超过 50MB 限制", "error");
            return;
        }
        state.uploading = true;
        var formData = new FormData();
        formData.append("file", file);
        showToast("正在上传 " + file.name + "...", "info");
        try {
            var data = await apiPost("/books/upload", formData, true);
            var resultDiv = $("upload-result");
            if (resultDiv && data) {
                resultDiv.innerHTML =
                    '<div class="book-id">Book ID: ' + escapeHtml(data.book_id || "") + "</div>" +
                    "<div>" + escapeHtml(data.filename || file.name) + " (" + formatSize(data.size || file.size) + ")</div>";
                resultDiv.classList.remove("hidden");
            }
            selectBook(data && data.book_id, (data && data.filename) || file.name);
            showToast("上传成功", "success");
        } catch (err) {
            showToast(err.message, "error");
        } finally {
            state.uploading = false;
        }
    }

    /* ===================== 创建任务 ===================== */
    function selectBook(bookId, title) {
        state.currentBookId = bookId;
        state.currentBookTitle = title || bookId;
        var overlay = $("create-job-overlay");
        var section = $("create-job-section");
        if (overlay && section) {
            overlay.classList.remove("hidden");
            overlay.setAttribute("aria-hidden", "false");
            section.classList.remove("hidden");
            document.body.style.overflow = "hidden";
            var info = $("selected-book-info");
            if (!info) {
                info = document.createElement("div");
                info.id = "selected-book-info";
                info.style.cssText = "margin-bottom:12px;padding:10px 12px;background:rgba(255,36,66,.06);border-radius:8px;font-size:.85rem;";
                section.insertBefore(info, section.firstChild);
            }
            info.innerHTML = '已选择书籍：<strong>' + escapeHtml(state.currentBookTitle) + "</strong>";
            section.scrollIntoView({ behavior: "smooth", block: "center" });
            /* #90: 打开创建任务模态时启用焦点陷阱 */
            trapFocus(section);
        }
        showToast("已选择: " + (title || bookId), "info");
    }

    /* B2: 关闭创建任务模态 */
    function closeCreateJobModal() {
        var overlay = $("create-job-overlay");
        var section = $("create-job-section");
        if (overlay && section) {
            section.classList.add("hidden");
            overlay.classList.add("hidden");
            overlay.setAttribute("aria-hidden", "true");
            document.body.style.overflow = "";
            /* #90: 关闭创建任务模态时释放焦点陷阱并恢复焦点 */
            releaseFocusTrap();
        }
    }

    function setupCreateJob() {
        on($("create-job-btn"), "click", createJob);
        /* B2: 关闭按钮 + 遮罩点击关闭 */
        on($("create-job-close"), "click", closeCreateJobModal);
        var overlay = $("create-job-overlay");
        if (overlay) {
            on(overlay, "click", function (e) {
                if (e.target === overlay) closeCreateJobModal();
            });
        }
    }

    async function createJob() {
        if (!state.currentBookId) {
            showToast("请先选择或上传书籍", "error");
            return;
        }
        var provider = ($("provider-select") && $("provider-select").value) || null;
        var model = ($("model-input") && $("model-input").value.trim()) || null;
        var body = { book_id: state.currentBookId };
        if (provider) body.provider = provider;
        if (model) body.model = model;

        var btn = $("create-job-btn");
        /* #129: 保留原始文案，仅用 .btn-loading 的 spinner 作为视觉反馈 */
        var btnOriginalText = btn ? btn.textContent : "";
        if (btn) { btn.disabled = true; btn.textContent = ""; btn.classList.add("btn-loading"); }
        showToast("正在创建任务...", "info");
        try {
            var data = await apiPost("/jobs/create", body);
            showToast("任务已创建: " + (data.book_title || data.job_id), "success");
            state.currentBookId = null;
            state.currentBookTitle = "";
            if (btn) { btn.disabled = false; btn.textContent = btnOriginalText; btn.classList.remove("btn-loading"); }
            /* #106: 创建成功后重置 Provider 与模型选择 */
            if ($("provider-select")) $("provider-select").value = "";
            if ($("model-input")) $("model-input").value = "";
            closeCreateJobModal();
            /* B1: 传递新任务 ID 供 loadJobs 高亮 */
            state.newJobId = data.job_id;
            /* #120: 通过路由导航，使浏览器后退按钮可在标签间切换 */
            if (window.Router) Router.navigate("jobs"); else switchTab("jobs");
            startPolling(data.job_id);
        } catch (err) {
            if (btn) { btn.disabled = false; btn.textContent = btnOriginalText; btn.classList.remove("btn-loading"); }
            showToast(err.message, "error");
        }
    }

    /* ===================== 任务列表 ===================== */
    var jobsReqId = 0; /* #103: 请求令牌，防止竞态 */

    async function loadJobs() {
        var list = $("jobs-list");
        if (!list) return;
        var myReqId = ++jobsReqId; /* 记录本次请求序号 */
        /* 显示 loading 状态，避免空状态闪烁 */
        list.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><p>正在加载任务列表…</p></div>';
        try {
            var data = await apiGet("/jobs/");
            /* 若已发起新请求，丢弃本次过期响应 */
            if (myReqId !== jobsReqId) return;
            var jobs = (data && data.jobs) || [];
            state.jobsCache = jobs;
            renderJobs(jobs);
            jobs.forEach(function (j) {
                if (j.status === "pending" || j.status === "running") startPolling(j.job_id);
            });
        } catch (err) {
            if (myReqId !== jobsReqId) return;
            /* #110: 用事件处理器替代内联 onclick，避免整页刷新 */
            list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><p class="empty-state-title">加载失败</p><p class="empty-state-desc">' + escapeHtml(err.message) + '</p><button class="btn btn-sm btn-primary" id="retry-jobs-btn">重新加载</button></div>';
            var retryBtn = $("retry-jobs-btn");
            if (retryBtn) on(retryBtn, "click", function () { loadJobs(); });
            showToast(err.message, "error");
        }
    }

    function renderJobs(jobs) {
        var list = $("jobs-list");
        if (!jobs.length) {
            list.innerHTML = '<div class="empty-state"><div class="empty-state-icon"><svg width="48" height="48" viewBox="0 0 24 24" fill="none"><path d="M6 2h8l4 4v16a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5" opacity="0.4"/><path d="M14 2v4h4M8 12h8M8 16h6" stroke="currentColor" stroke-width="1.5" opacity="0.4"/></svg></div><p class="empty-state-title">还没有拆书任务</p><p class="empty-state-desc">上传一本电子书或点击示例书籍，即可开始拆解</p><a href="#" class="btn btn-sm btn-primary" data-tab="home">去首页开始</a></div>';
            return;
        }
        list.innerHTML = jobs.map(jobItemHtml).join("");
        list.querySelectorAll(".job-item").forEach(bindJobItem);
        /* B1: 新创建任务卡片高亮 2 秒 */
        if (state.newJobId) {
            var newCard = list.querySelector('.job-item[data-job-id="' + state.newJobId + '"]');
            if (newCard) {
                newCard.classList.add("job-new-highlight");
                newCard.scrollIntoView({ behavior: "smooth", block: "center" });
                setTimeout(function () { newCard.classList.remove("job-new-highlight"); }, 2500);
            }
            state.newJobId = null;
        }
    }

    function jobItemHtml(job) {
        var title = job.book_title || job.book_filename || job.job_id;
        var progressVal = Number(job.progress);
        if (isNaN(progressVal)) progressVal = 0;
        var progress = Math.max(0, Math.min(100, progressVal));
        var fillClass = job.status === "done" ? "done"
            : job.status === "failed" ? "failed"
            : job.status === "cancelled" ? "cancelled" : "";

        var parts = [];
        /* B5: "reconciled" 是内部状态不是 provider，不显示在元信息 */
        if (job.provider && job.provider !== "reconciled") {
            parts.push('<span class="job-meta-tag">' + escapeHtml(providerLabel(job.provider)) + '</span>');
        }
        /* P2-7: 添加创建时间 */
        var timeStr = job.finished_at || job.started_at;
        if (timeStr) {
            parts.push('<span class="job-meta-tag">📅 ' + formatTime(timeStr) + '</span>');
        }
        /* B6: duration=0 显示"示例数据"而非"0.0秒" */
        if (job.duration_seconds != null && job.duration_seconds > 0) {
            parts.push('<span class="job-meta-tag">⏱ ' + formatDuration(job.duration_seconds) + '</span>');
        } else if (job.duration_seconds === 0) {
            parts.push('<span class="job-meta-tag job-meta-empty">📋 示例</span>');
        }
        var artifactCount = job.artifact_count || 0;
        /* D4: 0 产物添加 job-meta-empty 类降低视觉权重 */
        var artifactClass = artifactCount === 0 ? " job-meta-empty" : "";
        parts.push('<span class="job-meta-tag' + artifactClass + '">📦 ' + artifactCount + ' 项产物</span>');
        var meta = parts.join('');

        /* P0-2/P0-3: 列表卡片不再内嵌按钮，整卡可点击进入详情，删除在详情页操作 */
        return '<div class="job-item" data-job-id="' + escapeAttr(job.job_id) + '" role="button" tabindex="0" aria-label="' + escapeAttr(title) + '，点击查看详情">' +
            '<div class="job-top">' +
            '<div class="job-info" style="flex:1;min-width:0;">' +
            /* C1: 状态徽章移至标题右侧 */
            '<div class="job-title-row">' +
            '<span class="job-title">' + escapeHtml(title) + "</span>" +
            '<span class="status-badge ' + statusClass(job.status) + '">' + statusText(job.status) + "</span>" +
            "</div>" +
            '<span class="job-meta">' + meta + "</span>" +
            /* D3: 已完成/失败/取消状态隐藏进度条和 current_step */
            (job.status === "done" || job.status === "failed" || job.status === "cancelled"
                ? ""
                : '<div class="progress-bar"><div class="progress-fill ' + fillClass + '" style="width:' + progress + '%"></div></div>' +
                  (job.current_step ? '<span class="job-step">' + escapeHtml(job.current_step) + "</span>" : "")) +
            "</div>" +
            /* P0-2: 右侧仅保留箭头指示可点击 */
            '<span class="job-chevron" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M9 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' +
            "</div></div>";
    }

    function bindJobItem(item) {
        on(item, "click", function (e) {
            /* P0-2: 整卡可点击进入详情 */
            showJobDetail(item.dataset.jobId);
        });
        on(item, "keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                showJobDetail(item.dataset.jobId);
            }
        });
        item.querySelectorAll("[data-action]").forEach(function (btn) {
            on(btn, "click", function (e) {
                e.stopPropagation();
                var action = btn.dataset.action;
                var jid = btn.dataset.jobId;
                if (action === "cancel") cancelJob(jid);
                else if (action === "delete") deleteJob(jid);
                else if (action === "view") {
                    showJobDetail(jid);
                }
            });
        });
    }

    function updateJobCard(job) {
        var card = document.querySelector('.job-item[data-job-id="' + CSS.escape(job.job_id) + '"]');
        if (!card) return;

        var progressVal = Number(job.progress);
        if (isNaN(progressVal)) progressVal = 0;
        var progress = Math.max(0, Math.min(100, progressVal));
        var fillClass = job.status === "done" ? "done"
            : job.status === "failed" ? "failed"
            : job.status === "cancelled" ? "cancelled" : "";

        // 差量更新：仅更新动态部分，避免整卡重建导致闪烁
        var fill = card.querySelector(".progress-fill");
        if (fill) {
            fill.style.width = progress + "%";
            fill.className = "progress-fill " + fillClass;
        }

        var badge = card.querySelector(".status-badge");
        if (badge) {
            badge.textContent = statusText(job.status);
            badge.className = "status-badge " + statusClass(job.status);
        }

        var step = card.querySelector(".job-step");
        if (job.current_step) {
            if (step) {
                step.textContent = job.current_step;
            } else {
                var info = card.querySelector(".job-info");
                if (info) {
                    var s = document.createElement("span");
                    s.className = "job-step";
                    s.textContent = job.current_step;
                    info.appendChild(s);
                }
            }
        } else if (step) {
            step.remove();
        }

        // 状态变更时更新操作按钮
        var actionsDiv = card.querySelector(".job-actions");
        if (actionsDiv && (job.status === "done" || job.status === "failed" || job.status === "cancelled")) {
            var cancelBtn = actionsDiv.querySelector('[data-action="cancel"]');
            if (cancelBtn) {
                cancelBtn.dataset.action = "delete";
                cancelBtn.textContent = "删除";
            }
        }
    }

    /* ===================== 任务详情 / 操作 ===================== */
    var detailReqId = 0; /* 请求令牌，防止竞态 */

    async function showJobDetail(jobId) {
        state.currentJobId = jobId;
        var myReqId = ++detailReqId; /* 记录本次请求序号 */
        var section = $("job-detail-section");
        var content = $("job-detail-content");
        if (!section || !content) return;
        content.innerHTML = '<p class="placeholder-text">加载中...</p>';
        section.classList.remove("hidden");
        try {
            var job = await apiGet("/jobs/" + jobId);
            /* 若用户已切换到其他任务，丢弃本次过期响应 */
            if (myReqId !== detailReqId) return;
            renderJobDetail(job);
            var artDiv = $("artifacts-list");
            if (job.status === "done") {
                loadArtifacts(jobId);
            } else if (artDiv) {
                artDiv.innerHTML = '<p class="placeholder-text">任务尚未完成</p>';
            }
            if (job.status === "pending" || job.status === "running") startPolling(jobId);
            section.scrollIntoView({ behavior: "smooth" });
        } catch (err) {
            if (myReqId !== detailReqId) return;
            content.innerHTML = '<p class="placeholder-text">加载详情失败: ' + escapeHtml(err.message) + "</p>";
        }
    }

    /* 拆书阶段定义 */
    var PIPELINE_STEPS = [
        { key: "parse", label: "解析文档", threshold: 0 },
        { key: "outline", label: "提取大纲", threshold: 10 },
        { key: "concepts", label: "抽取概念", threshold: 25 },
        { key: "relationships", label: "挖掘关系", threshold: 45 },
        { key: "anatomy", label: "概念解剖", threshold: 60 },
        { key: "render", label: "渲染产物", threshold: 75 },
        { key: "bundle", label: "打包完成", threshold: 90 }
    ];

    function renderProgressTimeline(progress, currentStep, status) {
        /* 已完成的终态 */
        if (status === "done" || progress >= 100) {
            var doneHtml = '<div class="step-timeline">';
            PIPELINE_STEPS.forEach(function (s, idx) {
                doneHtml += '<div class="step-item done"><span class="step-num">' + (idx + 1) + '</span><span class="step-check">✓</span><span class="step-label">' + s.label + "</span></div>";
            });
            doneHtml += "</div>";
            return doneHtml;
        }

        /* 失败/取消 */
        if (status === "failed" || status === "cancelled") {
            var failHtml = '<div class="step-timeline">';
            PIPELINE_STEPS.forEach(function (s, idx) {
                var isActive = currentStep && currentStep.indexOf(s.label) >= 0;
                var cls = isActive ? "active failed" : (progress >= s.threshold ? "done" : "pending");
                var icon = cls.indexOf("done") >= 0 ? "✓" : (isActive ? "✕" : "○");
                failHtml += '<div class="step-item ' + cls + '"><span class="step-num">' + (idx + 1) + '</span><span class="step-check">' + icon + "</span><span class=\"step-label\">" + s.label + "</span></div>";
            });
            failHtml += "</div>";
            return failHtml;
        }

        /* 运行中：根据进度推断当前阶段 */
        var html = '<div class="step-timeline">';
        PIPELINE_STEPS.forEach(function (s, idx) {
            var isCurrent = false;
            /* 优先用 current_step 文本匹配 */
            if (currentStep) {
                isCurrent = currentStep.indexOf(s.label) >= 0 || currentStep.indexOf(s.key) >= 0;
            }
            /* 回退：用进度区间推断 */
            if (!isCurrent) {
                var nextStep = null;
                for (var i = 0; i < PIPELINE_STEPS.length; i++) {
                    if (progress < PIPELINE_STEPS[i].threshold) { nextStep = PIPELINE_STEPS[i]; break; }
                }
                if (nextStep && nextStep.key === s.key) isCurrent = true;
            }

            var isDone = progress >= s.threshold && !isCurrent;
            var cls = isDone ? "done" : (isCurrent ? "active" : "pending");
            var icon = isDone ? "✓" : (isCurrent ? "●" : "○");
            html += '<div class="step-item ' + cls + '"><span class="step-num">' + (idx + 1) + '</span><span class="step-check">' + icon + "</span><span class=\"step-label\">" + s.label + "</span></div>";
        });
        html += "</div>";
        return html;
    }

    function renderJobDetail(job) {
        var content = $("job-detail-content");
        if (!content) return;
        if ($("job-detail-title")) $("job-detail-title").textContent = job.book_title || job.book_filename || job.job_id;

        /* #115: 轮询每 3s 重建 HTML 会折叠已展开的 <details>。
           重建前按 summary 文本记录展开状态，重建后再恢复。 */
        var detailsOpen = {};
        content.querySelectorAll("details").forEach(function (d) {
            var sum = d.querySelector("summary");
            var key = sum ? sum.textContent.trim() : "";
            if (key) detailsOpen[key] = d.hasAttribute("open") || d.open;
        });

        var progress = Math.max(0, Math.min(100, job.progress || 0));
        var fillClass = job.status === "done" ? "done"
            : job.status === "failed" ? "failed"
            : job.status === "cancelled" ? "cancelled" : "";

        /* C3: 统计卡片改为紧凑状态条 */
        var html = '<div class="job-status-bar">';
        html += '<span class="status-badge ' + statusClass(job.status) + '">' + statusText(job.status) + "</span>";
        html += '<span class="job-status-sep">·</span>';
        html += '<span class="job-status-item">📦 ' + (job.artifact_count || 0) + ' 项产物</span>';
        if (job.stats && job.stats.concept_count != null) {
            html += '<span class="job-status-sep">·</span>';
            html += '<span class="job-status-item">🧠 ' + job.stats.concept_count + ' 个概念</span>';
        }
        if (job.stats && job.stats.relationship_count != null) {
            html += '<span class="job-status-sep">·</span>';
            html += '<span class="job-status-item">🔗 ' + job.stats.relationship_count + ' 条关系</span>';
        }
        html += "</div>";

        /* C3: 操作按钮行优先展示 */
        html += '<div class="job-actions" style="margin:10px 0;">';
        if (job.status === "pending" || job.status === "running") {
            html += '<button class="btn btn-sm btn-secondary" data-action="cancel" data-job-id="' + job.job_id + '">取消任务</button>';
            /* 进度条 */
            html += '<div class="progress-bar" style="flex:1;margin:0 8px;"><div class="progress-fill ' + fillClass + '" style="width:' + progress + '%"></div></div>';
        }
        if (job.status === "done") {
            html += '<button class="btn btn-sm btn-primary" id="view-knowledge-btn" data-job-id="' + job.job_id + '">查看知识模型</button>';
        }
        /* B4: 删除按钮弱化为 ghost-icon，移至右侧 */
        html += '<button class="btn btn-sm btn-ghost job-delete-btn" data-action="delete" data-job-id="' + job.job_id + '" aria-label="删除任务"><svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>';
        html += "</div>";

        /* C3: 折叠面板移至操作按钮下方 */
        if (job.status === "running" || job.status === "pending") {
            html += '<div class="progress-percent">' + Math.round(progress) + '%</div>';
            html += renderProgressTimeline(progress, job.current_step, job.status);
        } else if (job.current_step) {
            html += '<details class="job-meta-details"><summary>处理步骤</summary>';
            html += renderProgressTimeline(progress, job.current_step, job.status);
            html += '</details>';
        }

        /* 技术元信息折叠 */
        var metaParts = [];
        if (job.provider && job.provider !== "reconciled") metaParts.push("Provider: " + escapeHtml(job.provider));
        if (job.model) metaParts.push("模型: " + escapeHtml(job.model));
        if (job.started_at) metaParts.push("开始: " + formatTime(job.started_at));
        if (job.finished_at) metaParts.push("结束: " + formatTime(job.finished_at));
        if (job.duration_seconds != null && job.duration_seconds > 0) metaParts.push("耗时: " + formatDuration(job.duration_seconds));
        if (metaParts.length) {
            html += '<details class="job-meta-details"><summary>技术信息</summary><div class="job-meta" style="margin:8px 0;">' + metaParts.join(" · ") + "</div></details>";
        }

        if (job.error) {
            html += '<div class="job-error-box">错误: ' + escapeHtml(job.error) + "</div>";
        }

        content.innerHTML = html;

        /* #115: 恢复 <details> 展开状态（按 summary 文本匹配） */
        content.querySelectorAll("details").forEach(function (d) {
            var sum = d.querySelector("summary");
            var key = sum ? sum.textContent.trim() : "";
            if (key && detailsOpen[key]) {
                d.setAttribute("open", "");
                d.open = true;
            }
        });

        content.querySelectorAll("[data-action]").forEach(function (btn) {
            on(btn, "click", function () {
                var action = btn.dataset.action;
                var jid = btn.dataset.jobId;
                if (action === "cancel") cancelJob(jid);
                else if (action === "delete") deleteJob(jid);
            });
        });
        on($("view-knowledge-btn"), "click", function () {
            openKnowledgeForJob(job.job_id);
        });
    }

    async function cancelJob(jobId) {
        var ok = await showConfirmDialog("确定取消该任务？", { okText: "确认取消", okClass: "btn-warning" });
        if (!ok) return;
        try {
            await apiPost("/jobs/" + jobId + "/cancel", {});
            showToast("已发送取消请求", "info");
            startPolling(jobId); // 继续轮询直到状态变为 cancelled
            /* #104: 等待后端处理取消请求后再刷新列表与详情，避免读到旧状态 */
            setTimeout(function () {
                loadJobs();
                if (state.currentJobId === jobId) showJobDetail(jobId);
            }, 500);
        } catch (err) {
            showToast(err.message, "error");
        }
    }

    async function deleteJob(jobId) {
        var ok = await showConfirmDialog("确定删除该任务记录？删除后无法恢复。");
        if (!ok) return;
        try {
            await apiDelete("/jobs/" + jobId);
            showToast("已删除任务", "success");
            stopPolling(jobId);
            if (state.currentJobId === jobId) {
                var sec = $("job-detail-section");
                if (sec) sec.classList.add("hidden");
                state.currentJobId = null;
            }
            await loadJobs();
            /* 全部任务删除后隐藏详情面板 */
            if (state.jobsCache.length === 0) {
                var sec2 = $("job-detail-section");
                if (sec2) sec2.classList.add("hidden");
                state.currentJobId = null;
            }
        } catch (err) {
            showToast(err.message, "error");
        }
    }

    /* ===================== 实时轮询 ===================== */
    var POLL_MAX_ERRORS = 10; /* 连续失败上限 */
    var pollErrors = {}; /* pollErrors[jobId] = 连续失败次数 */

    function startPolling(jobId) {
        if (!jobId || state.polls[jobId]) return;
        pollErrors[jobId] = 0;
        var timer = setInterval(function () { pollOnce(jobId); }, POLL_INTERVAL);
        state.polls[jobId] = timer;
        pollOnce(jobId); // 立即执行一次
    }

    function stopPolling(jobId) {
        if (state.polls[jobId]) {
            clearInterval(state.polls[jobId]);
            delete state.polls[jobId];
        }
        delete pollErrors[jobId];
    }

    async function pollOnce(jobId) {
        try {
            var job = await apiGet("/jobs/" + jobId);
            if (!job || typeof job !== "object") return;
            pollErrors[jobId] = 0; /* 成功时重置错误计数 */

            updateJobCard(job);

            var detailOpen = state.currentJobId === jobId
                && $("job-detail-section")
                && !$("job-detail-section").classList.contains("hidden");
            if (detailOpen) renderJobDetail(job);

            var terminal = job.status === "done" || job.status === "failed" || job.status === "cancelled";
            if (terminal) {
                stopPolling(jobId);
                if (job.status === "done") {
                    showToast("拆书完成！共 " + (job.artifact_count || 0) + " 个产物", "success");
                    if (detailOpen) loadArtifacts(jobId);
                } else if (job.status === "failed") {
                    showToast("任务失败: " + (job.error || "未知错误"), "error");
                } else {
                    showToast("任务已取消", "info");
                }
                loadJobs();
            }
        } catch (err) {
            /* 连续失败超过上限时停止轮询，避免无限重试 */
            pollErrors[jobId] = (pollErrors[jobId] || 0) + 1;
            if (pollErrors[jobId] >= POLL_MAX_ERRORS) {
                stopPolling(jobId);
                showToast("任务状态更新失败，请刷新重试", "error");
            }
        }
    }

    /* ===================== 产物列表 / 预览 ===================== */
    async function loadArtifacts(jobId) {
        var div = $("artifacts-list");
        if (!div) return;
        div.innerHTML = '<p class="placeholder-text">加载产物中...</p>';
        try {
            var data = await apiGet("/artifacts/" + jobId + "/list");
            renderArtifacts(jobId, (data && data.artifacts) || []);
        } catch (err) {
            /* 404 表示产物目录不存在（任务可能无产物），显示空状态而非错误 */
            if (err.status === 404) {
                div.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📦</div><p class="empty-state-title">暂无产物</p><p class="empty-state-desc">任务完成后将在此显示产物</p></div>';
            } else {
                div.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><p class="empty-state-title">加载产物失败</p><p class="empty-state-desc">' + escapeHtml(err.message) + '</p><button class="btn btn-sm btn-primary" id="retry-artifacts-btn">重试</button></div>';
                var retryBtn = $("retry-artifacts-btn");
                if (retryBtn) on(retryBtn, "click", function () { loadArtifacts(jobId); });
            }
        }
    }

    /* 产物类型映射：文件名 → 友好名称 + 分组 */
    var ARTIFACT_TYPE_MAP = {
        ".md": { label: "Markdown 笔记", group: "笔记", icon: "doc" },
        ".org": { label: "Org 笔记", group: "笔记", icon: "doc" },
        "概念卡片": { label: "概念卡片", group: "概念", icon: "card" },
        "概念解剖": { label: "概念解剖", group: "概念", icon: "anatomy" },
        "知识图谱": { label: "知识图谱", group: "图谱", icon: "graph" },
        "思维导图": { label: "思维导图", group: "图谱", icon: "tree" },
        "信息图": { label: "信息图", group: "图谱", icon: "info" },
        "knowledge_model.json": { label: "原始知识模型", group: "数据", icon: "code" },
        "manifest.json": { label: "产物清单", group: "数据", icon: "code" }
    };

    function getArtifactMeta(filename) {
        var name = filename || "";
        var lower = name.toLowerCase();
        /* 优先按关键词匹配 */
        for (var key in ARTIFACT_TYPE_MAP) {
            if (name.indexOf(key) >= 0 || lower.indexOf(key.toLowerCase()) >= 0) {
                return ARTIFACT_TYPE_MAP[key];
            }
        }
        /* 按扩展名匹配 */
        var dot = name.lastIndexOf(".");
        var ext = dot >= 0 ? name.substring(dot).toLowerCase() : "";
        if (ext === ".html") return { label: "HTML 产物", group: "其他", icon: "doc" };
        if (ext === ".json") return { label: "JSON 数据", group: "数据", icon: "code" };
        return { label: name || "未知产物", group: "其他", icon: "doc" };
    }

    function artifactIconSvg(type) {
        var icons = {
            doc: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M6 2h8l4 4v16a2 2 0 01-2 2H6a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" stroke-width="1.5"/><path d="M14 2v4h4M8 12h8M8 16h6" stroke="currentColor" stroke-width="1.5"/></svg>',
            card: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M7 9h6M7 13h4" stroke="currentColor" stroke-width="1.5"/></svg>',
            anatomy: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M5.6 18.4L18.4 5.6" stroke="currentColor" stroke-width="1" opacity=".5"/></svg>',
            graph: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="6" cy="6" r="2.5" stroke="currentColor" stroke-width="1.5"/><circle cx="18" cy="6" r="2.5" stroke="currentColor" stroke-width="1.5"/><circle cx="12" cy="18" r="2.5" stroke="currentColor" stroke-width="1.5"/><path d="M8 7l8 9M8 5h8M7 8l4 8" stroke="currentColor" stroke-width="1.2"/></svg>',
            tree: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="4" r="2" stroke="currentColor" stroke-width="1.5"/><circle cx="6" cy="12" r="2" stroke="currentColor" stroke-width="1.5"/><circle cx="18" cy="12" r="2" stroke="currentColor" stroke-width="1.5"/><circle cx="6" cy="20" r="2" stroke="currentColor" stroke-width="1.5"/><circle cx="18" cy="20" r="2" stroke="currentColor" stroke-width="1.5"/><path d="M12 6v2M12 8L8 10M12 8l4 2M6 14v4M18 14v4" stroke="currentColor" stroke-width="1.2"/></svg>',
            info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M7 8h10v3H7zM7 13h6v5H7z" stroke="currentColor" stroke-width="1.2"/></svg>',
            code: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M8 6L2 12l6 6M16 6l6 6-6 6" stroke="currentColor" stroke-width="1.5"/></svg>'
        };
        return icons[type] || icons.doc;
    }

    function renderArtifacts(jobId, artifacts) {
        var div = $("artifacts-list");
        if (!artifacts.length) {
            div.innerHTML = '<p class="placeholder-text">暂无产物</p>';
            return;
        }

        /* 按分组组织产物 */
        var groups = {};
        var groupOrder = ["笔记", "概念", "图谱", "数据", "其他"];
        artifacts.forEach(function (a) {
            var filename = a.filename || a.name || "";
            var meta = getArtifactMeta(filename);
            if (!groups[meta.group]) groups[meta.group] = [];
            groups[meta.group].push({
                filename: filename,
                label: meta.label,
                icon: meta.icon,
                size: a.size || 0,
                artifact_type: a.artifact_type || a.type || ""
            });
        });

        /* 构建分组 HTML */
        var html = '';

        /* C4: 批量下载按钮增大但降级为次级样式 */
        html += '<div class="artifact-toolbar"><span class="artifact-count">共 ' + artifacts.length + ' 个产物</span><button class="btn btn-secondary" id="download-all-btn" data-job-id="' + escapeAttr(jobId) + '" aria-label="下载全部产物 ZIP" style="min-height:44px;padding:10px 20px;">⬇ 下载全部 ZIP</button></div>';

        groupOrder.forEach(function (groupName) {
            if (!groups[groupName]) return;
            var items = groups[groupName];
            html += '<div class="artifact-group">';
            html += '<div class="artifact-group-title">' + escapeHtml(groupName) + ' <span class="artifact-group-count">' + items.length + '</span></div>';
            html += '<div class="artifact-group-items">';
            items.forEach(function (item) {
                var safe = encodeURIComponent(item.filename);
                var downloadUrl = API_BASE + "/artifacts/" + jobId + "/" + safe;
                var sizeText = item.size > 0 ? formatSize(item.size) : "";
                html += '<div class="artifact-item-v2">';
                html += '<span class="artifact-icon-v2">' + artifactIconSvg(item.icon) + "</span>";
                html += '<div class="artifact-info">';
                html += '<a href="#" class="artifact-name" data-preview="' + safe + '" data-filename="' + escapeAttr(item.filename) + '">' + escapeHtml(item.label) + "</a>";
                if (sizeText) html += '<span class="artifact-size">' + sizeText + "</span>";
                html += "</div>";
                html += '<a href="' + downloadUrl + '" download class="btn btn-sm btn-ghost artifact-dl" title="下载 ' + escapeAttr(item.label) + '" aria-label="下载 ' + escapeAttr(item.label) + '"><svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 3v12m0 0l-5-5m5 5l5-5M4 21h16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></a>';
                html += "</div>";
            });
            html += "</div></div>";
        });

        div.innerHTML = html;

        /* 绑定预览事件 */
        div.querySelectorAll("[data-preview]").forEach(function (a) {
            on(a, "click", function (e) {
                e.preventDefault();
                previewArtifact(jobId, a.dataset.filename);
            });
        });

        /* 绑定批量下载 */
        var dlAll = $("download-all-btn");
        if (dlAll) {
            on(dlAll, "click", function () {
                var jid = dlAll.dataset.jobId;
                window.open(API_BASE + "/artifacts/" + jid + "/download-all", "_blank");
            });
        }
    }

    async function previewArtifact(jobId, filename) {
        var title = filename || "预览";
        var downloadUrl = API_BASE + "/artifacts/" + jobId + "/" + encodeURIComponent(filename);
        openModal(title, '<p class="placeholder-text">加载中...</p>', downloadUrl);
        try {
            var lower = (filename || "").toLowerCase();
            if (lower.indexOf(".html") >= 0) {
                var iframe = document.createElement("iframe");
                iframe.src = API_BASE + "/artifacts/" + jobId + "/preview/" + encodeURIComponent(filename);
                /* #137: sandbox 设为最严格，仅展示静态内容，阻止脚本与同源访问 */
                iframe.setAttribute("sandbox", "");
                iframe.style.cssText = "width:100%;min-height:60vh;border:none;border-radius:8px;";
                var body = $("modal-body");
                body.innerHTML = "";
                body.appendChild(iframe);
            } else {
                var res = await fetch(API_BASE + "/artifacts/" + jobId + "/preview/" + encodeURIComponent(filename));
                if (!res.ok) throw new Error("预览失败 (" + res.status + ")");
                var text = await res.text();
                var pre = document.createElement("pre");
                pre.textContent = text;
                var body2 = $("modal-body");
                body2.innerHTML = "";
                body2.appendChild(pre);
            }
        } catch (err) {
            var body3 = $("modal-body");
            /* #111: 预览失败时提供重试按钮，重新发起同一预览请求 */
            if (body3) {
                body3.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚠️</div><p class="empty-state-title">预览失败</p><p class="empty-state-desc">' + escapeHtml(err.message) + '</p><button class="btn btn-sm btn-primary" id="retry-preview-btn">重试</button></div>';
                var retryBtn = $("retry-preview-btn");
                if (retryBtn) on(retryBtn, "click", function () { previewArtifact(jobId, filename); });
            }
        }
    }

    /* ===================== 模态焦点陷阱（无障碍 #90） ===================== */
    /* 记录打开模态前的焦点元素，关闭后恢复；并在模态内循环 Tab 焦点 */
    var focusTrapCtx_ = { lastFocused: null, modal: null, handler: null };

    function getFocusableEls(container) {
        if (!container) return [];
        var sel = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
        return Array.prototype.slice.call(container.querySelectorAll(sel)).filter(function (el) {
            /* 过滤不可见元素 */
            return el.offsetParent !== null || el === document.activeElement;
        });
    }

    function trapFocus(modalEl) {
        if (!modalEl) return;
        /* 先释放已有焦点陷阱，避免监听器残留 */
        releaseFocusTrap();
        focusTrapCtx_.lastFocused = document.activeElement;
        focusTrapCtx_.modal = modalEl;
        /* 聚焦模态内第一个可聚焦元素 */
        var focusable = getFocusableEls(modalEl);
        if (focusable.length) {
            focusable[0].focus();
        } else {
            modalEl.setAttribute("tabindex", "-1");
            modalEl.focus();
        }
        /* Tab / Shift+Tab 在模态内循环 */
        focusTrapCtx_.handler = function (e) {
            if (e.key !== "Tab") return;
            var items = getFocusableEls(modalEl);
            if (!items.length) return;
            var first = items[0];
            var last = items[items.length - 1];
            var active = document.activeElement;
            if (e.shiftKey) {
                if (active === first || !modalEl.contains(active)) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (active === last || !modalEl.contains(active)) {
                    e.preventDefault();
                    first.focus();
                }
            }
        };
        modalEl.addEventListener("keydown", focusTrapCtx_.handler);
    }

    function releaseFocusTrap() {
        if (focusTrapCtx_.handler && focusTrapCtx_.modal) {
            focusTrapCtx_.modal.removeEventListener("keydown", focusTrapCtx_.handler);
        }
        /* 恢复打开模态前的焦点 */
        if (focusTrapCtx_.lastFocused && typeof focusTrapCtx_.lastFocused.focus === "function") {
            try { focusTrapCtx_.lastFocused.focus(); } catch (e) {}
        }
        focusTrapCtx_.lastFocused = null;
        focusTrapCtx_.modal = null;
        focusTrapCtx_.handler = null;
    }

    function openModal(title, html, downloadUrl) {
        if ($("modal-title")) $("modal-title").textContent = title || "预览";
        var body = $("modal-body");
        if (body) body.innerHTML = html || "";
        var dl = $("modal-download");
        if (dl) {
            if (downloadUrl) {
                dl.href = downloadUrl;
                dl.classList.remove("hidden");
            } else {
                dl.classList.add("hidden");
            }
        }
        var modal = $("preview-modal");
        if (modal) modal.classList.remove("hidden");
        document.body.classList.add("modal-open");
        /* #90: 打开模态时启用焦点陷阱 */
        if (modal) trapFocus(modal);
    }

    function closeModal() {
        var modal = $("preview-modal");
        if (modal) modal.classList.add("hidden");
        document.body.classList.remove("modal-open");
        /* #90: 关闭模态时释放焦点陷阱并恢复焦点 */
        releaseFocusTrap();
        var body = $("modal-body");
        if (body) {
            var iframe = body.querySelector("iframe");
            if (iframe) iframe.src = "about:blank";
            body.innerHTML = "";
        }
    }

    /* ===================== #102: 统一 Escape 键处理 ===================== */
    /**
     * 单一 document 级 keydown 监听器：按优先级判断当前打开的
     * Modal/抽屉/全屏，仅关闭最上层那一个，避免多个监听器同时触发。
     */
    function handleEscapeKey(e) {
        if (e.key !== "Escape") return;
        /* 1. 确认对话框（最高优先级） */
        var confirmModal = $("confirm-modal");
        if (confirmModal && !confirmModal.classList.contains("hidden")) {
            closeModal_();
            if (confirmResolve_) { confirmResolve_(false); }
            return;
        }
        /* 2. API Key 快速配置 Modal（由 index.html 内联脚本管理，逻辑简单在此直接关闭） */
        var settingsModal = $("settings-modal");
        if (settingsModal && !settingsModal.classList.contains("hidden")) {
            settingsModal.classList.add("hidden");
            document.body.classList.remove("modal-open");
            return;
        }
        /* 3. 创建任务模态 */
        var cjOverlay = $("create-job-overlay");
        if (cjOverlay && !cjOverlay.classList.contains("hidden")) {
            closeCreateJobModal();
            return;
        }
        /* 4. 产物预览模态 */
        var previewModal = $("preview-modal");
        if (previewModal && !previewModal.classList.contains("hidden")) {
            closeModal();
            return;
        }
        /* 5. 知识图谱全屏 */
        var fsCard = document.querySelector(".graph-fullscreen");
        if (fsCard) {
            fsCard.classList.remove("graph-fullscreen");
            document.body.style.overflow = "";
            var fsBtn = document.getElementById("graph-fullscreen-btn");
            if (fsBtn) {
                fsBtn.textContent = "⛶ 全屏";
                fsBtn.setAttribute("aria-label", "全屏查看图谱");
            }
            var kcEl = document.getElementById("knowledge-graph-chart");
            if (kcEl && kcEl._echartsInstance) {
                setTimeout(function () { kcEl._echartsInstance.resize(); }, 120);
            }
            return;
        }
        /* 6. 移动端抽屉 */
        var drawer = $("mobile-menu-drawer");
        if (drawer && drawer.classList.contains("is-open")) {
            closeMobileMenu();
            return;
        }
    }

    /* ===================== 知识浏览器 ===================== */
    async function refreshKnowledgeJobs() {
        var sel = $("knowledge-job-select");
        if (!sel) return [];
        try {
            var data = await apiGet("/jobs/");
            var done = ((data && data.jobs) || []).filter(function (j) {
                return j.status === "done" || j.status === "reconciled" || j.status === "completed";
            });
            var prev = sel.value;
            /* B6: 下拉项追加日期区分同名任务 */
            sel.innerHTML = '<option value="">-- 请选择 --</option>' + done.map(function (j) {
                var t = j.book_title || j.book_filename || j.job_id;
                /* 追加 started_at 日期 (MM-DD HH:mm) */
                if (j.started_at) {
                    var d = new Date(j.started_at);
                    if (!isNaN(d.getTime())) {
                        var mm = String(d.getMonth() + 1).padStart(2, "0");
                        var dd = String(d.getDate()).padStart(2, "0");
                        var hh = String(d.getHours()).padStart(2, "0");
                        var mi = String(d.getMinutes()).padStart(2, "0");
                        t += " (" + mm + "-" + dd + " " + hh + ":" + mi + ")";
                    }
                }
                return '<option value="' + j.job_id + '">' + escapeHtml(t) + "</option>";
            }).join("");
            if (prev && done.some(function (j) { return j.job_id === prev; })) sel.value = prev;
            return done;
        } catch (err) {
            sel.innerHTML = '<option value="">加载失败</option>';
            return [];
        }
    }

    async function openKnowledgeForJob(jobId) {
        /* #120: 通过路由导航，使浏览器后退按钮可在标签间切换 */
        if (window.Router) Router.navigate("knowledge"); else switchTab("knowledge");
        await refreshKnowledgeJobs();
        var sel = $("knowledge-job-select");
        if (sel) sel.value = jobId;
        loadKnowledge(jobId);
    }

    async function loadKnowledge(jobId) {
        var content = $("knowledge-content");
        if (!content) return;
        if (!jobId) {
            /* 检查任务下拉框是否有已完成任务，决定空状态文案 */
            var sel = $("knowledge-job-select");
            var hasJobs = sel && sel.options && sel.options.length > 1;
            var icon = hasJobs ? "📖" : "📚";
            var title = hasJobs ? "选择一本书开始探索" : "暂无已完成的拆书任务";
            var desc = hasJobs
                ? "从上方下拉选择已完成的拆书任务，浏览概念卡片、知识图谱和关系网络。"
                : "上传一本书，AI 将自动拆解为大纲、概念卡片和知识图谱。完成后可在此浏览。";
            var btnText = hasJobs ? "去上传书籍" : "立即上传";
            content.innerHTML = '<div class="empty-state empty-state-lg">' +
                '<div class="empty-state-icon">' + icon + '</div>' +
                '<p class="empty-state-title">' + title + '</p>' +
                '<p class="empty-state-desc">' + desc + '</p>' +
                '<button class="btn btn-primary btn-large btn-block" type="button" data-go-home>' + btnText + '</button>' +
                '</div>';
            /* 绑定按钮事件 */
            var goBtn = content.querySelector("[data-go-home]");
            if (goBtn) goBtn.addEventListener("click", function () {
                /* #121: 直接通过路由切换到首页并滚动到上传区，不再模拟底部导航点击 */
                if (window.Router) Router.navigate("home"); else switchTab("home");
                var dz = $("drop-zone");
                if (dz) dz.scrollIntoView({ behavior: "smooth" });
            });
            return;
        }
        content.innerHTML = '<div class="skeleton-card">' +
            '<div class="skeleton-line skeleton-title"></div>' +
            '<div class="skeleton-row">' +
            '<div class="skeleton-stat"></div><div class="skeleton-stat"></div><div class="skeleton-stat"></div>' +
            '</div>' +
            '<div class="skeleton-tabs"></div>' +
            '<div class="skeleton-line skeleton-w-80"></div>' +
            '<div class="skeleton-line skeleton-w-60"></div>' +
            '<div class="skeleton-line skeleton-w-90"></div>' +
            '<div class="skeleton-line skeleton-w-50"></div>' +
            '</div>';
        try {
            var km = await apiGet("/artifacts/" + jobId + "/knowledge");
            /* #118: 将知识模型缓存到 JS 变量，避免把整份 JSON 写进 DOM data-* 属性 */
            if (km) state.lastKnowledge = km;
            renderKnowledge(km);
        } catch (err) {
            content.innerHTML = '<p class="placeholder-text">加载失败: ' + escapeHtml(err.message) + "</p>";
        }
    }

    /**
     * 验证 source_chapter 是否为有效的章节引用。
     * 过滤掉 LLM 误将正文片段当作来源的情况。
     * 规则：长度 ≤ 40 字符、不含句号/逗号/分号等句子标点。
     */
    function isValidSourceChapter(src) {
        if (!src || typeof src !== "string") return false;
        var s = src.trim();
        if (s.length === 0 || s.length > 40) return false;
        /* 含有句号、问号、感叹号或连续逗号的视为正文片段 */
        if (/[。？！]/.test(s)) return false;
        if (/,.+,/.test(s)) return false;
        /* 含有连续 10 字以上无标点的片段且无"章/节/部分"关键词的视为可疑 */
        if (s.length > 20 && !/章|节|部分|篇|录|前言|序|附录/.test(s)) return false;
        return true;
    }

    /**
     * 将关系类型归类为语义类别，用于着色。
     * - hierarchical: 层次关系 (is-a, part-of, subtype-of, instance-of)
     * - functional:   功能关系 (depends-on, supports, enables, uses, produces)
     * - causal:       因果关系 (causes, leads-to, results-in, prevents)
     * - oppositional: 对立关系 (contradicts, opposes, contrasts-with)
     * - associative:  关联关系 (related-to, similar-to, associated-with)
     */
    function categorizeRelation(type) {
        if (!type) return "associative";
        var t = type.toLowerCase().replace(/[_\s]/g, "-");
        var hierarchical = ["is-a", "part-of", "subtype-of", "instance-of", "has-a", "type-of"];
        var functional = ["depends-on", "supports", "enables", "uses", "produces", "requires", "implements", "contains"];
        var causal = ["causes", "leads-to", "results-in", "prevents", "triggers", "affects"];
        var oppositional = ["contradicts", "opposes", "contrasts-with", "incompatible-with"];
        if (hierarchical.indexOf(t) !== -1) return "hierarchical";
        if (functional.indexOf(t) !== -1) return "functional";
        if (causal.indexOf(t) !== -1) return "causal";
        if (oppositional.indexOf(t) !== -1) return "oppositional";
        return "associative";
    }

    function outlineCount(outline) {
        var n = 0;
        function walk(nodes) {
            if (!Array.isArray(nodes)) return;
            nodes.forEach(function (node) {
                n++;
                if (Array.isArray(node.children) && node.children.length) walk(node.children);
            });
        }
        walk(outline);
        return n;
    }

    function renderKnowledge(km) {
        var content = $("knowledge-content");
        var concepts = km.concepts || [];
        var rels = km.relationships || [];
        var outline = km.outline || [];
        var bookTitle = km.book_title || "知识模型";
        var html = "";

        /* 概览卡片（始终显示） */
        html += '<div class="card km-overview-card"><div class="card-header"><h2>' + escapeHtml(bookTitle) + "</h2></div>";
        if (km.book_author) {
            html += '<div class="concept-meta" style="margin-bottom:8px;">作者: ' + escapeHtml(km.book_author) + "</div>";
        }
        /* P4-6: 统计卡片改为紧凑单行 */
        html += '<div class="km-stats-inline">';
        html += '<span class="km-stat-pill">🧠 ' + concepts.length + ' 概念</span>';
        html += '<span class="km-stat-pill">🔗 ' + rels.length + ' 关系</span>';
        html += '<span class="km-stat-pill">📋 ' + outlineCount(outline) + ' 大纲</span>';
        html += "</div>";
        if (km.summary) {
            html += '<div class="km-section"><div class="stat-label" style="margin-bottom:6px;">全书总结</div>' +
                '<div class="km-summary">' + escapeHtml(km.summary) + "</div></div>";
        }
        html += "</div>";

        /* 分段切换栏 */
        html += '<div class="km-subtabs" role="tablist" aria-label="知识视图">';
        html += '<button class="km-subtab active" data-km-tab="graph" role="tab" aria-selected="true">图谱</button>';
        html += '<button class="km-subtab" data-km-tab="concepts" role="tab" aria-selected="false">概念 (' + concepts.length + ')</button>';
        html += '<button class="km-subtab" data-km-tab="posters" role="tab" aria-selected="false">海报 (' + concepts.length + ')</button>';
        html += '<button class="km-subtab" data-km-tab="relations" role="tab" aria-selected="false">关系 (' + rels.length + ')</button>';
        html += "</div>";

        /* Panel: 知识图谱（默认显示） */
        html += '<div class="km-panel active" data-km-panel="graph">';
        html += '<div class="card graph-canvas-card">';
        html += '<div class="card-header"><h2>知识图谱</h2>';
        html += '<div class="graph-toolbar">';
        html += '<span class="graph-hint"><span class="graph-hint-desktop">拖拽节点 · 滚轮缩放 · 点击节点查看概念</span><span class="graph-hint-mobile">双指缩放 · 拖拽移动 · 点击节点查看概念</span></span>';
        html += '<button class="btn btn-sm btn-secondary graph-reset-btn" type="button" title="重置缩放和位置">重置视图</button>';
        /* D2: 全屏按钮 */
        html += '<button class="btn btn-sm btn-secondary graph-fullscreen-btn" id="graph-fullscreen-btn" type="button" title="全屏查看图谱" aria-label="全屏查看图谱">⛶ 全屏</button>';
        html += '</div></div>';
        html += '<div id="knowledge-graph-chart"></div>';
        /* D1: 图例说明 */
        html += '<div class="graph-legend"><span class="graph-legend-item"><span class="graph-legend-dot" style="background:#ef4444"></span>核心</span><span class="graph-legend-item"><span class="graph-legend-dot" style="background:#f59e0b"></span>重要</span><span class="graph-legend-item"><span class="graph-legend-dot" style="background:#10b981"></span>参考</span></div>';
        html += "</div></div>";

        /* Panel: 概念卡片 */
        html += '<div class="km-panel" data-km-panel="concepts">';
        html += '<div class="card"><h2>概念 (' + concepts.length + ")</h2>";
        if (!concepts.length) {
            html += '<div class="empty-state"><div class="empty-state-icon">📋</div><p class="empty-state-title">暂无概念</p></div>';
        } else {
            html += '<div class="km-search-bar"><svg class="km-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="M21 21l-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><input type="text" class="form-control km-concept-filter" placeholder="过滤概念名称、定义、类型..." data-km-filter="concepts"><span class="km-filter-count"></span></div>';
            html += '<div class="km-concepts">';
            concepts.forEach(function (c) {
                var imp = c.importance || "medium";
                var impLabel = imp === "high" ? "高" : imp === "low" ? "低" : "中";
                var searchText = (c.name + " " + (c.definition || "") + " " + (c.type || "") + " " + (c.source_chapter || "")).toLowerCase();
                html += '<div class="concept-card km-concept-card" data-search="' + escapeHtml(searchText) + '">';
                html += '<h3>' + escapeHtml(c.name) +
                    '<span class="imp-badge imp-' + imp + '">' + impLabel + "</span></h3>";
                if (c.definition) {
                    /* D2: 定义限2行+展开/收起按钮 */
                    html += '<div class="concept-def-wrap">';
                    html += '<div class="concept-def concept-def-clamp">' + escapeHtml(c.definition) + "</div>";
                    if (c.definition.length > 60) {
                        html += '<button class="concept-def-toggle" type="button" aria-expanded="false">展开 ▼</button>';
                    }
                    html += '</div>';
                }
                var meta = [];
                if (c.type) meta.push("类型: " + escapeHtml(c.type));
                if (c.source_chapter && isValidSourceChapter(c.source_chapter)) meta.push("来源: " + escapeHtml(c.source_chapter));
                if (meta.length) html += '<div class="concept-meta">' + meta.join(" · ") + "</div>";
                /* E1: 示例默认折叠，点击展开 */
                if (Array.isArray(c.examples) && c.examples.length) {
                    html += '<details class="concept-examples"><summary>查看 ' + c.examples.length + ' 个示例</summary>';
                    html += '<div class="concept-meta">' + c.examples.map(escapeHtml).join("、") + "</div>";
                    html += '</details>';
                }
                html += "</div>";
            });
            html += "</div>";
        }
        html += "</div></div>";

        /* Panel: 知识海报 */
        html += '<div class="km-panel" data-km-panel="posters">';
        html += '<div class="card poster-cards-card">';
        html += '<div class="card-header"><h2>知识海报</h2>';
        html += '<span class="graph-hint">每张卡片可单独导出</span></div>';
        html += '<div class="km-search-bar"><input type="text" class="form-control km-poster-filter" placeholder="过滤海报名称..." data-km-filter="posters"><span class="km-filter-count"></span></div>';
        html += '<div class="poster-cards-grid" id="poster-cards-grid"></div>';
        html += "</div></div>";

        /* Panel: 关系列表 */
        html += '<div class="km-panel" data-km-panel="relations">';
        html += '<div class="card"><h2>关系 (' + rels.length + ")</h2>";
        if (!rels.length) {
            html += '<div class="empty-state"><div class="empty-state-icon">🔗</div><p class="empty-state-title">暂无关系</p></div>';
        } else {
            html += '<div class="km-search-bar"><input type="text" class="form-control km-rel-filter" placeholder="过滤源概念、目标概念、关系类型..." data-km-filter="relations"><span class="km-filter-count"></span></div>';
            html += '<div class="rel-list">';
            rels.forEach(function (r) {
                var searchText = (r.source + " " + r.target + " " + (r.type || "") + " " + (r.description || "")).toLowerCase();
                var relCategory = categorizeRelation(r.type);
                html += '<div class="rel-item" data-search="' + escapeHtml(searchText) + '">';
                html += "<strong>" + escapeHtml(r.source) + "</strong>";
                html += '<span class="rel-type rel-cat-' + relCategory + '">' + escapeHtml(r.type) + "</span>";
                html += "<strong>" + escapeHtml(r.target) + "</strong>";
                if (r.description) {
                    html += '<div class="concept-meta" style="margin-top:4px;">' + escapeHtml(r.description) + "</div>";
                }
                html += "</div>";
            });
            html += "</div>";
        }
        html += "</div></div>";

        /* #117: 重建 innerHTML 前释放旧 ECharts 实例，避免内存泄漏 / canvas 残留 */
        if (content._echartsInstance) {
            try { content._echartsInstance.dispose(); } catch (e) {}
        }
        content.innerHTML = html;
        content._echartsInstance = null;

        /* B1: 触摸设备强制显示移动端图谱提示（兜底媒体查询） */
        if ("ontouchstart" in window || navigator.maxTouchPoints > 0) {
            var dHint = content.querySelector(".graph-hint-desktop");
            var mHint = content.querySelector(".graph-hint-mobile");
            if (dHint) dHint.style.display = "none";
            if (mHint) mHint.style.display = "inline";
        }

        /* D2: 知识图谱全屏按钮绑定 */
        var fullscreenBtn = content.querySelector("#graph-fullscreen-btn");
        var fsHeaderTimer = null;
        if (fullscreenBtn) {
            on(fullscreenBtn, "click", function () {
                var chartCard = content.querySelector(".graph-canvas-card");
                if (!chartCard) return;
                var isFs = chartCard.classList.contains("graph-fullscreen");
                if (isFs) {
                    /* 退出全屏 */
                    chartCard.classList.remove("graph-fullscreen");
                    document.body.style.overflow = "";
                    fullscreenBtn.textContent = "⛶ 全屏";
                    fullscreenBtn.setAttribute("aria-label", "全屏查看图谱");
                    if (fsHeaderTimer) { clearTimeout(fsHeaderTimer); fsHeaderTimer = null; }
                } else {
                    /* 进入全屏 */
                    chartCard.classList.add("graph-fullscreen");
                    document.body.style.overflow = "hidden";
                    fullscreenBtn.textContent = "✕ 退出全屏";
                    fullscreenBtn.setAttribute("aria-label", "退出全屏");
                    /* D7: 5 秒后自动隐藏控制栏 */
                    fsHeaderTimer = setTimeout(function () {
                        var header = chartCard.querySelector(".card-header");
                        if (header && chartCard.classList.contains("graph-fullscreen")) {
                            header.classList.add("graph-header-hidden");
                        }
                    }, 5000);
                    /* C5: 首次进入全屏提示"轻触屏幕显示控制栏" */
                    if (!state._fsHintShown) {
                        state._fsHintShown = true;
                        setTimeout(function () {
                            showToast("轻触图谱区域可显示控制栏", "info");
                        }, 600);
                    }
                }
                /* resize ECharts */
                var kcEl = document.getElementById("knowledge-graph-chart");
                if (kcEl && kcEl._echartsInstance) {
                    setTimeout(function () { kcEl._echartsInstance.resize(); }, 120);
                }
            });

            /* D7: 点击图谱区域呼出控制栏 */
            var kcEl2 = document.getElementById("knowledge-graph-chart");
            if (kcEl2) {
                on(kcEl2, "click", function () {
                    var chartCard = content.querySelector(".graph-canvas-card");
                    if (!chartCard || !chartCard.classList.contains("graph-fullscreen")) return;
                    var header = chartCard.querySelector(".card-header");
                    if (header) {
                        header.classList.remove("graph-header-hidden");
                        if (fsHeaderTimer) clearTimeout(fsHeaderTimer);
                        fsHeaderTimer = setTimeout(function () {
                            if (chartCard.classList.contains("graph-fullscreen")) {
                                header.classList.add("graph-header-hidden");
                            }
                        }, 5000);
                    }
                });
            }
        }

        /* 绑定分段切换 */
        content.querySelectorAll(".km-subtab").forEach(function (tab) {
            on(tab, "click", function () {
                var target = tab.dataset.kmTab;
                content.querySelectorAll(".km-subtab").forEach(function (t) {
                    t.classList.remove("active");
                    t.setAttribute("aria-selected", "false");
                });
                tab.classList.add("active");
                tab.setAttribute("aria-selected", "true");
                content.querySelectorAll(".km-panel").forEach(function (p) {
                    if (p.dataset.kmPanel === target) {
                        p.classList.add("active");
                        /* 切换到图谱时需要 resize ECharts */
                        if (target === "graph" && content._echartsInstance) {
                            setTimeout(function () { content._echartsInstance.resize(); }, 100);
                        }
                        /* B3: 切换到非图谱 Tab 时自动滚动到面板顶部 */
                        if (target !== "graph") {
                            setTimeout(function () {
                                p.scrollIntoView({ behavior: "smooth", block: "start" });
                            }, 100);
                        }
                    } else {
                        p.classList.remove("active");
                    }
                });
            });
        });

        /* 通用过滤函数：在指定面板内过滤带 data-search 的元素 */
        function setupKmFilter(filterInput, itemSelector) {
            if (!filterInput) return;
            var panel = filterInput.closest(".km-panel");
            if (!panel) return;
            var countEl = panel.querySelector(".km-filter-count");
            /* #116: 输入过滤加 200ms 防抖，避免每次按键都遍历整个 DOM */
            on(filterInput, "input", debounce(function () {
                var query = filterInput.value.trim().toLowerCase();
                var items = panel.querySelectorAll(itemSelector);
                var visible = 0;
                items.forEach(function (item) {
                    var searchText = item.dataset.search || "";
                    if (!query || searchText.indexOf(query) >= 0) {
                        item.style.display = "";
                        visible++;
                    } else {
                        item.style.display = "none";
                    }
                });
                if (countEl) {
                    countEl.textContent = query ? visible + "/" + items.length + " 匹配" : "";
                }
            }, 200));
        }

        /* 概念过滤 */
        setupKmFilter(content.querySelector(".km-concept-filter"), ".concept-card");

        /* D2: 概念定义展开/收起 */
        content.querySelectorAll(".concept-def-toggle").forEach(function (btn) {
            on(btn, "click", function (e) {
                e.stopPropagation();
                var wrap = btn.closest(".concept-def-wrap");
                var def = wrap ? wrap.querySelector(".concept-def") : null;
                if (!def) return;
                var expanded = btn.getAttribute("aria-expanded") === "true";
                if (expanded) {
                    def.classList.add("concept-def-clamp");
                    btn.textContent = "展开 ▼";
                    btn.setAttribute("aria-expanded", "false");
                } else {
                    def.classList.remove("concept-def-clamp");
                    btn.textContent = "收起 ▲";
                    btn.setAttribute("aria-expanded", "true");
                }
            });
        });

        /* 关系过滤 */
        setupKmFilter(content.querySelector(".km-rel-filter"), ".rel-item");
        /* 海报过滤 */
        setupKmFilter(content.querySelector(".km-poster-filter"), ".poster-mini");

        /* 生成知识海报卡片到 grid */
        var posterGrid = $("poster-cards-grid");
        if (posterGrid && window.generatePosterCard) {
            concepts.forEach(function (c, idx) {
                var imp = c.importance || "medium";
                var metaParts = [];
                if (c.type) metaParts.push("类型: " + c.type);
                if (c.source_chapter && isValidSourceChapter(c.source_chapter)) metaParts.push("来源: " + c.source_chapter);
                var examplesText = Array.isArray(c.examples) && c.examples.length ? c.examples.join("、") : "";
                var posterMini = window.generatePosterCard(
                    c.name || ("概念" + (idx + 1)),
                    c.definition || "",
                    metaParts.join(" · "),
                    examplesText,
                    imp,
                    bookTitle,
                    idx
                );
                posterGrid.appendChild(posterMini);
            });
        }

        /* 触发 ECharts 图谱渲染 */
        if (window.initKnowledgeGraph) {
            window.initKnowledgeGraph(content, km);
        }
    }

    /* ===================== 设置 ===================== */
    async function loadSettings() {
        var status = $("settings-status");
        try {
            var data = await apiGet("/settings/");
            var sp = $("settings-provider");
            var sm = $("settings-model");
            if (sp && data.default_provider) sp.value = data.default_provider;
            if (sm) sm.value = data.default_model || "";

            /* D3: Provider 切换时动态提示模型和注意事项 */
            if (sp && !sp._hintBound) {
                sp._hintBound = true;
                on(sp, "change", function () {
                    var provider = sp.value;
                    /* 如果模型为空或等于之前 provider 的默认值，则自动填充建议模型 */
                    if (sm && (!sm.value || Object.values(PROVIDER_MODELS).indexOf(sm.value) >= 0)) {
                        sm.value = PROVIDER_MODELS[provider] || "";
                    }
                    /* 显示 provider 提示 */
                    var hint = PROVIDER_HINTS[provider];
                    var hintEl = $("provider-hint");
                    if (hintEl) {
                        hintEl.textContent = hint || "";
                        hintEl.style.display = hint ? "block" : "none";
                    }
                });
                /* 初始触发一次 */
                if (sp.value) sp.dispatchEvent(new Event("change"));
            }

            var html = '<div class="km-section"><div class="stat-label" style="margin-bottom:6px;">Provider 状态</div>';
            var providers = data.providers || {};
            PROVIDERS.forEach(function (p) {
                var info = providers[p.value] || {};
                var configured = !!info.configured;
                var key = info.api_key || "";
                /* 前端脱敏：仅显示前3位+****+后4位 */
                var maskedKey = "";
                if (key && key.length > 8) {
                    maskedKey = key.slice(0, 3) + "****" + key.slice(-4);
                } else if (key) {
                    maskedKey = "****";
                }
                html += '<div class="artifact-item" style="justify-content:space-between;">';
                html += "<span>" + escapeHtml(p.label) +
                    '<span class="provider-status ' + (configured ? "ok" : "no") + '">' +
                    (configured ? "已配置" : "未配置") + "</span></span>";
                if (maskedKey) html += '<span class="concept-meta">' + escapeHtml(maskedKey) + "</span>";
                html += "</div>";
            });
            html += "</div>";
            if (status) status.innerHTML = html;
        } catch (err) {
            if (status) status.innerHTML = '<p class="placeholder-text">加载设置失败: ' + escapeHtml(err.message) + "</p>";
        }
    }

    async function saveSettings() {
        var provider = ($("settings-provider") && $("settings-provider").value) || null;
        var apiKey = ($("settings-apikey") && $("settings-apikey").value.trim()) || null;
        var model = ($("settings-model") && $("settings-model").value.trim()) || null;
        var body = {};
        if (provider) body.provider = provider;
        if (apiKey) body.api_key = apiKey;
        if (model) body.model = model;
        if (!Object.keys(body).length) {
            showToast("没有需要保存的更改", "info");
            return;
        }
        var btn = $("save-settings-btn");
        if (btn) btn.disabled = true;
        try {
            await apiPut("/settings/", body);
            showToast("设置已保存", "success");
            if ($("settings-apikey")) $("settings-apikey").value = "";
            loadSettings();
            /* B4: 保存成功按钮变绿+勾号 1.5 秒 */
            if (btn) {
                var origText = btn.textContent;
                btn.classList.add("btn-save-success");
                btn.textContent = "✓ 已保存";
                setTimeout(function () {
                    btn.classList.remove("btn-save-success");
                    btn.textContent = origText;
                }, 1500);
            }
        } catch (err) {
            showToast(err.message, "error");
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    /* ===================== 初始化 ===================== */
    function init() {
        ensureLayout();
        initTheme();

        /* #102: 统一的 Escape 键监听器 —— 按优先级关闭当前打开的 Modal/抽屉/全屏 */
        on(document, "keydown", handleEscapeKey);

        /* 导航点击 — 使用事件委托捕获动态添加的 data-tab 链接 */
        document.addEventListener("click", function (e) {
            var link = e.target.closest("[data-tab]");
            if (!link) return;
            e.preventDefault();
            var tab = link.dataset.tab;
            /* S1-BUG1/2/3: 统一通过 Router.navigate 切换，确保 URL 同步 */
            if (window.Router && typeof Router.navigate === "function") {
                Router.navigate(tab);
            } else {
                switchTab(tab);
            }
            /* "查看示例效果"特殊处理：跳转知识页并自动加载第一个有产物的任务 */
            if (link.id === "view-demo-link" || link.id === "hero-demo-link") {
                refreshKnowledgeJobs().then(function (doneJobs) {
                    var sel = $("knowledge-job-select");
                    if (sel && sel.options.length > 1) {
                        /* 优先选择有产物的任务 */
                        var bestIdx = -1;
                        for (var i = 0; i < doneJobs.length; i++) {
                            if ((doneJobs[i].artifact_count || 0) > 0) { bestIdx = i + 1; break; }
                        }
                        if (bestIdx < 0) bestIdx = sel.options.length - 1;
                        sel.selectedIndex = bestIdx;
                        loadKnowledge(sel.value);
                    }
                });
            }
        });

        /* 模态框关闭 */
        on($("modal-close"), "click", closeModal);
        /* #99: 统一预览模态两个关闭按钮，均调用 closeModal */
        on($("preview-close"), "click", closeModal);
        on($("modal-overlay"), "click", closeModal);

        /* B1: 移动端汉堡菜单抽屉 */
        initMobileMenu();

        /* 确认对话框关闭（点击背景或 Escape 时视为取消） */
        var confirmModal = $("confirm-modal");
        if (confirmModal) {
            var confirmBackdrop = confirmModal.querySelector("[data-close]");
            if (confirmBackdrop) {
                on(confirmBackdrop, "click", function () {
                    closeModal_();
                    if (confirmResolve_) { confirmResolve_(false); }
                });
            }
            /* #102: Escape 键由 init 顶部统一的 handleEscapeKey 处理 */
        }

        /* 上传 / 创建任务 */
        setupUpload();
        setupCreateJob();

        /* 任务列表交互（防抖：请求期间禁用按钮+loading 动画） */
        on($("refresh-jobs-btn"), "click", function () {
            var btn = $("refresh-jobs-btn");
            if (btn && btn.disabled) return;
            if (btn) { btn.disabled = true; btn.classList.add("btn-loading"); }
            loadJobs().finally(function () {
                if (btn) { btn.disabled = false; btn.classList.remove("btn-loading"); }
            });
        });

        /* E5: 任务页下拉刷新手势（移动端） */
        initPullToRefresh();

        /* E6: 触摸反馈涟漪 */
        initRipple();

        on($("close-detail-btn"), "click", function () {
            var sec = $("job-detail-section");
            if (sec) sec.classList.add("hidden");
            state.currentJobId = null;
        });

        /* 知识浏览器（防抖） */
        on($("load-knowledge-btn"), "click", function () {
            var sel = $("knowledge-job-select");
            if (sel && sel.value) loadKnowledge(sel.value);
        });

        /* 知识页空状态"去上传书籍"按钮（模板内置引导） */
        document.querySelectorAll("[data-go-home]").forEach(function (btn) {
            on(btn, "click", function () {
                /* #121: 直接通过路由切换到首页并滚动到上传区 */
                if (window.Router) Router.navigate("home"); else switchTab("home");
                var dz = $("drop-zone");
                if (dz) dz.scrollIntoView({ behavior: "smooth" });
            });
        });

        /* 选择任务后自动加载知识模型 */
        on($("knowledge-job-select"), "change", function () {
            var sel = $("knowledge-job-select");
            if (sel && sel.value) loadKnowledge(sel.value);
        });

        /* 设置 */
        on($("save-settings-btn"), "click", saveSettings);

        /* D1: API Key 可见性切换 */
        var apikeyToggle = $("apikey-toggle");
        if (apikeyToggle) {
            on(apikeyToggle, "click", function () {
                var input = $("settings-apikey");
                if (!input) return;
                var isHidden = input.type === "password";
                input.type = isHidden ? "text" : "password";
                apikeyToggle.textContent = isHidden ? "🙈" : "👁";
                apikeyToggle.setAttribute("aria-pressed", String(isHidden));
            });
        }

        /* 加载示例书籍 */
        loadSamples();

        /* ---- 阶段C 架构重构集成 ---- */
        // 路由：管理 Tab 切换 + URL 同步
        Router.init({
            onChange: function (tab) {
                switchTab(tab);
            },
        });

        // 确认对话框：绑定 DOM 事件
        if (window.ConfirmModal) {
            ConfirmModal.bind();
        }

        // 全局错误兜底（保留 ErrorBoundary 的全局 window 监听）
        // 已在 error-boundary.js 中通过 addEventListener 绑定

        // S1-BUG1: 默认显示路由指定的 Tab（或 home）
        var initialTab = Router.getCurrentTab();
        if (initialTab) {
            switchTab(initialTab);
        } else {
            switchTab("home");
        }
    }

    /* 兼容脚本在 DOMContentLoaded 之后执行的情况 */
    if (document.readyState !== "loading") init();
    else document.addEventListener("DOMContentLoaded", init);
})();
