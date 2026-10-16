document.addEventListener("DOMContentLoaded", () => {
  document.querySelector('[data-form-errors]')?.focus();
  const filterToggle = document.querySelector('[data-filter-toggle]');
  const filterControls = document.querySelector('#catalogue-filter-controls');
  if (filterToggle && filterControls) {
    const mobileFilters = window.matchMedia('(max-width: 800px)');
    const setFiltersOpen = (open) => {
      filterControls.hidden = !open;
      filterToggle.setAttribute('aria-expanded', String(open));
    };
    const syncFilters = () => {
      filterToggle.hidden = !mobileFilters.matches;
      setFiltersOpen(!mobileFilters.matches || Boolean(filterControls.querySelector('[role=alert]')));
    };
    filterToggle.addEventListener('click', () => setFiltersOpen(filterControls.hidden));
    mobileFilters.addEventListener('change', syncFilters);
    syncFilters();
  }
  const menu = document.querySelector("[data-menu-toggle]");
  const navigation = document.querySelector(".nav-links");
  if (menu && navigation) {
    menu.addEventListener("click", () => {
      const opened = navigation.classList.toggle("is-open");
      menu.setAttribute("aria-expanded", String(opened));
      document.dispatchEvent(new Event('header-layout-change'));
    });
    navigation.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        navigation.classList.remove("is-open");
        menu.setAttribute("aria-expanded", "false");
        document.dispatchEvent(new Event('header-layout-change'));
        menu.focus();
      }
    });
  }
  document.querySelectorAll("[data-print]").forEach((button) => button.addEventListener("click", () => window.print()));
  const addLine = document.querySelector("[data-add-quote-line]");
  if (addLine) addLine.addEventListener("click", () => {
    const total = document.querySelector('[name="lines-TOTAL_FORMS"]');
    const template = document.querySelector("[data-quote-empty]");
    const body = document.querySelector("[data-quote-lines]");
    const index = Number(total.value);
    if (index >= 50) { addLine.disabled = true; return; }
    const fragment = template.content.cloneNode(true);
    fragment.querySelectorAll("[name], [id], [for]").forEach((element) => {
      ["name", "id", "for"].forEach((attribute) => {
        if (element.hasAttribute(attribute)) element.setAttribute(attribute, element.getAttribute(attribute).replaceAll("__prefix__", String(index)));
      });
    });
    body.append(fragment);
    total.value = String(index + 1);
  });
  const root = document.documentElement;
  const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  const selector = document.querySelector("[data-motion-mode]");
  let mode = "device";
  try { mode = localStorage.getItem("smartliving-motion") || "device"; } catch (_) {}
  if (!["device", "full", "off"].includes(mode)) mode = "device";
  const targets = [...document.querySelectorAll(".hero .eyebrow, .hero h1, .hero p, .hero .actions, .section > .eyebrow, .section h2, .section-config p, .card, .faq, .detail, .footer-grid > div, .living-kicker, .living-hero h1, .living-hero-content > p, .living-hero-actions, .living-intro, .living-intro-copy, .living-scene-section, .living-section-heading, .living-paths > a, .living-plan-steps > div")];
  let observer;
  const applyMotion = () => {
    const enabled = mode === "full" || (mode === "device" && !preference.matches);
    root.dataset.motion = enabled ? "on" : "off";
    if (observer) observer.disconnect();
    targets.forEach((target) => target.classList.remove("motion-pending"));
    if (!enabled || !("IntersectionObserver" in window)) return;
    observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.remove("motion-pending");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.08 });
    targets.forEach((target) => {
      if (target.dataset.motionSeen) return;
      target.dataset.motionSeen = "true";
      const siblings = [...target.parentElement.children];
      target.style.setProperty("--reveal-delay", `${Math.min(siblings.indexOf(target) % 4, 3) * 70}ms`);
      target.classList.add("motion-reveal", "motion-pending");
      observer.observe(target);
    });
  };
  if (selector) {
    selector.value = mode;
    selector.addEventListener("change", () => {
      mode = selector.value;
      try { localStorage.setItem("smartliving-motion", mode); } catch (_) {}
      applyMotion();
    });
  }
  preference.addEventListener("change", applyMotion);
  applyMotion();
  document.addEventListener("focusin", (event) => {
    const reveal = event.target.closest(".motion-pending");
    if (reveal) reveal.classList.remove("motion-pending");
  });
  const header = document.querySelector(".site-header");
  const topButton = document.querySelector("[data-scroll-top]");
  let queued = false;
  const updateScroll = () => {
    if (header) header.classList.toggle("is-scrolled", window.scrollY > 20);
    if (topButton) topButton.hidden = window.scrollY < 450;
    queued = false;
  };
  window.addEventListener("scroll", () => {
    if (!queued) { queued = true; requestAnimationFrame(updateScroll); }
  }, { passive: true });
  if (topButton) topButton.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: root.dataset.motion === "on" ? "smooth" : "instant" });
    const brand = document.querySelector(".brand");
    if (brand) brand.focus({ preventScroll: true });
  });
  updateScroll();
  const categorySelect = document.querySelector('#catalogue-category');
  const cctvFilters = document.querySelector('[data-cctv-filters]');
  categorySelect?.addEventListener('change', () => {
    if (!cctvFilters) return;
    const active = categorySelect.value === 'cctv-surveillance';
    cctvFilters.hidden = !active;
    cctvFilters.disabled = !active;
    if (!active) cctvFilters.querySelectorAll('select').forEach(select => { select.value = ''; });
  });
  const productType = document.querySelector('#id_product_type');
  const updateCameraFilters = () => {
    if (!productType || !cctvFilters) return;
    const cameras = !productType.value || productType.value === 'cctv-cameras';
    cctvFilters.querySelectorAll('select[name^="camera_"]').forEach(select => {
      select.disabled = !cameras;
      if (!cameras) select.value = '';
    });
  };
  productType?.addEventListener('change', updateCameraFilters);
  updateCameraFilters();
  const main = document.querySelector("[data-gallery-main]");
  document.querySelectorAll("[data-gallery-thumb]").forEach((button) => button.addEventListener("click", () => {
    if (!main) return;
    main.src = button.dataset.galleryThumb;
    main.alt = button.dataset.galleryAlt || "Product image";
    document.querySelectorAll("[data-gallery-thumb]").forEach((item) => { item.classList.remove("active"); item.setAttribute("aria-pressed", "false"); });
    button.classList.add("active");
    button.setAttribute("aria-pressed", "true");
  }));
});
