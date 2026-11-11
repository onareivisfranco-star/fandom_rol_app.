from app import app, db, Usuario
from werkzeug.security import generate_password_hash

with app.app_context():
    usuario = Usuario.query.filter_by(username='Jhosseli').first()
    
    if usuario:
        nueva_clave = 'rolmulti04'
        usuario.password = generate_password_hash(nueva_clave)
        db.session.commit()
        print(f"¡Contraseña de Jhosseli actualizada con éxito a: {nueva_clave}!")
    else:
        print("No se encontró al usuario Jhosseli.")