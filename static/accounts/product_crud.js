"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const status = document.getElementById("product-status");
  const csrfInput = document.querySelector("#csrf-token-form input[name=csrfmiddlewaretoken]");

  document.querySelectorAll(".ajax-delete-product").forEach((button) => {
    button.addEventListener("click", async () => {
      const productId = button.dataset.productId;
      if (!window.confirm("Remove this product from the list?")) return;

      button.disabled = true;
      status.textContent = "Removing product…";
      status.setAttribute("role", "status");

      try {
        const response = await fetch(button.dataset.deleteUrl, {
          method: "DELETE",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfInput?.value || "",
            "X-Requested-With": "XMLHttpRequest",
          },
          body: JSON.stringify({ product_id: Number(productId) }),
          credentials: "same-origin",
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          throw new Error(result.message || "The product could not be removed.");
        }

        // Remove the row only after the server confirms the delete succeeded.
        document.getElementById(`product-${productId}`)?.remove();
        status.textContent = result.message;
        const list = document.getElementById("product-list");
        if (list && list.children.length === 0) {
          document.getElementById("product-table").hidden = true;
          document.getElementById("empty-products").hidden = false;
        }
      } catch (error) {
        status.textContent = error.message || "A network error occurred. Please try again.";
        button.disabled = false;
      }
    });
  });
});
