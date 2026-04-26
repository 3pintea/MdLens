from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MdLens</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --line: #d9dee7;
      --text: #20242c;
      --muted: #667085;
      --accent: #0f766e;
      --accent-dark: #0b4f49;
      --accent-soft: #e2f4f1;
      --focus: #2563eb;
      --code: #f0f3f7;
      --danger: #b42318;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      letter-spacing: 0;
    }

    button, input { font: inherit; }

    .shell {
      display: grid;
      grid-template-columns: var(--sidebar-width, 320px) 6px minmax(0, 1fr);
      grid-template-rows: 58px minmax(0, 1fr);
      min-height: 100vh;
    }

    .topbar {
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
      padding: 0 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }

    .brand {
      font-size: 17px;
      font-weight: 750;
      white-space: nowrap;
    }

    .root-control {
      display: grid;
      grid-template-columns: minmax(180px, 480px) auto;
      align-items: center;
      gap: 8px;
      min-width: 260px;
      flex: 0 1 532px;
      margin-left: auto;
    }

    .root-input {
      min-width: 0;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      color: var(--text);
      background: #fff;
      outline: none;
    }

    .root-input:focus {
      border-color: var(--focus);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.13);
    }

    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .tool-button {
      min-height: 32px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 12px;
      background: #fff;
      color: #344054;
      cursor: pointer;
      font-weight: 650;
      white-space: nowrap;
    }

    .tool-button:hover { background: #f1f4f8; }
    .tool-button:disabled { cursor: wait; opacity: 0.65; }

    .tool-button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }

    .tool-button.primary:hover { background: var(--accent-dark); }

    .tool-button.top-action {
      width: 64px;
      padding: 0;
      text-align: center;
    }

    .sidebar {
      min-height: 0;
      background: var(--panel);
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
    }

    .search {
      padding: 12px;
    }

    .search input {
      width: 100%;
      height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      color: var(--text);
      background: #fff;
      outline: none;
    }

    .search input:focus {
      border-color: var(--focus);
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.13);
    }

    .side-actions {
      display: flex;
      gap: 8px;
      padding: 10px 12px;
    }

    .side-actions .tool-button {
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .splitter {
      min-width: 6px;
      background: linear-gradient(90deg, transparent, var(--line), transparent);
      cursor: col-resize;
    }

    .splitter:hover,
    .splitter.dragging {
      background: linear-gradient(90deg, transparent, var(--accent), transparent);
    }

    .tree {
      min-height: 0;
      overflow: auto;
      padding: 10px 8px 18px;
      font-size: 14px;
    }

    .tree details { margin: 1px 0; }

    .tree summary {
      cursor: pointer;
      border-radius: 5px;
      padding: 5px 6px;
      color: #344054;
      overflow-wrap: anywhere;
    }

    .tree summary:hover { background: #f1f4f8; }

    .children {
      margin-left: 14px;
      border-left: 1px solid #e5e9f0;
      padding-left: 6px;
    }

    .file-button {
      display: block;
      width: 100%;
      min-height: 30px;
      margin: 1px 0;
      border: 0;
      border-radius: 5px;
      padding: 5px 7px;
      text-align: left;
      color: var(--text);
      background: transparent;
      cursor: pointer;
      overflow-wrap: anywhere;
    }

    .file-button:hover { background: #f1f4f8; }

    .file-button.active {
      background: var(--accent-soft);
      color: var(--accent-dark);
      font-weight: 650;
    }

    .path {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 400;
      overflow-wrap: anywhere;
    }

    .main {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }

    .docbar {
      min-width: 0;
      padding: 14px 28px 12px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }

    .docbar h1 {
      margin: 0;
      font-size: 20px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }

    .docbar p {
      margin: 3px 0 0;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }

    .content-wrap {
      min-height: 0;
      overflow: auto;
      padding: 28px;
    }

    .markdown-body {
      max-width: 980px;
      margin: 0 auto;
      line-height: 1.75;
      font-size: 16px;
      overflow-wrap: anywhere;
    }

    .empty { color: var(--muted); }
    .error { color: var(--danger); }

    .markdown-body h1,
    .markdown-body h2,
    .markdown-body h3 {
      line-height: 1.3;
      margin: 1.5em 0 0.55em;
    }

    .markdown-body h1:first-child,
    .markdown-body h2:first-child,
    .markdown-body h3:first-child { margin-top: 0; }

    .markdown-body p,
    .markdown-body ul,
    .markdown-body ol,
    .markdown-body blockquote,
    .markdown-body pre,
    .markdown-body table { margin: 0.8em 0; }

    .markdown-body a { color: #075985; }

    .markdown-body code {
      border-radius: 4px;
      padding: 0.12em 0.32em;
      background: var(--code);
      font-family: Consolas, "Liberation Mono", monospace;
      font-size: 0.92em;
    }

    .markdown-body pre {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #101828;
      color: #f8fafc;
    }

    .markdown-body pre code {
      padding: 0;
      background: transparent;
      color: inherit;
    }

    .markdown-body blockquote {
      margin-left: 0;
      border-left: 4px solid var(--line);
      padding-left: 14px;
      color: #475467;
    }

    .markdown-body table {
      width: 100%;
      border-collapse: collapse;
      display: block;
      overflow-x: auto;
    }

    .markdown-body th,
    .markdown-body td {
      border: 1px solid var(--line);
      padding: 8px 10px;
    }

    .markdown-body th { background: #eef2f7; }

    .markdown-body img {
      max-width: 100%;
      height: auto;
      border-radius: 6px;
    }

    @media (max-width: 940px) {
      .root-control { grid-template-columns: minmax(160px, 1fr) auto; }
    }

    @media (max-width: 760px) {
      .shell {
        grid-template-columns: 1fr;
        grid-template-rows: auto 44vh minmax(0, 1fr);
      }

      .topbar {
        align-items: stretch;
        flex-wrap: wrap;
        padding: 10px 12px;
      }

      .brand { width: 100%; }
      .root-control { min-width: 0; width: calc(100% - 72px); }
      .toolbar { margin-left: auto; }
      .tool-button { padding: 0 10px; }
      .sidebar {
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
      .splitter { display: none; }
      .docbar { padding: 12px 16px; }
      .content-wrap { padding: 18px 16px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="brand">MdLens</div>
      <form class="root-control" id="root-form">
        <input class="root-input" id="root-input" type="text" placeholder="Folder path or repository URL" autocomplete="off">
        <button class="tool-button primary top-action" id="switch-folder" type="submit" title="Switch source">Go</button>
      </form>
      <div class="toolbar">
        <button class="tool-button top-action" id="refresh-button" type="button" title="Rebuild index">Sync</button>
      </div>
    </header>
    <aside class="sidebar">
      <div class="search">
        <input id="search-input" type="search" placeholder="Search" autocomplete="off">
      </div>
      <div class="side-actions">
        <button class="tool-button" id="expand-all" type="button" title="Expand all folders">Expand</button>
        <button class="tool-button" id="collapse-all" type="button" title="Collapse all folders">Collapse</button>
      </div>
      <nav class="tree" id="tree"></nav>
    </aside>
    <div class="splitter" id="splitter" aria-hidden="true"></div>
    <main class="main">
      <div class="docbar">
        <h1 id="doc-title">MdLens</h1>
        <p id="doc-path"></p>
      </div>
      <div class="content-wrap">
        <article class="markdown-body empty" id="content"></article>
      </div>
    </main>
  </div>
  <script>
    const messages = {
      selectFile: "\u30d5\u30a1\u30a4\u30eb\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
      loadFailed: "\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002",
      noResult: "\u8a72\u5f53\u306a\u3057",
      syncing: "Syncing",
      syncFailed: "\u540c\u671f\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002",
      switching: "Switching",
      switchFailed: "\u30d5\u30a9\u30eb\u30c0\u306e\u5207\u308a\u66ff\u3048\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002",
      enterFolder: "\u30d5\u30a9\u30eb\u30c0\u30d1\u30b9\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
      apiUnavailable: "Cannot reach the MdLens API. Open the page from the running server URL and reload.",
    };

    const state = {
      files: [],
      activeId: null,
      root: "",
      searchTimer: 0,
    };

    const shellEl = document.querySelector(".shell");
    const splitterEl = document.getElementById("splitter");
    const treeEl = document.getElementById("tree");
    const contentEl = document.getElementById("content");
    const titleEl = document.getElementById("doc-title");
    const pathEl = document.getElementById("doc-path");
    const searchInput = document.getElementById("search-input");
    const rootForm = document.getElementById("root-form");
    const rootInput = document.getElementById("root-input");
    const switchFolderButton = document.getElementById("switch-folder");
    const refreshButton = document.getElementById("refresh-button");
    const expandAllButton = document.getElementById("expand-all");
    const collapseAllButton = document.getElementById("collapse-all");

    const savedSidebarWidth = Number(localStorage.getItem("mdlens.sidebarWidth"));
    if (savedSidebarWidth) {
      shellEl.style.setProperty("--sidebar-width", `${savedSidebarWidth}px`);
    }

    function makeNode() {
      return { dirs: new Map(), files: [] };
    }

    function buildTree(files) {
      const root = makeNode();
      for (const file of files) {
        const parts = file.rel_path.split("/");
        let node = root;
        for (const part of parts.slice(0, -1)) {
          if (!node.dirs.has(part)) node.dirs.set(part, makeNode());
          node = node.dirs.get(part);
        }
        node.files.push(file);
      }
      return root;
    }

    function fileButton(file) {
      const button = document.createElement("button");
      button.className = "file-button";
      button.type = "button";
      button.dataset.id = file.id;
      button.textContent = file.title || file.name;
      button.title = file.rel_path;
      button.addEventListener("click", () => loadFile(file.id));
      if (state.activeId === file.id) button.classList.add("active");
      return button;
    }

    function renderNode(node, isRoot = false) {
      const fragment = document.createDocumentFragment();
      const entries = [...node.dirs.entries()].sort((a, b) => a[0].localeCompare(b[0]));

      for (const [dirName, child] of entries) {
        const details = document.createElement("details");
        details.open = isRoot;
        const summary = document.createElement("summary");
        summary.textContent = dirName;
        details.appendChild(summary);
        const children = document.createElement("div");
        children.className = "children";
        children.appendChild(renderNode(child));
        details.appendChild(children);
        fragment.appendChild(details);
      }

      for (const file of node.files) {
        fragment.appendChild(fileButton(file));
      }

      return fragment;
    }

    function renderTree() {
      treeEl.replaceChildren(renderNode(buildTree(state.files), true));
      updateActiveButton();
    }

    function setAllDetails(open) {
      for (const details of treeEl.querySelectorAll("details")) {
        details.open = open;
      }
    }

    function updateActiveButton() {
      for (const button of document.querySelectorAll(".file-button")) {
        button.classList.toggle("active", Number(button.dataset.id) === state.activeId);
      }
    }

    function setPlaceholder(message = messages.selectFile, isError = false) {
      titleEl.textContent = "MdLens";
      pathEl.textContent = "";
      contentEl.className = isError ? "markdown-body empty error" : "markdown-body empty";
      contentEl.textContent = message;
    }

    function applyTreeData(data) {
      state.files = data.files || [];
      state.root = data.root || "";
      rootInput.value = state.root;
    }

    async function fetchJson(url, options = {}, fallbackMessage = messages.loadFailed) {
      let response;
      try {
        response = await fetch(url, options);
      } catch (_error) {
        throw new Error(`${messages.apiUnavailable} Current page: ${location.origin}`);
      }

      let data = {};
      try {
        data = await response.json();
      } catch (_error) {
        if (response.ok) return data;
        throw new Error(`${fallbackMessage} (${response.status})`);
      }

      if (!response.ok) {
        throw new Error(data.detail || data.error || `${fallbackMessage} (${response.status})`);
      }
      return data;
    }

    async function loadTree(selectInitial = true) {
      const data = await fetchJson("/api/tree", {}, messages.loadFailed);
      applyTreeData(data);

      if (searchInput.value.trim()) {
        await search(searchInput.value);
      } else {
        renderTree();
      }

      if (!selectInitial) return;
      const params = new URLSearchParams(location.search);
      const initialId = Number(params.get("id")) || state.activeId || (state.files[0] && state.files[0].id);
      if (initialId) await loadFile(initialId, true);
      else setPlaceholder();
    }

    async function loadFile(id, replaceOnly = false) {
      let data;
      try {
        data = await fetchJson(`/api/file?id=${encodeURIComponent(id)}`, {}, messages.loadFailed);
      } catch (error) {
        setPlaceholder(error.message, true);
        return;
      }
      state.activeId = data.id;
      titleEl.textContent = data.title || data.name;
      pathEl.textContent = data.path;
      contentEl.className = "markdown-body";
      contentEl.innerHTML = data.html;
      updateActiveButton();
      if (!replaceOnly) {
        history.replaceState(null, "", `?id=${encodeURIComponent(data.id)}`);
      }
    }

    function renderResults(results) {
      const fragment = document.createDocumentFragment();
      if (!results.length) {
        const empty = document.createElement("div");
        empty.className = "path";
        empty.textContent = messages.noResult;
        fragment.appendChild(empty);
      }
      for (const file of results) {
        const button = fileButton(file);
        const path = document.createElement("span");
        path.className = "path";
        path.textContent = file.rel_path;
        button.appendChild(path);
        fragment.appendChild(button);
      }
      treeEl.replaceChildren(fragment);
      updateActiveButton();
    }

    async function search(query) {
      if (!query.trim()) {
        renderTree();
        return;
      }
      const data = await fetchJson(`/api/search?q=${encodeURIComponent(query)}`, {}, messages.loadFailed);
      renderResults(data.results || []);
    }

    function setButtonBusy(button, text) {
      const previousText = button.textContent;
      button.disabled = true;
      button.textContent = text;
      return () => {
        button.disabled = false;
        button.textContent = previousText;
      };
    }

    async function refreshIndex() {
      const restoreButton = setButtonBusy(refreshButton, messages.syncing);
      try {
        await fetchJson("/api/refresh", { method: "POST" }, messages.syncFailed);
        await loadTree(false);
        if (state.activeId && state.files.some((file) => file.id === state.activeId)) {
          await loadFile(state.activeId, true);
        } else {
          state.activeId = null;
          setPlaceholder();
        }
      } catch (error) {
        setPlaceholder(error.message, true);
      } finally {
        restoreButton();
      }
    }

    async function switchFolder() {
      const folder = rootInput.value.trim();
      if (!folder) {
        setPlaceholder(messages.enterFolder, true);
        return;
      }

      const restoreButton = setButtonBusy(switchFolderButton, messages.switching);
      try {
        const data = await fetchJson("/api/folder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder }),
        }, messages.switchFailed);

        state.activeId = null;
        searchInput.value = "";
        history.replaceState(null, "", location.pathname);
        applyTreeData(data);
        renderTree();
        if (state.files[0]) await loadFile(state.files[0].id, true);
        else setPlaceholder();
      } catch (error) {
        setPlaceholder(error.message, true);
      } finally {
        restoreButton();
      }
    }

    searchInput.addEventListener("input", () => {
      clearTimeout(state.searchTimer);
      state.searchTimer = setTimeout(() => search(searchInput.value).catch((error) => {
        setPlaceholder(error.message, true);
      }), 180);
    });
    rootForm.addEventListener("submit", (event) => {
      event.preventDefault();
      switchFolder();
    });
    refreshButton.addEventListener("click", refreshIndex);
    expandAllButton.addEventListener("click", () => setAllDetails(true));
    collapseAllButton.addEventListener("click", () => setAllDetails(false));

    splitterEl.addEventListener("pointerdown", (event) => {
      if (window.innerWidth <= 760) return;
      event.preventDefault();
      splitterEl.classList.add("dragging");
      splitterEl.setPointerCapture(event.pointerId);

      const onMove = (moveEvent) => {
        const maxWidth = Math.max(280, window.innerWidth - 420);
        const width = Math.min(Math.max(moveEvent.clientX, 240), maxWidth);
        shellEl.style.setProperty("--sidebar-width", `${width}px`);
        localStorage.setItem("mdlens.sidebarWidth", String(width));
      };

      const onUp = () => {
        splitterEl.classList.remove("dragging");
        splitterEl.removeEventListener("pointermove", onMove);
        splitterEl.removeEventListener("pointerup", onUp);
        splitterEl.removeEventListener("pointercancel", onUp);
      };

      splitterEl.addEventListener("pointermove", onMove);
      splitterEl.addEventListener("pointerup", onUp);
      splitterEl.addEventListener("pointercancel", onUp);
    });

    setPlaceholder();
    loadTree().catch((error) => {
      setPlaceholder(error.message, true);
    });
  </script>
</body>
</html>
"""
