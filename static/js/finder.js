document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-finder-form]');
  if (!form) return;
  const goal = form.querySelector('[name=goal]');
  const update = () => {
    const cctv = ['cctv', 'multiple'].includes(goal.value);
    ['cameras', 'connection'].forEach(name => {
      const field = form.querySelector(`[name="${name}"]`);
      field.closest('.form-row').hidden = !cctv;
      field.disabled = !cctv;
      if (!cctv) field.value = '';
    });
  };
  goal.addEventListener('change', update);
  update();
});
