from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os
import secrets

app = Flask(__name__)
app.secret_key = 'labubu_clave_secreta_cambiar_en_produccion'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'tienda_labubu'
mysql = MySQL(app)

CARPETA_IMAGENES = os.path.join(app.root_path, 'static', 'images', 'productos')
os.makedirs(CARPETA_IMAGENES, exist_ok=True)
EXTENSIONES_PERMITIDAS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}

# Duracion de la sesion / token. Se deja en 2 minutos para que se pueda
# notar y probar facilmente en el video de demostracion. En un ambiente
# real se recomendaria subirlo (por ejemplo, 30 minutos).
DURACION_SESION = timedelta(minutes=2)


def extensionValida(nombreArchivo):
    return '.' in nombreArchivo and nombreArchivo.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS


# ---------------------------------------------------------------
# Manejo de tokens de sesion (tabla `sesion`)
# ---------------------------------------------------------------

def crearToken(idUsuario):
    """Genera un token unico, lo guarda en BD con su fecha de expiracion
    y lo deja listo en la cookie de sesion de Flask."""
    token = secrets.token_hex(32)
    expiracion = datetime.now() + DURACION_SESION

    cur = mysql.connection.cursor()
    # Se desactivan tokens previos del usuario para dejar solo uno activo
    cur.execute('UPDATE sesion SET bActivo = 0 WHERE idUsuario = %s', (idUsuario,))
    cur.execute(
        'INSERT INTO sesion (idUsuario, cToken, dExpiracion) VALUES (%s, %s, %s)',
        (idUsuario, token, expiracion)
    )
    mysql.connection.commit()

    session.permanent = True
    app.permanent_session_lifetime = DURACION_SESION
    session['idUsuario'] = idUsuario
    session['cToken'] = token


def sesionValida():
    """Valida que el token en la cookie exista, este activo y no haya
    expirado. Si es valido, renueva su expiracion (sesion deslizante:
    mientras el usuario siga navegando, no se le cierra la sesion)."""
    idUsuario = session.get('idUsuario')
    token = session.get('cToken')
    if not idUsuario or not token:
        return False

    cur = mysql.connection.cursor()
    cur.execute(
        'SELECT dExpiracion FROM sesion WHERE cToken = %s AND idUsuario = %s AND bActivo = 1',
        (token, idUsuario)
    )
    fila = cur.fetchone()
    if not fila:
        return False

    if fila[0] < datetime.now():
        cur.execute('UPDATE sesion SET bActivo = 0 WHERE cToken = %s', (token,))
        mysql.connection.commit()
        return False

    # Se renueva la expiracion porque el usuario sigue activo
    nuevaExpiracion = datetime.now() + DURACION_SESION
    cur.execute('UPDATE sesion SET dExpiracion = %s WHERE cToken = %s', (nuevaExpiracion, token))
    mysql.connection.commit()
    return True


def cerrarSesionBD():
    token = session.get('cToken')
    if token:
        cur = mysql.connection.cursor()
        cur.execute('UPDATE sesion SET bActivo = 0 WHERE cToken = %s', (token,))
        mysql.connection.commit()
    session.clear()


def loginRequerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not sesionValida():
            session.clear()
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------
# Login
# ---------------------------------------------------------------

@app.route('/')
def home():
    if sesionValida():
        return redirect('/productos')
    return redirect('/login')


@app.route('/login', methods=['GET'])
def loginForm():
    if sesionValida():
        return redirect('/productos')
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    cUsuario = request.form.get('cUsuario')
    cPassword = request.form.get('cPassword')

    cur = mysql.connection.cursor()
    cur.execute(
        'SELECT idUsuario, cUsuario, cPassword, cNombre FROM usuario WHERE cUsuario = %s AND bActivo = 1',
        (cUsuario,)
    )
    fila = cur.fetchone()

    if fila and check_password_hash(fila[2], cPassword):
        crearToken(fila[0])
        session['cNombre'] = fila[3]
        return redirect('/productos')
    else:
        return render_template('login.html', error='Usuario o contraseña incorrectos')


@app.route('/logout')
def logout():
    cerrarSesionBD()
    return redirect('/login')


@app.route('/registro', methods=['GET'])
def registroForm():
    if sesionValida():
        return redirect('/productos')
    return render_template('registro.html')


@app.route('/registro', methods=['POST'])
def registro():
    cUsuario = request.form.get('cUsuario', '').strip()
    cPassword = request.form.get('cPassword', '')
    cPassword2 = request.form.get('cPassword2', '')
    cNombre = request.form.get('cNombre', '').strip()
    cCorreo = request.form.get('cCorreo', '').strip()

    if not cUsuario or not cPassword:
        return render_template('registro.html', error='Usuario y contraseña son obligatorios',
                                cUsuario=cUsuario, cNombre=cNombre, cCorreo=cCorreo)

    if cPassword != cPassword2:
        return render_template('registro.html', error='Las contraseñas no coinciden',
                                cUsuario=cUsuario, cNombre=cNombre, cCorreo=cCorreo)

    cur = mysql.connection.cursor()
    cur.execute('SELECT idUsuario FROM usuario WHERE cUsuario = %s', (cUsuario,))
    if cur.fetchone():
        return render_template('registro.html', error='Ese nombre de usuario ya esta registrado',
                                cNombre=cNombre, cCorreo=cCorreo)

    try:
        hashPassword = generate_password_hash(cPassword, method='pbkdf2:sha256')
        cur.execute(
            'INSERT INTO usuario(cUsuario, cPassword, cNombre, cCorreo) VALUES(%s,%s,%s,%s)',
            (cUsuario, hashPassword, cNombre, cCorreo)
        )
        mysql.connection.commit()
        return render_template('login.html', exito='Cuenta creada correctamente. Ya puedes iniciar sesion.')
    except Exception as e:
        mysql.connection.rollback()
        return render_template('registro.html', error=f'Ocurrio un error: {e}',
                                cUsuario=cUsuario, cNombre=cNombre, cCorreo=cCorreo)


# =================================================================
# CATALOGO: PRODUCTO
# =================================================================

@app.route('/productos')
@loginRequerido
def productos():
    cur = mysql.connection.cursor()
    cur.execute('''SELECT p.idProducto, p.cNombre, p.fPrecio, p.iStock, p.cImagen, p.bActivo,
                           c.cNombre, pr.cNombre
                    FROM producto p
                    LEFT JOIN categoria c ON c.idCategoria = p.idCategoria
                    LEFT JOIN proveedor pr ON pr.idProveedor = p.idProveedor
                    ORDER BY p.idProducto DESC''')
    data = cur.fetchall()

    cur.execute('SELECT idCategoria, cNombre FROM categoria WHERE bActivo = 1')
    categorias = cur.fetchall()
    cur.execute('SELECT idProveedor, cNombre FROM proveedor WHERE bActivo = 1')
    proveedores = cur.fetchall()

    return render_template('productos.html', productos=data, categorias=categorias,
                            proveedores=proveedores, usuario_nombre=session.get('cNombre'), activo='productos')


@app.route('/productos/crear', methods=['POST'])
@loginRequerido
def crearProducto():
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    precio = request.form.get('fPrecio')
    stock = request.form.get('iStock')
    idCategoria = request.form.get('idCategoria') or None
    idProveedor = request.form.get('idProveedor') or None
    nombreImagen = None

    archivo = request.files.get('cImagen')
    if archivo and archivo.filename and extensionValida(archivo.filename):
        nombreImagen = secure_filename(archivo.filename)
        archivo.save(os.path.join(CARPETA_IMAGENES, nombreImagen))

    try:
        cursor.execute(
            'INSERT INTO producto(cNombre,fPrecio,iStock,cImagen,idCategoria,idProveedor) VALUES(%s,%s,%s,%s,%s,%s)',
            (nombre, precio, stock, nombreImagen, idCategoria, idProveedor)
        )
        mysql.connection.commit()
        return {"Resultado": "Producto creado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/productos/editar/<id>', methods=['POST'])
@loginRequerido
def editarProducto(id):
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    precio = request.form.get('fPrecio')
    stock = request.form.get('iStock')
    idCategoria = request.form.get('idCategoria') or None
    idProveedor = request.form.get('idProveedor') or None

    archivo = request.files.get('cImagen')
    nombreImagen = None
    if archivo and archivo.filename and extensionValida(archivo.filename):
        nombreImagen = secure_filename(archivo.filename)
        archivo.save(os.path.join(CARPETA_IMAGENES, nombreImagen))

    try:
        if nombreImagen:
            cursor.execute(
                'UPDATE producto SET cNombre=%s, fPrecio=%s, iStock=%s, cImagen=%s, idCategoria=%s, idProveedor=%s WHERE idProducto=%s',
                (nombre, precio, stock, nombreImagen, idCategoria, idProveedor, id)
            )
        else:
            cursor.execute(
                'UPDATE producto SET cNombre=%s, fPrecio=%s, iStock=%s, idCategoria=%s, idProveedor=%s WHERE idProducto=%s',
                (nombre, precio, stock, idCategoria, idProveedor, id)
            )
        mysql.connection.commit()
        return {"Resultado": "Producto actualizado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/productos/estado/<id>', methods=['POST'])
@loginRequerido
def estadoProducto(id):
    cursor = mysql.connection.cursor()
    nuevoEstado = request.form.get('bActivo')
    try:
        cursor.execute('UPDATE producto SET bActivo=%s WHERE idProducto=%s', (nuevoEstado, id))
        mysql.connection.commit()
        accion = "activado" if nuevoEstado == '1' else "desactivado"
        return {"Resultado": f"Producto {accion} correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


# =================================================================
# CATALOGO: CATEGORIA
# =================================================================

@app.route('/categorias')
@loginRequerido
def categorias():
    cur = mysql.connection.cursor()
    cur.execute('SELECT idCategoria, cNombre, cDescripcion, bActivo FROM categoria ORDER BY idCategoria DESC')
    data = cur.fetchall()
    return render_template('categorias.html', categorias=data, usuario_nombre=session.get('cNombre'), activo='categorias')


@app.route('/categorias/crear', methods=['POST'])
@loginRequerido
def crearCategoria():
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    descripcion = request.form.get('cDescripcion')
    try:
        cursor.execute('INSERT INTO categoria(cNombre, cDescripcion) VALUES(%s,%s)', (nombre, descripcion))
        mysql.connection.commit()
        return {"Resultado": "Categoria creada correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/categorias/editar/<id>', methods=['POST'])
@loginRequerido
def editarCategoria(id):
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    descripcion = request.form.get('cDescripcion')
    try:
        cursor.execute('UPDATE categoria SET cNombre=%s, cDescripcion=%s WHERE idCategoria=%s',
                        (nombre, descripcion, id))
        mysql.connection.commit()
        return {"Resultado": "Categoria actualizada correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/categorias/estado/<id>', methods=['POST'])
@loginRequerido
def estadoCategoria(id):
    cursor = mysql.connection.cursor()
    nuevoEstado = request.form.get('bActivo')
    try:
        cursor.execute('UPDATE categoria SET bActivo=%s WHERE idCategoria=%s', (nuevoEstado, id))
        mysql.connection.commit()
        accion = "activada" if nuevoEstado == '1' else "desactivada"
        return {"Resultado": f"Categoria {accion} correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


# =================================================================
# CATALOGO: PROVEEDOR
# =================================================================

@app.route('/proveedores')
@loginRequerido
def proveedores():
    cur = mysql.connection.cursor()
    cur.execute('SELECT idProveedor, cNombre, cContacto, cTelefono, cCorreo, bActivo FROM proveedor ORDER BY idProveedor DESC')
    data = cur.fetchall()
    return render_template('proveedores.html', proveedores=data, usuario_nombre=session.get('cNombre'), activo='proveedores')


@app.route('/proveedores/crear', methods=['POST'])
@loginRequerido
def crearProveedor():
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    contacto = request.form.get('cContacto')
    telefono = request.form.get('cTelefono')
    correo = request.form.get('cCorreo')
    try:
        cursor.execute(
            'INSERT INTO proveedor(cNombre, cContacto, cTelefono, cCorreo) VALUES(%s,%s,%s,%s)',
            (nombre, contacto, telefono, correo)
        )
        mysql.connection.commit()
        return {"Resultado": "Proveedor creado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/proveedores/editar/<id>', methods=['POST'])
@loginRequerido
def editarProveedor(id):
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    contacto = request.form.get('cContacto')
    telefono = request.form.get('cTelefono')
    correo = request.form.get('cCorreo')
    try:
        cursor.execute(
            'UPDATE proveedor SET cNombre=%s, cContacto=%s, cTelefono=%s, cCorreo=%s WHERE idProveedor=%s',
            (nombre, contacto, telefono, correo, id)
        )
        mysql.connection.commit()
        return {"Resultado": "Proveedor actualizado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/proveedores/estado/<id>', methods=['POST'])
@loginRequerido
def estadoProveedor(id):
    cursor = mysql.connection.cursor()
    nuevoEstado = request.form.get('bActivo')
    try:
        cursor.execute('UPDATE proveedor SET bActivo=%s WHERE idProveedor=%s', (nuevoEstado, id))
        mysql.connection.commit()
        accion = "activado" if nuevoEstado == '1' else "desactivado"
        return {"Resultado": f"Proveedor {accion} correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


# =================================================================
# CATALOGO: USUARIO
# =================================================================

@app.route('/usuarios')
@loginRequerido
def usuarios():
    cur = mysql.connection.cursor()
    cur.execute('SELECT idUsuario, cUsuario, cNombre, cCorreo, bActivo FROM usuario ORDER BY idUsuario DESC')
    data = cur.fetchall()
    return render_template('usuarios.html', usuarios=data, usuario_nombre=session.get('cNombre'), activo='usuarios')


@app.route('/usuarios/crear', methods=['POST'])
@loginRequerido
def crearUsuario():
    cursor = mysql.connection.cursor()
    usuario = request.form.get('cUsuario')
    password = request.form.get('cPassword')
    nombre = request.form.get('cNombre')
    correo = request.form.get('cCorreo')
    try:
        hashPassword = generate_password_hash(password, method='pbkdf2:sha256')
        cursor.execute(
            'INSERT INTO usuario(cUsuario, cPassword, cNombre, cCorreo) VALUES(%s,%s,%s,%s)',
            (usuario, hashPassword, nombre, correo)
        )
        mysql.connection.commit()
        return {"Resultado": "Usuario creado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/usuarios/editar/<id>', methods=['POST'])
@loginRequerido
def editarUsuario(id):
    cursor = mysql.connection.cursor()
    usuario = request.form.get('cUsuario')
    password = request.form.get('cPassword')
    nombre = request.form.get('cNombre')
    correo = request.form.get('cCorreo')
    try:
        if password:
            hashPassword = generate_password_hash(password, method='pbkdf2:sha256')
            cursor.execute(
                'UPDATE usuario SET cUsuario=%s, cPassword=%s, cNombre=%s, cCorreo=%s WHERE idUsuario=%s',
                (usuario, hashPassword, nombre, correo, id)
            )
        else:
            cursor.execute(
                'UPDATE usuario SET cUsuario=%s, cNombre=%s, cCorreo=%s WHERE idUsuario=%s',
                (usuario, nombre, correo, id)
            )
        mysql.connection.commit()
        return {"Resultado": "Usuario actualizado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/usuarios/estado/<id>', methods=['POST'])
@loginRequerido
def estadoUsuario(id):
    cursor = mysql.connection.cursor()
    nuevoEstado = request.form.get('bActivo')
    try:
        cursor.execute('UPDATE usuario SET bActivo=%s WHERE idUsuario=%s', (nuevoEstado, id))
        mysql.connection.commit()
        accion = "activado" if nuevoEstado == '1' else "desactivado"
        return {"Resultado": f"Usuario {accion} correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


if __name__ == '__main__':
    app.run(port=3000, debug=True)
