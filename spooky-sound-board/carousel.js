/**
 * Viewport-width carousel (pixel transforms — avoids % of full track bugs).
 * - [data-carousel] root
 * - optional data-autoplay="ms"
 * - [data-carousel-prev] / [data-carousel-next]
 * - .carousel-dots (filled automatically)
 * - [data-carousel-status] for "1 / N"
 */
(function () {
  function initCarousel(root) {
    const track = root.querySelector(".carousel-track");
    if (!track) return;

    const slides = Array.from(track.querySelectorAll(".carousel-slide"));
    if (slides.length === 0) return;

    const prevBtn = root.querySelector("[data-carousel-prev]");
    const nextBtn = root.querySelector("[data-carousel-next]");
    const dotsHost = root.querySelector(".carousel-dots");
    const statusEl = root.querySelector("[data-carousel-status]");
    const viewport = root.querySelector(".carousel-viewport") || track.parentElement;
    if (!viewport) return;

    let index = Math.max(
      0,
      slides.findIndex((s) => s.classList.contains("is-active"))
    );
    if (index < 0) index = 0;

    let autoplayMs = parseInt(root.getAttribute("data-autoplay") || "0", 10);
    if (Number.isNaN(autoplayMs) || autoplayMs < 0) autoplayMs = 0;
    let timer = null;
    let touchStartX = 0;
    let touchDeltaX = 0;
    let isDragging = false;

    // Build dots once
    if (dotsHost) {
      dotsHost.innerHTML = "";
      slides.forEach((_, i) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "carousel-dot";
        btn.setAttribute("role", "tab");
        btn.setAttribute("aria-label", "Go to slide " + (i + 1));
        btn.addEventListener("click", () => goTo(i, true));
        dotsHost.appendChild(btn);
      });
    }

    function dots() {
      return dotsHost ? Array.from(dotsHost.querySelectorAll(".carousel-dot")) : [];
    }

    function slideWidth() {
      return viewport.clientWidth || root.clientWidth || 1;
    }

    function layoutSlides() {
      const w = slideWidth();
      // Each slide must match the visible viewport width exactly
      slides.forEach((slide) => {
        slide.style.flex = "0 0 " + w + "px";
        slide.style.width = w + "px";
        slide.style.minWidth = w + "px";
        slide.style.maxWidth = w + "px";
      });
      track.style.width = w * slides.length + "px";
    }

    function render(animate) {
      layoutSlides();
      const w = slideWidth();
      if (animate === false) {
        track.style.transition = "none";
      } else {
        track.style.transition = "";
      }
      track.style.transform = "translate3d(" + -index * w + "px, 0, 0)";
      // Force reflow then restore transition after hard jump
      if (animate === false) {
        void track.offsetWidth;
        track.style.transition = "";
      }

      slides.forEach((slide, i) => {
        const on = i === index;
        slide.classList.toggle("is-active", on);
        slide.setAttribute("aria-hidden", on ? "false" : "true");
      });
      dots().forEach((dot, i) => {
        const on = i === index;
        dot.classList.toggle("is-active", on);
        dot.setAttribute("aria-selected", on ? "true" : "false");
      });
      if (statusEl) {
        statusEl.textContent = index + 1 + " / " + slides.length;
      }
    }

    function goTo(i, userInitiated) {
      index = ((i % slides.length) + slides.length) % slides.length;
      render(true);
      if (userInitiated) restartAutoplay();
    }

    function next(user) {
      goTo(index + 1, user);
    }
    function prev(user) {
      goTo(index - 1, user);
    }

    function stopAutoplay() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    }

    function startAutoplay() {
      stopAutoplay();
      if (autoplayMs <= 0 || slides.length < 2) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      timer = setInterval(() => next(false), autoplayMs);
    }

    function restartAutoplay() {
      stopAutoplay();
      startAutoplay();
    }

    if (prevBtn) prevBtn.addEventListener("click", () => prev(true));
    if (nextBtn) nextBtn.addEventListener("click", () => next(true));

    root.tabIndex = 0;
    root.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        next(true);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        prev(true);
      }
    });

    root.addEventListener("mouseenter", stopAutoplay);
    root.addEventListener("mouseleave", startAutoplay);
    root.addEventListener("focusin", stopAutoplay);
    root.addEventListener("focusout", (e) => {
      if (!root.contains(e.relatedTarget)) startAutoplay();
    });

    function onPointerDown(e) {
      isDragging = true;
      touchStartX = e.clientX ?? (e.touches && e.touches[0].clientX) ?? 0;
      touchDeltaX = 0;
      stopAutoplay();
      track.style.transition = "none";
    }

    function onPointerMove(e) {
      if (!isDragging) return;
      const x = e.clientX ?? (e.touches && e.touches[0].clientX) ?? 0;
      touchDeltaX = x - touchStartX;
      const w = slideWidth();
      track.style.transform =
        "translate3d(" + (-index * w + touchDeltaX) + "px, 0, 0)";
    }

    function onPointerUp() {
      if (!isDragging) return;
      isDragging = false;
      track.style.transition = "";
      const w = slideWidth();
      const threshold = w * 0.18;
      if (touchDeltaX > threshold) prev(true);
      else if (touchDeltaX < -threshold) next(true);
      else {
        render(true);
        restartAutoplay();
      }
      touchDeltaX = 0;
    }

    viewport.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);

    viewport.addEventListener(
      "touchstart",
      (e) => {
        if (!e.touches[0]) return;
        isDragging = true;
        touchStartX = e.touches[0].clientX;
        touchDeltaX = 0;
        stopAutoplay();
        track.style.transition = "none";
      },
      { passive: true }
    );
    viewport.addEventListener(
      "touchmove",
      (e) => {
        if (!isDragging || !e.touches[0]) return;
        touchDeltaX = e.touches[0].clientX - touchStartX;
        const w = slideWidth();
        track.style.transform =
          "translate3d(" + (-index * w + touchDeltaX) + "px, 0, 0)";
      },
      { passive: true }
    );
    viewport.addEventListener("touchend", onPointerUp);

    // Keep layout correct on resize / font load
    window.addEventListener("resize", () => render(false));
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => render(false));
      ro.observe(viewport);
    }

    render(false);
    startAutoplay();
  }

  function boot() {
    document.querySelectorAll("[data-carousel]").forEach(initCarousel);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
