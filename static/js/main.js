"use strict";

// Phase 1 contains no database-backed search yet. Keep interactions intentionally minimal.
document.querySelectorAll("[data-placeholder-link]").forEach((link) => {
  link.addEventListener("click", () => {
    // Navigation goes to a clear in-app Phase 1 placeholder page.
  });
});
