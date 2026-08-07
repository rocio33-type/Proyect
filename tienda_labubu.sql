-- =========================================================
-- LabubuStore - Base de datos actualizada
-- Catalogos: usuario, categoria, proveedor, producto
-- Ademas: tabla `sesion` para el manejo de tokens de login
-- =========================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

/*!40101 SET NAMES utf8mb4 */;

-- Se elimina la base de datos anterior (si existia) para evitar conflictos
-- con tablas viejas del proyecto original, y se crea limpia desde cero.
DROP DATABASE IF EXISTS tienda_labubu;
CREATE DATABASE tienda_labubu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE tienda_labubu;

-- --------------------------------------------------------
-- Tabla: usuario  (catalogo 1)
-- --------------------------------------------------------
CREATE TABLE `usuario` (
  `idUsuario` int(11) NOT NULL AUTO_INCREMENT,
  `cUsuario` varchar(50) NOT NULL,
  `cPassword` varchar(255) NOT NULL,
  `cNombre` varchar(100) DEFAULT NULL,
  `cCorreo` varchar(120) DEFAULT NULL,
  `bActivo` tinyint(1) NOT NULL DEFAULT 1,
  `dFechaAlta` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`idUsuario`),
  UNIQUE KEY `cUsuario` (`cUsuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Usuario admin por defecto -> usuario: admin  / password: admin123
-- La contraseña ya esta hasheada con werkzeug (pbkdf2:sha256)
INSERT INTO `usuario` (`idUsuario`, `cUsuario`, `cPassword`, `cNombre`, `cCorreo`, `bActivo`) VALUES
(1, 'admin', 'pbkdf2:sha256:1000000$kRHS4haElVxayxrK$40a073feac927cca8dbc2ce9f3413f9357d6718e86f40516bf5d044519e78359', 'Administrador', 'admin@labubustore.com', 1);

-- --------------------------------------------------------
-- Tabla: sesion  (guarda el token unico de cada login)
-- --------------------------------------------------------
CREATE TABLE `sesion` (
  `idSesion` int(11) NOT NULL AUTO_INCREMENT,
  `idUsuario` int(11) NOT NULL,
  `cToken` varchar(64) NOT NULL,
  `dCreacion` datetime NOT NULL DEFAULT current_timestamp(),
  `dExpiracion` datetime NOT NULL,
  `bActivo` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`idSesion`),
  UNIQUE KEY `cToken` (`cToken`),
  KEY `idUsuario` (`idUsuario`),
  CONSTRAINT `fk_sesion_usuario` FOREIGN KEY (`idUsuario`) REFERENCES `usuario` (`idUsuario`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------
-- Tabla: categoria  (catalogo 2)
-- --------------------------------------------------------
CREATE TABLE `categoria` (
  `idCategoria` int(11) NOT NULL AUTO_INCREMENT,
  `cNombre` varchar(100) NOT NULL,
  `cDescripcion` varchar(255) DEFAULT NULL,
  `bActivo` tinyint(1) NOT NULL DEFAULT 1,
  `dFechaAlta` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`idCategoria`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `categoria` (`idCategoria`, `cNombre`, `cDescripcion`, `bActivo`) VALUES
(1, 'Ediciones especiales', 'Figuras Labubu de colaboraciones y ediciones limitadas', 1),
(2, 'Clasicos', 'Figuras Labubu de la linea original', 1);

-- --------------------------------------------------------
-- Tabla: proveedor  (catalogo 3)
-- --------------------------------------------------------
CREATE TABLE `proveedor` (
  `idProveedor` int(11) NOT NULL AUTO_INCREMENT,
  `cNombre` varchar(150) NOT NULL,
  `cContacto` varchar(100) DEFAULT NULL,
  `cTelefono` varchar(20) DEFAULT NULL,
  `cCorreo` varchar(120) DEFAULT NULL,
  `bActivo` tinyint(1) NOT NULL DEFAULT 1,
  `dFechaAlta` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`idProveedor`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `proveedor` (`idProveedor`, `cNombre`, `cContacto`, `cTelefono`, `cCorreo`, `bActivo`) VALUES
(1, 'Pop Mart Distribuciones', 'Laura Chen', '5512345678', 'ventas@popmartdist.com', 1);

-- --------------------------------------------------------
-- Tabla: producto  (catalogo 4)
-- --------------------------------------------------------
CREATE TABLE `producto` (
  `idProducto` int(11) NOT NULL AUTO_INCREMENT,
  `cNombre` varchar(150) NOT NULL,
  `cDescripcion` text DEFAULT NULL,
  `fPrecio` decimal(10,2) NOT NULL,
  `iStock` int(11) NOT NULL DEFAULT 0,
  `cImagen` varchar(255) DEFAULT NULL,
  `idCategoria` int(11) DEFAULT NULL,
  `idProveedor` int(11) DEFAULT NULL,
  `bActivo` tinyint(1) NOT NULL DEFAULT 1,
  `dFechaAlta` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`idProducto`),
  KEY `idCategoria` (`idCategoria`),
  KEY `idProveedor` (`idProveedor`),
  CONSTRAINT `fk_producto_categoria` FOREIGN KEY (`idCategoria`) REFERENCES `categoria` (`idCategoria`) ON DELETE SET NULL,
  CONSTRAINT `fk_producto_proveedor` FOREIGN KEY (`idProveedor`) REFERENCES `proveedor` (`idProveedor`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `producto` (`idProducto`, `cNombre`, `cDescripcion`, `fPrecio`, `iStock`, `cImagen`, `idCategoria`, `idProveedor`, `bActivo`) VALUES
(1, 'Edicion Snoopy', 'Figura Labubu coleccion Snoopy', 300.00, 25, 'Captura_de_pantalla_2026-06-21_135656.png', 1, 1, 1),
(2, 'Edicion Kuromi', 'Figura Labubu coleccion Kuromi', 499.00, 12, 'Captura_de_pantalla_2026-06-21_140002.png', 1, 1, 1);

COMMIT;
