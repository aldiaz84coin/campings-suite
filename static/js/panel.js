/* Camping panel behaviour. Everything degrades gracefully without JavaScript. */
(function () {
  "use strict";

  function $(selector, root) { return (root || document).querySelector(selector); }
  function $$(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }

  function csrfToken() {
    var input = $("input[name=csrfmiddlewaretoken]");
    if (input) return input.value;
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function message(templateId, key, values) {
    var template = document.getElementById(templateId);
    var node = template && template.content.querySelector('[data-msg="' + key + '"]');
    var text = node ? node.textContent : "";
    Object.keys(values || {}).forEach(function (name) {
      text = text.replace("{" + name + "}", values[name]);
    });
    return text;
  }

  // Dropdowns built with <details data-dropdown>.
  function setupDropdowns() {
    document.addEventListener("click", function (event) {
      $$("details[data-dropdown][open]").forEach(function (details) {
        if (!details.contains(event.target)) details.removeAttribute("open");
      });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      $$("details[data-dropdown][open]").forEach(function (details) { details.removeAttribute("open"); });
      closeSidebar();
    });
  }

  // Mobile sidebar.
  function closeSidebar() {
    var sidebar = $("[data-sidebar]");
    if (!sidebar) return;
    sidebar.classList.remove("is-open");
    $$(".sidebar-backdrop").forEach(function (el) { el.classList.remove("is-open"); });
  }
  function setupSidebar() {
    var sidebar = $("[data-sidebar]");
    if (!sidebar) return;
    $$("[data-sidebar-open]").forEach(function (button) {
      button.addEventListener("click", function () {
        sidebar.classList.add("is-open");
        $$(".sidebar-backdrop").forEach(function (el) { el.classList.add("is-open"); });
      });
    });
    $$("[data-sidebar-close]").forEach(function (el) { el.addEventListener("click", closeSidebar); });
  }

  // Language tabs of translated fields; switching one switches the whole form.
  function setupTranslatedFields() {
    function activate(scope, lang) {
      $$("[data-i18n-field]", scope).forEach(function (field) {
        var panes = $$(".i18n-pane", field);
        var hasLang = panes.some(function (pane) { return pane.dataset.lang === lang; });
        var target = hasLang ? lang : panes[0] && panes[0].dataset.lang;
        panes.forEach(function (pane) { pane.classList.toggle("is-active", pane.dataset.lang === target); });
        $$(".i18n-tab", field).forEach(function (tab) {
          var active = tab.dataset.lang === target;
          tab.classList.toggle("is-active", active);
          tab.setAttribute("aria-selected", active ? "true" : "false");
        });
      });
    }
    var fields = $$("[data-i18n-field]");
    if (!fields.length) return;
    var scopes = [];
    fields.forEach(function (field) {
      var scope = field.closest("form") || document;
      if (scopes.indexOf(scope) === -1) scopes.push(scope);
      // Show the first language that has an error, if any.
    });
    scopes.forEach(function (scope) {
      var first = $(".i18n-tab", scope);
      if (first) activate(scope, first.dataset.lang);
    });
    document.addEventListener("click", function (event) {
      var tab = event.target.closest(".i18n-tab");
      if (!tab) return;
      activate(tab.closest("form") || document, tab.dataset.lang);
    });
    document.addEventListener("input", function (event) {
      var pane = event.target.closest(".i18n-pane");
      if (!pane) return;
      var field = pane.closest("[data-i18n-field]");
      var dot = $('.i18n-tab[data-lang="' + pane.dataset.lang + '"] .i18n-dot', field);
      if (dot) dot.classList.toggle("is-filled", event.target.value.trim() !== "");
    });
  }

  // Buttons with data-confirm ask before submitting.
  function setupConfirm() {
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-confirm]");
      if (button && !window.confirm(button.dataset.confirm)) event.preventDefault();
    });
  }

  function setupCopy() {
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-copy]");
      if (!button) return;
      var input = $("[data-copy-source]", button.parentNode);
      if (!input) return;
      input.select();
      var done = function () { button.classList.add("is-copied"); setTimeout(function () { button.classList.remove("is-copied"); }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(input.value).then(done, function () { document.execCommand("copy"); done(); });
      else { document.execCommand("copy"); done(); }
    });
  }

  function setupRowLinks() {
    document.addEventListener("click", function (event) {
      var row = event.target.closest("tr[data-href]");
      if (!row || event.target.closest("a, button, input, form")) return;
      window.location.href = row.dataset.href;
    });
  }

  // Photo uploads with progress, one request per file.
  function setupDropzone() {
    var zone = $("[data-dropzone]");
    if (!zone || !window.FormData) return;
    var input = $('input[type="file"]', zone);
    var progress = $("[data-upload-progress]", zone);
    var bar = $("[data-progress-bar]", zone);
    var text = $("[data-progress-text]", zone);
    var maxBytes = parseInt(zone.dataset.maxMb || "20", 10) * 1024 * 1024;

    function uploadOne(file) {
      return new Promise(function (resolve) {
        var data = new FormData();
        data.append("images", file);
        var xhr = new XMLHttpRequest();
        xhr.open("POST", zone.getAttribute("action") || window.location.pathname);
        xhr.setRequestHeader("X-CSRFToken", csrfToken());
        xhr.setRequestHeader("X-Requested-With", "fetch");
        xhr.setRequestHeader("Accept", "application/json");
        xhr.onload = function () {
          var body = {};
          try { body = JSON.parse(xhr.responseText); } catch (e) { body = { errors: [message("upload-messages", "error")] }; }
          resolve(body.errors || []);
        };
        xhr.onerror = function () { resolve([file.name + ": " + message("upload-messages", "error")]); };
        xhr.send(data);
      });
    }

    function uploadAll(files) {
      files = Array.prototype.slice.call(files || []);
      if (!files.length) return;
      var errors = [];
      var valid = files.filter(function (file) {
        if (file.size > maxBytes) {
          errors.push(message("upload-messages", "too-big", { name: file.name }));
          return false;
        }
        return true;
      });
      progress.hidden = false;
      var done = 0;
      var chain = Promise.resolve();
      valid.forEach(function (file) {
        chain = chain.then(function () {
          text.textContent = message("upload-messages", "uploading", { done: done + 1, total: valid.length });
          return uploadOne(file).then(function (fileErrors) {
            errors = errors.concat(fileErrors);
            done += 1;
            bar.style.width = Math.round((done / valid.length) * 100) + "%";
          });
        });
      });
      chain.then(function () {
        if (errors.length) {
          text.textContent = errors.join(" · ");
          text.classList.add("field__error");
          if (done) setTimeout(function () { window.location.reload(); }, 2500);
        } else {
          text.textContent = message("upload-messages", "done");
          window.location.reload();
        }
      });
    }

    input.addEventListener("change", function () { uploadAll(input.files); input.value = ""; });
    ["dragenter", "dragover"].forEach(function (name) {
      zone.addEventListener(name, function (event) {
        if (!event.dataTransfer || Array.prototype.indexOf.call(event.dataTransfer.types, "Files") === -1) return;
        event.preventDefault();
        zone.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (name) {
      zone.addEventListener(name, function () { zone.classList.remove("is-dragover"); });
    });
    zone.addEventListener("drop", function (event) {
      if (!event.dataTransfer || !event.dataTransfer.files.length) return;
      event.preventDefault();
      uploadAll(event.dataTransfer.files);
    });
  }

  // Drag & drop ordering of photos.
  function setupSortable() {
    var grid = $("[data-sortable]");
    if (!grid) return;
    var status = $("[data-reorder-status]");
    var dragged = null;

    function save() {
      var order = $$("[data-id]", grid).map(function (item) { return parseInt(item.dataset.id, 10); });
      $$("[data-id]", grid).forEach(function (item, index) { item.classList.toggle("is-cover", index === 0); });
      fetch(grid.dataset.reorderUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken(), "X-Requested-With": "fetch" },
        body: JSON.stringify({ order: order }),
      }).then(function (response) {
        status.textContent = message("upload-messages", response.ok ? "saved" : "error");
        if (response.ok) setTimeout(function () { window.location.reload(); }, 600);
      });
    }

    grid.addEventListener("dragstart", function (event) {
      dragged = event.target.closest("[data-id]");
      if (!dragged) return;
      dragged.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", dragged.dataset.id);
    });
    grid.addEventListener("dragover", function (event) {
      if (!dragged) return;
      event.preventDefault();
      var target = event.target.closest("[data-id]");
      if (!target || target === dragged) return;
      var rect = target.getBoundingClientRect();
      var after = event.clientX > rect.left + rect.width / 2;
      grid.insertBefore(dragged, after ? target.nextSibling : target);
    });
    grid.addEventListener("drop", function (event) { if (dragged) event.preventDefault(); });
    grid.addEventListener("dragend", function () {
      if (!dragged) return;
      dragged.classList.remove("is-dragging");
      dragged = null;
      save();
    });
  }

  // Live preview on the appearance page.
  function setupAppearance() {
    var form = $("[data-appearance-form]");
    var preview = $("[data-preview]");
    if (!form || !preview) return;
    var primary = $('input[name="primary_color"]', form);
    var accent = $('input[name="accent_color"]', form);
    function refresh() {
      preview.style.setProperty("--primary", primary.value);
      preview.style.setProperty("--accent", accent.value);
      var checked = $('input[name="font_style"]:checked', form);
      if (checked) preview.className = "mini-site font-" + checked.value;
    }
    form.addEventListener("input", refresh);
    form.addEventListener("change", refresh);
    $$("[data-presets] button").forEach(function (button) {
      button.addEventListener("click", function () {
        primary.value = button.dataset.primary;
        accent.value = button.dataset.accent;
        refresh();
      });
    });
  }

  // Opening dates are irrelevant when the camping opens all year.
  function setupSeasonToggle() {
    var checkbox = $('input[name="open_all_year"]');
    var dates = $("[data-season-dates]");
    if (!checkbox || !dates) return;
    function refresh() { dates.hidden = checkbox.checked; }
    checkbox.addEventListener("change", refresh);
    refresh();
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupDropdowns();
    setupSidebar();
    setupTranslatedFields();
    setupConfirm();
    setupCopy();
    setupRowLinks();
    setupDropzone();
    setupSortable();
    setupAppearance();
    setupSeasonToggle();
  });
})();
