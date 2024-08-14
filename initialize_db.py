from app import app
from models import db, Usuario
from werkzeug.security import generate_password_hash

# Dados do usuário administrador
admin_usuario = "admin"
admin_senha = "admin"  # Mude para uma senha mais segura em produção

# Criação do banco de dados e adição do usuário
with app.app_context():
    # Cria o banco de dados
    db.create_all()

    # Verifica se o usuário administrador já existe
    if not Usuario.query.filter_by(usuario=admin_usuario).first():
        # Cria um novo usuário administrador
        admin = Usuario(
            usuario=admin_usuario,
            senha=generate_password_hash(admin_senha),
            nivel_acesso="admin",
            is_admin=True  # Define como True para administrador
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário administrador criado com sucesso.")
    else:
        print("Usuário administrador já existe.")
