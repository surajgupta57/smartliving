document.addEventListener('DOMContentLoaded', () => {
  const brandCarousel = document.querySelector('[data-brand-carousel]');
  if (brandCarousel) {
    const toggle = brandCarousel.querySelector('[data-brand-motion-toggle]');
    const brandGroup = brandCarousel.querySelector('.living-brands-group');
    const setBrandSpeed = () => {
      brandCarousel.style.setProperty('--brand-duration', `${Math.max(35, brandGroup.getBoundingClientRect().width / 26)}s`);
    };
    setBrandSpeed();
    if ('ResizeObserver' in window) new ResizeObserver(setBrandSpeed).observe(brandGroup);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const setPlayback = (running) => {
      brandCarousel.dataset.brandMotion = running ? 'running' : 'paused';
      toggle.setAttribute('aria-pressed', String(!running));
      toggle.textContent = running ? 'Pause motion' : 'Play motion';
    };
    brandCarousel.classList.add('is-ready');
    toggle.hidden = false;
    // This independently controlled carousel is explicitly configured to autoplay.
    setPlayback(true);
    toggle.addEventListener('click', () => setPlayback(brandCarousel.dataset.brandMotion !== 'running'));
    reducedMotion.addEventListener('change', () => setPlayback(!reducedMotion.matches));
  }

  const scenes = {
    home: { title: 'Walk in. Wind down.', caption: 'Coming home · a warmer welcome', description: 'A planned lighting scene can bring your favourite spaces to life with a single action. Discuss compatible controls and installation with our team.' },
    evening: { title: 'Turn the lights down. Take a breath.', caption: 'Quiet evening · a softer atmosphere', description: 'Explore softer lighting for reading, relaxing or watching a film. Scene control and dimming depend on compatible lights and selected equipment.' },
    away: { title: 'Step out. Stay connected.', caption: 'Away from home · keep a clear view', description: 'Discuss connected CCTV and remote viewing so you can check on your property. Features depend on equipment, configuration and internet access.' }
  };
  const visual = document.querySelector('[data-scene-visual]');
  const controls = [...document.querySelectorAll('[data-living-scene]')];
  if (!visual) return;
  controls.forEach((button) => button.addEventListener('click', () => {
    const key = button.dataset.livingScene;
    const scene = scenes[key];
    if (!scene) return;
    visual.dataset.scene = key;
    document.querySelector('[data-scene-title]').textContent = scene.title;
    document.querySelector('[data-scene-description]').textContent = scene.description;
    document.querySelector('[data-scene-caption]').textContent = scene.caption;
    controls.forEach((control) => {
      const selected = control === button;
      control.classList.toggle('is-selected', selected);
      control.setAttribute('aria-pressed', String(selected));
    });
  }));
});
