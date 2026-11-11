from app import app, db, Usuario

with app.app_context():
    usuario = Usuario.query.filter_by(username='Lalita').first()
    
    if usuario:
        # Cambia esto a 'aprobado = True' si tu columna se llama así en el código
        usuario.is_approved = True 
        db.session.commit()
        print("¡Cuenta de Lalita aprobada con éxito!")
    else:
        print("No se encontró al usuario Lalita.")