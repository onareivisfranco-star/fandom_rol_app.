/* Reproductor de música ambiental. Nunca arranca solo la primera vez: hace falta pulsar play.
   Recuerda volumen, silencio, canción, posición y si estaba sonando. */
(function () {
  var raiz = document.getElementById('reproductor');
  if (!raiz) return;
  var pistas = [];
  try { pistas = JSON.parse(raiz.getAttribute('data-pistas') || '[]'); } catch (e) {}
  if (!pistas.length) return;

  var A = window.MRP.audio;
  var audio = new Audio();
  audio.preload = 'none';
  audio.loop = pistas.length === 1;
  var $ = function (id) { return document.getElementById(id); };
  var bPlay = $('mp-play'), bMute = $('mp-mute'), vol = $('mp-vol'), titulo = $('mp-titulo');
  var bPrev = $('mp-prev'), bNext = $('mp-next'), bSfx = $('mp-sfx');
  var i = Math.min(Math.max(A.get().track | 0, 0), pistas.length - 1);

  function cargar(idx, desde) {
    i = (idx + pistas.length) % pistas.length;
    audio.src = pistas[i].archivo;
    titulo.textContent = pistas[i].titulo;
    titulo.title = pistas[i].titulo;
    A.set({ track: i, time: desde || 0 });
    if (desde) audio.addEventListener('loadedmetadata', function () { try { audio.currentTime = desde; } catch (e) {} }, { once: true });
  }
  function pintar() {
    var e = A.get();
    raiz.classList.toggle('sonando', !audio.paused);
    raiz.classList.toggle('silenciado', !!e.muted);
    bPlay.setAttribute('aria-label', audio.paused ? 'Reproducir música ambiental' : 'Pausar música ambiental');
    bPlay.setAttribute('aria-pressed', String(!audio.paused));
    bMute.setAttribute('aria-pressed', String(!!e.muted));
    bMute.setAttribute('aria-label', e.muted ? 'Activar sonido' : 'Silenciar');
    if (bSfx) { bSfx.setAttribute('aria-pressed', String(!!e.sfx)); bSfx.classList.toggle('apagado', !e.sfx); }
    vol.value = Math.round(e.vol * 100);
    audio.volume = e.muted ? 0 : e.vol;
  }
  function reproducir() {
    var p = audio.play();
    if (p && p.catch) p.catch(function () { raiz.classList.add('pendiente'); });
    return p;
  }

  bPlay.addEventListener('click', function () {
    if (audio.paused) {
      if (A.get().muted) A.set({ muted: false });          // pulsar play es una decisión clara de escuchar
      if (!audio.src) cargar(i, A.get().time);
      pintar();
      raiz.classList.remove('pendiente');
      A.set({ playing: true });
      reproducir();
    } else {
      audio.pause(); A.set({ playing: false });
    }
  });
  bMute.addEventListener('click', function () {
    var m = !A.get().muted;
    A.set({ muted: m });
    if (m && !audio.paused) { audio.pause(); A.set({ playing: false }); }   // silenciado = no suena nada
    pintar();
  });
  vol.addEventListener('input', function () {
    var v = vol.value / 100;
    A.set({ vol: v, muted: v === 0 ? true : false });
    if (v === 0 && !audio.paused) { audio.pause(); A.set({ playing: false }); }
    pintar();
  });
  function cambiar(delta) {
    var sonaba = !audio.paused;
    cargar(i + delta, 0);
    if (sonaba) reproducir();
  }
  if (bPrev) bPrev.addEventListener('click', function () { cambiar(-1); });
  if (bNext) bNext.addEventListener('click', function () { cambiar(1); });
  if (bSfx) bSfx.addEventListener('click', function () { A.set({ sfx: !A.get().sfx }); pintar(); if (A.get().sfx) window.MRP.sfx('tap'); });

  audio.addEventListener('play', pintar);
  audio.addEventListener('pause', pintar);
  audio.addEventListener('ended', function () { if (pistas.length > 1) cambiar(1); });
  var ultimo = 0;
  audio.addEventListener('timeupdate', function () {
    var ahora = Date.now();
    if (ahora - ultimo > 1000 && !audio.paused) { ultimo = ahora; A.set({ time: Math.floor(audio.currentTime) }); }
  });
  window.addEventListener('pagehide', function () { if (!audio.paused) A.set({ time: Math.floor(audio.currentTime) }); });

  // Al cambiar de página: si ya estaba sonando y no está silenciado, continúa por donde iba.
  cargar(i, A.get().time);
  pintar();
  var e0 = A.get();
  if (e0.playing && !e0.muted) {
    var p = audio.play();
    if (p && p.catch) p.catch(function () {
      // El navegador pide un gesto: seguimos en cuanto el usuario toque algo.
      raiz.classList.add('pendiente');
      var seguir = function () {
        document.removeEventListener('pointerdown', seguir, true); document.removeEventListener('keydown', seguir, true);
        raiz.classList.remove('pendiente');
        var s = A.get(); if (s.playing && !s.muted && audio.paused) reproducir();
      };
      document.addEventListener('pointerdown', seguir, true); document.addEventListener('keydown', seguir, true);
    });
  }
})();
