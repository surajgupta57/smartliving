document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('[data-workspace-nav-toggle]');
  const navigation = document.querySelector('#workspace-navigation');
  if (!toggle || !navigation) return;
  const compact = window.matchMedia('(max-width: 1100px)');
  const setOpen = open => {
    navigation.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
    const icon = toggle.querySelector('[data-workspace-nav-icon]');
    if (icon) icon.textContent = open ? '−' : '+';
  };
  const sync = () => {
    // Return focus to the visible menu button when a resize hides a focused link.
    const restoreFocus = compact.matches && navigation.contains(document.activeElement);
    toggle.hidden = !compact.matches;
    setOpen(!compact.matches);
    if (restoreFocus) toggle.focus();
  };
  toggle.addEventListener('click', () => setOpen(navigation.hidden));
  const closeOnEscape = event => {
    if (event.key === 'Escape' && compact.matches) {
      setOpen(false);
      toggle.focus();
    }
  };
  navigation.addEventListener('keydown', closeOnEscape);
  toggle.addEventListener('keydown', closeOnEscape);
  compact.addEventListener('change', sync);
  sync();
});
