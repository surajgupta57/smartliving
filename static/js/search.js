document.addEventListener('DOMContentLoaded', () => {
  const search = document.querySelector('[data-public-search]');
  if (search) {
    const root = document.querySelector('[data-search-root]'), trigger = root.querySelector('[data-search-open]'), panel = root.querySelector('[role=dialog]'), backdrop = root.querySelector('[data-search-backdrop]');
    const input = search.querySelector('[name=q]'), links = search.querySelector('[data-search-links]'), status = search.querySelector('[data-search-status]'), discovery = search.querySelector('[data-search-discovery]');
    let timer, controller, version = 0, loaded = false, recent = [];
    let scrollTimer, sizeTimer;
    const header = root.closest('.site-header'), space = header?.parentElement;
    const measureSearch = () => {
      root.style.setProperty('--search-row-height', `${trigger.offsetHeight + 24}px`);
      if (space?.classList.contains('header-space') && !header.classList.contains('header-lean')) {
        space.style.height = `${header.offsetHeight}px`;
      }
    };
    const showSearch = () => {
      root.classList.remove('search-scrolling');
      header?.classList.remove('header-lean');
    };
    measureSearch();
    document.addEventListener('header-layout-change', measureSearch);
    space?.classList.add('header-enhanced');
    document.fonts?.ready.then(measureSearch);
    window.addEventListener('resize', () => {
      clearTimeout(sizeTimer); clearTimeout(scrollTimer); showSearch();
      sizeTimer = setTimeout(measureSearch, 350);
    });
    window.addEventListener('scroll', () => {
      clearTimeout(scrollTimer);
      if (window.matchMedia('(min-width: 1201px)').matches) { showSearch(); return; }
      if (!panel.hidden || trigger.matches(':focus-visible') || window.scrollY < 20) {
        showSearch();
        return;
      }
      root.classList.add('search-scrolling');
      header?.classList.add('header-lean');
      scrollTimer = setTimeout(showSearch, 320);
    }, {passive:true});
    root.addEventListener('focusin', showSearch);

    try { recent = JSON.parse(localStorage.getItem('smartliving-searches') || '[]'); if (!Array.isArray(recent)) recent = []; recent = recent.filter(x => typeof x === 'string').slice(0, 6); } catch (_) {}
    const saveRecent = () => { const q = input.value.trim(); if (q.length < 2) return; recent = [q, ...recent.filter(x => x !== q)].slice(0,6); try { localStorage.setItem('smartliving-searches', JSON.stringify(recent)); } catch (_) {} renderRecent(); };
    const renderRecent = () => { const box = search.querySelector('[data-recent-links]'); box.replaceChildren(); search.querySelector('[data-recent-section]').hidden = !recent.length; recent.forEach(q => {const button = document.createElement('button'); button.type = 'button'; button.textContent = q; button.onclick = () => {input.value = q; update();}; box.append(button);}); };
    const cancel = () => { ++version; clearTimeout(timer); controller?.abort(); };
    const close = () => { cancel(); panel.hidden = backdrop.hidden = true; trigger.setAttribute('aria-expanded','false'); document.body.classList.remove('search-is-open'); trigger.focus(); };
    const update = () => {
      cancel(); const current = version, q = input.value.trim(); links.replaceChildren(); discovery.hidden = q.length >= 2;
      if (q.length < 2) {status.textContent = 'Start typing or choose a recent or featured product.'; return;}
      const params = new URLSearchParams(new FormData(search));
      if (!search.querySelector('[name=type]:checked')) { status.textContent = 'Choose at least one search type.'; return; }
      timer = setTimeout(async () => {
        controller = new AbortController(); status.textContent = 'Finding matches…';
        try {
          const response = await fetch(`${search.dataset.endpoint}?${params}`, {signal:controller.signal}); if (!response.ok) throw Error();
          const data = await response.json(); if (current !== version) return;
          data.results.forEach(item => {const a = document.createElement('a'); a.href = item.url; const type = document.createElement('span'), copy = document.createElement('strong'), context = document.createElement('small'); type.textContent = item.type || 'Product'; copy.textContent = item.title; context.textContent = item.context || 'Open result'; a.append(type,copy,context); a.onclick = saveRecent; links.append(a);});
          status.textContent = data.results.length ? `${data.results.length} top matches` : 'No matches. Try a broader term.';
        } catch (e) {if (e.name !== 'AbortError' && current === version) status.textContent = 'Search is temporarily unavailable. Please try again.';}
      },250);
    };
    trigger.onclick = async () => {
      clearTimeout(scrollTimer); showSearch();
      panel.hidden = backdrop.hidden = false; trigger.setAttribute('aria-expanded','true'); document.body.classList.add('search-is-open'); renderRecent(); input.focus();
      if (!loaded) try {
        const response = await fetch(`${search.dataset.endpoint}?discovery=1`); if (!response.ok) throw Error(); const data = await response.json();
        data.categories.forEach(item => {const option = document.createElement('option'); option.value = item.slug; option.textContent = item.name; search.querySelector('select').append(option);});
        const box = search.querySelector('[data-recommended-links]'); data.recommended.forEach(item => {const a = document.createElement('a'); a.href = item.url; a.textContent = item.title; box.append(a);}); search.querySelector('[data-recommended-section]').hidden = !data.recommended.length; loaded = true;
      } catch (_) { /* Search remains available without discovery. */ }
    };
    root.querySelector('[data-search-close]').onclick = close; backdrop.onclick = close;
    search.querySelector('[data-clear-recent]').onclick = () => {recent = []; try {localStorage.removeItem('smartliving-searches');} catch (_) {} renderRecent();};
    input.addEventListener('input', update); search.addEventListener('change', update);
    search.addEventListener('submit', e => {e.preventDefault(); saveRecent(); update();});
    panel.addEventListener('keydown', e => { if (e.key === 'Escape') {close(); return;} if (e.key === 'Tab') {const items = [...panel.querySelectorAll('input,button,select,a')].filter(x => !x.disabled && x.getClientRects().length); const first = items[0], last = items.at(-1); if (e.shiftKey && document.activeElement === first) {e.preventDefault(); last.focus();} else if (!e.shiftKey && document.activeElement === last) {e.preventDefault(); first.focus();}} });
  }
  const form = document.querySelector('[data-catalogue-filters]');
  if (!form) return;
  const results = form.querySelector('[data-catalogue-results]'), status = form.querySelector('[data-filter-status]');
  let timer, controller, version = 0;
  const load = async (url, push = true) => {
    const current = ++version; controller?.abort(); controller = new AbortController();
    results.setAttribute('aria-busy', 'true'); status.textContent = 'Updating products…';
    try {
      const response = await fetch(url, {signal: controller.signal, headers: {'X-Catalogue-Live':'1'}});
      if (!response.ok) throw Error();
      const data = await response.json(); if (current !== version) return;
      results.innerHTML = data.html; if (push) history.pushState({}, '', url);
      status.textContent = 'Results updated.';
    } catch (e) { if (e.name !== 'AbortError' && current === version) status.textContent = 'Live update unavailable. Use Apply filters to continue.'; }
    finally { if (current === version) results.removeAttribute('aria-busy'); }
  };
  const schedule = () => { clearTimeout(timer); ++version; controller?.abort(); timer = setTimeout(() => load(`${form.action.split('?')[0]}?${new URLSearchParams(new FormData(form))}`), 300); };
  form.querySelector('[name=q]').addEventListener('input', schedule);
  form.addEventListener('change', schedule);
  // Native submission remains available if JavaScript or a request fails.
  results.addEventListener('click', e => { const a = e.target.closest('.pagination a'); if (a && !e.ctrlKey && !e.metaKey && !e.shiftKey) {e.preventDefault(); clearTimeout(timer); load(a.href);} });
  window.addEventListener('popstate', () => location.reload());
});
