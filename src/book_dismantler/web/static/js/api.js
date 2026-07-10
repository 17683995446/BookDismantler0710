/**
 * Book Dismantler · API 通信模块
 *
 * 封装与 FastAPI 后端的 fetch 通信，提供超时控制和错误处理。
 * 通过 window.BD_API 命名空间暴露，供 app.js 使用。
 */
(function () {
    "use strict";

    var API_BASE = "/api";
    var API_TIMEOUT_MS = 20000; /* 20s 超时 */

    function fetchWithTimeout(url, opts) {
        var ctrl = new AbortController();
        var timer = setTimeout(function () { ctrl.abort(); }, API_TIMEOUT_MS);
        opts = opts || {};
        opts.signal = ctrl.signal;
        return fetch(url, opts)
            .finally(function () { clearTimeout(timer); })
            .catch(function (err) {
                /* #108: 将 AbortError（超时/取消）翻译为友好的中文提示 */
                if (err && (err.name === "AbortError" || ctrl.signal.aborted)) {
                    throw new Error("请求超时，请检查网络连接后重试");
                }
                throw err;
            });
    }

    async function parseBody(res) {
        /* 处理 204 No Content 或空响应体，避免 res.json() 抛错 */
        if (res.status === 204) return null;
        var text = await res.text();
        if (!text) return null;
        try { return JSON.parse(text); } catch (e) { return null; }
    }

    async function apiGet(path) {
        var res = await fetchWithTimeout(API_BASE + path);
        if (!res.ok) throw await toError(res);
        return parseBody(res);
    }

    async function apiPost(path, body, isForm) {
        var opts = { method: "POST" };
        if (isForm) {
            opts.body = body; // FormData
        } else {
            opts.headers = { "Content-Type": "application/json" };
            opts.body = body == null ? "{}" : JSON.stringify(body);
        }
        var res = await fetchWithTimeout(API_BASE + path, opts);
        if (!res.ok) throw await toError(res);
        return parseBody(res);
    }

    async function apiPut(path, body) {
        var res = await fetchWithTimeout(API_BASE + path, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: body == null ? "{}" : JSON.stringify(body)
        });
        if (!res.ok) throw await toError(res);
        return parseBody(res);
    }

    async function apiDelete(path) {
        var res = await fetchWithTimeout(API_BASE + path, { method: "DELETE" });
        if (!res.ok) throw await toError(res);
        return parseBody(res);
    }

    async function toError(res) {
        /* #109: 根据状态码补充友好提示，便于用户理解错误原因 */
        var suffix = "";
        if (res.status === 500) suffix = "：服务器内部错误";
        else if (res.status === 502 || res.status === 503) suffix = "：服务暂时不可用";
        else if (res.status === 404) suffix = "：资源不存在";
        else if (res.status === 403) suffix = "：无权限访问";
        var detail = "请求失败 (" + res.status + ")" + suffix;
        try {
            var data = await parseBody(res);
            if (data && data.detail) detail = data.detail;
        } catch (e) { /* 非 JSON 错误体 */ }
        var err = new Error(detail);
        err.status = res.status;
        return err;
    }

    /* ===================== 暴露命名空间 ===================== */
    window.BD_API = {
        BASE: API_BASE,
        get: apiGet,
        post: apiPost,
        put: apiPut,
        delete: apiDelete,
        toError: toError
    };
})();
