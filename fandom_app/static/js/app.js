(function () {
  // Menú lateral en el celular
  var menu = document.getElementById('menu'), velo = document.getElementById('velo');
  var btn = document.getElementById('btn-menu');
  function alternar(abrir) {
    if (!menu) return;
    menu.classList.toggle('abierto', abrir);
    if (velo) velo.classList.toggle('abierto', abrir);
  }
  if (btn) btn.addEventListener('click', function () { alternar(!menu.classList.contains('abierto')); });
  if (velo) velo.addEventListener('click', function () { alternar(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') alternar(false); });

  // Filtros por estado + buscador + paginación (cuadrícula adaptable)
  document.querySelectorAll('[data-filtros]').forEach(function (grupo) {
    var sel = grupo.getAttribute('data-filtros');
    var destino = document.querySelector(sel);
    if (!destino) return;
    var buscador = document.querySelector(grupo.getAttribute('data-buscador') || '#none');
    var pager = document.querySelector('[data-paginacion="' + sel + '"]');
    var vacio = destino.parentElement.querySelector('.vacio-filtro');
    var porPagina = parseInt(destino.getAttribute('data-pagina') || '0', 10);
    var chips = grupo.querySelectorAll('[data-estado]');
    var estado = '', pagina = 1;

    function dibujarPager(paginas) {
      if (!pager) return;
      pager.hidden = paginas <= 1;
      pager.innerHTML = '';
      if (paginas <= 1) return;
      function boton(txt, p, etiqueta, activo, off) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'pag-btn' + (activo ? ' activo' : '');
        b.textContent = txt; b.setAttribute('aria-label', etiqueta);
        if (activo) b.setAttribute('aria-current', 'page');
        b.disabled = !!off;
        b.addEventListener('click', function () { pagina = p; aplicar(false, true); });
        pager.appendChild(b);
      }
      boton('‹', pagina - 1, 'Página anterior', false, pagina === 1);
      for (var p = 1; p <= paginas; p++) boton(String(p), p, 'Página ' + p, p === pagina, false);
      boton('›', pagina + 1, 'Página siguiente', false, pagina === paginas);
    }

    function aplicar(reiniciar, desplazar) {
      if (reiniciar) pagina = 1;
      var q = buscador ? buscador.value.trim().toLowerCase() : '';
      var items = Array.prototype.slice.call(destino.querySelectorAll('.pj-item'));
      var ok = items.filter(function (it) {
        return (!estado || it.dataset.estado === estado) && (!q || it.dataset.texto.indexOf(q) !== -1);
      });
      var paginas = porPagina ? Math.max(1, Math.ceil(ok.length / porPagina)) : 1;
      if (pagina > paginas) pagina = paginas;
      var ini = porPagina ? (pagina - 1) * porPagina : 0;
      var fin = porPagina ? ini + porPagina : ok.length;
      items.forEach(function (it) { it.hidden = true; });
      ok.slice(ini, fin).forEach(function (it) { it.hidden = false; });
      if (vacio) vacio.hidden = ok.length !== 0;
      dibujarPager(paginas);
      if (desplazar) destino.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    chips.forEach(function (c) {
      c.addEventListener('click', function () {
        chips.forEach(function (x) { x.classList.remove('activo'); });
        c.classList.add('activo');
        estado = c.dataset.estado;
        aplicar(true);
      });
    });
    if (buscador) buscador.addEventListener('input', function () { aplicar(true); });
    aplicar(true);
  });

  // Chat: ir al último mensaje
  var caja = document.getElementById('chat-caja');
  if (caja) caja.scrollTop = caja.scrollHeight;
})();
