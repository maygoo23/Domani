/**
 * Domani — Client-side utilities
 */

// Auto-dismiss flash alerts after 6 seconds
document.addEventListener('DOMContentLoaded', () => {
  const alerts = document.querySelectorAll('.domani-alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      bsAlert?.close();
    }, 6000);
  });

  // Restore form inputs from URL params (after redirect back to add form on error)
  const urlParams = new URLSearchParams(window.location.search);
  const prefill = urlParams.get('name');
  if (prefill) {
    const nameInput = document.getElementById('name');
    if (nameInput) nameInput.value = prefill;
  }
});

// Confirm dialog helper
function confirmDelete(message) {
  return confirm(message || 'Are you sure?');
}

// HTMX: show a spinner on the refresh button during request
document.body.addEventListener('htmx:beforeRequest', (evt) => {
  const btn = evt.detail.elt;
  if (btn.tagName === 'BUTTON') {
    const icon = btn.querySelector('i.fa-rotate');
    if (icon) {
      icon.classList.add('fa-spin');
      btn.disabled = true;
    }
  }
});

document.body.addEventListener('htmx:afterRequest', (evt) => {
  const btn = evt.detail.elt;
  if (btn.tagName === 'BUTTON') {
    const icon = btn.querySelector('i.fa-rotate');
    if (icon) {
      icon.classList.remove('fa-spin');
      btn.disabled = false;
    }
  }
});
