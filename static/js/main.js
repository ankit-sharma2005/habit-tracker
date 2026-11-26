/* main.js
   =======
   Two tiny helpers shared by every page:

   1. A confirmation popup for any form that carries
      data-confirm="..." - used by the delete buttons.
   2. Auto-dismissing flash messages after a few seconds.

   No frameworks are used, so this stays easy to read for a beginner. */

(function () {
  "use strict";

  // 1. Confirmation popups -------------------------------------------------
  // Listening on the document means every current and future form works,
  // without adding onclick="..." to each one.
  document.addEventListener("submit", function (event) {
    var form = event.target.closest("form.confirm-form");
    if (!form) {
      return; // not a form that needs confirmation
    }

    var message = form.dataset.confirm || "Are you sure?";
    if (!window.confirm(message)) {
      event.preventDefault(); // the user clicked "Cancel": stop the submit
    }
  });

  // 2. Auto-dismiss flashes -----------------------------------------------
  var alerts = document.querySelectorAll(".flash-area .alert");
  if (alerts.length) {
    window.setTimeout(function () {
      alerts.forEach(function (alert) {
        if (window.bootstrap && window.bootstrap.Alert) {
          window.bootstrap.Alert.getOrCreateInstance(alert).close();
        }
      });
    }, 6000);
  }
})();
