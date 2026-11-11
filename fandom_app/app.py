import hmac
import os
import random
import re
import secrets
import shutil
import uuid
from datetime import datetime

import click
from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   session, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup, escape
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from iconos import ico

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# En producción define la variable de entorno SECRET_KEY (no dejes la de abajo).
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'cambia-esta-clave-antes-de-publicar')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # fotos de hasta 5 MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

EXTENSIONES_OK = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
NOMBRE_SITIO = 'Multi Roll Play'
LEMA_SITIO = 'Un mundo, infinitas historias'
CODIGO_POR_DEFECTO = 'FANDOM2026'

# Estados del personaje: (texto que se guarda, clase CSS)
ESTADOS = [
    ('Buscando rol', 'buscando'),
    ('Libre', 'libre'),
    ('En rol', 'enrol'),
    ('Ocupado', 'ocupado'),
]
ESTADO_CLASE = dict(ESTADOS)

GENEROS = ['Fantasía', 'Aventura', 'Acción', 'Drama', 'Romance', 'Misterio', 'Terror',
           'Ciencia ficción', 'Slice of life', 'Comedia']
TIPOS_ROL = ['Uno a uno', 'Grupal', 'Trama larga', 'Rol corto', 'Rol libre']
PRIORIDAD_ESTADO = {'Buscando rol': 0, 'Libre': 1, 'En rol': 2, 'Ocupado': 3}
SE_BUSCA, ENCONTRADO = 'Se busca', 'Encontrado'
MAX_BUSQUEDAS_ABIERTAS = 5   # por persona, para que el tablón no se llene

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Inicia sesión para entrar.'


# ------------------------------------------------------------------
# UTILIDADES DE TEXTO (fandoms y nombres)
# ------------------------------------------------------------------
ALIAS_OC = {'oc', 'ocs', 'o.c.', 'original', 'originales', 'original character', 'original characters',
            'personaje original', 'personajes originales'}


def norm(texto):
    return re.sub(r'\s+', ' ', (texto or '').strip()).lower()


def clave_fandom(fandom):
    """Agrupa variantes: 'OC', 'OCs', 'Personajes originales'... son la misma categoría."""
    n = norm(fandom)
    return 'oc' if n in ALIAS_OC else n


def etiqueta_fandom(fandom):
    return 'OCs' if clave_fandom(fandom) == 'oc' else (fandom or '').strip()


# ------------------------------------------------------------------
# MODELOS
# ------------------------------------------------------------------
class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')       # 'user', 'admin', 'owner' (dueña) o 'creator' (creadora)
    puntos = db.Column(db.Integer, default=0)
    is_approved = db.Column(db.Boolean, default=False)         # lo aprueba un admin
    foto_url = db.Column(db.String(300), nullable=True)        # foto de perfil
    bio = db.Column(db.String(300), nullable=True)             # presentación breve
    # sin borrado en cascada: si una cuenta se elimina, sus personajes quedan libres en la lista
    personajes = db.relationship('Personaje', backref='dueno', lazy=True, cascade='save-update, merge')
    solicitudes = db.relationship('Solicitud', backref='autor', lazy=True,
                                  cascade='all, delete-orphan')

    @property
    def es_dueno(self):          # nivel máximo: la dueña del grupo y la creadora tienen los mismos permisos
        return self.role in ('owner', 'creator')

    @property
    def es_admin(self):          # el nivel máximo también tiene poderes de admin
        return self.role in ('admin', 'owner', 'creator')

    @property
    def etiqueta_rol(self):
        return ('Creadora' if self.role == 'creator' else 'Dueña' if self.role == 'owner'
                else 'Admin' if self.es_admin else 'Rolero')


class Personaje(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    fandom = db.Column(db.String(100), nullable=False)
    etiquetas = db.Column(db.String(120), nullable=True)    # ej. "Espía, Estratega"
    avatar_url = db.Column(db.String(300), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    estado_rol = db.Column(db.String(50), default='Buscando rol')   # = disponibilidad
    genero = db.Column(db.String(60), nullable=True)        # género narrativo / temática preferida
    tipo_rol = db.Column(db.String(60), nullable=True)      # tipo de rol que busca
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)   # vacío = libre en su fandom

    @property
    def libre(self):
        return self.usuario_id is None

    @property
    def grupo(self):
        return clave_fandom(self.fandom)

    @property
    def clase_estado(self):
        return ESTADO_CLASE.get(self.estado_rol, 'buscando')

    @property
    def lista_etiquetas(self):
        return [e.strip() for e in (self.etiquetas or '').split(',') if e.strip()]

    @property
    def imagen(self):
        return self.avatar_url or url_for('static', filename='img/avatar_default.svg')


class Solicitud(db.Model):
    """Un personaje que alguien quiere para rolear y todavía no está en el grupo."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    fandom = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)           # qué trama o tipo de rol quiere
    estado = db.Column(db.String(20), default='Se busca')     # 'Se busca' | 'Encontrado'


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, nullable=False)        # quien envía la conexión
    user2_id = db.Column(db.Integer, nullable=False)        # dueño del personaje
    personaje_id = db.Column(db.Integer, nullable=True)     # personaje que le interesó
    solicitud_id = db.Column(db.Integer, nullable=True)     # búsqueda a la que respondió
    estado = db.Column(db.String(20), default='pendiente')  # 'pendiente' | 'match'
    # personaje_id es del user2 y personaje2_id es del user1 (los dos personajes del match)
    personaje2_id = db.Column(db.Integer, nullable=True)
    creado = db.Column(db.DateTime, default=datetime.utcnow)
    visto1 = db.Column(db.Boolean, default=True)            # ¿user1 ya vio el match?
    visto2 = db.Column(db.Boolean, default=True)            # ¿user2 ya vio el match?
    leido1 = db.Column(db.Integer, default=0)               # último mensaje que leyó user1
    leido2 = db.Column(db.Integer, default=0)               # último mensaje que leyó user2
    mensajes = db.relationship('Mensaje', backref='match_chat', lazy=True,
                               cascade='all, delete-orphan')


class Interes(db.Model):
    """Cada deslizamiento: 'like' (me interesa) o 'pass' (pasar). Uno por persona y personaje."""
    __table_args__ = (db.UniqueConstraint('usuario_id', 'personaje_id', name='uq_interes'),)
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, nullable=False)
    personaje_id = db.Column(db.Integer, nullable=False)
    decision = db.Column(db.String(10), nullable=False)
    creado = db.Column(db.DateTime, default=datetime.utcnow)


class Mensaje(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    remitente_id = db.Column(db.Integer, nullable=False)
    texto = db.Column(db.Text, nullable=False)
    creado = db.Column(db.DateTime, default=datetime.utcnow)


class Ajuste(db.Model):
    clave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.String(200), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


# ------------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------------
def migrar_columnas():
    """Agrega las columnas nuevas a tu database.db existente sin borrar nada."""
    nuevas = {
        'usuario': {'is_approved': 'BOOLEAN DEFAULT 1',   # los usuarios ya existentes quedan aprobados
                    'foto_url': 'VARCHAR(300)', 'bio': 'VARCHAR(300)'},
        'personaje': {'etiquetas': 'VARCHAR(120)', 'genero': 'VARCHAR(60)', 'tipo_rol': 'VARCHAR(60)'},
        'match': {'personaje_id': 'INTEGER', 'solicitud_id': 'INTEGER', 'personaje2_id': 'INTEGER',
                  'creado': 'DATETIME', 'visto1': 'BOOLEAN DEFAULT 1', 'visto2': 'BOOLEAN DEFAULT 1',
                  'leido1': 'INTEGER DEFAULT 0', 'leido2': 'INTEGER DEFAULT 0'},
        'mensaje': {'creado': 'DATETIME'},
    }
    for tabla, columnas in nuevas.items():
        existentes = {r[1] for r in db.session.execute(text(f'PRAGMA table_info("{tabla}")'))}
        for col, tipo in columnas.items():
            if col not in existentes:
                db.session.execute(text(f'ALTER TABLE "{tabla}" ADD COLUMN {col} {tipo}'))
                if tabla == 'match' and col in ('leido1', 'leido2'):   # los mensajes que ya había cuentan como leídos
                    db.session.execute(text(
                        f'UPDATE "match" SET {col} = COALESCE((SELECT MAX(id) FROM mensaje WHERE match_id = "match".id), 0)'))
    db.session.commit()


def respaldar_bd():
    ruta = os.path.join(app.instance_path, 'database.db')
    if os.path.exists(ruta):
        shutil.copy2(ruta, ruta + '.respaldo-' + datetime.now().strftime('%Y%m%d-%H%M%S'))


def preparar_personaje():
    '''SQLite no permite quitar NOT NULL de una columna. Para que un personaje pueda quedar libre
    (sin dueño) se renombra la tabla vieja; db.create_all() crea la nueva y luego se copian los datos.'''
    info = list(db.session.execute(text('PRAGMA table_info("personaje")')))
    if info and any(r[1] == 'usuario_id' and r[3] for r in info):
        respaldar_bd()                                   # copia de seguridad automática antes de tocar nada
        db.session.execute(text('ALTER TABLE personaje RENAME TO personaje_vieja'))
        db.session.commit()


def terminar_personaje():
    hay = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='personaje_vieja'")).first()
    if not hay:
        return
    viejas = [r[1] for r in db.session.execute(text('PRAGMA table_info("personaje_vieja")'))]
    nuevas = {r[1] for r in db.session.execute(text('PRAGMA table_info("personaje")'))}
    cols = ', '.join(f'"{c}"' for c in viejas if c in nuevas)
    db.session.execute(text(f'INSERT OR IGNORE INTO personaje ({cols}) SELECT {cols} FROM personaje_vieja'))
    db.session.execute(text('DROP TABLE personaje_vieja'))
    db.session.commit()


def reparar_tablas_antiguas():
    """Tu database.db venía de una versión vieja donde 'match' usaba otras columnas.
    Si esa tabla está vacía la recreamos con el esquema nuevo; si tuviera datos, avisamos."""
    cols = {r[1] for r in db.session.execute(text('PRAGMA table_info("match")'))}
    if not cols or 'user1_id' in cols:
        return
    filas = db.session.execute(text('SELECT COUNT(*) FROM "match"')).scalar()
    if filas:
        raise RuntimeError('La tabla match tiene datos con un esquema antiguo; '
                           'respalda database.db y bórrala para empezar de cero.')
    db.session.execute(text('DROP TABLE IF EXISTS mensaje'))
    db.session.execute(text('DROP TABLE "match"'))
    db.session.commit()


def listar_pistas():
    """Las pistas son los audios de static/audio. Agrega o quita archivos y listo."""
    carpeta = os.path.join(BASE_DIR, 'static', 'audio')
    try:
        nombres = sorted(f for f in os.listdir(carpeta) if f.lower().endswith(('.mp3', '.ogg', '.m4a', '.wav')))
    except OSError:
        nombres = []
    pistas = []
    for f in nombres:
        titulo = re.sub(r'^\d+[_\-\s]*', '', os.path.splitext(f)[0]).replace('_', ' ').strip()
        pistas.append({'archivo': url_for('static', filename='audio/' + f), 'titulo': titulo.capitalize() or f})
    return pistas


def avatar(usuario, clase=''):
    """Foto de perfil o, si no hay, la inicial del nombre."""
    if usuario is not None and getattr(usuario, 'foto_url', None):
        return Markup('<img class="avatar %s" src="%s" alt="" loading="lazy">') % (clase, usuario.foto_url)
    inicial = (getattr(usuario, 'username', '?') or '?')[0].upper()
    return Markup('<span class="avatar %s">%s</span>') % (clase, inicial)


app.jinja_env.globals.update(ico=ico, avatar=avatar, listar_pistas=listar_pistas)


def codigo_invitacion():
    aj = db.session.get(Ajuste, 'codigo_invitacion')
    return aj.valor if aj else CODIGO_POR_DEFECTO


def guardar_imagen(archivo):
    """Guarda una foto subida con nombre único. Devuelve la URL o None."""
    if not archivo or not archivo.filename:
        return None
    ext = archivo.filename.rsplit('.', 1)[-1].lower() if '.' in archivo.filename else ''
    if ext not in EXTENSIONES_OK:
        flash('Esa imagen no es válida. Usa PNG, JPG, GIF o WEBP.', 'warning')
        return None
    nombre = f'{uuid.uuid4().hex}.{ext}'
    archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(nombre)))
    return url_for('static', filename=f'uploads/{nombre}')


def admin_required(f):
    from functools import wraps

    @wraps(f)
    @login_required
    def envoltura(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return envoltura


def owner_required(f):
    from functools import wraps

    @wraps(f)
    @login_required
    def envoltura(*args, **kwargs):
        if not current_user.es_dueno:
            abort(403)
        return f(*args, **kwargs)
    return envoltura


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_hex(16)
    return session['_csrf']


@app.before_request
def proteger_csrf():
    if request.method == 'POST':
        enviado = request.form.get('_csrf') or request.headers.get('X-CSRF-Token', '')
        if not hmac.compare_digest(session.get('_csrf', '').encode(), enviado.encode()):
            abort(400)


@app.context_processor
def inyectar():
    pendientes = abiertas = nuevos = sin_leer = 0
    if current_user.is_authenticated:
        yo = current_user.id
        sin_leer = (db.session.query(func.count(Mensaje.id)).join(Match, Mensaje.match_id == Match.id)
                    .filter(Match.estado == 'match', Mensaje.remitente_id != yo)
                    .filter(((Match.user1_id == yo) & (Mensaje.id > func.coalesce(Match.leido1, 0))) |
                            ((Match.user2_id == yo) & (Mensaje.id > func.coalesce(Match.leido2, 0)))).scalar() or 0)
        pendientes = Match.query.filter_by(user2_id=yo, estado='pendiente').count()
        abiertas = Solicitud.query.filter_by(estado=SE_BUSCA).count()
        nuevos = Match.query.filter(Match.estado == 'match').filter(
            ((Match.user1_id == yo) & (Match.visto1 == False)) |       # noqa: E712
            ((Match.user2_id == yo) & (Match.visto2 == False))).count()  # noqa: E712
    return dict(csrf_token=csrf_token, NOMBRE_SITIO=NOMBRE_SITIO, LEMA_SITIO=LEMA_SITIO,
                ESTADOS=ESTADOS, solicitudes_pendientes=pendientes, busquedas_abiertas=abiertas,
                matches_nuevos=nuevos, chat_sin_leer=sin_leer, GENEROS=GENEROS, TIPOS_ROL=TIPOS_ROL)


@app.errorhandler(403)
def prohibido(e):
    return render_template('error.html', titulo='Sin permiso',
                           mensaje='No tienes permiso para ver esto.'), 403


@app.errorhandler(404)
def no_encontrado(e):
    return render_template('error.html', titulo='No encontrado',
                           mensaje='Esa página no existe.'), 404


@app.errorhandler(400)
def mala_peticion(e):
    return render_template('error.html', titulo='Algo salió mal',
                           mensaje='Recarga la página e inténtalo otra vez.'), 400


@app.errorhandler(413)
def muy_grande(e):
    return render_template('error.html', titulo='Imagen muy pesada',
                           mensaje='La foto supera los 5 MB. Prueba con una más liviana.'), 413


# ------------------------------------------------------------------
# CUENTAS
# ------------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        codigo = (request.form.get('invite_code') or '').strip()

        if not hmac.compare_digest(codigo.encode(), codigo_invitacion().encode()):
            flash('El código de invitación es incorrecto.', 'danger')
            return redirect(url_for('register'))
        if len(username) < 3 or len(password) < 6:
            flash('El usuario necesita 3 letras o más y la contraseña 6 o más.', 'warning')
            return redirect(url_for('register'))
        if Usuario.query.filter(func.lower(Usuario.username) == username.lower()).first():
            flash('Ese nombre de usuario ya existe.', 'warning')
            return redirect(url_for('register'))

        db.session.add(Usuario(username=username, is_approved=False,
                               password_hash=generate_password_hash(password)))
        db.session.commit()
        flash('Cuenta creada. Un admin la aprobará pronto y podrás entrar.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        usuario = Usuario.query.filter(func.lower(Usuario.username) == username.lower()).first()
        if usuario and check_password_hash(usuario.password_hash, request.form.get('password') or ''):
            if not usuario.is_approved:
                flash('Tu cuenta aún no fue aprobada por un admin.', 'warning')
                return redirect(url_for('login'))
            login_user(usuario)
            return redirect(url_for('home'))
        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ------------------------------------------------------------------
# INICIO, EXPLORAR Y PERSONAJES
# ------------------------------------------------------------------
def personajes_de_otros():
    return (Personaje.query.join(Usuario, Personaje.usuario_id == Usuario.id)
            .filter(Personaje.usuario_id != current_user.id, Usuario.is_approved == True)  # noqa: E712
            .order_by(Personaje.id.desc()).all())


@app.route('/')
def home():
    if not current_user.is_authenticated:
        return render_template('home.html', personajes=[], top_usuarios=[], busquedas=[], registros={})
    top = (Usuario.query.filter(Usuario.puntos > 0, Usuario.is_approved == True)  # noqa: E712
           .order_by(Usuario.puntos.desc()).limit(3).all())
    busquedas = (Solicitud.query.filter_by(estado=SE_BUSCA)
                 .order_by(Solicitud.id.desc()).limit(4).all())
    return render_template('home.html', personajes=personajes_de_otros(), top_usuarios=top,
                           busquedas=busquedas, registros=registros_busquedas(busquedas))


@app.route('/personajes')
@login_required
def personajes():
    return render_template('personajes.html', personajes=personajes_de_otros())


@app.route('/personaje/<int:pid>')
@login_required
def personaje(pid):
    pj = db.get_or_404(Personaje, pid)
    if pj.usuario_id is None:
        abort(404)                      # personaje libre: aún no tiene dueño
    conexion = conexion_con(pj.usuario_id) if pj.usuario_id != current_user.id else None
    return render_template('personaje.html', pj=pj, conexion=conexion)


def conexion_con(otro_id):
    """La conexión (pendiente o match) que ya existe con otra persona, si la hay."""
    yo = current_user.id
    return Match.query.filter(
        ((Match.user1_id == yo) & (Match.user2_id == otro_id)) |
        ((Match.user1_id == otro_id) & (Match.user2_id == yo))).first()


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', personajes=current_user.personajes)


@app.route('/profile/editar', methods=['POST'])
@login_required
def perfil_editar():
    u = current_user._get_current_object()
    nuevo = re.sub(r'\s+', ' ', (request.form.get('username') or '').strip())
    if nuevo and nuevo != u.username:
        if not 3 <= len(nuevo) <= 40:
            flash('El nombre de usuario debe tener entre 3 y 40 caracteres.', 'warning')
            return redirect(url_for('profile', editar=1))
        otro = Usuario.query.filter(func.lower(Usuario.username) == nuevo.lower(), Usuario.id != u.id).first()
        if otro:
            flash('Ese nombre de usuario ya está en uso.', 'warning')
            return redirect(url_for('profile', editar=1))
        u.username = nuevo
    u.bio = (request.form.get('bio') or '').strip()[:300] or None
    if request.form.get('quitar_foto'):
        u.foto_url = None
    foto = guardar_imagen(request.files.get('foto'))
    if foto:
        u.foto_url = foto
    db.session.commit()
    flash('Perfil actualizado.', 'success')
    return redirect(url_for('profile'))


@app.route('/profile/password', methods=['POST'])
@login_required
def perfil_password():
    actual = request.form.get('actual') or ''
    nueva = request.form.get('nueva') or ''
    if not check_password_hash(current_user.password_hash, actual):
        flash('La contraseña actual no es correcta.', 'danger')
    elif len(nueva) < 6 or nueva != (request.form.get('repetir') or ''):
        flash('La nueva contraseña necesita 6 caracteres o más y debe repetirse igual.', 'warning')
    else:
        current_user.password_hash = generate_password_hash(nueva)
        db.session.commit()
        flash('Contraseña cambiada.', 'success')
    return redirect(url_for('profile', editar=1))


@app.route('/u/<int:uid>')
@login_required
def perfil_usuario(uid):
    if uid == current_user.id:
        return redirect(url_for('profile'))
    u = db.get_or_404(Usuario, uid)
    if not u.is_approved and not current_user.es_admin:
        abort(404)
    return render_template('perfil.html', u=u, conexion=conexion_con(u.id))


def leer_formulario_personaje(pj):
    nombre = (request.form.get('nombre') or '').strip()
    fandom = (request.form.get('fandom') or '').strip()
    if not nombre or not fandom:
        flash('El nombre y el fandom son obligatorios.', 'warning')
        return False
    pj.nombre = nombre[:100]
    pj.fandom = fandom[:100]
    pj.etiquetas = (request.form.get('etiquetas') or '').strip()[:120]
    pj.descripcion = (request.form.get('descripcion') or '').strip()
    estado = request.form.get('estado_rol')
    if estado in ESTADO_CLASE:
        pj.estado_rol = estado
    genero = request.form.get('genero')
    pj.genero = genero if genero in GENEROS else None
    tipo = request.form.get('tipo_rol')
    pj.tipo_rol = tipo if tipo in TIPOS_ROL else None
    foto = guardar_imagen(request.files.get('avatar_file'))
    url = (request.form.get('avatar_url') or '').strip()
    if foto:
        pj.avatar_url = foto
    elif url.startswith(('http://', 'https://')):
        pj.avatar_url = url[:300]
    return True


@app.route('/personaje/nuevo', methods=['GET', 'POST'])
@login_required
def personaje_nuevo():
    if request.method == 'POST':
        pj = Personaje(dueno=current_user._get_current_object())
        if leer_formulario_personaje(pj):
            db.session.add(pj)
            db.session.commit()
            flash(f'{pj.nombre} ya está en tu galería.', 'success')
            return redirect(url_for('profile'))
        db.session.rollback()
    return render_template('personaje_form.html', pj=None)


@app.route('/personaje/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
def personaje_editar(pid):
    pj = db.get_or_404(Personaje, pid)
    if pj.usuario_id != current_user.id:
        abort(403)
    if request.method == 'POST':
        if leer_formulario_personaje(pj):
            db.session.commit()
            flash('Cambios guardados.', 'success')
            return redirect(url_for('profile'))
        db.session.rollback()
    return render_template('personaje_form.html', pj=pj)


@app.route('/personaje/<int:pid>/estado', methods=['POST'])
@login_required
def personaje_estado(pid):
    pj = db.get_or_404(Personaje, pid)
    if pj.usuario_id != current_user.id:
        abort(403)
    nuevo = request.form.get('estado_rol')
    if nuevo in ESTADO_CLASE:
        pj.estado_rol = nuevo
        db.session.commit()
        flash(f'{pj.nombre} ahora está: {nuevo}.', 'success')
    return redirect(request.referrer or url_for('profile'))


@app.route('/personaje/<int:pid>/eliminar', methods=['POST'])
@login_required
def personaje_eliminar(pid):
    pj = db.get_or_404(Personaje, pid)
    if pj.usuario_id != current_user.id:
        abort(403)
    Interes.query.filter_by(personaje_id=pj.id).delete()
    db.session.delete(pj)
    db.session.commit()
    flash('Personaje eliminado.', 'info')
    return redirect(url_for('profile'))


# ------------------------------------------------------------------
# CONEXIONES (MATCH) Y CHAT
# ------------------------------------------------------------------
def iniciar_conexion(destino_id, personaje_id=None, solicitud_id=None):
    """Crea una solicitud de conexión. Devuelve ('nueva' | 'aceptada' | 'existe', match)."""
    existente = Match.query.filter(
        ((Match.user1_id == current_user.id) & (Match.user2_id == destino_id)) |
        ((Match.user1_id == destino_id) & (Match.user2_id == current_user.id))).first()
    if existente is None:
        m = Match(user1_id=current_user.id, user2_id=destino_id, personaje_id=personaje_id,
                  solicitud_id=solicitud_id, estado='pendiente')
        db.session.add(m)
        db.session.commit()
        return 'nueva', m
    if existente.estado == 'pendiente' and existente.user1_id == destino_id:
        # La otra persona ya te había escrito: se conectan al instante.
        existente.estado = 'match'
        existente.visto1, existente.visto2 = False, True   # avisa a quien envió primero
        db.session.commit()
        return 'aceptada', existente
    return 'existe', existente


@app.route('/conectar/<int:pid>', methods=['POST'])
@login_required
def conectar(pid):
    pj = db.get_or_404(Personaje, pid)
    if pj.usuario_id is None:
        abort(404)
    if pj.usuario_id == current_user.id:
        flash('No puedes conectar con tu propio personaje.', 'warning')
        return redirect(url_for('home'))

    resultado, m = iniciar_conexion(pj.usuario_id, personaje_id=pj.id)
    if resultado == 'nueva':
        flash(f'Le avisamos a {pj.dueno.username} que quieres rolear con {pj.nombre}.', 'success')
    elif resultado == 'aceptada':
        flash('¡Match! Ya pueden hablar.', 'success')
        return redirect(url_for('chat', match_id=m.id))
    else:
        flash('Ya tienes una conexión con esta persona.', 'info')
    return redirect(request.referrer or url_for('home'))


# ------------------------------------------------------------------
# MATCHES: DESCUBRIR (DESLIZAR), LISTA Y ACCIONES
# ------------------------------------------------------------------
def quiere_json():
    return request.headers.get('X-Requested-With') == 'fetch'


def lado(m, yo):
    """(id de la otra persona, mi personaje, su personaje, ¿es nuevo para mí?)"""
    if m.user1_id == yo:
        return m.user2_id, m.personaje2_id, m.personaje_id, not m.visto1
    return m.user1_id, m.personaje_id, m.personaje2_id, not m.visto2


def candidatos_descubrir():
    """Personajes de otras personas que aún no he deslizado ni tienen ya un match o solicitud mía."""
    yo = current_user.id
    vistos = [r.personaje_id for r in Interes.query.filter_by(usuario_id=yo).all()]
    excluidos = set()
    for m in Match.query.filter((Match.user1_id == yo) | (Match.user2_id == yo)).all():
        if m.estado == 'match' or m.user1_id == yo:   # ya son match, o yo ya le escribí
            excluidos.add(m.user2_id if m.user1_id == yo else m.user1_id)
    q = (Personaje.query.join(Usuario, Personaje.usuario_id == Usuario.id)
         .filter(Personaje.usuario_id != yo, Usuario.is_approved == True))  # noqa: E712
    if vistos:
        q = q.filter(~Personaje.id.in_(vistos))
    if excluidos:
        q = q.filter(~Personaje.usuario_id.in_(excluidos))
    return q.all()


@app.route('/matches/descubrir')
@login_required
def descubrir():
    pool = candidatos_descubrir()
    fandoms = sorted({p.fandom for p in pool}, key=str.lower)
    f = {k: (request.args.get(k) or '').strip() for k in ('fandom', 'tipo_rol', 'genero', 'estado')}
    f['buscando'] = request.args.get('buscando') == '1'
    cartas = [p for p in pool if
              (not f['fandom'] or p.fandom.lower() == f['fandom'].lower()) and
              (not f['tipo_rol'] or p.tipo_rol == f['tipo_rol']) and
              (not f['genero'] or p.genero == f['genero']) and
              (not f['estado'] or p.estado_rol == f['estado']) and
              (not f['buscando'] or p.estado_rol == 'Buscando rol')]
    random.shuffle(cartas)
    cartas.sort(key=lambda p: PRIORIDAD_ESTADO.get(p.estado_rol, 2))   # primero los que buscan rol
    activos = sum(1 for k in ('fandom', 'tipo_rol', 'genero', 'estado') if f[k]) + (1 if f['buscando'] else 0)
    return render_template('descubrir.html', cartas=cartas[:30], total=len(cartas), fandoms=fandoms,
                           filtros=f, filtros_activos=activos)


def crear_match_si_mutuo(pj):
    """Se llama tras un 'me interesa' sobre el personaje pj. Devuelve el Match si ahora hay interés mutuo."""
    yo, otro = current_user.id, pj.usuario_id
    mis_ids = [p.id for p in current_user.personajes]
    interes_otro = None
    if mis_ids:
        interes_otro = (Interes.query.filter(Interes.usuario_id == otro, Interes.decision == 'like',
                                             Interes.personaje_id.in_(mis_ids))
                        .order_by(Interes.id).first())
    existente = conexion_con(otro)
    if existente is not None:
        if existente.estado == 'match':
            return None
        solicitud_de_otro = existente.user1_id == otro      # la otra persona ya me había escrito
        if not (solicitud_de_otro or interes_otro):
            return None
        if solicitud_de_otro:
            existente.personaje2_id = pj.id
            existente.visto1, existente.visto2 = False, True
        else:
            existente.personaje_id = pj.id
            existente.personaje2_id = interes_otro.personaje_id
            existente.visto1, existente.visto2 = True, False
        existente.estado = 'match'
        existente.creado = datetime.utcnow()
        db.session.commit()
        return existente
    if interes_otro is None:
        return None
    m = Match(user1_id=yo, user2_id=otro, personaje_id=pj.id, personaje2_id=interes_otro.personaje_id,
              estado='match', visto1=True, visto2=False, creado=datetime.utcnow())
    db.session.add(m)
    db.session.commit()
    # si dos personas deslizan a la vez podrían crearse dos filas: se conserva una sola
    filas = Match.query.filter(
        ((Match.user1_id == yo) & (Match.user2_id == otro)) |
        ((Match.user1_id == otro) & (Match.user2_id == yo))).order_by(Match.id).all()
    if len(filas) > 1:
        conservar = next((f for f in filas if f.estado == 'match'), filas[0])
        for f in filas:
            if f is not conservar:
                db.session.delete(f)
        db.session.commit()
        m = conservar
    return m


@app.route('/matches/accion', methods=['POST'])
@login_required
def match_accion():
    try:
        pid = int(request.form.get('personaje_id', ''))
    except ValueError:
        abort(400)
    decision = request.form.get('decision')
    if decision not in ('like', 'pass'):
        abort(400)
    pj = db.get_or_404(Personaje, pid)
    if pj.usuario_id is None or pj.usuario_id == current_user.id or not pj.dueno.is_approved:
        abort(400)

    nuevo = Interes.query.filter_by(usuario_id=current_user.id, personaje_id=pid).first() is None
    match = None
    if nuevo:
        db.session.add(Interes(usuario_id=current_user.id, personaje_id=pid, decision=decision))
        try:
            db.session.commit()
        except IntegrityError:          # doble clic: ya estaba guardado
            db.session.rollback()
            nuevo = False
        if nuevo and decision == 'like':
            match = crear_match_si_mutuo(pj)

    if quiere_json():
        datos = {'ok': True, 'repetido': not nuevo, 'match': None}
        if match is not None:
            _, mio_id, _, _ = lado(match, current_user.id)
            mio = db.session.get(Personaje, mio_id) if mio_id else None
            datos['match'] = {
                'id': match.id, 'chat': url_for('chat', match_id=match.id),
                'perfil': url_for('personaje', pid=pj.id), 'matches': url_for('matches'),
                'usuario': pj.dueno.username, 'su_nombre': pj.nombre, 'su_imagen': pj.imagen,
                'mi_nombre': mio.nombre if mio else current_user.username,
                'mi_imagen': mio.imagen if mio else (current_user.foto_url or url_for('static', filename='img/avatar_default.svg')),
            }
        return jsonify(datos)
    if match is not None:
        flash(f'¡Es un Match con {pj.dueno.username}!', 'success')
        return redirect(url_for('chat', match_id=match.id))
    return redirect(url_for('descubrir'))


@app.route('/matches')
@login_required
def matches():
    yo = current_user.id
    filas = (Match.query.filter(Match.estado == 'match')
             .filter((Match.user1_id == yo) | (Match.user2_id == yo))
             .order_by(Match.id.desc()).all())
    datos = []
    for m in filas:
        otro_id, mio_id, suyo_id, nuevo = lado(m, yo)
        datos.append({'match': m, 'usuario': db.session.get(Usuario, otro_id), 'nuevo': nuevo,
                      'mio': db.session.get(Personaje, mio_id) if mio_id else None,
                      'suyo': db.session.get(Personaje, suyo_id) if suyo_id else None})
        if m.user1_id == yo:
            m.visto1 = True
        else:
            m.visto2 = True
    db.session.commit()
    return render_template('matches.html', matches=datos)


# ------------------------------------------------------------------
# PERSONAJES SOLICITADOS ("SE BUSCA")
# ------------------------------------------------------------------
def nombres_compatibles(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    wa, wb = set(na.split()), set(nb.split())
    menor, mayor = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    return len(min(na, nb, key=len)) >= 4 and menor <= mayor     # 'Sasuke' coincide con 'Sasuke Uchiha'


def registros_busquedas(solicitudes):
    """Para cada búsqueda, ¿el personaje ya está registrado? -> {id: {'tipo': 'equipo'|'propio'|'libre', 'pj': ...}}"""
    solicitudes = list(solicitudes)
    if not solicitudes:
        return {}
    todos = Personaje.query.options(joinedload(Personaje.dueno)).all()
    res = {}
    for sol in solicitudes:
        fs = clave_fandom(sol.fandom)
        cands = [p for p in todos if nombres_compatibles(p.nombre, sol.nombre)
                 and (not fs or not p.grupo or p.grupo == fs or fs in p.grupo or p.grupo in fs)]
        ajenos = [p for p in cands if p.usuario_id and p.usuario_id != sol.usuario_id and p.dueno.is_approved]
        propios = [p for p in cands if p.usuario_id == sol.usuario_id]
        libres = [p for p in cands if p.usuario_id is None]
        if ajenos:
            res[sol.id] = {'tipo': 'equipo', 'pj': ajenos[0]}
        elif propios:
            res[sol.id] = {'tipo': 'propio', 'pj': propios[0]}
        elif libres:
            res[sol.id] = {'tipo': 'libre', 'pj': libres[0]}
    return res


@app.route('/solicitados')
@login_required
def solicitados():
    abiertas = Solicitud.query.filter_by(estado=SE_BUSCA).order_by(Solicitud.id.desc()).all()
    mias = (Solicitud.query.filter_by(usuario_id=current_user.id)
            .order_by(Solicitud.id.desc()).all())
    encontradas = []
    if current_user.es_admin:
        encontradas = (Solicitud.query.filter_by(estado=ENCONTRADO)
                       .order_by(Solicitud.id.desc()).all())
    return render_template('solicitados.html', abiertas=abiertas, mias=mias, encontradas=encontradas,
                           maximo=MAX_BUSQUEDAS_ABIERTAS, registros=registros_busquedas(abiertas))


@app.route('/solicitados/nueva', methods=['POST'])
@login_required
def solicitud_nueva():
    nombre = (request.form.get('nombre') or '').strip()
    fandom = (request.form.get('fandom') or '').strip()
    if not nombre or not fandom:
        flash('Escribe el nombre del personaje y de qué fandom es.', 'warning')
        return redirect(url_for('solicitados'))
    abiertas = Solicitud.query.filter_by(usuario_id=current_user.id, estado=SE_BUSCA).count()
    if abiertas >= MAX_BUSQUEDAS_ABIERTAS:
        flash(f'Ya tienes {MAX_BUSQUEDAS_ABIERTAS} búsquedas abiertas. Cierra alguna para pedir otra.', 'warning')
        return redirect(url_for('solicitados'))
    db.session.add(Solicitud(usuario_id=current_user.id, nombre=nombre[:100], fandom=fandom[:100],
                             descripcion=(request.form.get('descripcion') or '').strip()[:600]))
    db.session.commit()
    flash(f'Listo: ahora se busca a {nombre[:100]}.', 'success')
    return redirect(url_for('solicitados'))


def solicitud_propia_o_admin(sid):
    sol = db.get_or_404(Solicitud, sid)
    if sol.usuario_id != current_user.id and not current_user.es_admin:
        abort(403)
    return sol


@app.route('/solicitados/<int:sid>/estado', methods=['POST'])
@login_required
def solicitud_estado(sid):
    """Alterna entre 'Se busca' y 'Encontrado' (lo puede hacer quien lo pidió o un admin)."""
    sol = solicitud_propia_o_admin(sid)
    if sol.estado == SE_BUSCA:
        sol.estado = ENCONTRADO
        flash(f'{sol.nombre} marcado como encontrado. Ya no aparece en el tablón.', 'success')
    else:
        if (Solicitud.query.filter_by(usuario_id=sol.usuario_id, estado=SE_BUSCA).count()
                >= MAX_BUSQUEDAS_ABIERTAS):
            flash('Esa persona ya tiene el máximo de búsquedas abiertas.', 'warning')
            return redirect(url_for('solicitados'))
        sol.estado = SE_BUSCA
        flash(f'{sol.nombre} vuelve a buscarse.', 'success')
    db.session.commit()
    return redirect(request.referrer or url_for('solicitados'))


@app.route('/solicitados/<int:sid>/eliminar', methods=['POST'])
@login_required
def solicitud_eliminar(sid):
    sol = solicitud_propia_o_admin(sid)
    db.session.delete(sol)
    db.session.commit()
    flash('Búsqueda eliminada.', 'info')
    return redirect(request.referrer or url_for('solicitados'))


@app.route('/solicitados/<int:sid>/tengo', methods=['POST'])
@login_required
def solicitud_tengo(sid):
    """Alguien que tiene (o puede hacer) ese personaje avisa a quien lo pidió."""
    sol = db.get_or_404(Solicitud, sid)
    if sol.usuario_id == current_user.id:
        flash('Esa búsqueda es tuya.', 'warning')
        return redirect(url_for('solicitados'))
    if sol.estado != SE_BUSCA:
        flash('Ese personaje ya fue encontrado.', 'info')
        return redirect(url_for('solicitados'))
    resultado, m = iniciar_conexion(sol.usuario_id, solicitud_id=sol.id)
    if resultado == 'nueva':
        flash(f'Le avisamos a {sol.autor.username} que puedes ser {sol.nombre}.', 'success')
    elif resultado == 'aceptada':
        flash('¡Match! Ya pueden hablar.', 'success')
        return redirect(url_for('chat', match_id=m.id))
    else:
        flash('Ya tienes una conexión con esta persona.', 'info')
    return redirect(url_for('solicitados'))


@app.route('/conexiones')
@login_required
def conexiones():
    uid = current_user.id
    todas = Match.query.filter((Match.user1_id == uid) | (Match.user2_id == uid)).all()

    def fila(m):
        otro = db.session.get(Usuario, m.user2_id if m.user1_id == uid else m.user1_id)
        return {'match': m, 'usuario': otro,
                'personaje': db.session.get(Personaje, m.personaje_id) if m.personaje_id else None,
                'solicitud': db.session.get(Solicitud, m.solicitud_id) if m.solicitud_id else None}

    recibidas = [fila(m) for m in todas if m.estado == 'pendiente' and m.user2_id == uid]
    enviadas = [fila(m) for m in todas if m.estado == 'pendiente' and m.user1_id == uid]
    activas = [fila(m) for m in todas if m.estado == 'match']
    return render_template('conexiones.html', recibidas=recibidas, enviadas=enviadas, activas=activas)


@app.route('/conexiones/<int:mid>/<accion>', methods=['POST'])
@login_required
def responder_conexion(mid, accion):
    m = db.get_or_404(Match, mid)
    if m.user2_id != current_user.id or m.estado != 'pendiente':
        abort(403)
    if accion == 'aceptar':
        m.estado = 'match'
        m.visto1, m.visto2 = False, True
        db.session.commit()
        flash('¡Conexión aceptada!', 'success')
        return redirect(url_for('chat', match_id=m.id))
    if accion == 'rechazar':
        db.session.delete(m)
        db.session.commit()
        flash('Solicitud rechazada.', 'info')
        return redirect(url_for('conexiones'))
    abort(404)


def marcar_leido(m, yo, hasta):
    if m.user1_id == yo:
        m.leido1 = max(m.leido1 or 0, hasta)
    else:
        m.leido2 = max(m.leido2 or 0, hasta)


def datos_mensaje(msg, yo):
    return {'id': msg.id, 'mio': msg.remitente_id == yo, 'texto': msg.texto,
            'hora': (msg.creado.isoformat() + 'Z') if msg.creado else ''}


def match_del_usuario(match_id):
    m = db.get_or_404(Match, match_id)
    if current_user.id not in (m.user1_id, m.user2_id) or m.estado != 'match':
        abort(403)
    return m


@app.route('/chat/<int:match_id>', methods=['GET', 'POST'])
@login_required
def chat(match_id):
    m = match_del_usuario(match_id)
    otro = db.session.get(Usuario, m.user2_id if m.user1_id == current_user.id else m.user1_id)

    if request.method == 'POST':
        texto = (request.form.get('texto') or '').strip()
        if texto:
            db.session.add(Mensaje(match_id=m.id, remitente_id=current_user.id, texto=texto[:2000]))
            db.session.commit()
        return redirect(url_for('chat', match_id=m.id))
    ultimo = db.session.query(func.max(Mensaje.id)).filter(Mensaje.match_id == m.id).scalar() or 0
    marcar_leido(m, current_user.id, ultimo)
    db.session.commit()
    return render_template('chat.html', match=m, otro=otro)


@app.route('/api/chats')
@login_required
def api_chats():
    """Lista de conversaciones para el chat flotante."""
    yo = current_user.id
    filas = (Match.query.filter(Match.estado == 'match')
             .filter((Match.user1_id == yo) | (Match.user2_id == yo)).all())
    chats, total = [], 0
    for m in filas:
        otro = db.session.get(Usuario, m.user2_id if m.user1_id == yo else m.user1_id)
        ultimo = Mensaje.query.filter_by(match_id=m.id).order_by(Mensaje.id.desc()).first()
        leido = (m.leido1 if m.user1_id == yo else m.leido2) or 0
        sin_leer = Mensaje.query.filter(Mensaje.match_id == m.id, Mensaje.id > leido, Mensaje.remitente_id != yo).count()
        total += sin_leer
        chats.append({'id': m.id, 'usuario': otro.username, 'foto': otro.foto_url, 'sin_leer': sin_leer,
                      'perfil': url_for('perfil_usuario', uid=otro.id),
                      'ultimo': (('Tú: ' if ultimo.remitente_id == yo else '') + ultimo.texto[:60]) if ultimo else 'Aún no hay mensajes',
                      'orden': ultimo.id if ultimo else 0, 'match': m.id})
    chats.sort(key=lambda c: (c['orden'], c['match']), reverse=True)
    return jsonify(ok=True, chats=chats, sin_leer=total)


@app.route('/api/chat/<int:match_id>', methods=['GET', 'POST'])
@login_required
def api_chat(match_id):
    m = match_del_usuario(match_id)
    yo = current_user.id
    if request.method == 'POST':
        texto = (request.form.get('texto') or '').strip()
        if not texto:
            return jsonify(ok=False), 400
        msg = Mensaje(match_id=m.id, remitente_id=yo, texto=texto[:2000])
        db.session.add(msg)
        db.session.commit()
        marcar_leido(m, yo, msg.id)
        db.session.commit()
        return jsonify(ok=True, mensaje=datos_mensaje(msg, yo))
    try:
        desde = int(request.args.get('desde', 0) or 0)
    except ValueError:
        desde = 0
    msgs = (Mensaje.query.filter(Mensaje.match_id == m.id, Mensaje.id > desde)
            .order_by(Mensaje.id).limit(200).all())
    if msgs:
        marcar_leido(m, yo, msgs[-1].id)      # este endpoint solo se usa con la conversación abierta
        db.session.commit()
    otro = db.session.get(Usuario, m.user2_id if m.user1_id == yo else m.user1_id)
    return jsonify(ok=True, mensajes=[datos_mensaje(x, yo) for x in msgs], usuario=otro.username)


# ------------------------------------------------------------------
# PANEL DE ADMIN
# ------------------------------------------------------------------
def orden_usuarios(usuarios):
    usuarios = sorted(usuarios, key=lambda u: ((u.username or '').lower()))
    usuarios.sort(key=lambda u: 0 if u.es_dueno else 1 if u.es_admin else 2)
    return usuarios


def datos_admin():
    """Números que se muestran en las pestañas y tarjetas del panel."""
    total = Personaje.query.count()
    libres = Personaje.query.filter(Personaje.usuario_id.is_(None)).count()
    return {
        'usuarios': Usuario.query.filter_by(is_approved=True).count(),
        'pendientes': Usuario.query.filter_by(is_approved=False).count(),
        'personajes': total - libres, 'catalogo': total, 'libres': libres,
        'busquedas': Solicitud.query.filter_by(estado=SE_BUSCA).count(),
        'conexiones': Match.query.filter_by(estado='match').count(),
        'por_estado': {e: Personaje.query.filter(Personaje.usuario_id.isnot(None), Personaje.estado_rol == e).count()
                       for e, _ in ESTADOS},
    }


@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', stats=datos_admin(), codigo=codigo_invitacion(), activa='resumen')


@app.route('/admin/roleros')
@admin_required
def admin_roleros():
    usuarios = orden_usuarios(Usuario.query.filter_by(is_approved=True).all())
    return render_template('admin_roleros.html', usuarios=usuarios, stats=datos_admin(), activa='roleros')


@app.route('/admin/pendientes')
@admin_required
def admin_pendientes():
    pendientes = Usuario.query.filter_by(is_approved=False).order_by(Usuario.id).all()
    return render_template('admin_pendientes.html', pendientes=pendientes, stats=datos_admin(), activa='pendientes')


@app.route('/admin/personajes')
@admin_required
def admin_personajes():
    usuarios = orden_usuarios(Usuario.query.options(joinedload(Usuario.personajes)).all())
    fandoms = sorted({etiqueta_fandom(p.fandom) for p in Personaje.query.all()}, key=str.lower)
    return render_template('admin_personajes.html', usuarios=usuarios, fandoms=fandoms,
                           stats=datos_admin(), activa='personajes')


def catalogo_agrupado():
    """Todos los personajes (con dueño o libres) agrupados por fandom; las OCs van primero."""
    todos = (Personaje.query.options(joinedload(Personaje.dueno))
             .order_by(func.lower(Personaje.nombre)).all())
    grupos = {}
    for p in todos:
        g = grupos.setdefault(p.grupo, {'clave': p.grupo, 'nombre': etiqueta_fandom(p.fandom),
                                        'personajes': [], 'libres': 0, 'ocupados': 0})
        g['personajes'].append(p)
        g['libres' if p.libre else 'ocupados'] += 1
    return sorted(grupos.values(), key=lambda g: (g['clave'] != 'oc', g['nombre'].lower()))


@app.route('/admin/lista')
@admin_required
def admin_lista():
    grupos = catalogo_agrupado()
    texto = '\n'.join(f"{g['nombre']}: " + ', '.join(p.nombre for p in g['personajes']) for g in grupos)
    usuarios = orden_usuarios(Usuario.query.filter_by(is_approved=True).all())
    return render_template('admin_lista.html', grupos=grupos, texto=texto, usuarios=usuarios,
                           stats=datos_admin(), activa='lista')


@app.route('/admin/busquedas')
@admin_required
def admin_busquedas():
    abiertas = Solicitud.query.filter_by(estado=SE_BUSCA).order_by(Solicitud.id.desc()).all()
    return render_template('admin_busquedas.html', abiertas=abiertas, registros=registros_busquedas(abiertas),
                           stats=datos_admin(), activa='busquedas')


@app.route('/admin/puntos/<int:uid>', methods=['POST'])
@admin_required
def admin_puntos(uid):
    u = db.get_or_404(Usuario, uid)
    try:
        cantidad = int(request.form.get('puntos', ''))
    except ValueError:
        flash('Escribe un número (puede ser negativo para restar).', 'warning')
        return redirect(url_for('admin'))
    if abs(cantidad) > 10000:
        flash('Ese número es demasiado grande.', 'warning')
        return redirect(url_for('admin'))
    u.puntos = max(0, (u.puntos or 0) + cantidad)
    db.session.commit()
    flash(f'{cantidad:+d} puntos para {u.username}. Total: {u.puntos}.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/aprobar/<int:uid>', methods=['POST'])
@admin_required
def admin_aprobar(uid):
    u = db.get_or_404(Usuario, uid)
    if u.id == current_user.id:
        abort(400)
    if u.es_dueno or (u.es_admin and not current_user.es_dueno):
        abort(403)
    u.is_approved = not u.is_approved
    db.session.commit()
    flash(f'{u.username}: cuenta {"aprobada" if u.is_approved else "suspendida"}.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/rol/<int:uid>', methods=['POST'])
@owner_required
def admin_rol(uid):
    """Solo el dueño del grupo nombra o quita admins."""
    u = db.get_or_404(Usuario, uid)
    if u.es_dueno:
        flash('El dueño no puede cambiar su propio rol.', 'warning')
        return redirect(url_for('admin'))
    if not u.is_approved:
        flash('Primero aprueba la cuenta de esa persona.', 'warning')
        return redirect(url_for('admin'))
    u.role = 'user' if u.es_admin else 'admin'
    db.session.commit()
    flash(f'{u.username} ahora es {"admin" if u.es_admin else "rolero normal"}.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/codigo', methods=['POST'])
@admin_required
def admin_codigo():
    nuevo = (request.form.get('codigo') or '').strip()
    if len(nuevo) < 4:
        flash('El código necesita al menos 4 caracteres.', 'warning')
        return redirect(url_for('admin'))
    aj = db.session.get(Ajuste, 'codigo_invitacion') or Ajuste(clave='codigo_invitacion', valor=nuevo)
    aj.valor = nuevo
    db.session.add(aj)
    db.session.commit()
    flash('Código de invitación actualizado.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/rechazar/<int:uid>', methods=['POST'])
@admin_required
def admin_rechazar(uid):
    """Rechaza una cuenta que todavía no fue aprobada (se elimina)."""
    u = db.get_or_404(Usuario, uid)
    if u.is_approved or u.es_admin:
        abort(403)
    nombre = u.username
    db.session.delete(u)
    db.session.commit()
    flash(f'Cuenta de {nombre} rechazada y eliminada.', 'info')
    return redirect(url_for('admin_pendientes'))


@app.route('/admin/renombrar/<int:uid>', methods=['POST'])
@owner_required
def admin_renombrar(uid):
    u = db.get_or_404(Usuario, uid)
    nuevo = re.sub(r'\s+', ' ', (request.form.get('username') or '').strip())
    if not 3 <= len(nuevo) <= 40:
        flash('El nombre debe tener entre 3 y 40 caracteres.', 'warning')
    elif Usuario.query.filter(func.lower(Usuario.username) == nuevo.lower(), Usuario.id != u.id).first():
        flash('Ya existe una cuenta con ese nombre.', 'warning')
    else:
        u.username = nuevo
        db.session.commit()
        flash('Nombre cambiado.', 'success')
    return redirect(url_for('admin_roleros'))


def responder_admin(mensaje, ok=True, **datos):
    """Las acciones rápidas piden JSON (sin recargar); sin JavaScript se vuelve a la página."""
    if quiere_json():
        return jsonify(ok=ok, mensaje=mensaje, **datos), (200 if ok else 400)
    flash(mensaje, 'success' if ok else 'warning')
    return redirect(request.referrer or url_for('admin_lista'))


def liberar_personaje(pj):
    """Desvincula el personaje de su dueño: vuelve a estar libre en su fandom."""
    Interes.query.filter_by(personaje_id=pj.id).delete()
    pj.dueno = None
    pj.estado_rol = 'Libre'


@app.route('/admin/personaje/<int:pid>/liberar', methods=['POST'])
@admin_required
def admin_pj_liberar(pid):
    pj = db.get_or_404(Personaje, pid)
    anterior = pj.dueno.username if pj.dueno else None
    liberar_personaje(pj)
    db.session.commit()
    return responder_admin(f'{pj.nombre} quedó libre.', id=pj.id, anterior=anterior)


@app.route('/admin/personaje/<int:pid>/asignar', methods=['POST'])
@admin_required
def admin_pj_asignar(pid):
    pj = db.get_or_404(Personaje, pid)
    nombre = (request.form.get('usuario') or '').strip()
    u = Usuario.query.filter(func.lower(Usuario.username) == nombre.lower()).first() if nombre else None
    if u is None or not u.is_approved:
        return responder_admin('Escribe el nombre de un usuario aprobado (elígelo de la lista).', ok=False)
    pj.dueno = u
    pj.estado_rol = 'Buscando rol'
    db.session.commit()
    return responder_admin(f'{pj.nombre} ahora es de {u.username}.', id=pj.id, usuario=u.username,
                           usuario_id=u.id, perfil=url_for('perfil_usuario', uid=u.id))


@app.route('/admin/personaje/<int:pid>/quitar', methods=['POST'])
@admin_required
def admin_pj_eliminar(pid):
    """Elimina el personaje de la lista por completo (por ejemplo, un error al registrarlo)."""
    pj = db.get_or_404(Personaje, pid)
    nombre = pj.nombre
    Interes.query.filter_by(personaje_id=pj.id).delete()
    db.session.delete(pj)
    db.session.commit()
    return responder_admin(f'{nombre} se eliminó de la lista.', id=pid)


@app.route('/admin/personaje/nuevo', methods=['POST'])
@admin_required
def admin_pj_nuevo():
    """Agrega un personaje a un fandom (libre) o directamente a un usuario."""
    nombre = (request.form.get('nombre') or '').strip()[:100]
    fandom = (request.form.get('fandom') or '').strip()[:100]
    quien = (request.form.get('usuario') or '').strip()
    if not nombre or not fandom:
        return responder_admin('Escribe el nombre del personaje y su fandom (o OC).', ok=False)
    if 'oc' == clave_fandom(fandom):
        fandom = 'OC'
    u = None
    if quien:
        u = Usuario.query.filter(func.lower(Usuario.username) == quien.lower()).first()
        if u is None:
            return responder_admin(f'No existe el usuario {quien}.', ok=False)
    for p in Personaje.query.all():
        if p.grupo == clave_fandom(fandom) and norm(p.nombre) == norm(nombre):
            dueno = f' (lo tiene {p.dueno.username})' if p.dueno else ' (está libre)'
            return responder_admin(f'{p.nombre} ya está en la lista de {etiqueta_fandom(p.fandom)}{dueno}.', ok=False)
    pj = Personaje(nombre=nombre, fandom=fandom, dueno=u, estado_rol='Buscando rol' if u else 'Libre')
    db.session.add(pj)
    db.session.commit()
    return responder_admin(f'{nombre} se agregó a {etiqueta_fandom(fandom)}.', id=pj.id)


@app.route('/admin/usuario/<int:uid>/liberar-todos', methods=['POST'])
@admin_required
def admin_liberar_todos(uid):
    """Para cuando alguien sale del grupo: todos sus personajes vuelven a quedar libres."""
    u = db.get_or_404(Usuario, uid)
    ids = []
    for p in list(u.personajes):
        liberar_personaje(p)
        ids.append(p.id)
    suspendida = False
    if request.form.get('suspender') and not u.es_admin and u.id != current_user.id:
        u.is_approved = False
        suspendida = True
    db.session.commit()
    texto = f'{len(ids)} personaje(s) de {u.username} quedaron libres.' + (' La cuenta fue suspendida.' if suspendida else '')
    return responder_admin(texto, ids=ids, suspendida=suspendida, usuario=u.username)


def parsear_lista(texto):
    """'Naruto: Sasuke, Sakura' o 'Naruto:' seguido de un nombre por línea -> [(fandom, [nombres])]."""
    orden, datos, actual, ignoradas = [], {}, None, 0
    for linea in (texto or '').splitlines():
        l = re.sub(r'^\s*(?:[-*•·]+|\d+[.)])\s*', '', linea.strip())
        if not l:
            continue
        if ':' in l:
            cabeza, _, resto = l.partition(':')
            actual = cabeza.strip()
            if not actual:
                ignoradas += 1
                continue
        elif actual is None:
            ignoradas += 1
            continue
        else:
            resto = l
        for nombre in re.split(r'[,;]', resto):
            nombre = nombre.strip()
            if nombre:
                clave = clave_fandom(actual)
                if clave not in datos:
                    datos[clave] = {'fandom': 'OC' if clave == 'oc' else actual[:100], 'nombres': []}
                    orden.append(clave)
                datos[clave]['nombres'].append(nombre[:100])
    return [(datos[k]['fandom'], datos[k]['nombres']) for k in orden], ignoradas


@app.route('/admin/lista/guardar', methods=['POST'])
@admin_required
def admin_lista_guardar():
    """Pega una lista 'Fandom: personaje, personaje' y se agrega a la lista del grupo."""
    datos, ignoradas = parsear_lista(request.form.get('texto'))
    if not datos:
        flash('No encontré personajes. Usa el formato  Naruto: Sasuke, Sakura  (una línea por fandom).', 'warning')
        return redirect(url_for('admin_lista'))
    existentes = {(p.grupo, norm(p.nombre)): p for p in Personaje.query.all()}
    vistos, nuevos = set(), 0
    for fandom, nombres in datos:
        for nombre in nombres:
            k = (clave_fandom(fandom), norm(nombre))
            vistos.add(k)
            if k in existentes:
                continue
            existentes[k] = Personaje(nombre=nombre, fandom=fandom, estado_rol='Libre')   # nace libre, sin dueño
            db.session.add(existentes[k])
            nuevos += 1
    quitados = 0
    if request.form.get('quitar_libres'):
        for k, p in list(existentes.items()):
            if p.libre and k not in vistos and p.id is not None:     # solo libres: nunca toca personajes con dueño
                db.session.delete(p)
                quitados += 1
    db.session.commit()
    texto = f'Lista guardada: {nuevos} personaje(s) nuevos'
    texto += f' y {quitados} libre(s) quitados.' if quitados else '.'
    if ignoradas:
        texto += f' ({ignoradas} línea(s) sin fandom se ignoraron.)'
    flash(texto, 'success')
    return redirect(url_for('admin_lista'))


# ------------------------------------------------------------------
# COMANDOS Y ARRANQUE
# ------------------------------------------------------------------
@app.cli.command('hacer-admin')
@click.argument('username')
def hacer_admin(username):
    """Convierte a un usuario en admin: flask --app app hacer-admin NOMBRE"""
    u = Usuario.query.filter(func.lower(Usuario.username) == username.lower()).first()
    if not u:
        raise click.ClickException(f'No existe el usuario {username}.')
    if u.es_dueno:
        raise click.ClickException(f'{u.username} ya está en el nivel máximo (dueña o creadora).')
    u.role, u.is_approved = 'admin', True
    db.session.commit()
    click.echo(f'{u.username} ahora es admin.')


def _buscar_usuario(username):
    u = Usuario.query.filter(func.lower(Usuario.username) == username.lower()).first()
    if not u:
        raise click.ClickException(f'No existe el usuario {username}.')
    return u


def _nombrar_nivel_maximo(username, rol, etiqueta):
    u = _buscar_usuario(username)
    for otro in Usuario.query.filter_by(role=rol).all():
        otro.role = 'admin'          # quien tuviera ese cargo antes pasa a admin
    u.role, u.is_approved = rol, True
    db.session.commit()
    click.echo(f'{u.username} ahora es {etiqueta}.')


@app.cli.command('hacer-dueno')
@click.argument('username')
def hacer_dueno(username):
    """Nombra a la dueña del grupo (solo una): flask --app app hacer-dueno NOMBRE"""
    _nombrar_nivel_maximo(username, 'owner', 'la dueña del grupo')


@app.cli.command('hacer-creadora')
@click.argument('username')
def hacer_creadora(username):
    """Nombra a la creadora de la página (mismos permisos que la dueña): flask --app app hacer-creadora NOMBRE"""
    _nombrar_nivel_maximo(username, 'creator', 'la creadora')


@app.cli.command('renombrar-usuario')
@click.argument('actual')
@click.argument('nuevo')
def renombrar_usuario(actual, nuevo):
    """Cambia el nombre de una cuenta: flask --app app renombrar-usuario ACTUAL NUEVO"""
    u = _buscar_usuario(actual)
    if Usuario.query.filter(func.lower(Usuario.username) == nuevo.lower(), Usuario.id != u.id).first():
        raise click.ClickException(f'Ya existe un usuario llamado {nuevo}.')
    u.username = nuevo.strip()
    db.session.commit()
    click.echo(f'Listo: {actual} ahora se llama {u.username}.')


with app.app_context():
    reparar_tablas_antiguas()
    preparar_personaje()
    db.create_all()
    terminar_personaje()
    migrar_columnas()

if __name__ == '__main__':
    app.run(debug=True)
