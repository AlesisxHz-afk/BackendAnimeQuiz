from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from database import Base

class Rol(Base):
    __tablename__ = "roles"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(50), nullable=False, unique=True, index=True)
    descripcion = Column(String(255), nullable=True)

    usuarios = relationship("Usuario", back_populates="rol")


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    alias = Column(String(50), nullable=False, unique=True, index=True)
    contrasena = Column("contraseña", String(255), nullable=False)
    rol_id = Column(BigInteger, ForeignKey("roles.id"), nullable=False)
    foto_url = Column(String(500), nullable=True)
    creado_en = Column(DateTime, server_default=func.now(), nullable=False)

    rol = relationship("Rol", back_populates="usuarios")
    preguntas = relationship("Pregunta", back_populates="usuario", cascade="all, delete-orphan")


class Pregunta(Base):
    __tablename__ = "preguntas"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    nombre = Column(String(255), nullable=False)
    respuestas = Column(String(2000), nullable=False)
    respuesta_correcta = Column(String(255), nullable=False)
    img_url = Column(String(500), nullable=True)
    creado_en = Column(DateTime, server_default=func.now(), nullable=False)

    usuario = relationship("Usuario", back_populates="preguntas")
