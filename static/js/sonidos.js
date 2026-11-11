/* Ajustes de audio compartidos + sonidos de interfaz (un "tap" suave, sintetizado con WebAudio).
   No hay archivos de sonido: se generan en el navegador, así que no pesan ni tienen derechos de autor. */
(function () {
  var KEY = 'mrp.audio';
  var base = { vol: 0.35, muted: false, sfx: true, track: 0, playing: false, time: 0 };
  var datos = base;
  try { datos = Object.assign({}, base, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) {}
  var MRP = window.MRP = window.MRP || {};
  MRP.audio = {
    get: function () { return datos; },
    set: function (cambios) {
      datos = Object.assign({}, datos, cambios);
      try { localStorage.setItem(KEY, JSON.stringify(datos)); } catch (e) {}
    }
  };

  var ctx = null;
  function ac() {
    if (!ctx) { var C = window.AudioContext || window.webkitAudioContext; if (!C) return null; ctx = new C(); }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  function tono(c, f, dur, tipo, vol, retraso, fFinal) {
    var t0 = c.currentTime + (retraso || 0);
    var o = c.createOscillator(), g = c.createGain();
    o.type = tipo || 'sine';
    o.frequency.setValueAtTime(f, t0);
    if (fFinal) o.frequency.exponentialRampToValueAtTime(fFinal, t0 + dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(vol, t0 + 0.006);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    o.connect(g); g.connect(c.destination);
    o.start(t0); o.stop(t0 + dur + 0.02);
  }
  var SONIDOS = {
    tap:   function (c) { tono(c, 540, 0.07, 'sine', 0.16, 0, 420); tono(c, 1080, 0.04, 'sine', 0.05, 0); },
    // burbuja: un "blop" corto que sube de tono (menú lateral, filtros, pestañas)
    nav:   function (c) { tono(c, 330, 0.11, 'sine', 0.15, 0, 820); tono(c, 990, 0.05, 'sine', 0.04, 0.03, 1500); },
    enviar:  function (c) { tono(c, 620, 0.06, 'sine', 0.14, 0, 760); tono(c, 930, 0.1, 'sine', 0.1, 0.05); },
    recibir: function (c) { tono(c, 880, 0.09, 'sine', 0.1, 0); tono(c, 660, 0.16, 'sine', 0.09, 0.08); },
    like:  function (c) { tono(c, 660, 0.14, 'sine', 0.15, 0); tono(c, 990, 0.2, 'sine', 0.12, 0.07); tono(c, 1320, 0.26, 'sine', 0.07, 0.14); },
    pass:  function (c) { tono(c, 340, 0.13, 'triangle', 0.12, 0, 190); },
    // brillitos: acorde ascendente más una lluvia de campanitas agudas
    match: function (c) {
      [523, 659, 784, 1047, 1319].forEach(function (f, i) { tono(c, f, 0.5, 'sine', 0.11, i * 0.09); });
      var notas = [1568, 1760, 2093, 2349, 2637, 3136, 3520];
      for (var k = 0; k < 16; k++) {
        var f2 = notas[(k * 3 + (k >> 1)) % notas.length];
        tono(c, f2, 0.28 + (k % 3) * 0.06, 'sine', 0.035 + (k % 4) * 0.008, 0.12 + k * 0.075);
      }
      tono(c, 400, 0.9, 'sine', 0.05, 0.05, 2400);
    }
  };
  MRP.sfx = function (nombre) {
    var e = datos;
    if (!e.sfx || e.muted) return;
    var c = ac(); if (!c || !SONIDOS[nombre]) return;
    SONIDOS[nombre](c);
  };

  // Un "tap" al pulsar botones, pestañas, filtros y enlaces del menú
  document.addEventListener('click', function (ev) {
    var el = ev.target.closest && ev.target.closest('button, a.btn, a.tab, a.nav-link, .chip, .icono-btn, summary, .pag-btn');
    if (!el || el.disabled || el.hasAttribute('data-silencio')) return;
    var nombre = el.getAttribute('data-sonido') || (el.matches('.chip, .nav-link, .tab, .pag-btn') ? 'nav' : 'tap');
    MRP.sfx(nombre);
  }, true);
})();
