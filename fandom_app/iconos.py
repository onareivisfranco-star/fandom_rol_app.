"""Juego de iconos único (trazo lineal, 24x24) para toda la plataforma.
Uso en plantillas:  {{ ico('heart') }}  o  {{ ico('heart', 18, 'mi-clase') }}"""
from markupsafe import Markup

_P = {
    'home': 'M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10',
    'users': 'M9 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M16 4.8a3.5 3.5 0 010 6.4M18 14.3c2.2.7 3.5 2.6 3.5 5.7',
    'user': 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4.4 3.6-7 8-7s8 2.6 8 7',
    'search': 'M11 17.5a6.5 6.5 0 100-13 6.5 6.5 0 000 13zM16 16l5 5',
    'heart': 'M12 20.5s-8-4.7-8-10.2A4.6 4.6 0 0112 7.4a4.6 4.6 0 018 2.9c0 5.5-8 10.2-8 10.2z',
    'heart-spark': 'M12 20.5s-8-4.7-8-10.2A4.6 4.6 0 0112 7.4a4.6 4.6 0 018 2.9c0 5.5-8 10.2-8 10.2zM19 1.5v4M17 3.5h4',
    'sparkle': 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16v4M17 18h4',
    'crown': 'M3 18h18M4 7l4.5 4L12 5l3.5 6L20 7l-1.5 11h-13z',
    'bell': 'M6 16v-5a6 6 0 0112 0v5l1.5 2h-15zM10 21h4',
    'play': 'M8 5l11 7-11 7z',
    'pause': 'M8 5v14M16 5v14',
    'next': 'M6 5l9 7-9 7zM18 5v14',
    'prev': 'M18 5l-9 7 9 7zM6 5v14',
    'volume': 'M4 9v6h4l5 4V5L8 9zM16.5 8.5a5 5 0 010 7M19 6a8.5 8.5 0 010 12',
    'volume-off': 'M4 9v6h4l5 4V5L8 9zM17 9l5 6M22 9l-5 6',
    'music': 'M9 18V5l11-2v13M6 21a3 3 0 100-6 3 3 0 000 6zM17 19a3 3 0 100-6 3 3 0 000 6z',
    'x': 'M6 6l12 12M18 6L6 18',
    'check': 'M5 12.5l4.5 4.5L19 7',
    'plus': 'M12 5v14M5 12h14',
    'message': 'M4 5h16v11H9l-5 4z',
    'lock': 'M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 017 0v3',
    'star': 'M12 3l2.8 5.8 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 3 1.1-6.2L3 9.7l6.2-.9z',
    'trophy': 'M8 4h8v5a4 4 0 01-8 0zM8 6H4v1a3 3 0 003 3M16 6h4v1a3 3 0 01-3 3M12 13v4M8 20h8',
    'back': 'M15 5l-7 7 7 7',
    'edit': 'M4 20l1-4L16 5l3 3L8 19zM14 7l3 3',
    'trash': 'M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13',
    'filter': 'M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M15 6m-2 0a2 2 0 104 0 2 2 0 10-4 0M9 12m-2 0a2 2 0 104 0 2 2 0 10-4 0M17 18m-2 0a2 2 0 104 0 2 2 0 10-4 0',
    'camera': 'M4 8h3l2-3h6l2 3h3v11H4zM12 17a3.5 3.5 0 100-7 3.5 3.5 0 000 7z',
    'menu': 'M4 7h16M4 12h16M4 17h16',
    'undo': 'M9 7L4 12l5 5M4 12h11a5 5 0 010 10h-3',
    'eye': 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z',
    'wand': 'M4 20L15 9M14 4l1 2.2 2.2 1L15 8.2 14 10.4 13 8.2 10.8 7.2 13 6.2zM19 12l.7 1.5 1.5.7-1.5.7L19 16.4l-.7-1.5-1.5-.7 1.5-.7z',
}
_RELLENOS = {'play'}


def ico(nombre, tam=20, clase=''):
    d = _P.get(nombre)
    if d is None:
        return Markup('')
    relleno = 'currentColor' if nombre in _RELLENOS else 'none'
    return Markup(
        f'<svg class="ico {clase}" width="{tam}" height="{tam}" viewBox="0 0 24 24" fill="{relleno}" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false"><path d="{d}"/></svg>')
