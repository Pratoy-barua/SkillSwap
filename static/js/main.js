"use strict";

// Phase 1 contains no database-backed search yet. Keep interactions intentionally minimal.
document.querySelectorAll("[data-placeholder-link]").forEach((link) => {
  link.addEventListener("click", () => {
    // Navigation goes to a clear in-app Phase 1 placeholder page.
  });
});

// Notifications: Real-time Mark as Read and Mark All as Read handling
document.addEventListener("DOMContentLoaded", function () {
  // Delegate submission of mark-single-read-form
  document.addEventListener("submit", function (e) {
    const singleForm = e.target.closest(".mark-single-read-form");
    if (singleForm) {
      e.preventDefault();
      const notificationRow = singleForm.closest(".notification-item-row");
      const formData = new FormData(singleForm);

      fetch(singleForm.action, {
        method: "POST",
        body: formData,
        headers: {
          "Accept": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then((res) => res.json())
        .then((data) => {
          if (data && data.success) {
            updateNotificationCount(data.unread_count);
            if (notificationRow) {
              notificationRow.classList.remove("unread");
              notificationRow.classList.add("read");
              const dot = notificationRow.querySelector(".notification-dot");
              if (dot) dot.remove();
              const title = notificationRow.querySelector(".notification-title");
              if (title) {
                title.classList.remove("text-dark");
                title.classList.add("text-secondary", "fw-semibold");
              }
              singleForm.remove();
            }
          } else {
            singleForm.submit();
          }
        })
        .catch(() => {
          singleForm.submit();
        });
      return;
    }

    const allForm = e.target.closest(".mark-all-read-form");
    if (allForm) {
      e.preventDefault();
      const formData = new FormData(allForm);

      fetch(allForm.action, {
        method: "POST",
        body: formData,
        headers: {
          "Accept": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then((res) => res.json())
        .then((data) => {
          if (data && data.success) {
            updateNotificationCount(0);
            document.querySelectorAll(".notification-item-row.unread").forEach((row) => {
              row.classList.remove("unread");
              row.classList.add("read");
              const dot = row.querySelector(".notification-dot");
              if (dot) dot.remove();
              const title = row.querySelector(".notification-title");
              if (title) {
                title.classList.remove("text-dark");
                title.classList.add("text-secondary", "fw-semibold");
              }
              const rowForm = row.querySelector(".mark-single-read-form");
              if (rowForm) rowForm.remove();
            });
            allForm.classList.add("d-none");
            const caughtUp = document.getElementById("allReadStatusText");
            if (caughtUp) caughtUp.classList.remove("d-none");
          } else {
            allForm.submit();
          }
        })
        .catch(() => {
          allForm.submit();
        });
      return;
    }
  });

  function updateNotificationCount(count) {
    const badge = document.getElementById("navNotificationCount");
    const dropdownBadge = document.getElementById("dropdownUnreadBadge");
    const dashboardStatCount = document.getElementById("dashboardUnreadCount");

    if (count > 0) {
      if (badge) {
        badge.textContent = count;
        badge.classList.remove("d-none");
      } else {
        const bellBtn = document.getElementById("notificationBellBtn");
        if (bellBtn) {
          const newBadge = document.createElement("span");
          newBadge.className = "notification-count";
          newBadge.id = "navNotificationCount";
          newBadge.textContent = count;
          bellBtn.appendChild(newBadge);
        }
      }
      if (dropdownBadge) {
        dropdownBadge.textContent = count + " unread";
        dropdownBadge.classList.remove("d-none");
      }
    } else {
      if (badge) {
        badge.remove();
      }
      if (dropdownBadge) {
        dropdownBadge.classList.add("d-none");
      }
      const allForm = document.getElementById("markAllReadForm");
      if (allForm) allForm.classList.add("d-none");
      const caughtUp = document.getElementById("allReadStatusText");
      if (caughtUp) caughtUp.classList.remove("d-none");
    }

    if (dashboardStatCount) {
      dashboardStatCount.textContent = count;
    }
  }
});
