/* Public website behaviour: menu, dropdowns, photo viewer and live price quotes. */
(function () {
  "use strict";

  // Close <details> dropdowns when clicking elsewhere or pressing Escape.
  function setupDropdowns() {
    document.addEventListener("click", function (event) {
      document.querySelectorAll("details[data-dropdown][open]").forEach(function (details) {
        if (!details.contains(event.target)) details.removeAttribute("open");
      });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        document.querySelectorAll("details[data-dropdown][open]").forEach(function (details) {
          details.removeAttribute("open");
        });
      }
    });
  }

  function setupNav() {
    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.querySelector("[data-nav]");
    if (!toggle || !nav) return;
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  function setupLightbox() {
    var dialog = document.querySelector("[data-lightbox-dialog]");
    if (!dialog || typeof dialog.showModal !== "function") return;
    var image = dialog.querySelector("[data-lightbox-image]");
    var caption = dialog.querySelector("[data-lightbox-caption]");
    var counter = dialog.querySelector("[data-lightbox-counter]");
    var items = [];
    var index = 0;

    function show(i) {
      index = (i + items.length) % items.length;
      var item = items[index];
      image.src = item.getAttribute("href");
      var img = item.querySelector("img");
      image.alt = img ? img.alt : "";
      caption.textContent = item.dataset.caption || "";
      counter.textContent = items.length > 1 ? index + 1 + " / " + items.length : "";
      dialog.querySelector("[data-lightbox-prev]").hidden = items.length < 2;
      dialog.querySelector("[data-lightbox-next]").hidden = items.length < 2;
    }

    document.addEventListener("click", function (event) {
      var link = event.target.closest("a[data-lightbox]");
      if (!link) return;
      event.preventDefault();
      var group = link.dataset.lightbox;
      items = Array.prototype.slice.call(document.querySelectorAll('a[data-lightbox="' + group + '"]'));
      show(items.indexOf(link));
      dialog.showModal();
    });
    dialog.querySelector("[data-lightbox-close]").addEventListener("click", function () { dialog.close(); });
    dialog.querySelector("[data-lightbox-prev]").addEventListener("click", function () { show(index - 1); });
    dialog.querySelector("[data-lightbox-next]").addEventListener("click", function () { show(index + 1); });
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft") show(index - 1);
      if (event.key === "ArrowRight") show(index + 1);
    });
    var startX = null;
    dialog.addEventListener("touchstart", function (event) { startX = event.touches[0].clientX; }, { passive: true });
    dialog.addEventListener("touchend", function (event) {
      if (startX === null) return;
      var dx = event.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 50) show(index + (dx < 0 ? 1 : -1));
      startX = null;
    });
  }

  function addDays(isoDate, days) {
    var date = new Date(isoDate + "T00:00:00");
    date.setDate(date.getDate() + days);
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return date.getFullYear() + "-" + month + "-" + day;
  }

  function linkDates(form) {
    var arrival = form.querySelector('input[name="arrival"]');
    var departure = form.querySelector('input[name="departure"]');
    if (!arrival || !departure) return;
    arrival.addEventListener("change", function () {
      if (!arrival.value) return;
      var next = addDays(arrival.value, 1);
      departure.min = next;
      if (!departure.value || departure.value <= arrival.value) departure.value = next;
    });
  }

  function setupBookingForm() {
    document.querySelectorAll(".stay-search").forEach(linkDates);
    var form = document.querySelector("[data-booking-form]");
    if (!form) return;
    linkDates(form);

    var box = form.querySelector("[data-quote-box]");
    var body = form.querySelector("[data-quote-body]");
    var url = form.dataset.quoteUrl;
    var template = document.getElementById("quote-messages");
    function msg(key) {
      var node = template && template.content.querySelector('[data-msg="' + key + '"]');
      return node ? node.textContent : "";
    }

    function selectedAccommodation() {
      var checked = form.querySelector('input[name="accommodation"]:checked');
      return checked ? checked.value : "";
    }

    function filterExtras() {
      var acc = selectedAccommodation();
      form.querySelectorAll(".extra-option").forEach(function (option) {
        var allowed = option.dataset.accommodations;
        var visible = !allowed || !acc || allowed.split(",").indexOf(acc) !== -1;
        option.hidden = !visible;
        if (!visible) option.querySelector("input").checked = false;
      });
    }

    function el(tag, className, text) {
      var node = document.createElement(tag);
      if (className) node.className = className;
      if (text) node.textContent = text;
      return node;
    }

    function render(data) {
      body.textContent = "";
      if (data.errors && data.errors.length) {
        var errors = el("ul", "quote-errors");
        data.errors.forEach(function (error) { errors.appendChild(el("li", "", error)); });
        body.appendChild(errors);
      }
      if (data.lines && data.lines.length) {
        body.appendChild(el("p", "quote-nights", data.nights_label));
        var list = el("ul", "quote-lines");
        data.lines.forEach(function (line) {
          var item = el("li");
          var label = el("span");
          label.appendChild(el("strong", "", line.label));
          label.appendChild(el("small", "", line.detail));
          item.appendChild(label);
          item.appendChild(el("span", "", line.amount_display));
          list.appendChild(item);
        });
        body.appendChild(list);
        var total = el("p", "quote-total");
        total.appendChild(el("span", "", msg("total")));
        total.appendChild(el("strong", "", data.total_display));
        body.appendChild(total);
        if (data.deposit_display) {
          var deposit = el("p", "quote-deposit");
          deposit.appendChild(el("span", "", msg("deposit")));
          deposit.appendChild(el("span", "", data.deposit_display));
          body.appendChild(deposit);
        }
      } else if (!data.errors || !data.errors.length) {
        body.appendChild(el("p", "muted", msg("empty")));
      }
    }

    var timer = null;
    var controller = null;
    function update() {
      var params = new URLSearchParams();
      var acc = selectedAccommodation();
      var arrival = form.querySelector('input[name="arrival"]').value;
      var departure = form.querySelector('input[name="departure"]').value;
      if (!acc || !arrival || !departure) {
        render({ lines: [], errors: [] });
        return;
      }
      params.set("accommodation", acc);
      params.set("arrival", arrival);
      params.set("departure", departure);
      ["adults", "children", "pets"].forEach(function (name) {
        var input = form.querySelector('input[name="' + name + '"]');
        if (input && input.value !== "") params.set(name, input.value);
      });
      form.querySelectorAll('input[name="extras"]:checked').forEach(function (input) {
        params.append("extras", input.value);
      });
      if (controller) controller.abort();
      controller = typeof AbortController === "function" ? new AbortController() : null;
      box.classList.add("is-loading");
      fetch(url + "?" + params.toString(), { headers: { Accept: "application/json" }, signal: controller ? controller.signal : undefined })
        .then(function (response) { return response.json(); })
        .then(render)
        .catch(function (error) {
          if (error && error.name === "AbortError") return;
          body.textContent = "";
          body.appendChild(el("p", "muted", msg("error")));
        })
        .finally(function () { box.classList.remove("is-loading"); });
    }

    form.addEventListener("change", function (event) {
      if (event.target.name === "accommodation") filterExtras();
      clearTimeout(timer);
      timer = setTimeout(update, 150);
    });
    form.addEventListener("input", function (event) {
      if (["adults", "children", "pets"].indexOf(event.target.name) === -1) return;
      clearTimeout(timer);
      timer = setTimeout(update, 350);
    });
    filterExtras();
    if (!body.querySelector(".quote-lines, .quote-errors")) update();
  }

  // Statistics (Google Analytics) only after the visitor accepts them.
  function setupConsent() {
    var box = document.querySelector("[data-consent]");
    if (!box) return;
    var id = box.getAttribute("data-ga") || "";
    function read() {
      var match = document.cookie.match(/(?:^|;\s*)cookie_consent=(granted|denied)/);
      return match ? match[1] : null;
    }
    function save(value) {
      document.cookie = "cookie_consent=" + value + "; max-age=31536000; path=/; SameSite=Lax" +
        (location.protocol === "https:" ? "; Secure" : "");
    }
    function forgetAnalytics() {
      // Stops an already loaded gtag from sending hits or writing cookies again.
      window["ga-disable-" + id] = true;
      // Analytics sets its cookies on the widest domain it can, so try them all.
      var parts = location.hostname.split(".");
      var domains = [""];
      for (var i = 0; i < parts.length - 1; i++) {
        domains.push(parts.slice(i).join("."), "." + parts.slice(i).join("."));
      }
      document.cookie.split(";").forEach(function (item) {
        var name = item.split("=")[0].trim();
        if (name.indexOf("_ga") !== 0) return;
        domains.forEach(function (domain) {
          document.cookie = name + "=; max-age=0; path=/" + (domain ? "; domain=" + domain : "");
        });
      });
    }
    function loadAnalytics() {
      if (!/^G-[A-Z0-9]{4,16}$/.test(id)) return;
      window["ga-disable-" + id] = false;
      if (window.__campingAnalytics) return;
      window.__campingAnalytics = true;
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { window.dataLayer.push(arguments); };
      window.gtag("js", new Date());
      window.gtag("config", id);
      var script = document.createElement("script");
      script.async = true;
      script.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
      document.head.appendChild(script);
    }
    var choice = read();
    if (choice === "granted") loadAnalytics();
    else box.hidden = choice === "denied";
    box.addEventListener("click", function (event) {
      var button = event.target.closest("[data-consent-choice]");
      if (!button) return;
      var value = button.getAttribute("data-consent-choice");
      save(value);
      box.hidden = true;
      if (value === "granted") loadAnalytics();
      else forgetAnalytics();
    });
    document.addEventListener("click", function (event) {
      if (event.target.closest("[data-consent-reset]")) box.hidden = false;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupConsent();
    setupDropdowns();
    setupNav();
    setupLightbox();
    setupBookingForm();
  });
})();
