"""富途牛牛 PyQt6 WebEngine 客户端：左侧自选栏 + 右侧个股详情，外加登录页。

三个页面都直接复用 futunn.com 的原始前端：
  - 自选栏（左）：个股页里的 Vue 组件 WatchListModal，注入样式铺满左侧视图并常驻；
    点击条目时拦截它的 router.push，改为在右侧打开个股；
  - 个股详情（右）：/stock/<CODE> 页面本身，隐藏站点导航、页脚和工具栏；
  - 市场行情（右）：个股页面包屑「美股市场 / 港股市场」指向的 /quote/us、/quote/hk 等页面；
  - 登录页：passport.futunn.com 的登录界面（?type=login），在右侧打开，登录成功后由它跳回 target；
  - 本地自选（左）：同一个 WatchListModal，数据换成本机 local_watchlist.json 里的股票 + 实时报价，不需要登录。

登录态由持久化的 QWebEngineProfile 保存（.qt_profile/），下次启动无需重新登录。

用法:
    python futu_app.py
    python futu_app.py --code NVDA-US
"""

import argparse
import contextlib
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtCore import QByteArray, QLockFile, QSettings, QStandardPaths, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWebEngineCore import (
    QWebEngineLoadingInfo,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineScript,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

from futu_api import FutuClient, RateLimited, app_dir, resource_dir
from local_watchlist import LocalWatchlist, SaveError, StockNotFound, build_item, resolve

BASE_URL = "https://www.futunn.com"
US_MARKET_URL = f"{BASE_URL}/quote/us"
# 左侧自选栏挂在美股市场页上：同样有 ToolBar 和 WatchListModal，比个股页请求少，也不受个股页限流影响
WATCH_HOST_URL = US_MARKET_URL
AUTO_REFRESH_MS = 3000  # 站点自己每 60 秒轮询一次，这里额外按 3 秒触发它的刷新回调
SLOW_REFRESH_S = 60  # 关掉快速刷新后，本地自选按站点的节奏刷新（站点页面自己会轮询，本地列表不会）
RATE_LIMIT_PAUSE_S = 60
LIST_WIDTH = 880  # 站点自选弹窗 .content 的原始宽度
PASSPORT_HOST = "passport.futunn.com"
DEFAULT_CODE = "TSLA-US"
PROFILE_DIR = app_dir() / ".qt_profile"  # 跟着 exe/源码目录走，复制到哪就用哪


def _icon_file() -> Path:
    # 打包后图标被收进内部资源目录；脚本运行时在 launcher/ 下
    for p in (resource_dir() / "futu.ico", Path(__file__).resolve().parent / "launcher" / "futu.ico"):
        if p.exists():
            return p
    return resource_dir() / "futu.ico"


ICON_FILE = _icon_file()
APP_UA_TOKEN = "FutuWatchlist/1.0"
COOKIE_DOMAINS = ("futunn.com", "www.futunn.com")
CHROMIUM_EPOCH_OFFSET = 11644473600  # 1601-01-01 到 1970-01-01 的秒数

STOCK_PATH_RE = re.compile(
    r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?"
    r"(stock|etfs|futures|index|options|currency|crypto|sectors)/([^/?#]+)",
    re.I,
)
# 个股页面包屑「美股市场 / 港股市场」等指向的行情页：/quote/us、/quote/hk、/quote/us/stock-list/...
MARKET_PATH_RE = re.compile(r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?quote(?:/|$)", re.I)

PAGE_CSS = """
#header, #footer, .top-banner { display: none !important; }
body { position: static !important; }
"""

DETAIL_CSS = """
section.tool-bar { display: none !important; }
"""

WATCH_CSS = """
section.watchlist-modal { z-index: 2147483000 !important; width: 100vw !important; height: 100vh !important; }
section.watchlist-modal .mask,
section.watchlist-modal .close-icon { display: none !important; }
section.watchlist-modal .content {
  top: 0 !important; left: 0 !important; transform: none !important;
  width: 100vw !important; max-width: none !important;
  height: 100vh !important; max-height: none !important;
  border-radius: 0 !important; box-shadow: none !important;
  padding: 12px 16px 12px !important;
  display: flex !important; flex-direction: column !important; overflow: hidden !important;
}
section.watchlist-modal .list { flex: 1 1 auto !important; height: auto !important; max-height: none !important; }
section.watchlist-modal .list-head,
section.watchlist-modal .list-item { width: auto !important; min-width: 100% !important; }
@media (max-width: 620px) {
  section.watchlist-modal .col.change-value,
  section.watchlist-modal .col.volume { display: none !important; }
  section.watchlist-modal .col.name { min-width: 0 !important; }
  section.watchlist-modal .col.price { width: 96px !important; }
  /* 右侧紧挨着自选心形，盘前/盘后/夜盘标签没处顺延，就在列内留出标签宽度，所有行的涨跌幅仍对齐 */
  section.watchlist-modal .col.change { width: 128px !important; padding-right: 44px !important; }
  section.watchlist-modal .col.watchlist { width: 44px !important; }
}
/* 盘前/盘后/夜盘：涨跌幅和其他行对齐，标签顺延到列外（涨跌额列左侧的空白里） */
section.watchlist-modal .col.change:has(.disc-change),
section.watchlist-modal .col.change .disc-change { overflow: visible !important; }
section.watchlist-modal .col.change .disc-change { position: relative; }
section.watchlist-modal .col.change-value { width: 132px !important; }
section.watchlist-modal .col.change .disc-status {
  position: absolute; left: 100%; top: 50%; transform: translateY(-50%);
  margin-left: 4px !important; white-space: nowrap;
}
section.watchlist-modal .header h3[data-fa-title] { font-size: 0 !important; }
section.watchlist-modal .header h3[data-fa-title]::after { content: attr(data-fa-title); font-size: var(--fa-h3-size); }
html.fa-drag, html.fa-drag * { cursor: grabbing !important; user-select: none !important; }
section.watchlist-modal .list-item.fa-moving { transition: transform .15s ease; }
section.watchlist-modal .list-item.fa-dragged {
  position: relative; z-index: 2; transition: none;
  background: #fff; box-shadow: 0 4px 16px rgba(0, 0, 0, .18);
}
html.fa-local-empty section.watchlist-modal .content::after {
  content: "本地自选还是空的：在顶部「添加本地自选」输入框里输入代码（如 TSLA、00700、600519）回车即可添加";
  display: block; padding: 48px 24px; text-align: center; color: #888; font-size: 14px; line-height: 1.8;
}
"""

# window.__faRole 由每个视图自己的页面脚本注入：'watch' 为左侧自选栏，'detail' 为右侧个股详情。
#
# 自选栏：ToolBar 的自选按钮点击后 toolbarStore.label = "工具栏-自选"，App 才会挂载
# section.watchlist-modal；SSR 输出的按钮在 Vue 水合前点击无效，所以要轮询直到弹窗出现。
# 条目点击走 WatchListModal.stockClick：更新个股 store、router.push(个股路径)，最后 closeModal()，
# 即 toolbarStore.label = "" 再 commonStore.switchWatch(false)。左侧让 router.push 只记录路径、
# 在 switchWatch(false) 里同步把 label 改回去（Vue 异步渲染看不到变化，弹窗不会卸载），
# 再把条目数据和路径通过 console 交给 Python，由右侧用同一个 stockClick 打开。
PAGE_JS = """
(function () {
  if (location.hostname !== 'www.futunn.com' || window.__fa) return;
  window.__fa = true;

  var css = %(css)s, roleCss = %(role_css)s;
  new MutationObserver(function (_, observer) {
    if (!document.head) return;
    var style = document.createElement('style');
    style.id = 'fa-style';
    style.textContent = css + (roleCss[window.__faRole] || '');
    document.head.appendChild(style);
    observer.disconnect();
  }).observe(document, { childList: true, subtree: true });

  function rootVm() {
    var app = document.getElementById('app');
    return app && app.__vue__;
  }

  // App 组件（setup 里暴露了 WatchListModal 组件定义）
  function appVm() {
    var queue = rootVm() ? [rootVm()] : [];
    for (var i = 0; i < queue.length && i < 20; i++) {
      var vm = queue[i];
      if (vm._setupState && vm._setupState.WatchListModal) return vm;
      queue.push.apply(queue, vm.$children);
    }
    return null;
  }

  function patchWatch(modal) {
    var vm = rootVm(), modalVm = modal.__vue__;
    if (!vm || !vm.$router || !vm.$pinia || !modalVm || !modalVm._setupState) return;
    var router = vm.$router, lastPath = '';
    if (!router.__fa) {
      router.__fa = true;
      router.push = router.replace = function (loc) {
        lastPath = typeof loc === 'string' ? loc : (loc && (loc.fullPath || loc.path)) || '';
        return Promise.resolve();
      };
    }
    var common = vm.$pinia._s.get('common_data'), toolbar = vm.$pinia._s.get('tool-bar');
    if (common && toolbar && toolbar.$state.label && !common.__fa) {
      common.__fa = true;
      var label = toolbar.$state.label, switchWatch = common.switchWatch;
      common.switchWatch = function (show) {
        if (!show) {
          toolbar.$state.label = label;
          return;
        }
        return switchWatch.apply(this, arguments);
      };
    }
    var setup = modalVm._setupState;
    if (!setup.__fa) {
      setup.__fa = true;
      var stockClick = setup.stockClick, watchClick = setup.watchClick;
      setup.stockClick = function (item) {
        lastPath = '';
        stockClick(item);
        if (lastPath) console.info('__FA_OPEN__' + JSON.stringify({ path: lastPath, item: item }));
      };
      // 本地自选里的爱心表示「从本地自选删除」，不走站点的加/删自选
      setup.watchClick = function (item) {
        if (local.on) {
          console.info('__FA_LOCAL_DEL__' + item.stockId);
          return;
        }
        return watchClick(item);
      };
    }
  }

  // 本地自选：复用同一个 WatchListModal，只把 watch_list store 的数据换成 Python 推过来的本地条目。
  // 本地模式下 fetchList / getIdsMap 不请求服务端，updateList 直接用本地条目，避免在途请求把列表覆盖回去。
  var local = { on: false, items: [], dirty: false, applied: false }, origStore = null;

  function watchStore() {
    var vm = rootVm();
    return vm && vm.$pinia && vm.$pinia._s.get('watch_list');
  }

  function applyLocal() {
    var store = watchStore(), vm = rootVm();
    if (!store) return false;
    if (!origStore) {
      origStore = { fetchList: store.fetchList, getIdsMap: store.getIdsMap, updateList: store.updateList };
      store.fetchList = function () { return local.on ? Promise.resolve() : origStore.fetchList.apply(this, arguments); };
      store.getIdsMap = function () { return local.on ? Promise.resolve() : origStore.getIdsMap.apply(this, arguments); };
      store.updateList = function () {
        if (local.on) { if (!dragging()) this.list = local.items.slice(); return; }
        return origStore.updateList.apply(this, arguments);
      };
    }
    if (local.on) {
      var ids = {};
      local.items.forEach(function (it) { ids[it.stockId] = true; });
      store.$patch(function (s) {
        s.list = local.items.slice();
        s.idsMap = ids;
        s.isMore = false;
        s.loading = false;
      });
    } else if (local.applied) {
      store.$patch(function (s) { s.idsMap = {}; });
      store.resetData();
      var common = vm.$pinia._s.get('common_data');
      if (common && common.userInfo && common.userInfo.isLogin) store.getIdsMap();
    }
    local.applied = local.on;
    return true;
  }

  window.__faSetLocal = function (on, items) {
    local.on = on;
    if (items) local.items = items;
    local.dirty = true;
  };

  // 本地自选拖动排序：按住条目上下拖，其它条目让出位置，松开鼠标就落在当前位置，新顺序交给 Python 安全保存。
  // 拖动期间不应用新推来的行情（列表重绘会打断拖动），松开后再应用。
  var drag = null, suppressClick = false;

  function dragging() {
    return !!(drag && drag.active);
  }

  document.addEventListener('pointerdown', function (e) {
    // 上次按下后在窗口外松开、没收到 pointerup 的残留状态，先清掉
    if (drag) endDrag(null, drag.active);
    if (window.__faRole !== 'watch' || !local.on || e.button !== 0) return;
    var row = e.target.closest && e.target.closest('section.watchlist-modal .list > .list-item');
    if (!row || e.target.closest('.col.watchlist')) return;
    var list = row.parentElement;
    var rows = Array.prototype.filter.call(list.children, function (el) { return el.classList.contains('list-item'); });
    drag = { id: e.pointerId, row: row, list: list, rows: rows, from: rows.indexOf(row), to: rows.indexOf(row),
             startY: e.clientY, y: e.clientY, scroll: list.scrollTop, active: false, timer: 0 };
    e.preventDefault();  // 不触发文字选中；click 照常触发，单击条目仍然打开详情
  }, true);

  document.addEventListener('pointermove', function (e) {
    if (!drag || e.pointerId !== drag.id) return;
    drag.y = e.clientY;
    if (!drag.active) {
      if (Math.abs(drag.y - drag.startY) < 6) return;
      startDrag();
    }
    layoutDrag();
  }, true);

  document.addEventListener('pointerup', function (e) { endDrag(e, true); }, true);
  document.addEventListener('pointercancel', function (e) { endDrag(e, false); }, true);
  document.addEventListener('lostpointercapture', function (e) { endDrag(e, true); }, true);
  window.addEventListener('blur', function () { endDrag(null, true); });

  // 拖动结束时鼠标还在条目上，吞掉随后的 click，免得松手就打开详情
  window.addEventListener('click', function (e) {
    if (!suppressClick) return;
    suppressClick = false;
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);

  function startDrag() {
    var listTop = drag.list.getBoundingClientRect().top;
    drag.active = true;
    drag.height = drag.row.getBoundingClientRect().height;
    drag.centers = drag.rows.map(function (r) {
      var b = r.getBoundingClientRect();
      return b.top - listTop + drag.scroll + b.height / 2;
    });
    drag.rows.forEach(function (r) { r.classList.add('fa-moving'); });
    drag.row.classList.add('fa-dragged');
    document.documentElement.classList.add('fa-drag');
    try { drag.row.setPointerCapture(drag.id); } catch (err) {}
    drag.timer = setInterval(autoScroll, 16);
  }

  // 位置都按列表内容坐标算：鼠标位移 + 列表滚动位移
  function layoutDrag() {
    var offset = drag.y - drag.startY + drag.list.scrollTop - drag.scroll;
    var center = drag.centers[drag.from] + offset, from = drag.from, to = 0;
    drag.centers.forEach(function (c, i) { if (i !== from && c < center) to++; });
    drag.to = to;
    drag.rows.forEach(function (r, i) {
      var shift = 0;
      if (i === from) shift = offset;
      else if (from < to && i > from && i <= to) shift = -drag.height;
      else if (to < from && i >= to && i < from) shift = drag.height;
      r.style.transform = shift ? 'translateY(' + shift + 'px)' : '';
    });
  }

  // 拖到列表上下边缘时自动滚动，离边缘越远滚得越快
  function autoScroll() {
    if (!drag || !drag.active) return;
    var r = drag.list.getBoundingClientRect(), edge = 48, step = 0;
    if (drag.y < r.top + edge) step = -Math.min(30, Math.ceil((r.top + edge - drag.y) / 4));
    else if (drag.y > r.bottom - edge) step = Math.min(30, Math.ceil((drag.y - r.bottom + edge) / 4));
    if (step) drag.list.scrollTop += step;
    layoutDrag();
  }

  function endDrag(e, commit) {
    if (!drag || (e && e.pointerId !== drag.id)) return;
    var d = drag;
    drag = null;
    clearInterval(d.timer);
    document.documentElement.classList.remove('fa-drag');
    d.rows.forEach(function (r) {
      r.classList.remove('fa-moving', 'fa-dragged');
      r.style.transform = '';
    });
    if (!d.active) return;
    suppressClick = true;
    setTimeout(function () { suppressClick = false; }, 0);
    var store = watchStore();
    if (commit && d.to !== d.from && store && store.list.length === d.rows.length) {
      var ids = store.list.map(function (it) { return String(it.stockId); });
      ids.splice(d.to, 0, ids.splice(d.from, 1)[0]);
      var byId = {};
      local.items.forEach(function (it) { byId[String(it.stockId)] = it; });
      local.items = ids.map(function (id) { return byId[id]; }).filter(Boolean);
      console.info('__FA_LOCAL_MOVE__' + JSON.stringify(ids));
    }
    local.dirty = true;
    if (applyLocal()) local.dirty = false;
  }

  function syncLocalView(modal) {
    if (local.dirty && !dragging() && applyLocal()) local.dirty = false;
    var h3 = modal.querySelector('.header h3');
    if (h3 && local.on && !h3.dataset.faTitle) {
      h3.style.setProperty('--fa-h3-size', getComputedStyle(h3).fontSize);
      h3.dataset.faTitle = '本地自选';
    } else if (h3 && !local.on && h3.dataset.faTitle) {
      delete h3.dataset.faTitle;
    }
    document.documentElement.classList.toggle('fa-local-empty', local.on && local.items.length === 0);
  }

  setInterval(function () {
    if (window.__faRole !== 'watch') return;
    var modal = document.querySelector('section.watchlist-modal');
    if (modal) {
      patchWatch(modal);
      syncLocalView(modal);
      return;
    }
    var btn = document.querySelector('section.tool-bar li.gap-item .tb-item');
    if (btn && !btn.classList.contains('active')) btn.click();
  }, 300);

  // 右侧切换个股：临时实例化一个不挂载的 WatchListModal，直接调用它的 stockClick，
  // 由站点自己更新个股 store、重置各模块数据并 router.push，和在站点里点自选条目完全一致。
  window.__faGo = function (item) {
    var app = appVm();
    if (!app || !item) return false;
    try {
      var Modal = app.$options._base.extend(app._setupState.WatchListModal);
      var modal = new Modal({ parent: app });
      modal._setupState.stockClick(item);
      modal.$destroy();
      return true;
    } catch (e) {
      console.error(e);
      return false;
    }
  };

  // 站点有个全局轮询模块：各模块（个股报价、分时图、资金、市场页榜单、自选列表…）把刷新回调注册进去，
  // 它每 60 秒跑一遍；导出的 Ew() 立即全跑一遍（就是个股页「刷新」按钮）。模块不挂在 window 上，
  // 借 webpack 的 chunk 回调拿到 __webpack_require__，按导出特征找到它。
  var poller;
  function sitePoller() {
    if (poller !== undefined) return poller;
    var chunk = window.webpackChunk_futu_official_quote_client, req = null;
    if (!chunk || !rootVm()) return null;
    poller = null;
    try {
      chunk.push([['fa-poller-' + Date.now()], {}, function (r) { req = r; }]);
      var ids = Object.keys((req && req.m) || {}), sig = /\\bEw:function[\\s\\S]*\\bqk:function[\\s\\S]*\\bxH:function/;
      ids.sort(function (a, b) { return (b === '39377') - (a === '39377'); });
      for (var i = 0; i < ids.length; i++) {
        var src = Function.prototype.toString.call(req.m[ids[i]]);
        if (src.length < 3000 && sig.test(src) && /6e4/.test(src)) {
          var mod = req(ids[i]);
          if (mod && typeof mod.Ew === 'function') { poller = mod; break; }
        }
      }
    } catch (e) {
      console.error(e);
    }
    return poller;
  }

  window.__faRefresh = function () {
    if (window.__faRole === 'watch') {
      var store = watchStore();
      if (!local.on && store && store.list.length && document.querySelector('section.watchlist-modal')) store.fresh();
      return 'watch';
    }
    var p = sitePoller();
    if (p) p.Ew();
    return p ? 'site' : 'none';
  };

  // 市场页榜单等处的个股链接是 target="_blank"，在右侧打开而不是弹新窗口
  document.addEventListener('click', function (e) {
    if (window.__faRole !== 'detail' || e.defaultPrevented || e.button !== 0 ||
        e.ctrlKey || e.metaKey || e.shiftKey) return;
    var a = e.target.closest && e.target.closest('a[target="_blank"][href]');
    if (!a || a.host !== location.host) return;
    e.preventDefault();
    console.info('__FA_NAV__' + a.href);
  });

  // 富途网关限流时接口返回 HTML「访问频繁」页面而不是 JSON，图表等模块会直接空白
  var blockedAt = 0;
  var xhrOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    if (/\\/quote-api\\//.test(url)) {
      this.addEventListener('load', function () {
        if (!/json/.test(this.getResponseHeader('content-type') || '')) blockedAt = Date.now();
      });
    }
    return xhrOpen.apply(this, arguments);
  };

  // 未登录时点爱心 / 添加自选等按钮，站点会调用 $goLogin 弹出精简版注册框（gold-flow，
  // 在被隐藏的 #header 里）。用户刚点击过才算登录意图，交给 Python 打开完整登录页；
  // 没有点击就弹出来的是营销弹窗，保持隐藏即可。
  var lastClick = 0, loginRequested = false;
  document.addEventListener('click', function (e) {
    if (e.isTrusted) lastClick = Date.now();
  }, true);
  setInterval(function () {
    if (document.querySelector('.official-gold-flow.show-modal') && Date.now() - lastClick < 3000) {
      loginRequested = true;
      lastClick = 0;
    }
  }, 300);

  window.__faState = function () {
    var common = window.__COMMON || {};
    var text = document.body ? document.body.innerText.slice(0, 200) : '';
    var modal = document.querySelector('section.watchlist-modal');
    var wantLogin = loginRequested;
    loginRequested = false;
    return {
      loginRequested: wantLogin,
      path: location.pathname,
      watch: !!modal,
      watchBlank: !!modal && !local.on && !modal.querySelector('.list-item, .loading, .empty-main'),
      blocked: Date.now() - blockedAt < 5000,
      blockedAt: blockedAt,
      nameRight: (function () {
        var col = modal && modal.querySelector('.list-item .col.name');
        return col ? Math.ceil(col.getBoundingClientRect().right) : 0;
      })(),
      ready: !!document.querySelector('section.tool-bar'),
      isLogin: common.isLogin === 'true',
      uid: common.uid || '',
      waf: /"code"\\s*:\\s*-12011/.test(text)
    };
  };
})();
""" % {"css": json.dumps(PAGE_CSS), "role_css": json.dumps({"watch": WATCH_CSS, "detail": DETAIL_CSS})}

STATE_JS = "JSON.stringify(window.__faState ? window.__faState() : null)"


def detail_url(code: str) -> str:
    return f"{BASE_URL}/stock/{code}"


def login_url(target: str) -> str:
    query = urllib.parse.urlencode({"type": "login", "target": target, "lang": "zh-cn"})
    return f"https://{PASSPORT_HOST}/?{query}"


def normalize_code(text: str) -> str:
    """TSLA -> TSLA-US，700 -> 00700-HK，NVDA.US -> NVDA-US"""
    s = text.strip().upper().replace(".", "-")
    if not s:
        return ""
    if "-" in s:
        return s
    if s.isdigit():
        return s.zfill(5) + "-HK"
    return s + "-US"


def is_futu_page(url: QUrl) -> bool:
    return url.host() == "www.futunn.com"


def is_stock_page(url: QUrl) -> bool:
    return is_futu_page(url) and bool(STOCK_PATH_RE.match(url.path()))


def is_allowed(url: QUrl) -> bool:
    """应用内允许打开的地址：登录页，或 www.futunn.com 的个股页、市场行情页。"""
    if url.host() == PASSPORT_HOST:
        return True
    return is_stock_page(url) or (is_futu_page(url) and bool(MARKET_PATH_RE.match(url.path())))


def read_profile_cookies(db: Path) -> dict[tuple[str, str], str]:
    if not db.exists():
        return {}
    now = int((time.time() + CHROMIUM_EPOCH_OFFSET) * 1_000_000)
    try:
        con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=1)
        try:
            rows = con.execute("SELECT host_key, name, value, expires_utc FROM cookies").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return {}
    jar = {}
    for host, name, value, expires in rows:
        domain = host.lstrip(".")
        if domain in COOKIE_DOMAINS and value and (not expires or expires > now):
            jar[(domain, name)] = value
    return jar


class PopupWindow(QWidget):
    """登录页里的第三方登录（微信 / QQ / Apple 等）会 window.open 授权页，
    并依赖 window.opener 回传结果，所以要给它一个真正的弹出窗口。"""

    def __init__(self, profile: QWebEngineProfile, parent: QWidget, on_return):
        super().__init__(parent, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(560, 720)
        self._on_return = on_return
        self.view = QWebEngineView(self)
        self.page = QWebEnginePage(profile, self.view)
        self.view.setPage(self.page)
        self.page.windowCloseRequested.connect(self.close)
        self.page.urlChanged.connect(self._check_return)
        self.view.titleChanged.connect(self.setWindowTitle)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def _check_return(self, url: QUrl):
        # 授权完成后若跳回了 futunn 站点（而不是自行关闭），把结果交回主窗口
        if is_futu_page(url):
            self.page.urlChanged.disconnect(self._check_return)
            self._on_return(url)
            self.close()


def page_script(name: str, source: str) -> QWebEngineScript:
    script = QWebEngineScript()
    script.setName(name)
    script.setSourceCode(source)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(False)
    return script


class FutuPage(QWebEnginePage):
    """role="watch" 是左侧自选栏，其中的任何跳转都转给右侧；role="detail" 是右侧个股详情 / 市场行情 / 登录页，
    在 www.futunn.com 上只允许停留在个股页和市场行情页，其它链接交给系统浏览器，登录流程不做限制。"""

    OPEN_PREFIX = "__FA_OPEN__"
    NAV_PREFIX = "__FA_NAV__"
    LOCAL_DEL_PREFIX = "__FA_LOCAL_DEL__"
    LOCAL_MOVE_PREFIX = "__FA_LOCAL_MOVE__"

    def __init__(self, profile, window, role: str):
        super().__init__(profile, window)
        self._window = window
        self.role = role
        self._popups = []
        self.scripts().insert(page_script("futu-role", f"window.__faRole = {json.dumps(role)};"))
        # 挂在页面上而不是 profile 上：页面进程崩溃重启后，Qt 只会给新进程重新注入页面级脚本
        self.scripts().insert(page_script("futu-app", PAGE_JS))

    def _in_login_flow(self) -> bool:
        return not is_futu_page(self.url())

    def javaScriptConsoleMessage(self, level, message, line, source):
        if self.role == "watch" and message.startswith(self.OPEN_PREFIX):
            try:
                data = json.loads(message[len(self.OPEN_PREFIX):])
                path, item = str(data["path"]), data.get("item")
            except (ValueError, KeyError, TypeError, AttributeError):
                return
            self._window.open_path(path, item if isinstance(item, dict) else None)
        elif self.role == "watch" and message.startswith(self.LOCAL_DEL_PREFIX):
            stock_id = message[len(self.LOCAL_DEL_PREFIX):]
            QTimer.singleShot(0, lambda: self._window.remove_local(stock_id))
        elif self.role == "watch" and message.startswith(self.LOCAL_MOVE_PREFIX):
            try:
                order = json.loads(message[len(self.LOCAL_MOVE_PREFIX):])
            except ValueError:
                return
            self._window.reorder_local(order)
        elif self.role == "detail" and message.startswith(self.NAV_PREFIX):
            self._window.route_url(QUrl(message[len(self.NAV_PREFIX):]))

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame and nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if self.role == "watch" or (not self._in_login_flow() and not is_allowed(url)):
                self._window.route_url(url)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def createWindow(self, _type):
        if self.role == "detail" and self._in_login_flow():
            window = PopupWindow(self.profile(), self._window, self._window.popup_returned)
            window.show()
            return window.page

        popup = QWebEnginePage(self.profile(), self)
        self._popups.append(popup)

        def release():
            if popup in self._popups:
                self._popups.remove(popup)
                popup.deleteLater()

        def route(url: QUrl):
            if url.isEmpty() or url.scheme() == "about":
                return
            popup.urlChanged.disconnect(route)
            self._window.route_url(url)
            release()

        popup.urlChanged.connect(route)
        QTimer.singleShot(30000, release)  # 一直停在空白页、没有跳转的弹窗不留在内存里
        return popup


class ClipBox(QWidget):
    """只露出子控件左边一部分：子控件保持 inner_width 宽，容器变窄时被右侧遮住，而不是跟着重排"""

    def __init__(self, child: QWidget, inner_width: int, parent=None):
        super().__init__(parent)
        self.child = child
        self.inner_width = inner_width
        child.setParent(self)

    def set_inner_width(self, width: int):
        self.inner_width = width
        self._fit()

    def resizeEvent(self, event):
        self._fit()
        super().resizeEvent(event)

    def _fit(self):
        self.child.setGeometry(0, 0, max(self.inner_width, self.width()), self.height())


class MainWindow(QMainWindow):
    api_done = pyqtSignal(object, bool)
    local_resolved = pyqtSignal(str, object)
    local_quotes_done = pyqtSignal(object, str)
    local_info_done = pyqtSignal(object, object, str)

    def __init__(self, profile: QWebEngineProfile, code: str):
        super().__init__()
        self.profile = profile
        self.code = code
        self.detail_path = urllib.parse.urlsplit(detail_url(code)).path  # 期货等不在 /stock/ 下，重载时用原路径
        self.local = LocalWatchlist()
        self.local_quotes: dict[str, dict] = {}
        self.local_busy = False
        self.local_info_checked = False
        self.left_mode = "local"  # local：本地自选；site：站点的热门自选 / 我的自选
        self.watch_blank_polls = 0
        self.cookies: dict[tuple[str, str], str | None] = {}
        self.use_disk_cookies = True
        self.states: dict[str, dict] = {"watch": {}, "detail": {}}
        self.waf_retries = {"watch": 0, "detail": 0}
        self.awaiting_login = False
        self.was_login: bool | None = None
        self.closing = False
        self.load_failures = {"watch": 0, "detail": 0}

        self.views: dict[str, QWebEngineView] = {}
        for role in ("watch", "detail"):
            view = QWebEngineView(self)
            view.setPage(FutuPage(profile, self, role))
            view.loadFinished.connect(lambda ok, r=role: self._on_load_finished(r, ok))
            view.page().renderProcessTerminated.connect(
                lambda status, code, r=role: self._on_render_terminated(r, status, code))
            view.page().loadingChanged.connect(lambda info, r=role: self._on_loading_changed(r, info))
            self.views[role] = view
        self.watch_view = self.views["watch"]
        self.detail_view = self.views["detail"]

        # 自选列表没展开详情时，右侧用空白占位，列表保持原宽度不被拉伸
        self.blank = QWidget(self)
        self.blank.setAutoFillBackground(True)
        palette = self.blank.palette()
        palette.setColor(self.blank.backgroundRole(), QColor("#ffffff"))
        self.blank.setPalette(palette)

        # 列表按站点弹窗的原始宽度排版，全部列都显示且不拉伸，右侧留白；
        # 展开详情时左侧只露出名称列：列表本身仍是 left_width 宽，其余部分被详情遮住
        self.left_width = LIST_WIDTH
        self.peek_width = 0  # 0 表示按页面里名称列的实际宽度
        self.watch_box = ClipBox(self.watch_view, self.left_width, self)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        for i, widget in enumerate((self.watch_box, self.detail_view, self.blank)):
            self.splitter.addWidget(widget)
            self.splitter.setStretchFactor(i, 0 if widget is self.watch_box else 1)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        self.setCentralWidget(self.splitter)
        self.resize(1440, 900)
        # 窗口大小、位置、是否最大化：上次关闭时的样子。存在项目目录，不进注册表；
        # 上次所在的显示器拔掉了的话 restoreGeometry 会把窗口挪回可见的屏幕
        self.settings = QSettings(str(PROFILE_DIR / "window.ini"), QSettings.Format.IniFormat)
        geometry = self.settings.value("geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        # page 是工具栏当前标签：local / site 为自选列表（点股票才在右侧展开详情），market 为市场页（独占）
        self.page = "local"
        self._layout(detail=False)
        self.setWindowTitle("富途牛牛")

        self._build_toolbar()
        self.status = QLabel()
        self.statusBar().addPermanentWidget(self.status)

        store = profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie_added)
        store.cookieRemoved.connect(self._on_cookie_removed)

        self.detail_view.titleChanged.connect(lambda t: self.setWindowTitle(t or "富途牛牛"))
        self.api_done.connect(self._on_api_done)
        self.local_resolved.connect(self._on_local_resolved)
        self.local_quotes_done.connect(self._on_local_quotes)
        self.local_info_done.connect(self._on_local_info)

        self.poll = QTimer(self, interval=1000, timeout=self._poll_state)
        self.poll.start()
        self.refresh_paused_until = 0.0
        self.block_strikes: list[float] = []
        self.seen_blocked: dict[str, int] = {}
        self.local_refreshed_at = 0.0
        self.refresh_timer = QTimer(self, interval=AUTO_REFRESH_MS, timeout=self._auto_refresh)
        self.refresh_timer.start()

        # 冷启动时两个视图同时请求，都会拿不到 wafToken 而被网关拦下（-12011）；
        # 先加载右侧，它通过后再加载左侧，超时也照样加载
        self.watch_started = False
        self.detail_view.load(QUrl(detail_url(code)))
        QTimer.singleShot(10000, self._start_watch)
        if self.local.warning:
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "本地自选", self.local.warning))

    def _emit(self, signal: str, *args):
        """后台线程交回结果。窗口关闭后就不再交：此时 C++ 对象可能已经释放，连取信号都会报错"""
        if self.closing:
            return
        with contextlib.suppress(RuntimeError):
            getattr(self, signal).emit(*args)

    def closeEvent(self, event):
        self.closing = True
        self.poll.stop()
        self.refresh_timer.stop()
        with contextlib.suppress(TypeError, RuntimeError):
            self.detail_view.titleChanged.disconnect()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.sync()
        super().closeEvent(event)

    def _start_watch(self):
        if not self.watch_started:
            self.watch_started = True
            self.watch_view.load(QUrl(WATCH_HOST_URL))

    # ---------- UI ----------

    def _build_toolbar(self):
        bar = QToolBar("导航", self)
        bar.setMovable(False)
        bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(bar)

        self.act_back = QAction("←", self, triggered=lambda: self.detail_view.back())
        self.act_local = QAction("本地自选", self, checkable=True, checked=True,
                                 triggered=lambda: self.switch_page("local"))
        self.act_watch = QAction("热门自选", self, checkable=True, triggered=lambda: self.switch_page("site"))
        self.act_market = QAction("美股市场", self, checkable=True, triggered=lambda: self.switch_page("market"))
        self.act_reload = QAction("刷新", self, shortcut=QKeySequence.StandardKey.Refresh,
                                  triggered=self.reload_all)
        bar.addAction(self.act_back)
        bar.addAction(self.act_local)
        bar.addAction(self.act_watch)
        bar.addAction(self.act_market)
        self.detail_view.urlChanged.connect(self._on_detail_url)

        self.local_input = QLineEdit(self)
        self.local_input.setPlaceholderText("添加本地自选：代码，回车")
        self.local_input.setFixedWidth(180)
        self.local_input.returnPressed.connect(self._add_local_input)
        bar.addWidget(self.local_input)
        bar.addSeparator()

        self.code_input = QLineEdit(self)
        self.code_input.setPlaceholderText("代码，如 TSLA / 00700 / NVDA-US，回车打开")
        self.code_input.setFixedWidth(260)
        self.code_input.returnPressed.connect(self._open_input_code)
        bar.addWidget(self.code_input)
        bar.addAction(self.act_reload)
        self.act_auto = QAction(f"{AUTO_REFRESH_MS // 1000}秒刷新", self, checkable=True, checked=True,
                                toolTip=f"每 {AUTO_REFRESH_MS // 1000} 秒刷新行情、分时图和自选列表；"
                                        f"关掉后按 {SLOW_REFRESH_S} 秒刷新")
        bar.addAction(self.act_auto)
        bar.addSeparator()

        self.act_login = QAction("登录", self, triggered=lambda: self._toggle_login())
        self.act_verify = QAction("接口验证", self, triggered=lambda: self.verify_with_token(True))
        bar.addAction(self.act_login)
        bar.addAction(self.act_verify)

    def _open_input_code(self):
        code = normalize_code(self.code_input.text())
        if code:
            self.code_input.clear()
            self.open_path(f"/stock/{code}")

    def reload_all(self):
        for role, view in self.views.items():
            if view.url().path() == "/403":
                view.load(QUrl(WATCH_HOST_URL if role == "watch" else self._detail_url()))
            else:
                view.reload()

    # ---------- 工具栏标签：本地自选 / 热门自选 / 美股市场 ----------

    def switch_page(self, page: str):
        """切换标签后之前展开的右侧详情一并收起：市场页独占整个窗口，自选列表保持原宽度、右侧留白"""
        if page == "market":
            self.page = "market"
            self._layout(detail=True)
            url = self.detail_view.url()
            if not (is_futu_page(url) and MARKET_PATH_RE.match(url.path())):
                self.detail_view.load(QUrl(US_MARKET_URL))
        else:
            changed = page != self.left_mode
            self.page = self.left_mode = page
            self._layout(detail=False)
            if changed:
                self._push_local()
                if page == "local":
                    self._refresh_local_quotes()
        self._sync_tabs()

    def _show_detail(self):
        """打开个股：自选列表页里右侧空白处换成详情，左侧列表不动"""
        if not self.detail_view.isVisible():
            self._layout(detail=True)
            self._update_status()

    def _layout(self, detail: bool):
        list_page = self.page != "market"
        self.watch_box.setVisible(list_page)
        self.detail_view.setVisible(detail)
        self.blank.setVisible(list_page and not detail)
        if list_page:
            self.watch_box.set_inner_width(self.left_width)
            left = self._peek_width() if detail else self.left_width
            rest = max(self.splitter.width() - left, 400)
            self.splitter.setSizes([left, rest if detail else 0, 0 if detail else rest])

    def _peek_width(self) -> int:
        """展开详情时左侧露出的宽度：到名称列右边为止"""
        if self.peek_width:
            return self.peek_width
        name_right = self.states["watch"].get("nameRight") or 0
        return min(name_right + 4, self.left_width) if name_right > 80 else 190

    def _on_splitter_moved(self, *_):
        if not self.watch_box.isVisible():
            return
        if self.detail_view.isVisible():
            self.peek_width = max(self.watch_box.width(), 60)
        else:
            self.left_width = max(self.watch_box.width(), 280)
            self.watch_box.set_inner_width(self.left_width)

    def _sync_tabs(self):
        self.act_local.setChecked(self.page == "local")
        self.act_watch.setChecked(self.page == "site")
        self.act_market.setChecked(self.page == "market")
        self._update_status()

    def _push_local(self):
        on = self.left_mode == "local"
        items = [build_item(e, self.local_quotes.get(e["stockId"])) for e in self.local.entries] if on else []
        js = f"window.__faSetLocal && window.__faSetLocal({json.dumps(on)}, {json.dumps(items, ensure_ascii=False)})"
        self.watch_view.page().runJavaScript(js)

    def _add_local_input(self):
        text = self.local_input.text().strip()
        if not text:
            return
        self.local_input.setEnabled(False)
        self.statusBar().showMessage(f"正在查找 {text} ...")
        client = FutuClient(self._futu_cookies(), self.profile.httpUserAgent())

        def work():
            try:
                result = resolve(client, text)
            except StockNotFound as exc:
                result = str(exc)
            except Exception as exc:  # noqa: BLE001
                result = f"查找 {text} 失败：{exc}"
            self._emit("local_resolved", text, result)

        threading.Thread(target=work, daemon=True).start()

    def _on_local_resolved(self, text: str, result):
        self.local_input.setEnabled(True)
        self.local_input.setFocus()
        if isinstance(result, str):
            self.statusBar().showMessage(result, 6000)
            return
        self.local_input.clear()
        label = f"{result['name']}（{result['stockCode']}.{result['marketLabel']}）"
        try:
            added = self.local.add(result)
        except SaveError as exc:
            QMessageBox.warning(self, "本地自选", f"{label} 没有添加：{exc}\n\nlocal_watchlist.json 保持原样。")
            return
        if added:
            self.statusBar().showMessage(f"已添加到本地自选：{label}", 5000)
        else:
            self.statusBar().showMessage(f"{label} 已在本地自选里", 5000)
        if self.page != "local":
            self.switch_page("local")
        self._push_local()
        self._refresh_local_quotes()

    def remove_local(self, stock_id: str):
        entry = self.local.find(stock_id)
        if not entry:
            return
        label = f"{entry['name']}（{entry['stockCode']}.{entry['marketLabel']}）"
        if QMessageBox.question(self, "本地自选", f"从本地自选删除 {label}？") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.local.remove(stock_id)
        except SaveError as exc:
            QMessageBox.warning(self, "本地自选", f"{label} 没有删除：{exc}\n\nlocal_watchlist.json 保持原样。")
            return
        self.local_quotes.pop(stock_id, None)
        self._push_local()
        self._update_status()

    def _check_local_info(self):
        """每次启动校对一次本地自选的代码、名称、证券类型（一个批量请求），防止股票改名、换代码后还显示旧的。
        要等页面过了网关校验（拿到 wafToken）才能调接口，所以从页面加载完成处触发。"""
        if self.local_info_checked or not self.local.entries:
            return
        self.local_info_checked = True
        client = FutuClient(self._futu_cookies(), self.profile.httpUserAgent())
        ids = [e["stockId"] for e in self.local.entries]

        def work():
            infos, error = [], ""
            try:
                for i in range(0, len(ids), 50):
                    batch = client.stock_infos(ids[i:i + 50])
                    if not isinstance(batch, list):
                        raise ValueError("个股资料接口返回格式不对")
                    infos += batch
            except Exception as exc:  # noqa: BLE001
                error = str(exc) or type(exc).__name__
            self._emit("local_info_done", infos, ids, error)

        threading.Thread(target=work, daemon=True).start()

    def _on_local_info(self, infos: list, ids: list, error: str):
        if error or not infos:
            self.local_info_checked = False  # 这次没查成，什么都不改，下次页面加载完再查
            return
        try:
            changes, missing = self.local.sync(infos, ids)
        except SaveError as exc:
            QMessageBox.warning(self, "本地自选", f"股票资料有更新，但没有保存：{exc}\n\nlocal_watchlist.json 保持原样。")
            return
        if changes:
            self._push_local()
            QMessageBox.information(self, "本地自选", "以下股票的资料在富途有变化，已更新到 local_watchlist.json：\n\n"
                                    + "\n".join(changes))
        if missing:
            self.statusBar().showMessage(f"没有查到 {'、'.join(missing)} 的最新资料（可能已停牌或退市），已原样保留", 10000)

    def reorder_local(self, stock_ids):
        # 在收到消息时同步保存，之后推给页面的行情都按新顺序；无论成败都推一次，让页面和文件保持一致
        try:
            if self.local.reorder(stock_ids):
                self.statusBar().showMessage("已调整本地自选顺序", 3000)
        except SaveError as exc:
            text = f"顺序没有保存：{exc}\n\nlocal_watchlist.json 保持原样，列表已恢复原来的顺序。"
            QTimer.singleShot(0, lambda: QMessageBox.warning(self, "本地自选", text))
        self._push_local()

    def _refresh_local_quotes(self):
        # 页面过了网关校验（拿到 wafToken cookie）之前直接调接口会被拦截
        passed = self.states["watch"].get("ready") or self.states["detail"].get("ready")
        if (self.local_busy or not passed or self.left_mode != "local" or not self.watch_view.isVisible()
                or not self.local.entries):
            return
        self.local_busy = True
        self.local_refreshed_at = time.monotonic()
        client = FutuClient(self._futu_cookies(), self.profile.httpUserAgent())
        entries = list(self.local.entries)

        def work():
            quotes, error = {}, ""
            for e in entries:
                try:
                    quotes[e["stockId"]] = client.stock_quote(e["stockId"], e["marketType"], e["instrumentType"])
                except RateLimited as exc:
                    error = str(exc)
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                    # 断网时每只都要等满超时，后面的就不再试了，下一轮刷新再来
                    error = f"网络连接失败（{getattr(exc, 'reason', exc)}），稍后自动重试"
                    break
                except Exception as exc:  # noqa: BLE001
                    error = f"{e['stockCode']} 行情获取失败：{exc}"
            self._emit("local_quotes_done", quotes, error)

        threading.Thread(target=work, daemon=True).start()

    def _on_local_quotes(self, quotes: dict, error: str):
        self.local_busy = False
        self.local_quotes.update({k: v for k, v in quotes.items() if isinstance(v, dict) and v})
        if error:
            self.statusBar().showMessage(f"本地自选：{error}", 5000)
            if "限流" in error or "频繁" in error:
                self._pause_refresh()
        if self.left_mode == "local":
            self._push_local()

    # ---------- 定时刷新 ----------

    def _auto_refresh(self):
        now = time.monotonic()
        if self.isMinimized() or now < self.refresh_paused_until:
            return
        if not self.act_auto.isChecked():
            if (self.left_mode == "local" and self.watch_view.isVisible()
                    and now - self.local_refreshed_at >= SLOW_REFRESH_S):
                self._refresh_local_quotes()
            return
        js = "window.__faRefresh && window.__faRefresh()"
        if (self.detail_view.isVisible() and self.states["detail"].get("ready")
                and is_futu_page(self.detail_view.url())):
            self.detail_view.page().runJavaScript(js)
        if self.watch_view.isVisible():
            if self.left_mode == "local":
                self._refresh_local_quotes()
            elif is_futu_page(self.watch_view.url()):
                self.watch_view.page().runJavaScript(js)

    def _pause_refresh(self):
        """30 秒内第二次被拦才暂停：冷启动时偶发一次拦截（还没拿到 wafToken）不算限流"""
        now = time.monotonic()
        if now < self.refresh_paused_until:
            return
        self.block_strikes = [t for t in self.block_strikes if now - t < 30] + [now]
        if len(self.block_strikes) >= 2:
            self.block_strikes.clear()
            self.refresh_paused_until = now + RATE_LIMIT_PAUSE_S

    # ---------- 页面切换 ----------

    def open_path(self, path: str, item: dict | None = None):
        """在右侧打开个股。带着自选条目数据且右侧已是个股页时，走站点自己的 stockClick，不整页刷新。"""
        path = urllib.parse.urlsplit(path).path
        m = STOCK_PATH_RE.match(path)
        if not m:
            return
        self._set_detail(m)
        self._show_detail()
        self._update_status()
        url = QUrl(BASE_URL + path)
        if not (item and is_futu_page(self.detail_view.url()) and self.states["detail"].get("ready")):
            self.detail_view.load(url)
            return

        def done(ok):
            if not ok:
                self.detail_view.load(url)

        self.detail_view.page().runJavaScript(f"window.__faGo({json.dumps(item)})", 0, done)

    def _set_detail(self, m: re.Match):
        self.code = urllib.parse.unquote(m.group(2)).upper()
        self.detail_path = m.group(0)

    def _detail_url(self) -> str:
        return BASE_URL + self.detail_path

    def _on_detail_url(self, url: QUrl):
        # 个股页面包屑「美股市场」等跳到市场页：等同于切到「美股市场」标签
        if self.page != "market" and is_futu_page(url) and MARKET_PATH_RE.match(url.path()):
            self.switch_page("market")
        self._update_status()

    def route_url(self, url: QUrl):
        if is_stock_page(url):
            self.open_path(url.path())
        elif is_allowed(url):
            self._show_detail()
            self.detail_view.setUrl(url)
        else:
            QDesktopServices.openUrl(url)

    def popup_returned(self, url: QUrl):
        if is_allowed(url):
            self.route_url(url)
        else:
            self.detail_view.load(QUrl(self._detail_url()))

    def show_login(self):
        self.awaiting_login = True
        self._show_detail()
        self.detail_view.load(QUrl(login_url(self._detail_url())))

    def _toggle_login(self):
        if not self._is_login():
            self.show_login()
            return
        if QMessageBox.question(self, "退出登录", "确定退出当前账号？") != QMessageBox.StandardButton.Yes:
            return
        self.profile.cookieStore().deleteAllCookies()
        self.cookies.clear()
        self.use_disk_cookies = False  # 磁盘上的 Cookies 库要等 Chromium 刷盘后才会清掉
        self.states = {"watch": {}, "detail": {}}
        self.was_login = False
        self.watch_view.load(QUrl(WATCH_HOST_URL))
        self.detail_view.load(QUrl(self._detail_url()))

    # ---------- 页面状态 ----------

    def _is_login(self) -> bool:
        state = self.states["detail"] or self.states["watch"]
        return bool(state.get("isLogin"))

    def _on_load_finished(self, role: str, ok: bool):
        view = self.views[role]
        if ok:
            self.load_failures[role] = 0
        if ok and is_futu_page(view.url()):
            view.page().runJavaScript(STATE_JS, 0, lambda raw: self._after_futu_load(role, raw))

    def _on_loading_changed(self, role: str, info: QWebEngineLoadingInfo):
        # 只管网络层面的失败（断网、DNS、连接被重置、服务端 5xx）；被新的跳转打断（Stopped）、404 之类不重试
        if info.status() != QWebEngineLoadingInfo.LoadStatus.LoadFailedStatus:
            return
        domain = info.errorDomain()
        retryable = domain in (QWebEngineLoadingInfo.ErrorDomain.ConnectionErrorDomain,
                               QWebEngineLoadingInfo.ErrorDomain.DnsErrorDomain,
                               QWebEngineLoadingInfo.ErrorDomain.HttpErrorDomain) or (
            domain == QWebEngineLoadingInfo.ErrorDomain.HttpStatusCodeDomain and info.errorCode() >= 500)
        if retryable:
            self._schedule_recover(role, f"加载失败（{info.errorString() or info.errorCode()}）")

    def _on_render_terminated(self, role: str, status, code: int):
        if status == QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus or self.closing:
            return
        self.states[role] = {}
        self._schedule_recover(role, f"进程意外退出（{status.name}，{code}）", force=True)

    def _recover_url(self, role: str) -> QUrl:
        if role == "watch":
            return QUrl(WATCH_HOST_URL)
        url = self.views[role].url()
        return url if is_allowed(url) else QUrl(self._detail_url())

    def _schedule_recover(self, role: str, reason: str, force: bool = False):
        """加载失败 / 页面进程崩溃后自动重新加载：3、6、12、24、30、30… 秒，网络恢复后自己回来，不用手点刷新。
        force：进程崩溃后页面一直停在「加载中」，不能按 isLoading 判断要不要重载"""
        if self.closing:
            return
        n = self.load_failures[role] = self.load_failures[role] + 1
        delay = min(3 * 2 ** (n - 1), 30)
        name = "左侧列表" if role == "watch" else "右侧页面"
        self.statusBar().showMessage(f"{name}{reason}，{delay} 秒后自动重试", delay * 1000)

        def retry():
            view = self.views[role]
            # 期间已经加载成功（计数清零 / 又失败过一次由那次负责）或者正在加载别的页面，就不打断
            if self.closing or self.load_failures[role] != n or (not force and view.page().isLoading()):
                return
            view.load(self._recover_url(role))

        QTimer.singleShot(delay * 1000, retry)

    def _after_futu_load(self, role: str, raw):
        state = self._parse_state(raw)
        if not state:
            return
        if state["waf"]:
            # 首次访问没有 wafToken 时服务端直接返回 {"code":-12011}，重载即可放行
            if self.waf_retries[role] < 6:
                self.waf_retries[role] += 1
                QTimer.singleShot(1000 * self.waf_retries[role], self.views[role].reload)
            return
        self.waf_retries[role] = 0
        self._apply_state(role, state)
        self._check_local_info()
        if role == "detail":
            self._start_watch()
        elif self.left_mode == "local":
            self._push_local()
            self._refresh_local_quotes()

        # 从未登录变成已登录（右侧登录页跳回、或其它方式登录）：还没刷新登录态的视图重新加载，
        # 左侧就会从「热门自选」切到「我的自选」
        if state["isLogin"] and (self.awaiting_login or self.was_login is False):
            self.awaiting_login = False
            for other, view in self.views.items():
                if other != role and not self.states[other].get("isLogin"):
                    view.reload()
            self.verify_with_token(False)
        self.was_login = state["isLogin"]

    def _poll_state(self):
        for role, view in self.views.items():
            if is_futu_page(view.url()):
                view.page().runJavaScript(STATE_JS, 0, lambda raw, r=role: self._on_state(r, raw))
        self.local.external_change()
        if self.local.notices:
            self.statusBar().showMessage("；".join(self.local.notices), 8000)
            self.local.notices.clear()
            self._push_local()
            self._update_status()

    @staticmethod
    def _parse_state(raw) -> dict | None:
        # 页面进程崩溃后、或注入脚本还没跑的页面上 __faState 不存在，拿到的是 "null"
        try:
            state = json.loads(raw) if isinstance(raw, str) else None
        except ValueError:
            return None
        return state if isinstance(state, dict) else None

    def _on_state(self, role: str, raw):
        state = self._parse_state(raw)
        if state:
            self._apply_state(role, state)

    def _apply_state(self, role: str, state: dict):
        self.states[role] = state
        if state.get("loginRequested") and not state["isLogin"]:
            QTimer.singleShot(0, self.show_login)
        if role == "detail":
            m = STOCK_PATH_RE.match(state.get("path", ""))
            if m:
                self._set_detail(m)
        else:
            self.watch_blank_polls = self.watch_blank_polls + 1 if state.get("watchBlank") else 0
            if self.watch_blank_polls >= 3:
                self.statusBar().showMessage("自选列表加载失败，可能被富途限流（访问频繁），稍后点「刷新」重试", 3000)
        if state.get("path") == "/403":
            self._pause_refresh()
            self.statusBar().showMessage("被富途网关限流（访问频繁，跳到了 403 页），过几分钟后点「←」或「刷新」重试", 5000)
        elif state.get("blocked"):
            if state.get("blockedAt") != self.seen_blocked.get(role):
                self.seen_blocked[role] = state.get("blockedAt")
                self._pause_refresh()
            if time.monotonic() < self.refresh_paused_until:
                self.statusBar().showMessage(
                    f"行情接口被富途网关限流（访问频繁），定时刷新暂停 {RATE_LIMIT_PAUSE_S} 秒；图表可能空白，稍后点「刷新」重试", 5000)
        self._update_status()

    def _update_status(self):
        login = self._is_login()
        self.act_login.setText("退出登录" if login else "登录")
        self.act_watch.setText("我的自选" if login else "热门自选")
        uid = (self.states["detail"] or self.states["watch"]).get("uid", "")
        if self.left_mode == "local":
            who = f"本地自选 {len(self.local.entries)} 只" + (f" · 已登录 uid {uid}" if login else " · 未登录")
        else:
            who = f"已登录 uid {uid}（我的自选）" if login else "未登录（热门自选）"
        path = self.detail_view.url().path()
        if not self.detail_view.isVisible():
            where = ""
        elif MARKET_PATH_RE.match(path):
            where = "市场行情 " + path
        else:
            where = self.code
        self.status.setText(f"{who}  ·  {where}" if where else who)

    # ---------- 用 cookie + quote-token 直接调接口 ----------

    def _on_cookie_added(self, cookie):
        domain = cookie.domain().lstrip(".")
        if domain in COOKIE_DOMAINS:
            self.cookies[(domain, bytes(cookie.name()).decode())] = bytes(cookie.value()).decode()

    def _on_cookie_removed(self, cookie):
        domain = cookie.domain().lstrip(".")
        if domain in COOKIE_DOMAINS:
            self.cookies[(domain, bytes(cookie.name()).decode())] = None

    def _futu_cookies(self) -> dict[str, str]:
        # loadAllCookies() 在 Qt 6.11 下不会回放已持久化的 cookie，历史 cookie 直接读 profile 的
        # SQLite（明文存储），本次运行里的增删以 cookieAdded/cookieRemoved 为准。
        jar = read_profile_cookies(PROFILE_DIR / "storage" / "Cookies") if self.use_disk_cookies else {}
        jar.update(self.cookies)
        merged = {n: v for (d, n), v in jar.items() if d == "futunn.com" and v is not None}
        merged.update({n: v for (d, n), v in jar.items() if d == "www.futunn.com" and v is not None})
        return merged

    def verify_with_token(self, show_dialog: bool):
        client = FutuClient(self._futu_cookies(), self.profile.httpUserAgent())

        def work():
            try:
                result = {"list": client.watch_list(), "ids": client.watch_ids()}
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
            self._emit("api_done", result, show_dialog)

        self.statusBar().showMessage("正在用 cookie + quote-token 请求 get-watch-list ...")
        threading.Thread(target=work, daemon=True).start()

    def _on_api_done(self, result: dict, show_dialog: bool):
        if "error" in result:
            msg = f"接口请求失败：{result['error']}"
            self.statusBar().showMessage(msg, 8000)
            if show_dialog:
                QMessageBox.warning(self, "接口验证", msg)
            return
        res = result["list"]
        data = res.get("data") or {}
        items = data.get("list") or []
        kind = "我的自选" if result["ids"] else "热门自选（未登录或自选为空）"
        summary = f"get-watch-list code={res.get('code')}，{kind}，共 {data.get('allCount', len(items))} 只"
        self.statusBar().showMessage(summary, 8000)
        if show_dialog:
            lines = [f"{i['stockCode']:<10}{i['name']}  {i.get('price', '')}  {i.get('changeRatio', '')}"
                     for i in items[:20]]
            QMessageBox.information(self, "接口验证", summary + "\n\n" + "\n".join(lines))


def remove_empty_dirs(path: Path, top: Path):
    """从 path 往上删空目录，最多删到 top（含）"""
    try:
        path.relative_to(top)
    except ValueError:
        return
    try:
        while path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            if path == top:
                break
            path = path.parent
    except OSError:
        pass


def create_profile(app: QApplication) -> QWebEngineProfile:
    PROFILE_DIR.mkdir(exist_ok=True)
    profile = QWebEngineProfile("futu", app)
    # 构造时 Qt 已在 AppData\Roaming\<应用名>\QtWebEngine\futu 建了空的默认目录（PyQt6 不能用
    # QWebEngineProfileBuilder 预先指定路径），改到项目目录后把它和变空的上级目录删掉
    default_dir = Path(profile.persistentStoragePath())
    profile.setPersistentStoragePath(str(PROFILE_DIR / "storage"))
    profile.setCachePath(str(PROFILE_DIR / "cache"))
    remove_empty_dirs(default_dir, Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)))
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
    profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")
    # 富途网关会拦截「UA 声称是 Chrome、TLS 指纹却不是正式版 Chrome」的请求（QtWebEngine 属于这种），
    # 接口一律返回「访问频繁」页面。去掉 Chrome/x 标识、如实保留 QtWebEngine 即可正常访问。
    ua = re.sub(r"Chrome/\S+\s*", "", profile.httpUserAgent())
    profile.setHttpUserAgent(f"{ua} {APP_UA_TOKEN}")
    return profile


def use_local_temp():
    """Chromium 和 Python 的临时文件都放进 .qt_profile\\tmp（子进程 QtWebEngineProcess 继承环境变量），
    启动时清掉上次残留的"""
    tmp = PROFILE_DIR / "tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    os.environ["TMP"] = os.environ["TEMP"] = str(tmp)


def log_uncaught_exceptions():
    """PyQt6 默认在槽函数里遇到未捕获的异常就终止整个程序。改成写进日志（双击 exe 启动时是 .qt_profile/app.log）
    后继续运行：本地自选每次保存都是原子的，某个操作中途出错不会留下写坏的文件，页面下次推送时会按文件重新显示。"""
    logged = 0

    def hook(exc_type, exc, tb):
        nonlocal logged
        logged += 1
        if logged > 50 or not sys.stderr:  # 同一个错误反复出现时日志不会无限增长
            return
        try:
            print(time.strftime("%Y-%m-%d %H:%M:%S"), "未捕获的异常：", file=sys.stderr)
            traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
        except Exception:  # noqa: BLE001  磁盘满等写不了日志时也不能再抛
            pass

    sys.excepthook = hook


def use_own_taskbar_icon():
    """任务栏默认按进程（pythonw.exe）分组并显示 Python 图标；给进程设自己的 AppUserModelID，
    任务栏才会单独成组、显示窗口图标。只作用于本进程，不写注册表。"""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Futunn.FutuWatchlist")
    except (AttributeError, OSError):
        pass


def main():
    parser = argparse.ArgumentParser(description="富途牛牛 左侧自选栏 + 右侧个股详情")
    parser.add_argument("--code", default=DEFAULT_CODE, help="初始个股代码，如 TSLA-US、00700-HK")
    args = parser.parse_args()

    PROFILE_DIR.mkdir(exist_ok=True)
    # 两个实例共用同一份 .qt_profile 会互相锁住浏览器数据。先拿锁：第二个实例不能清空正在运行那个的日志和临时目录
    lock = QLockFile(str(PROFILE_DIR / "app.lock"))
    first = lock.tryLock(100)
    if first:
        if sys.stderr is None:  # pythonw 启动（双击 exe）没有控制台，报错写进日志
            log = PROFILE_DIR / "app.log"
            with contextlib.suppress(OSError):  # 上次的日志留一份，崩溃后重启也还能看到原因
                if log.stat().st_size:
                    os.replace(log, PROFILE_DIR / "app.prev.log")
            sys.stdout = sys.stderr = open(log, "w", encoding="utf-8", buffering=1)
        use_local_temp()
    log_uncaught_exceptions()
    use_own_taskbar_icon()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DisableShaderDiskCache)  # 否则写 AppData\Local\...\cache
    app = QApplication(sys.argv)
    app.setApplicationName("FutuWatchlist")
    if ICON_FILE.exists():
        app.setWindowIcon(QIcon(str(ICON_FILE)))
    if not first:
        QMessageBox.information(None, "富途牛牛", "程序已经在运行了。")
        return

    window = MainWindow(create_profile(app), normalize_code(args.code) or DEFAULT_CODE)
    window.show()
    code = app.exec()
    # 先释放窗口（连同里面的网页），再随 app 释放 profile：顺序反了 Chromium 可能来不及把 cookie 等写盘
    sip.delete(window)
    sys.exit(code)


if __name__ == "__main__":
    main()
