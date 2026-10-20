(function () {
  const storageKey = "smartAttendanceTheme";

  const setTheme = (theme) => {
    document.body.classList.toggle("theme-dark", theme === "dark");
    localStorage.setItem(storageKey, theme);
  };

  const icon = (name) => `<i class="bi bi-${name}" aria-hidden="true"></i>`;

  document.addEventListener("DOMContentLoaded", () => {
    const title = (document.title || "Smart Attendance").replace(/\s*\|.*$/, "").trim();
    document.body.setAttribute("data-ui-title", title);
    document.body.classList.add("ui-redesigned");

    const stage = document.createElement("div");
    stage.className = "ui-stage";
    stage.setAttribute("aria-hidden", "true");
    stage.innerHTML = "<span></span><span></span><span></span>";
    document.body.prepend(stage);

    const pageChip = document.createElement("div");
    pageChip.className = "ui-page-chip";
    pageChip.textContent = title;
    document.body.appendChild(pageChip);

    const savedTheme = localStorage.getItem(storageKey);
    if (savedTheme === "dark") {
      document.body.classList.add("theme-dark");
    }

    const progress = document.createElement("div");
    progress.className = "ui-top-progress";
    document.body.appendChild(progress);

    const themeButton = document.createElement("button");
    themeButton.type = "button";
    themeButton.className = "ui-theme-toggle";
    themeButton.setAttribute("aria-label", "Toggle dark mode");
    themeButton.title = "Toggle dark mode";
    themeButton.innerHTML = icon(document.body.classList.contains("theme-dark") ? "sun" : "moon-stars");
    document.body.appendChild(themeButton);

    const scrollTop = document.createElement("button");
    scrollTop.type = "button";
    scrollTop.className = "ui-scroll-top";
    scrollTop.setAttribute("aria-label", "Back to top");
    scrollTop.title = "Back to top";
    scrollTop.innerHTML = icon("arrow-up");
    document.body.appendChild(scrollTop);

    themeButton.addEventListener("click", () => {
      const next = document.body.classList.contains("theme-dark") ? "light" : "dark";
      setTheme(next);
      themeButton.innerHTML = icon(next === "dark" ? "sun" : "moon-stars");
    });

    scrollTop.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    const revealItems = [
      ".card",
      ".card-box",
      ".dashboard-card",
      ".section-card",
      ".stat-card",
      ".metric-card",
      ".mini-stat",
      ".announcement",
      ".table-responsive",
      ".table-shell",
      ".alert"
    ].join(",");

    document.querySelectorAll(revealItems).forEach((el, index) => {
      el.setAttribute("data-reveal", "");
      el.style.transitionDelay = `${Math.min(index * 26, 260)}ms`;
    });

    const reveal = () => {
      document.querySelectorAll("[data-reveal]").forEach((el) => {
        const rect = el.getBoundingClientRect();
        if (rect.top < window.innerHeight - 36) {
          el.classList.add("is-visible");
        }
      });
    };

    const updateScrollUi = () => {
      const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progressAmount = scrollHeight > 0 ? window.scrollY / scrollHeight : 0;
      progress.style.transform = `scaleX(${Math.max(0, Math.min(1, progressAmount))})`;
      scrollTop.classList.toggle("is-visible", window.scrollY > 420);
      reveal();
    };

    reveal();
    updateScrollUi();
    window.addEventListener("scroll", updateScrollUi, { passive: true });
    window.addEventListener("resize", updateScrollUi);

    document.querySelectorAll("table").forEach((table) => {
      if (!table.closest(".table-responsive") && !table.closest(".table-shell")) {
        const wrapper = document.createElement("div");
        wrapper.className = "table-responsive";
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
      }
      table.classList.add("align-middle");

      const tbody = table.querySelector("tbody");
      const rowCount = tbody ? tbody.querySelectorAll("tr").length : 0;
      if (tbody && rowCount > 5 && !table.closest("form")) {
        const filter = document.createElement("input");
        filter.type = "search";
        filter.className = "form-control ui-table-filter";
        filter.placeholder = "Search this table";
        filter.setAttribute("aria-label", "Search this table");
        table.closest(".table-responsive, .table-shell").before(filter);
        filter.addEventListener("input", () => {
          const query = filter.value.trim().toLowerCase();
          tbody.querySelectorAll("tr").forEach((row) => {
            row.hidden = query.length > 0 && !row.textContent.toLowerCase().includes(query);
          });
        });
      }
    });

    const currentPath = window.location.pathname.replace(/\/$/, "") || "/";
    document.querySelectorAll(".sidebar a[href], .nav-link-custom[href], .navbar a[href]").forEach((link) => {
      const href = link.getAttribute("href");
      if (!href || href.startsWith("#")) return;
      const linkPath = new URL(href, window.location.origin).pathname.replace(/\/$/, "") || "/";
      if (linkPath === currentPath) {
        link.classList.add("is-current");
      }
    });

    document.querySelectorAll(".btn").forEach((button) => {
      button.addEventListener("click", (event) => {
        const rect = button.getBoundingClientRect();
        const ripple = document.createElement("span");
        ripple.className = "ui-ripple";
        ripple.style.left = `${event.clientX - rect.left}px`;
        ripple.style.top = `${event.clientY - rect.top}px`;
        button.appendChild(ripple);
        window.setTimeout(() => ripple.remove(), 600);
      });
    });

  });
})();
