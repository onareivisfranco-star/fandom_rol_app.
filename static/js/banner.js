/* Banner animado: el pelo ondea (WebGL), parallax suave y pausa para accesibilidad y ahorro de recursos.
   Los ojos, las mariposas y las estrellas se animan solo con CSS. */
(function () {
  var hero = document.getElementById('hero');
  if (!hero) return;
  var KEY = 'mrp.banner.pausa';
  var reducir = window.matchMedia('(prefers-reduced-motion: reduce)');
  var btn = document.getElementById('hero-pausa');
  var pausado = false, fuera = false, oculto = document.hidden;
  try { pausado = localStorage.getItem(KEY) === '1'; } catch (e) {}
  var motor = null;                                   // se rellena si WebGL está disponible

  function activo() { return !pausado && !fuera && !oculto && !reducir.matches; }
  function pintar() {
    hero.classList.toggle('pausada', pausado);
    if (btn) {
      btn.setAttribute('aria-pressed', String(pausado));
      btn.setAttribute('aria-label', pausado ? 'Reanudar animación del banner' : 'Pausar animación del banner');
      btn.title = pausado ? 'Reanudar animación' : 'Pausar animación';
    }
    if (motor) motor.estado();
  }
  if (btn) btn.addEventListener('click', function () {
    pausado = !pausado;
    try { localStorage.setItem(KEY, pausado ? '1' : '0'); } catch (e) {}
    pintar();
  });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (en) { fuera = !en[0].isIntersecting; hero.classList.toggle('fuera', fuera); if (motor) motor.estado(); }, { threshold: 0.05 }).observe(hero);
  }
  document.addEventListener('visibilitychange', function () { oculto = document.hidden; hero.classList.toggle('oculta', oculto); if (motor) motor.estado(); });
  if (reducir.addEventListener) reducir.addEventListener('change', pintar);

  // ---- parallax (el fondo, las mariposas y las partículas se mueven distinto; el título no)
  var tx = 0, ty = 0, cx = 0, cy = 0, raf = 0;
  function paso() {
    cx += (tx - cx) * 0.08; cy += (ty - cy) * 0.08;
    hero.style.setProperty('--px', cx.toFixed(3)); hero.style.setProperty('--py', cy.toFixed(3));
    raf = (Math.abs(tx - cx) > 0.002 || Math.abs(ty - cy) > 0.002) ? requestAnimationFrame(paso) : 0;
  }
  hero.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch' || reducir.matches || pausado) return;
    var r = hero.getBoundingClientRect();
    tx = ((e.clientX - r.left) / r.width - 0.5) * 2; ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
    if (!raf) raf = requestAnimationFrame(paso);
  });
  hero.addEventListener('pointerleave', function () { tx = ty = 0; if (!raf) raf = requestAnimationFrame(paso); });

  // ---- pelo que ondea: la ilustración completa se dibuja con un mapa de "peso":
  //      cara, mano y vestido quedan quietos; los mechones sueltos se mueven con ondas suaves.
  var cv = document.getElementById('chica-canvas'), img = hero.querySelector('.chica-img');
  if (cv && img) {
    var gl = null;
    try { gl = cv.getContext('webgl', { alpha: true, premultipliedAlpha: true, antialias: false }); } catch (e) {}
    if (gl) iniciarPelo(gl);
  }
  function iniciarPelo(gl) {
    var VS = 'attribute vec2 p;varying vec2 uv;void main(){uv=vec2((p.x+1.)/2.,(1.-p.y)/2.);gl_Position=vec4(p,0.,1.);}';
    var FS = 'precision mediump float;varying vec2 uv;uniform sampler2D tex,peso;uniform float t,amp;' +
      'void main(){' +
      ' float w=texture2D(peso,uv).r;' +
      ' float k=amp*w*(0.35+0.65*uv.y);' +
      ' float dx=sin(uv.y*11.+t*1.25+uv.x*4.)+.6*sin(uv.y*23.-t*1.7+uv.x*7.)+.35*sin(uv.y*37.+t*2.3);' +
      ' float dy=.6*sin(uv.x*9.+t*.95+uv.y*5.)+.3*sin(uv.x*21.-t*1.5);' +
      ' vec2 q=uv+vec2(dx,dy*.7)*k;' +
      ' gl_FragColor=texture2D(tex,q);}';
    function sh(tipo, src) { var s = gl.createShader(tipo); gl.shaderSource(s, src); gl.compileShader(s); return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null; }
    var vs = sh(gl.VERTEX_SHADER, VS), fs = sh(gl.FRAGMENT_SHADER, FS);
    if (!vs || !fs) return;
    var pr = gl.createProgram(); gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return;
    gl.useProgram(pr);
    var buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    var uT = gl.getUniformLocation(pr, 't'), uA = gl.getUniformLocation(pr, 'amp');
    gl.uniform1i(gl.getUniformLocation(pr, 'tex'), 0); gl.uniform1i(gl.getUniformLocation(pr, 'peso'), 1);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    function textura(unidad, fuente) {
      var tx = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + unidad); gl.bindTexture(gl.TEXTURE_2D, tx);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, fuente);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    }
    var listo = false, t0 = performance.now(), ultimo = 0, bucle = 0;
    function tamano() {
      var d = Math.min(window.devicePixelRatio || 1, 2), w = Math.max(2, Math.round(cv.clientWidth * d)), h = Math.max(2, Math.round(cv.clientHeight * d));
      if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
      gl.viewport(0, 0, cv.width, cv.height);
    }
    function dibujar(tiempo, amp) {
      tamano(); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(uT, tiempo); gl.uniform1f(uA, amp); gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    function cuadro(ahora) {
      bucle = 0;
      if (!listo || !activo()) return;
      bucle = requestAnimationFrame(cuadro);
      if (ahora - ultimo < 33) return;                // ~30 cuadros por segundo bastan para el pelo
      ultimo = ahora; dibujar((ahora - t0) / 1000, 0.0105);
    }
    motor = {
      estado: function () {
        if (!listo) return;
        if (activo()) { if (!bucle) bucle = requestAnimationFrame(cuadro); }
        else if (reducir.matches) dibujar(0, 0);       // sin movimiento: la ilustración original, quieta
      }
    };
    if ('ResizeObserver' in window) new ResizeObserver(function () { if (listo && !bucle) dibujar((performance.now() - t0) / 1000, activo() ? 0.0105 : 0); }).observe(cv);
    var peso = new Image();
    function arrancar() {
      if (!img.naturalWidth || !peso.naturalWidth) return;
      textura(0, img); textura(1, peso); listo = true;
      cv.hidden = false; dibujar(0, 0); img.style.visibility = 'hidden';
      motor.estado();
    }
    peso.onload = arrancar; peso.src = cv.getAttribute('data-peso');
    if (img.complete) arrancar(); else img.addEventListener('load', arrancar);
  }
  pintar();
})();
