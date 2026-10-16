document.addEventListener('DOMContentLoaded', () => {
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
