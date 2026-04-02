#!/usr/bin/env python3
"""
Создание или смена пароля суперадмина.

Использование:
    python create_superadmin.py
"""
import getpass
from app.database import engine, Base, SessionLocal
from app.models.admin_user import AdminUser, Role
from app.auth import hash_password

Base.metadata.create_all(bind=engine)


def main() -> None:
    print("=== Создание / обновление суперадмина ===\n")
    username = input("Логин: ").strip()
    if not username:
        print("Логин не может быть пустым.")
        return

    password = getpass.getpass("Пароль: ")
    if len(password) < 6:
        print("Пароль должен быть не короче 6 символов.")
        return

    password_hash = hash_password(password)

    with SessionLocal() as db:
        user = db.query(AdminUser).filter_by(username=username).first()
        if user:
            user.password_hash = password_hash
            user.role = Role.SUPERADMIN
            user.is_active = True
            print(f"\nПароль для '{username}' обновлён.")
        else:
            db.add(
                AdminUser(
                    username=username,
                    password_hash=password_hash,
                    role=Role.SUPERADMIN,
                    is_active=True,
                )
            )
            print(f"\nСуперадмин '{username}' создан.")
        db.commit()


if __name__ == "__main__":
    main()
