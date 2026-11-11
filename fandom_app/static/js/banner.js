/* Banner animado: pausa para accesibilidad, ahorro de recursos y un parallax suave en las capas. */
(function () {
  var hero = document.getElementById('hero');
  if (!hero) return;
  var KEY = 'mrp.banner.pausa';
  var reducir = window.matchMedia('(prefers-reduced-motion: reduce)');
  var btn = document.getElementById('hero-pausa');
  var pausado = false;
  try { pausado = localStorage.getItem(KEY) === '1'; } catch (e) {}

  function pintar() {
    hero.classList.toggle('pausada', pausado);
    if (!btn) return;
    btn.setAttribute('aria-pressed', String(pausado));
    btn.setAttribute('aria-label', pausado ? 'Reanudar animación del banner' : 'Pausar animación del banner');
    btn.title = pausado ? 'Reanudar animación' : 'Pausar animación';
  }
  if (btn) btn.addEventListener('click', function () {
    pausado = !pausado;
    try { localStorage.setItem(KEY, pausado ? '1' : '0'); } catch (e) {}
    pintar();
  });
  pintar();

  // Se detiene cuando el banner no se ve o la pestaña está oculta
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (en) { hero.classList.toggle('fuera', !en[0].isIntersecting); }, { threshold: 0.05 }).observe(hero);
  }
  document.addEventListener('visibilitychange', function () { hero.classList.toggle('oculta', document.hidden); });

  // Parallax: solo se mueven las capas (mariposas y partículas), nunca la ilustración base ni el título
  var tx = 0, ty = 0, cx = 0, cy = 0, raf = 0;
  function paso() {
    cx += (tx - cx) * 0.08; cy += (ty - cy) * 0.08;
    hero.style.setProperty('--px', cx.toFixed(3));
    hero.style.setProperty('--py', cy.toFixed(3));
    raf = (Math.abs(tx - cx) > 0.002 || Math.abs(ty - cy) > 0.002) ? requestAnimationFrame(paso) : 0;
  }
  hero.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch' || reducir.matches || pausado) return;
    var r = hero.getBoundingClientRect();
    tx = ((e.clientX - r.left) / r.width - 0.5) * 2;
    ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
    if (!raf) raf = requestAnimationFrame(paso);
  });
  hero.addEventListener('pointerleave', function () { tx = ty = 0; if (!raf) raf = requestAnimationFrame(paso); });
})();
