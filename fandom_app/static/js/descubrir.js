/* Descubrir: deslizar tarjetas (o usar los botones). Cada decisión se guarda en el servidor. */
(function () {
  var deck = document.getElementById('deck');
  if (!deck) return;
  var url = deck.getAttribute('data-accion');
  var csrf = document.body.getAttribute('data-csrf');
  var contador = document.getElementById('deck-contador');
  var bPasar = document.getElementById('btn-pasar'), bInteres = document.getElementById('btn-interes');
  var modal = document.getElementById('modal-match'), toast = document.getElementById('toast');
  var reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var enviando = false, drag = null;
  var sfx = function (n) { if (window.MRP && MRP.sfx) MRP.sfx(n); };

  function cartas() { return Array.prototype.slice.call(deck.querySelectorAll('.swipe-card:not(.saliendo)')); }
  function superior() { var c = cartas(); return c.length ? c[c.length - 1] : null; }
  function actualizar() {
    var n = cartas().length;
    contador.textContent = n ? n + (n === 1 ? ' perfil por descubrir' : ' perfiles por descubrir') : 'No quedan perfiles por ahora';
    deck.classList.toggle('vacio', n === 0);
    bPasar.disabled = bInteres.disabled = n === 0;
  }
  function aviso(texto) {
    toast.textContent = texto; toast.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(function () { toast.hidden = true; }, 4000);
  }

  function enviar(carta, decision) {
    if (enviando || !carta || !modal.hidden) return;
    enviando = true;
    var dir = decision === 'like' ? 1 : -1;
    carta.classList.add('saliendo');
    carta.style.setProperty(decision === 'like' ? '--si' : '--no', 1);
    carta.style.transition = reducir ? 'opacity .2s' : 'transform .45s ease-in, opacity .45s';
    carta.style.transform = reducir ? '' : 'translate(' + (dir * window.innerWidth * 0.9) + 'px,-30px) rotate(' + (dir * 22) + 'deg)';
    carta.style.opacity = '0';

    var fd = new FormData();
    fd.append('personaje_id', carta.getAttribute('data-id'));
    fd.append('decision', decision);
    fetch(url, { method: 'POST', body: fd, credentials: 'same-origin',
                 headers: { 'X-Requested-With': 'fetch', 'X-CSRF-Token': csrf } })
      .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
      .then(function (datos) {
        setTimeout(function () { carta.remove(); actualizar(); }, reducir ? 200 : 450);
        enviando = false;
        if (datos && datos.match) abrirMatch(datos.match);
      })
      .catch(function () {
        // no se guardó: la tarjeta vuelve a su lugar para poder intentarlo de nuevo
        carta.style.transition = 'transform .3s, opacity .3s';
        carta.style.transform = ''; carta.style.opacity = '';
        carta.style.setProperty('--si', 0); carta.style.setProperty('--no', 0);
        carta.classList.remove('saliendo');
        enviando = false;
        aviso('No pudimos guardar tu decisión. Revisa tu conexión e inténtalo otra vez.');
      });
  }

  // Arrastrar con el dedo o el mouse
  deck.addEventListener('pointerdown', function (e) {
    var c = e.target.closest('.swipe-card');
    if (!c || c !== superior() || enviando || e.target.closest('[data-nodrag]')) return;
    drag = { c: c, x: e.clientX, y: e.clientY, dx: 0, t: Date.now(), id: e.pointerId };
    c.setPointerCapture(e.pointerId);
    c.style.transition = 'none';
  });
  deck.addEventListener('pointermove', function (e) {
    if (!drag || e.pointerId !== drag.id) return;
    drag.dx = e.clientX - drag.x;
    var dy = (e.clientY - drag.y) * 0.2;
    drag.c.style.transform = reducir ? 'translate(' + drag.dx + 'px,0)' : 'translate(' + drag.dx + 'px,' + dy + 'px) rotate(' + (drag.dx / 18) + 'deg)';
    var p = Math.min(1, Math.abs(drag.dx) / 110);
    drag.c.style.setProperty('--si', drag.dx > 0 ? p : 0);
    drag.c.style.setProperty('--no', drag.dx < 0 ? p : 0);
  });
  function soltar(e) {
    if (!drag || e.pointerId !== drag.id) return;
    var c = drag.c, dx = drag.dx, vel = Math.abs(dx) / (Date.now() - drag.t + 1);
    drag = null;
    if (Math.abs(dx) > 110 || (Math.abs(dx) > 50 && vel > 0.6)) { enviar(c, dx > 0 ? 'like' : 'pass'); sfx(dx > 0 ? 'like' : 'pass'); }
    else {
      c.style.transition = 'transform .3s'; c.style.transform = '';
      c.style.setProperty('--si', 0); c.style.setProperty('--no', 0);
    }
  }
  deck.addEventListener('pointerup', soltar);
  deck.addEventListener('pointercancel', soltar);

  // Botones y teclado
  bInteres.addEventListener('click', function () { enviar(superior(), 'like'); });
  bPasar.addEventListener('click', function () { enviar(superior(), 'pass'); });
  document.addEventListener('keydown', function (e) {
    if (!modal.hidden) { if (e.key === 'Escape') cerrarMatch(); return; }
    var t = e.target.tagName;
    if (t === 'INPUT' || t === 'SELECT' || t === 'TEXTAREA' || t === 'SUMMARY') return;
    if (e.key === 'ArrowRight') { enviar(superior(), 'like'); sfx('like'); }
    if (e.key === 'ArrowLeft') { enviar(superior(), 'pass'); sfx('pass'); }
  });

  // Ventana "¡Es un Match!"
  function abrirMatch(m) {
    document.getElementById('mm-usuario').textContent = m.usuario;
    document.getElementById('mm-mio').src = m.mi_imagen;
    document.getElementById('mm-suyo').src = m.su_imagen;
    document.getElementById('mm-nombres').textContent = m.mi_nombre + ' y ' + m.su_nombre;
    document.getElementById('mm-chat').href = m.chat;
    document.getElementById('mm-perfil').href = m.perfil;
    modal.hidden = false;
    sfx('match');
    document.getElementById('mm-chat').focus();
  }
  function cerrarMatch() { modal.hidden = true; }
  document.getElementById('mm-seguir').addEventListener('click', cerrarMatch);
  modal.addEventListener('click', function (e) { if (e.target === modal) cerrarMatch(); });

  var det = document.querySelector('.filtros-det');
  if (det && window.innerWidth > 1100) det.open = true;
  actualizar();
})();
