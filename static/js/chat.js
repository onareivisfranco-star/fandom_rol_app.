/* Chat flotante: conversa desde cualquier página sin ir a Mis matches. */
(function () {
  var dock = document.getElementById('chat-dock'), btn = document.getElementById('chat-btn');
  if (!dock || !btn) return;
  var lista = document.getElementById('chat-lista'), hilo = document.getElementById('chat-hilo');
  var msgs = document.getElementById('chat-msgs'), form = document.getElementById('chat-form');
  var texto = document.getElementById('chat-texto'), titulo = document.getElementById('chat-titulo');
  var atras = document.getElementById('chat-atras'), cerrar = document.getElementById('chat-cerrar');
  var contador = document.getElementById('chat-contador');
  var csrf = document.body.getAttribute('data-csrf');
  var sfx = function (n) { if (window.MRP && MRP.sfx) MRP.sfx(n); };
  var abierto = false, actual = null, ultimoId = 0, tHilo = null, tResumen = null, sinLeerPrevio = parseInt(contador.textContent || '0', 10) || 0;

  function pedir(url, opciones) {
    opciones = opciones || {};
    opciones.credentials = 'same-origin';
    opciones.headers = Object.assign({ 'X-Requested-With': 'fetch', 'X-CSRF-Token': csrf }, opciones.headers || {});
    return fetch(url, opciones).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }
  function el(tag, clase, txt) { var e = document.createElement(tag); if (clase) e.className = clase; if (txt != null) e.textContent = txt; return e; }
  function hora(iso) {
    if (!iso) return '';
    var d = new Date(iso); return isNaN(d) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  function pintarContador(n) {
    contador.textContent = n; contador.hidden = !n;
    btn.setAttribute('aria-label', 'Mensajes' + (n ? ' (' + n + ' sin leer)' : ''));
  }

  function avatar(c) {
    if (c.foto) { var i = el('img', 'avatar avatar-md'); i.src = c.foto; i.alt = ''; return i; }
    return el('span', 'avatar avatar-md', (c.usuario || '?').charAt(0).toUpperCase());
  }
  function mostrarLista() {
    actual = null; clearInterval(tHilo);
    hilo.hidden = true; lista.hidden = false; atras.hidden = true; titulo.textContent = 'Mensajes';
    pedir('/api/chats').then(function (d) {
      lista.textContent = '';
      pintarContador(d.sin_leer);
      if (!d.chats.length) {
        lista.appendChild(el('div', 'vacio', 'Todavía no tienes conversaciones. Cuando hagas match con alguien, podrás escribirle aquí.'));
        return;
      }
      d.chats.forEach(function (c) {
        var f = el('button', 'chat-item'); f.type = 'button';
        f.appendChild(avatar(c));
        var t = el('span', 'chat-item-txt');
        t.appendChild(el('b', null, c.usuario)); t.appendChild(el('small', 'suave', c.ultimo));
        f.appendChild(t);
        if (c.sin_leer) f.appendChild(el('span', 'contador', c.sin_leer));
        f.addEventListener('click', function () { abrirHilo(c.id, c.usuario); });
        lista.appendChild(f);
      });
    }).catch(function () { lista.textContent = ''; lista.appendChild(el('div', 'vacio', 'No pudimos cargar tus mensajes. Inténtalo de nuevo.')); });
  }

  function burbuja(m) {
    var b = el('div', 'burbuja' + (m.mio ? ' mia' : ''));
    b.appendChild(el('span', null, m.texto));
    var h = hora(m.hora); if (h) b.appendChild(el('small', 'burbuja-hora', h));
    return b;
  }
  function agregar(lista_msgs, sonido) {
    var cerca = msgs.scrollHeight - msgs.scrollTop - msgs.clientHeight < 80;
    lista_msgs.forEach(function (m) { msgs.appendChild(burbuja(m)); ultimoId = Math.max(ultimoId, m.id); });
    if (cerca || sonido === 'propio') msgs.scrollTop = msgs.scrollHeight;
  }
  function cargarNuevos(primera) {
    if (actual == null) return;
    pedir('/api/chat/' + actual + '?desde=' + ultimoId).then(function (d) {
      if (actual == null) return;
      if (primera) { msgs.textContent = ''; if (!d.mensajes.length) msgs.appendChild(el('div', 'vacio', 'Rompe el hielo: cuéntale qué trama te gustaría rolear.')); }
      else if (d.mensajes.length && msgs.querySelector('.vacio')) msgs.textContent = '';
      var recibidos = d.mensajes.filter(function (m) { return !m.mio; }).length;
      if (primera && d.mensajes.length) msgs.textContent = '';
      agregar(d.mensajes);
      if (primera) msgs.scrollTop = msgs.scrollHeight;
      else if (recibidos) sfx('recibir');
    }).catch(function () {});
  }
  function abrirHilo(id, nombre) {
    actual = id; ultimoId = 0;
    lista.hidden = true; hilo.hidden = false; atras.hidden = false; titulo.textContent = nombre;
    msgs.textContent = '';
    cargarNuevos(true);
    clearInterval(tHilo); tHilo = setInterval(function () { if (!document.hidden) cargarNuevos(false); }, 4000);
    setTimeout(function () { texto.focus(); }, 50);
  }
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var t = texto.value.trim(); if (!t || actual == null) return;
    var fd = new FormData(); fd.append('texto', t);
    texto.value = '';
    pedir('/api/chat/' + actual, { method: 'POST', body: fd }).then(function (d) {
      if (msgs.querySelector('.vacio')) msgs.textContent = '';
      agregar([d.mensaje], 'propio');
      sfx('enviar');
    }).catch(function () { texto.value = t; });
  });

  function abrir(id) {
    abierto = true; dock.hidden = false; btn.setAttribute('aria-expanded', 'true');
    if (id) { var etiqueta = ''; abrirHilo(id, etiqueta || 'Conversación'); pedir('/api/chats').then(function (d) { d.chats.forEach(function (c) { if (c.id === id) titulo.textContent = c.usuario; }); pintarContador(d.sin_leer); }); }
    else mostrarLista();
  }
  function cerrarDock() {
    abierto = false; dock.hidden = true; btn.setAttribute('aria-expanded', 'false'); actual = null; clearInterval(tHilo);
    resumen();
  }
  btn.addEventListener('click', function () { abierto ? cerrarDock() : abrir(); });
  cerrar.addEventListener('click', cerrarDock);
  atras.addEventListener('click', mostrarLista);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && abierto) cerrarDock(); });
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-abrir-chat]');
    if (a && !e.ctrlKey && !e.metaKey && !e.shiftKey) { e.preventDefault(); abrir(parseInt(a.getAttribute('data-abrir-chat'), 10)); }
  });

  // Aviso de mensajes nuevos con el panel cerrado
  function resumen() {
    if (abierto || document.hidden) return;
    pedir('/api/chats').then(function (d) {
      if (d.sin_leer > sinLeerPrevio) sfx('recibir');
      sinLeerPrevio = d.sin_leer; pintarContador(d.sin_leer);
    }).catch(function () {});
  }
  tResumen = setInterval(resumen, 30000);
})();
