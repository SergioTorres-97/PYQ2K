// Polls the status API every 2 seconds while a simulation is running.
// Reloads the page when the status changes to 'done' or 'error'.
(function () {
  if (!window.STATUS_URL) return;
  if (!document.getElementById('spinner-area')) return;

  function poll() {
    fetch(window.STATUS_URL)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.status === 'done' || data.status === 'error') {
          window.location.reload();
        } else {
          setTimeout(poll, 2000);
        }
      })
      .catch(function () {
        setTimeout(poll, 3000);
      });
  }

  setTimeout(poll, 2000);
})();
