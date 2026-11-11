/* Panel de admin: búsqueda en vivo, acordeones con contadores, acciones rápidas sin recargar. */
(function () {
  var csrf = document.body.getAttribute('data-csrf');
  var sfx = function (n) { if (window.MRP && MRP.sfx) MRP.sfx(n); };
  function norm(t) { return (t || '').toLowerCase().trim(); }
  function el(tag, clase, txt) { var e = document.createElement(tag); if (clase) e.className = clase; if (txt != null) e.textContent = txt; return e; }
  var toast = document.createElement('div'); toast.className = 'toast'; toast.hidden = true; toast.setAttribute('role', 'status'); document.body.appendChild(toast);
  function aviso(txt, ok) {
    toast.textContent = txt; toast.style.borderColor = ok === false ? '#ff7ab8' : ''; toast.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(function () { toast.hidden = true; }, 3800);
  }

  // ---- búsqueda simple de la lista de roleros
  document.querySelectorAll('[data-buscar]').forEach(function (inp) {
    var cont = document.querySelector(inp.getAttribute('data-buscar'));
    inp.addEventListener('input', function () {
      var q = norm(inp.value);
      cont.querySelectorAll('[data-texto]').forEach(function (f) { f.hidden = q && f.getAttribute('data-texto').indexOf(q) === -1; });
    });
  });

  // ---- contadores y filtro de la lista por fandom
  var cont = document.getElementById('acordeones');
  function recontar() {
    if (!cont) return;
    var tl = 0, to = 0;
    cont.querySelectorAll('[data-grupo]').forEach(function (g) {
      var filas = g.querySelectorAll('.pj-fila');
      var libres = 0; filas.forEach(function (f) { if (f.getAttribute('data-libre') === '1') libres++; });
      g.querySelector('[data-libres]').textContent = libres;
      g.querySelector('[data-ocupados]').textContent = filas.length - libres;
      tl += libres; to += filas.length - libres;
      if (!filas.length) g.remove();
    });
    var a = document.getElementById('tot-libres'), b = document.getElementById('tot-ocupados');
    if (a) a.textContent = tl; if (b) b.textContent = to;
  }
  function filtrarLista() {
    var inp = document.getElementById('buscar-global');
    if (!inp || !cont) return;
    var q = norm(inp.value), hay = false;
    cont.querySelectorAll('[data-grupo]').forEach(function (g) {
      var visibles = 0;
      g.querySelectorAll('.pj-fila').forEach(function (f) {
        var ok = !q || f.getAttribute('data-texto').indexOf(q) !== -1 || g.getAttribute('data-grupo').indexOf(q) !== -1;
        f.hidden = !ok; if (ok) visibles++;
      });
      g.hidden = visibles === 0;
      if (q) g.open = visibles > 0;
      if (visibles) hay = true;
    });
    var sr = document.getElementById('sin-resultados'); if (sr) sr.hidden = hay || !q;
  }
  var bg = document.getElementById('buscar-global'); if (bg) bg.addEventListener('input', filtrarLista);

  // ---- búsqueda por usuario/personaje/fandom en la vista por usuario
  var bu = document.getElementById('buscar-usuarios');
  if (bu) bu.addEventListener('input', function () {
    var q = norm(bu.value), hay = false;
    document.querySelectorAll('[data-bloque]').forEach(function (b) {
      var ok = !q || b.getAttribute('data-texto').indexOf(q) !== -1;
      b.hidden = !ok; if (q && ok) b.open = true; if (ok) hay = true;
    });
    var sr = document.getElementById('sin-resultados'); if (sr) sr.hidden = hay || !q;
  });

  // ---- acciones rápidas en cada fila (sin recargar la página)
  function poner(fila, libre, usuario, perfil) {
    fila.setAttribute('data-libre', libre ? '1' : '0');
    fila.setAttribute('data-usuario', libre ? '' : norm(usuario));
    var chip = fila.querySelector('.dueno-chip');
    if (chip) { chip.textContent = libre ? '' : usuario; chip.setAttribute('href', libre ? '#' : (perfil || '#')); }
    var texto = fila.getAttribute('data-texto') || '';
    fila.setAttribute('data-texto', texto.replace(/ [^ ]*$/, '') + ' ' + (libre ? 'libre' : norm(usuario)));
  }
  function quitarFila(fila) {
    var ul = fila.parentElement; fila.remove();
    var bloque = ul && ul.closest('[data-bloque]');
    if (bloque) {
      var n = ul.querySelectorAll('.pj-fila').length;
      bloque.querySelector('[data-total]').textContent = n;
      var sin = bloque.querySelector('[data-sin-personajes]'); if (sin) sin.hidden = n > 0;
      var lt = bloque.querySelector('[data-accion="liberar-todos"]'); if (lt && !n) lt.remove();
    }
  }
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-ajax]');
    if (!f) return;
    e.preventDefault();
    var msg = f.getAttribute('data-confirmar');
    if (msg && !window.confirm(msg)) return;
    var accion = f.getAttribute('data-accion'), fila = f.closest('.pj-fila');
    var fd = new FormData(f);
    var boton = f.querySelector('button'); if (boton) boton.disabled = true;
    fetch(f.action, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch', 'X-CSRF-Token': csrf } })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (boton) boton.disabled = false;
        var d = res.d;
        if (!res.ok) { aviso(d.mensaje || 'No se pudo completar la acción.', false); return; }
        if (accion === 'asignar' && fila) { poner(fila, false, d.usuario, d.perfil); f.reset(); }
        else if (accion === 'liberar' && fila) {
          if (fila.getAttribute('data-modo') === 'usuario') quitarFila(fila); else poner(fila, true);
        }
        else if (accion === 'quitar' && fila) quitarFila(fila);
        else if (accion === 'liberar-todos') {
          var bloque = f.closest('[data-bloque]');
          if (bloque) bloque.querySelectorAll('.pj-fila').forEach(quitarFila);
          var res = document.getElementById('saliente-res');
          if (res && f.closest('#saliente-res')) { res.textContent = ''; res.appendChild(el('div', 'aviso aviso-success', d.mensaje)); }
          // en la lista general, los personajes liberados pasan a "libre"
          (d.ids || []).forEach(function (id) {
            var fl = document.querySelector('#acordeones .pj-fila[data-id="' + id + '"]'); if (fl) poner(fl, true);
          });
        }
        recontar(); filtrarLista(); sfx('enviar');
        aviso(d.mensaje, true);
      })
      .catch(function () { if (boton) boton.disabled = false; aviso('No pudimos conectar con el servidor. Inténtalo otra vez.', false); });
  });

  // ---- usuarios salientes: solo sus personajes + liberar todos
  var sal = document.getElementById('saliente'), salRes = document.getElementById('saliente-res');
  if (sal && cont) {
    var usuarios = {};
    document.querySelectorAll('#lista-usuarios option').forEach(function (o) {
      usuarios[norm(o.value)] = { nombre: o.value, id: o.getAttribute('data-id') };
    });
    sal.addEventListener('input', function () {
      var q = norm(sal.value); salRes.textContent = '';
      if (!q) return;
      var u = usuarios[q];
      if (!u) { salRes.appendChild(el('p', 'ayuda', 'Elige el nombre completo de la lista de sugerencias.')); return; }
      var filas = [].slice.call(cont.querySelectorAll('.pj-fila')).filter(function (f) { return f.getAttribute('data-usuario') === q; });
      var caja = el('div', 'saliente-caja');
      caja.appendChild(el('h3', 'cursivo', u.nombre + ' tiene ' + filas.length + ' personaje' + (filas.length === 1 ? '' : 's')));
      if (!filas.length) { caja.appendChild(el('p', 'suave', 'No tiene personajes asignados.')); salRes.appendChild(caja); return; }
      var ul = el('ul', 'pj-filas');
      filas.forEach(function (f) {
        var li = el('li', 'pj-fila-simple');
        li.appendChild(el('span', 'pj-fila-nombre', f.querySelector('.pj-fila-nombre').textContent));
        var g = f.closest('[data-grupo]').querySelector('.acordeon-nombre');
        li.appendChild(el('span', 'suave', g.childNodes[0].textContent.trim()));
        ul.appendChild(li);
      });
      caja.appendChild(ul);
      var fm = el('form', 'saliente-form');
      fm.method = 'post'; fm.action = '/admin/usuario/' + u.id + '/liberar-todos';
      fm.setAttribute('data-ajax', ''); fm.setAttribute('data-accion', 'liberar-todos');
      fm.setAttribute('data-confirmar', '¿Liberar TODOS los personajes de ' + u.nombre + '? Volverán a su fandom como libres.');
      fm.innerHTML = '<input type="hidden" name="_csrf" value="' + csrf + '">' +
        '<label class="check"><input type="checkbox" name="suspender" value="1">Suspender también su cuenta</label>';
      var b = el('button', 'btn btn-peligro'); b.textContent = 'Liberar todos los personajes';
      fm.appendChild(b); caja.appendChild(fm); salRes.appendChild(caja);
    });
  }

  // ---- copiar y guardar la lista
  var copiar = document.getElementById('copiar-lista');
  if (copiar) copiar.addEventListener('click', function () {
    var ta = document.getElementById('texto-lista'); ta.select();
    var listo = function () { var c = document.getElementById('copiado'); c.hidden = false; setTimeout(function () { c.hidden = true; }, 2500); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(listo, function () { document.execCommand('copy'); listo(); });
    else { document.execCommand('copy'); listo(); }
  });
  var fl = document.getElementById('form-lista');
  if (fl) fl.addEventListener('submit', function (e) {
    if (document.getElementById('quitar-libres').checked && !window.confirm('Se quitarán de la lista los personajes libres que no estén en este texto. ¿Continuar?')) e.preventDefault();
  });
})();
