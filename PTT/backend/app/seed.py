from app.core.security import hash_password
from app.db.base import Base  # noqa: F401
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User

ROLE_SEEDS = [
    ("administrador", "Administrador del sistema"),
    ("jefe_area", "Jefe de área"),
    ("encargado_inventario", "Encargado de inventario"),
]


def seed_roles_and_admin() -> None:
    db = SessionLocal()
    try:
        for name, description in ROLE_SEEDS:
            role = db.query(Role).filter(Role.name == name).first()
            if role is None:
                db.add(Role(name=name, description=description))

        db.commit()

        admin_role = db.query(Role).filter(Role.name == "administrador").first()
        if admin_role is None:
            raise RuntimeError("No se encontró el rol administrador tras la inserción")

        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user is None:
            db.add(
                User(
                    username="admin",
                    email="admin@ipi2.local",
                    full_name="Administrador del Sistema",
                    hashed_password=hash_password("Admin123!"),
                    role_id=admin_role.id,
                    is_active=True,
                )
            )
            db.commit()
            print("Seed completado: roles y usuario admin creados.")
        else:
            print("Seed completado: los datos base ya existen.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_roles_and_admin()
