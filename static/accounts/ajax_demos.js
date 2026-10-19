"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const status = document.getElementById("ajax-demo-status");
  const csrfToken = document.querySelector("#ajax-demo-csrf input[name=csrfmiddlewaretoken]")?.value || "";

  document.querySelectorAll(".ajax-demo-delete").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      status.textContent = "Removing item…";

      try {
        const response = await fetch(button.dataset.url, {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
            "X-Requested-With": "XMLHttpRequest",
          },
          credentials: "same-origin",
          body: JSON.stringify({ id: button.dataset.id }),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.message || "The item could not be removed.");
        }

        // This DOM removal is required: a successful server response alone does not update the page.
        document.getElementById(`${button.dataset.kind}-${result.id}`)?.remove();
        const list = document.getElementById(button.dataset.kind === "songs" ? "songs-list" : "watch-later-list");
        if (!list.querySelector("li:not(.empty-row)")) {
          const emptyMessage = document.createElement("li");
          emptyMessage.className = "empty-row";
          emptyMessage.textContent = button.dataset.kind === "songs" ? "No songs in this playlist." : "Your Watch Later list is empty.";
          list.appendChild(emptyMessage);
        }
        status.textContent = result.message;
      } catch (error) {
        status.textContent = error.message || "A network error occurred. Please try again.";
        button.disabled = false;
      }
    });
  });
});
