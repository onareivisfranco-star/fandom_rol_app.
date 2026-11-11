from app import app, db, Usuario
from werkzeug.security import generate_password_hash

with app.app_context():
    usuario = Usuario.query.filter_by(username='Lalita').first()

    if usuario:
        nueva_clave = 'Bamospormas1'
        usuario.password = generate_password_hash(nueva_clave)
        db.session.commit()
        print(f"¡Contraseña de Lalita actualizada con éxito a: {nueva_clave}!")
    else:
        print("No se encontró al usuario Lalita.")