document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-reminder-counts-url]');
  if (!root) return;
  let pending = false;
  let stopped = false;
  const refresh = async () => {
    if (pending || stopped || document.hidden) return;
    pending = true;
    try {
      const response = await fetch(root.dataset.reminderCountsUrl, {
        credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'},
      });
      if (response.redirected || response.status === 401 || response.status === 403) {
        stopped = true;
        return;
      }
      if (!response.ok || !response.headers.get('Content-Type')?.includes('application/json')) return;
      const counts = await response.json();
      if (!['total', 'overdue', 'today', 'unassigned'].every(key => Number.isSafeInteger(counts[key]) && counts[key] >= 0)) return;
      root.querySelectorAll('[data-followup-reminder-count]').forEach(el => { el.textContent = String(counts.total); });
      root.querySelectorAll('[data-unassigned-reminder-count]').forEach(el => { el.textContent = String(counts.unassigned); });
      const link = root.querySelector('[data-reminder-link]');
      if (link) link.setAttribute('aria-label', `${counts.total} follow-up reminders assigned to you, due today or overdue`);
    } catch (_) {
      // Keep the last known count when the network is unavailable.
    } finally {
      pending = false;
    }
  };
  window.setInterval(refresh, 60000);
  document.addEventListener('visibilitychange', refresh);
  window.addEventListener('focus', refresh);
});
