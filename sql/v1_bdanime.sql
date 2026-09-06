CREATE TABLE roles (
    id          BIGSERIAL PRIMARY KEY,
    nombre      VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(255)
);


CREATE TABLE usuarios (
    id              BIGSERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    alias           VARCHAR(50) NOT NULL UNIQUE,
    contraseña      VARCHAR(255) NOT NULL,
    rol_id          BIGINT NOT NULL,
    foto_url        VARCHAR(500),
    creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_usuarios_rol
        FOREIGN KEY (rol_id)
        REFERENCES roles(id)
);


CREATE TABLE preguntas (
    id                  BIGSERIAL PRIMARY KEY,
    usuario_id          BIGINT NOT NULL,
    nombre              VARCHAR(255) NOT NULL,
    respuestas          VARCHAR(2000) NOT NULL,
    respuesta_correcta  VARCHAR(255) NOT NULL,
    img_url              VARCHAR(500),
    creado_en            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_preguntas_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);