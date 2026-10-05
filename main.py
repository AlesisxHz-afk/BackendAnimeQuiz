import os
import shutil
import uuid
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select, text, func

from database import engine, Base, get_db
import models
import schemas
import security

load_dotenv()

# Asegurar que las tablas existan si es necesario
Base.metadata.create_all(bind=engine)

# Directorio de almacenamiento de imágenes
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
os.makedirs(IMG_DIR, exist_ok=True)

# Configuración de OpenAPI / Swagger UI (Usuarios y Roles separados)
tags_metadata = [
    {
        "name": "Usuarios",
        "description": "Endpoints de autenticación, registro con avatar, modificación y gestión de usuarios.",
    },
    {
        "name": "Roles",
        "description": "Endpoints para agregar, obtener, modificar y eliminar roles del sistema.",
    },
    {
        "name": "Preguntas",
        "description": "Endpoints para listar, agregar y eliminar preguntas del Anime Quiz.",
    },
]

app = FastAPI(
    title="Anime Quiz API - Autenticación y Usuarios",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata
)

# Montar directorio estático para servir las imágenes de /img
app.mount("/img", StaticFiles(directory=IMG_DIR), name="img")

# Configuración de CORS
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
if not origins or "*" in origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "online",
        "message": "Anime Quiz API activa",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/api/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Verifica el estado del servicio y la conectividad con la base de datos."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "environment": "production"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "database": f"error: {str(e)}"}
        )

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.Usuario:
    """Extrae y valida el usuario actual desde el JWT Token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación no proporcionado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = security.decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    alias: str = payload.get("sub")
    usuario = db.query(models.Usuario).filter(models.Usuario.alias == alias).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return usuario


# ==============================================================================
# RUTAS DEL SISTEMA (Excluidas de la documentación Swagger)
# ==============================================================================

@app.get("/", include_in_schema=False)
def root():
    return {
        "status": "online",
        "mensaje": "⛩️ Bienvenido a la API de Anime Quiz",
        "swagger_docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/api/health", include_in_schema=False)
def health_check(db: Session = Depends(get_db)):
    """Verifica el estado del servicio y la conexión a PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "postgres": "Aiven Cloud PostgreSQL OK"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error conectando a la base de datos: {str(e)}"
        )


# ==============================================================================
# RUTAS DE ROLES (Agregar, Obtener, Modificar y Eliminar)
# ==============================================================================

@app.post("/api/roles", response_model=schemas.RolResponse, status_code=status.HTTP_201_CREATED, tags=["Roles"])
def agregar_rol(rol_data: schemas.RolCreate, db: Session = Depends(get_db)):
    """
    Agrega un nuevo rol al sistema.
    - Valida que el nombre del rol sea único.
    """
    nombre_limpio = rol_data.nombre.strip()
    existing = db.query(models.Rol).filter(func.lower(models.Rol.nombre) == nombre_limpio.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El rol '{nombre_limpio}' ya existe en el sistema."
        )

    nuevo_rol = models.Rol(
        nombre=nombre_limpio,
        descripcion=rol_data.descripcion.strip() if rol_data.descripcion else None
    )
    db.add(nuevo_rol)
    db.commit()
    db.refresh(nuevo_rol)
    return schemas.RolResponse.model_validate(nuevo_rol)


@app.get("/api/roles", response_model=List[schemas.RolResponse], tags=["Roles"])
def obtener_roles(db: Session = Depends(get_db)):
    """
    Obtiene la lista completa de roles disponibles en el sistema.
    """
    roles = db.query(models.Rol).order_by(models.Rol.id.asc()).all()
    return [schemas.RolResponse.model_validate(r) for r in roles]


@app.get("/api/roles/{rol_id}", response_model=schemas.RolResponse, tags=["Roles"])
def obtener_rol_por_id(rol_id: int, db: Session = Depends(get_db)):
    """
    Obtiene el detalle de un rol específico mediante su ID.
    """
    rol = db.query(models.Rol).filter(models.Rol.id == rol_id).first()
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rol con ID {rol_id} no encontrado."
        )
    return schemas.RolResponse.model_validate(rol)


@app.put("/api/roles/{rol_id}", response_model=schemas.RolResponse, tags=["Roles"])
def modificar_rol(rol_id: int, rol_data: schemas.RolUpdate, db: Session = Depends(get_db)):
    """
    Modifica los datos de un rol existente por su ID.
    - Valida que el nuevo nombre no esté ya en uso por otro rol.
    """
    rol = db.query(models.Rol).filter(models.Rol.id == rol_id).first()
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rol con ID {rol_id} no encontrado."
        )

    if rol_data.nombre is not None:
        nombre_limpio = rol_data.nombre.strip()
        if nombre_limpio:
            existente = db.query(models.Rol).filter(
                func.lower(models.Rol.nombre) == nombre_limpio.lower(),
                models.Rol.id != rol_id
            ).first()
            if existente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe otro rol con el nombre '{nombre_limpio}'."
                )
            rol.nombre = nombre_limpio

    if rol_data.descripcion is not None:
        rol.descripcion = rol_data.descripcion.strip() if rol_data.descripcion else None

    db.commit()
    db.refresh(rol)
    return schemas.RolResponse.model_validate(rol)


@app.delete("/api/roles/{rol_id}", response_model=schemas.MessageResponse, tags=["Roles"])
def eliminar_rol(rol_id: int, db: Session = Depends(get_db)):
    """
    Elimina un rol por su ID.
    - Valida que no existan usuarios asignados a este rol antes de eliminar.
    """
    rol = db.query(models.Rol).filter(models.Rol.id == rol_id).first()
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rol con ID {rol_id} no encontrado."
        )

    usuarios_asignados = db.query(models.Usuario).filter(models.Usuario.rol_id == rol_id).count()
    if usuarios_asignados > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el rol '{rol.nombre}' porque está asignado a {usuarios_asignados} usuario(s)."
        )

    db.delete(rol)
    db.commit()
    return schemas.MessageResponse(mensaje=f"Rol '{rol.nombre}' (ID {rol_id}) eliminado correctamente.")


# ==============================================================================
# RUTAS DE USUARIOS (Registro con avatar, Login, Consulta, Modificar y Eliminar)
# ==============================================================================

@app.post("/api/auth/register", response_model=schemas.AuthResponse, status_code=status.HTTP_201_CREATED, tags=["Usuarios"])
async def registrar_usuario(
    nombre: str = Form(..., min_length=2, max_length=100, description="Nombre del usuario"),
    alias: str = Form(..., min_length=3, max_length=50, description="Alias único del usuario"),
    password: str = Form(..., min_length=4, max_length=100, description="Contraseña para hashear"),
    file: Optional[UploadFile] = File(None, description="Foto de perfil o avatar"),
    db: Session = Depends(get_db)
):
    """
    Registra un nuevo usuario en la base de datos junto con su foto de avatar:
    - Valida que el **alias** no esté en uso.
    - Busca en la base de datos el rol asignado como **USUARIO**.
    - Si se sube una imagen de **avatar**, se guarda directamente en `BACKENDANIME/img`.
    - Hashea la **contraseña** con **bcrypt**.
    - Genera y retorna el token JWT de acceso.
    """
    alias_limpio = alias.strip()
    nombre_limpio = nombre.strip()

    # 1. Verificar si el alias ya existe
    existing_user = db.query(models.Usuario).filter(models.Usuario.alias == alias_limpio).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El alias '{alias_limpio}' ya está registrado. Por favor elige otro."
        )

    # 2. Asignar rol buscando en la BD el rol con nombre 'USUARIO'
    rol_usuario = db.query(models.Rol).filter(func.upper(models.Rol.nombre) == "USUARIO").first()
    if not rol_usuario:
        # Si aún no existe el rol USUARIO en la base de datos, crearlo
        rol_usuario = models.Rol(
            nombre="USUARIO",
            descripcion="Rol predeterminado de usuario para Anime Quiz"
        )
        db.add(rol_usuario)
        db.commit()
        db.refresh(rol_usuario)

    rol_id_asignado = rol_usuario.id

    # 3. Procesar foto de avatar si fue subida
    foto_url = None
    if file and file.filename:
        if file.content_type and not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo adjunto no es una imagen válida."
            )
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
            ext = ".png"

        unique_filename = f"avatar_{uuid.uuid4().hex[:12]}{ext}"
        target_path = os.path.join(IMG_DIR, unique_filename)

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            foto_url = f"/img/{unique_filename}"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al guardar la foto de avatar: {str(e)}"
            )

    # 4. Hashear la contraseña de forma segura
    hashed_pwd = security.hash_password(password)

    # 5. Crear el nuevo usuario
    nuevo_usuario = models.Usuario(
        nombre=nombre_limpio,
        alias=alias_limpio,
        contrasena=hashed_pwd,
        rol_id=rol_id_asignado,
        foto_url=foto_url
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    # 6. Generar Token JWT
    access_token = security.create_access_token(
        data={"sub": nuevo_usuario.alias, "id": nuevo_usuario.id}
    )

    return schemas.AuthResponse(
        access_token=access_token,
        token_type="bearer",
        usuario=schemas.UsuarioResponse.model_validate(nuevo_usuario),
        message="¡Usuario registrado exitosamente!"
    )


@app.post("/api/auth/login", response_model=schemas.AuthResponse, tags=["Usuarios"])
def login_usuario(login_data: schemas.UsuarioLogin, db: Session = Depends(get_db)):
    """
    Inicia sesión verificando credenciales:
    - Busca el usuario por su **nombre** o **alias**.
    - Compara la contraseña con el hash almacenado con **bcrypt**.
    - Genera y retorna el token JWT de acceso si es correcto.
    """
    nombre_limpio = login_data.nombre.strip()
    usuario = db.query(models.Usuario).filter(func.lower(models.Usuario.nombre) == nombre_limpio.lower()).first()
    if not usuario:
        usuario = db.query(models.Usuario).filter(models.Usuario.nombre == nombre_limpio).first()
    if not usuario:
        usuario = db.query(models.Usuario).filter(models.Usuario.alias == nombre_limpio).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas. Verifica tu nombre de usuario y contraseña.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar contraseña hasheada
    if not security.verify_password(login_data.password, usuario.contrasena):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas. Verifica tu nombre de usuario y contraseña.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generar Token JWT
    access_token = security.create_access_token(
        data={"sub": usuario.alias, "id": usuario.id}
    )

    return schemas.AuthResponse(
        access_token=access_token,
        token_type="bearer",
        usuario=schemas.UsuarioResponse.model_validate(usuario),
        message="¡Inicio de sesión exitoso!"
    )


@app.put("/api/usuarios/{usuario_id}", response_model=schemas.UsuarioResponse, tags=["Usuarios"])
async def modificar_usuario(
    usuario_id: int,
    nombre: Optional[str] = Form(None, description="Nuevo nombre del usuario"),
    alias: Optional[str] = Form(None, description="Nuevo alias único"),
    password: Optional[str] = Form(None, description="Nueva contraseña (opcional)"),
    rol_id: Optional[int] = Form(None, description="Nuevo ID de rol (opcional)"),
    file: Optional[UploadFile] = File(None, description="Nueva foto de perfil o avatar (opcional)"),
    db: Session = Depends(get_db)
):
    """
    Modifica los datos de un usuario por su ID:
    - Actualiza nombre y alias (validando unicidad si cambia).
    - Si se envía rol_id, valida que exista y lo asigna.
    - Si se envía contraseña, se vuelve a hashear con bcrypt.
    - Si se envía un archivo de imagen, se sube y guarda en `BACKENDANIME/img`.
    """
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado."
        )

    if nombre is not None and nombre.strip():
        usuario.nombre = nombre.strip()

    if alias is not None and alias.strip():
        alias_limpio = alias.strip()
        if alias_limpio.lower() != usuario.alias.lower():
            existente = db.query(models.Usuario).filter(
                models.Usuario.alias == alias_limpio,
                models.Usuario.id != usuario_id
            ).first()
            if existente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El alias '{alias_limpio}' ya está en uso por otro usuario."
                )
            usuario.alias = alias_limpio

    if rol_id is not None:
        rol_obj = db.query(models.Rol).filter(models.Rol.id == rol_id).first()
        if not rol_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El rol especificado con ID {rol_id} no existe."
            )
        usuario.rol_id = rol_id

    if password is not None and password.strip():
        if len(password.strip()) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La nueva contraseña debe tener al menos 4 caracteres."
            )
        usuario.contrasena = security.hash_password(password.strip())

    if file and file.filename:
        if file.content_type and not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo enviado no es una imagen válida."
            )
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
            ext = ".png"

        unique_filename = f"avatar_{uuid.uuid4().hex[:12]}{ext}"
        target_path = os.path.join(IMG_DIR, unique_filename)

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            # Eliminar foto anterior si era local
            if usuario.foto_url and usuario.foto_url.startswith("/img/"):
                old_file = os.path.join(IMG_DIR, usuario.foto_url.replace("/img/", ""))
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass
            usuario.foto_url = f"/img/{unique_filename}"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al guardar la nueva imagen: {str(e)}"
            )

    db.commit()
    db.refresh(usuario)
    return schemas.UsuarioResponse.model_validate(usuario)


@app.get("/api/usuarios/{alias}", response_model=schemas.UsuarioResponse, tags=["Usuarios"])
def obtener_usuario_por_alias(alias: str, db: Session = Depends(get_db)):
    """Obtiene los datos de un usuario mediante su alias."""
    usuario = db.query(models.Usuario).filter(models.Usuario.alias == alias.strip()).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con alias '{alias}' no encontrado"
        )
    return schemas.UsuarioResponse.model_validate(usuario)


@app.get("/api/usuarios", response_model=List[schemas.UsuarioResponse], tags=["Usuarios"])
@app.get("/api/auth/usuarios", response_model=List[schemas.UsuarioResponse], include_in_schema=False)
def listar_usuarios(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Lista todos los usuarios registrados (sin exponer contraseñas ni hashes)."""
    usuarios = db.query(models.Usuario).order_by(models.Usuario.creado_en.desc()).offset(skip).limit(limit).all()
    return [schemas.UsuarioResponse.model_validate(u) for u in usuarios]


@app.delete("/api/usuarios/{usuario_id}", response_model=schemas.MessageResponse, tags=["Usuarios"])
def eliminar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    """
    Elimina un usuario por su ID.
    - Se eliminan en cascada sus preguntas asociadas.
    """
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado."
        )

    alias = usuario.alias

    # Si tiene foto local, limpiar el archivo en disco
    if usuario.foto_url and usuario.foto_url.startswith("/img/"):
        local_filename = usuario.foto_url.replace("/img/", "")
        local_file_path = os.path.join(IMG_DIR, local_filename)
        if os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
            except Exception:
                pass

    db.delete(usuario)
    db.commit()
    return schemas.MessageResponse(mensaje=f"Usuario '{alias}' (ID {usuario_id}) eliminado correctamente.")


# ==============================================================================
# RUTAS DE PREGUNTAS (Listar, Agregar, Modificar, Buscar por Nombre y Eliminar)
# ==============================================================================

import json

def parse_respuestas_to_json(respuestas_input: str) -> str:
    """Normaliza y convierte las opciones de respuesta a formato JSON string."""
    respuestas_input = respuestas_input.strip()
    # Si ya es un array JSON válido
    if respuestas_input.startswith("[") and respuestas_input.endswith("]"):
        try:
            parsed = json.loads(respuestas_input)
            if isinstance(parsed, list) and len(parsed) >= 2:
                return json.dumps([str(x).strip() for x in parsed if str(x).strip()], ensure_ascii=False)
        except Exception:
            pass
    # Si viene separado por comas
    items = [x.strip() for x in respuestas_input.split(",") if x.strip()]
    if len(items) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar al menos dos opciones de respuesta válidas."
        )
    return json.dumps(items, ensure_ascii=False)


@app.get("/api/preguntas", response_model=List[schemas.PreguntaResponse], tags=["Preguntas"])
def listar_preguntas(db: Session = Depends(get_db)):
    """
    Obtiene la lista de todas las preguntas del quiz registradas en la base de datos.
    """
    preguntas = db.query(models.Pregunta).order_by(models.Pregunta.id.desc()).all()
    return [schemas.PreguntaResponse.model_validate(p) for p in preguntas]


@app.get("/api/preguntas/nombre/{nombre}", response_model=schemas.PreguntaResponse, tags=["Preguntas"])
def obtener_pregunta_por_nombre(nombre: str, db: Session = Depends(get_db)):
    """
    Obtiene una pregunta mediante su nombre o enunciado.
    """
    nombre_limpio = nombre.strip()
    # 1. Búsqueda exacta
    pregunta = db.query(models.Pregunta).filter(
        func.lower(models.Pregunta.nombre) == nombre_limpio.lower()
    ).first()
    # 2. Búsqueda parcial si no hubo coincidencia exacta
    if not pregunta:
        pregunta = db.query(models.Pregunta).filter(
            models.Pregunta.nombre.ilike(f"%{nombre_limpio}%")
        ).first()

    if not pregunta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ninguna pregunta con el nombre '{nombre_limpio}'."
        )
    return schemas.PreguntaResponse.model_validate(pregunta)


@app.get("/api/preguntas/usuario/{usuario_id}", response_model=List[schemas.PreguntaResponse], tags=["Preguntas"])
def obtener_preguntas_por_usuario(
    usuario_id: str = Path(..., description="ID numérico del usuario o su alias"),
    db: Session = Depends(get_db)
):
    """
    Obtiene todas las preguntas asignadas o creadas por un usuario específico (por ID numérico o alias).
    """
    usuario_limpio = usuario_id.strip()
    if usuario_limpio.isdigit():
        user = db.query(models.Usuario).filter(models.Usuario.id == int(usuario_limpio)).first()
    else:
        user = db.query(models.Usuario).filter(func.lower(models.Usuario.alias) == usuario_limpio.lower()).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario '{usuario_limpio}' no encontrado."
        )

    preguntas = db.query(models.Pregunta).filter(models.Pregunta.usuario_id == user.id).order_by(models.Pregunta.id.desc()).all()
    return [schemas.PreguntaResponse.model_validate(p) for p in preguntas]


@app.get("/api/preguntas/{pregunta_id}", response_model=schemas.PreguntaResponse, tags=["Preguntas"])
def obtener_pregunta_por_id(pregunta_id: int, db: Session = Depends(get_db)):
    """
    Obtiene una pregunta específica por su ID.
    """
    pregunta = db.query(models.Pregunta).filter(models.Pregunta.id == pregunta_id).first()
    if not pregunta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pregunta con ID {pregunta_id} no encontrada."
        )
    return schemas.PreguntaResponse.model_validate(pregunta)


@app.post("/api/preguntas", response_model=schemas.PreguntaResponse, status_code=status.HTTP_201_CREATED, tags=["Preguntas"])
async def agregar_pregunta(
    nombre: str = Form(..., min_length=3, max_length=255, description="Texto de la pregunta"),
    respuestas: str = Form(..., description="Opciones de respuesta (se guardarán en formato JSON)"),
    respuesta_correcta: str = Form(..., description="Respuesta correcta seleccionada"),
    usuario_id: Optional[int] = Form(None, description="ID del usuario creador asignado"),
    file: Optional[UploadFile] = File(None, description="Imagen ilustrativa desde PC o galería"),
    db: Session = Depends(get_db)
):
    """
    Agrega una nueva pregunta al Anime Quiz:
    - Valida y asigna el **usuario_id** correspondiente.
    - Guarda las **respuestas en formato JSON**.
    - Sube la **imagen física** a `BACKENDANIME/img`.
    """
    user_id = usuario_id
    if not user_id:
        primer_user = db.query(models.Usuario).first()
        if not primer_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere al menos un usuario registrado en el sistema para asociar la pregunta."
            )
        user_id = primer_user.id
    else:
        user_exists = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Usuario asignado con ID {user_id} no existe."
            )

    # Convertir respuestas a formato JSON string
    respuestas_json = parse_respuestas_to_json(respuestas)

    # Validar que la respuesta correcta esté entre las opciones
    opciones_cargadas = json.loads(respuestas_json)
    correcta_limpia = respuesta_correcta.strip()
    if not any(c.lower() == correcta_limpia.lower() for c in opciones_cargadas):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La respuesta correcta debe ser una de las opciones de respuesta ingresadas."
        )

    # Subida de imagen al igual que en usuario
    img_url = None
    if file and file.filename:
        if file.content_type and not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo adjunto no es una imagen válida."
            )
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
            ext = ".png"

        unique_filename = f"pregunta_{uuid.uuid4().hex[:12]}{ext}"
        target_path = os.path.join(IMG_DIR, unique_filename)

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            img_url = f"/img/{unique_filename}"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al guardar la imagen de la pregunta: {str(e)}"
            )

    nueva_pregunta = models.Pregunta(
        usuario_id=user_id,
        nombre=nombre.strip(),
        respuestas=respuestas_json,
        respuesta_correcta=correcta_limpia,
        img_url=img_url
    )
    db.add(nueva_pregunta)
    db.commit()
    db.refresh(nueva_pregunta)
    return schemas.PreguntaResponse.model_validate(nueva_pregunta)


@app.put("/api/preguntas/{pregunta_id}", response_model=schemas.PreguntaResponse, tags=["Preguntas"])
async def modificar_pregunta(
    pregunta_id: int,
    nombre: Optional[str] = Form(None, description="Nuevo enunciado de la pregunta"),
    respuestas: Optional[str] = Form(None, description="Nuevas opciones de respuesta (en JSON o separadas por coma)"),
    respuesta_correcta: Optional[str] = Form(None, description="Nueva respuesta correcta"),
    usuario_id: Optional[int] = Form(None, description="Nuevo ID de usuario asignado"),
    file: Optional[UploadFile] = File(None, description="Nueva imagen ilustrativa desde PC o galería"),
    db: Session = Depends(get_db)
):
    """
    Modifica una pregunta existente:
    - Actualiza enunciado, respuestas (en formato JSON) y respuesta correcta.
    - Permite cambiar el usuario asignado.
    - Permite subir una nueva imagen y limpiar la anterior en disco.
    """
    pregunta = db.query(models.Pregunta).filter(models.Pregunta.id == pregunta_id).first()
    if not pregunta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pregunta con ID {pregunta_id} no encontrada."
        )

    if usuario_id is not None:
        user_exists = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Usuario con ID {usuario_id} no existe."
            )
        pregunta.usuario_id = usuario_id

    if nombre is not None and nombre.strip():
        pregunta.nombre = nombre.strip()

    if respuestas is not None and respuestas.strip():
        pregunta.respuestas = parse_respuestas_to_json(respuestas)

    if respuesta_correcta is not None and respuesta_correcta.strip():
        pregunta.respuesta_correcta = respuesta_correcta.strip()

    # Si se sube una nueva imagen de pregunta
    if file and file.filename:
        if file.content_type and not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo enviado no es una imagen válida."
            )
        _, ext = os.path.splitext(file.filename)
        ext = ext.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
            ext = ".png"

        unique_filename = f"pregunta_{uuid.uuid4().hex[:12]}{ext}"
        target_path = os.path.join(IMG_DIR, unique_filename)

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            # Limpiar imagen previa si era local
            if pregunta.img_url and pregunta.img_url.startswith("/img/"):
                old_file = os.path.join(IMG_DIR, pregunta.img_url.replace("/img/", ""))
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                    except Exception:
                        pass
            pregunta.img_url = f"/img/{unique_filename}"
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al guardar la nueva imagen: {str(e)}"
            )

    db.commit()
    db.refresh(pregunta)
    return schemas.PreguntaResponse.model_validate(pregunta)


@app.delete("/api/preguntas/{pregunta_id}", response_model=schemas.MessageResponse, tags=["Preguntas"])
def eliminar_pregunta(pregunta_id: int, db: Session = Depends(get_db)):
    """
    Elimina una pregunta por su ID y limpia su archivo de imagen en disco si existe.
    """
    pregunta = db.query(models.Pregunta).filter(models.Pregunta.id == pregunta_id).first()
    if not pregunta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pregunta con ID {pregunta_id} no encontrada."
        )

    if pregunta.img_url and pregunta.img_url.startswith("/img/"):
        local_filename = pregunta.img_url.replace("/img/", "")
        local_file_path = os.path.join(IMG_DIR, local_filename)
        if os.path.exists(local_file_path):
            try:
                os.remove(local_file_path)
            except Exception:
                pass

    db.delete(pregunta)
    db.commit()
    return schemas.MessageResponse(mensaje=f"Pregunta con ID {pregunta_id} eliminada correctamente.")
