from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

# --- ESQUEMAS DE ROLES ---
class RolBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=50, description="Nombre único del rol")
    descripcion: Optional[str] = Field(None, max_length=255, description="Descripción del rol")

class RolCreate(RolBase):
    pass

class RolUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=50, description="Nuevo nombre del rol")
    descripcion: Optional[str] = Field(None, max_length=255, description="Nueva descripción del rol")

class RolResponse(RolBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# --- ESQUEMAS DE USUARIOS ---
class UsuarioLogin(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre o alias del usuario")
    password: str = Field(..., min_length=1, description="Contraseña del usuario")

class UsuarioResponse(BaseModel):
    id: int
    nombre: str
    alias: str
    rol_id: int
    rol: Optional[RolResponse] = None
    foto_url: Optional[str] = None
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioResponse
    message: str


# --- ESQUEMAS DE PREGUNTAS ---
class PreguntaBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=255, description="Texto de la pregunta")
    respuestas: str = Field(..., max_length=2000, description="Opciones de respuesta separadas por coma o JSON")
    respuesta_correcta: str = Field(..., max_length=255, description="Respuesta correcta")
    img_url: Optional[str] = Field(None, max_length=500, description="URL de imagen ilustrativa")

class PreguntaCreate(PreguntaBase):
    usuario_id: Optional[int] = Field(None, description="ID del usuario creador")

class PreguntaResponse(PreguntaBase):
    id: int
    usuario_id: int
    creado_en: datetime
    usuario: Optional[UsuarioResponse] = None

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    mensaje: str
