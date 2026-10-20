// Cinematic landing motion: scroll-linked depth, pointer tilt, card spotlight.
// Only writes CSS custom properties (CSP-safe); all visuals live in style.css.
const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));

export function initMotion(root = document) {
  const still = matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.classList.contains('reduce-motion');
  if (still || !root.querySelector('.hero')) return () => {};
  const cleanup = [];
  const listen = (target, type, handler, options) => { target.addEventListener(type, handler, options); cleanup.push(() => target.removeEventListener(type, handler, options)); };

  const bar = document.createElement('div'); bar.className = 'scroll-progress'; bar.setAttribute('aria-hidden', 'true');
  document.body.append(bar); cleanup.push(() => bar.remove());
  const scene = root.querySelector('.preview-scene');
  const art = root.querySelector('.security-art');
  const hero = root.querySelector('.hero');
  document.documentElement.classList.add('motion-on'); cleanup.push(() => document.documentElement.classList.remove('motion-on'));

  let frame = 0;
  const update = () => {
    frame = 0;
    const height = document.documentElement.scrollHeight - innerHeight;
    bar.style.setProperty('--progress', height > 0 ? clamp(scrollY / height) : 0);
    hero.style.setProperty('--hero-p', clamp(scrollY / (innerHeight * .9)));
    if (art) { const box = art.getBoundingClientRect(); art.style.setProperty('--art-p', clamp(1 - (box.top + box.height / 2) / (innerHeight * 1.2), -1, 1).toFixed(3)); }
  };
  const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
  listen(window, 'scroll', schedule, { passive: true });
  listen(window, 'resize', schedule, { passive: true });
  cleanup.push(() => cancelAnimationFrame(frame));
  update();

  // Pointer tilt for the preview window and the shield object.
  const tilt = (element, strength) => {
    if (!element) return;
    listen(element, 'pointermove', event => {
      const box = element.getBoundingClientRect();
      element.style.setProperty('--tilt-y', ((event.clientX - box.left) / box.width - .5) * strength + 'deg');
      element.style.setProperty('--tilt-x', ((event.clientY - box.top) / box.height - .5) * -strength + 'deg');
    });
    listen(element, 'pointerleave', () => { element.style.setProperty('--tilt-x', '0deg'); element.style.setProperty('--tilt-y', '0deg'); });
  };
  tilt(scene, 6); tilt(art, 14);

  // Cursor spotlight on cards, delegated so re-renders need no rebinding.
  listen(document, 'pointermove', event => {
    const card = event.target.closest?.('.preview-row,.art-event,.security-facts>div,.art-credential,.art-password');
    if (!card) return;
    const box = card.getBoundingClientRect();
    card.style.setProperty('--mx', event.clientX - box.left + 'px');
    card.style.setProperty('--my', event.clientY - box.top + 'px');
  }, { passive: true });

  return () => cleanup.forEach(fn => fn());
}
