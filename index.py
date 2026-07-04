from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import os

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


def extensionValida(nombreArchivo):
    return '.' in nombreArchivo and nombreArchivo.rsplit('.', 1)[1].lower() in EXTENSIONES_PERMITIDAS


def usuarioLogueado():
    return 'idUsuario' in session


@app.route('/')
def home():
    if usuarioLogueado():
        return redirect('/productos')
    return redirect('/login')


@app.route('/login', methods=['GET'])
def loginForm():
    if usuarioLogueado():
        return redirect('/productos')
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    cUsuario = request.form.get('cUsuario')
    cPassword = request.form.get('cPassword')

    cur = mysql.connection.cursor()
    cur.execute(
        'SELECT idUsuario, cUsuario, cNombre FROM usuario WHERE cUsuario = %s AND cPassword = %s',
        (cUsuario, cPassword)
    )
    fila = cur.fetchone()

    if fila:
        session['idUsuario'] = fila[0]
        session['cUsuario'] = fila[1]
        session['cNombre'] = fila[2]
        return redirect('/productos')
    else:
        return render_template('login.html', error='Usuario o contraseña incorrectos')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/productos')
def productos():
    if not usuarioLogueado():
        return redirect('/login')
    cur = mysql.connection.cursor()
    cur.execute('SELECT idProducto, cNombre, fPrecio, iStock, cImagen, bActivo FROM producto')
    data = cur.fetchall()
    return render_template('productos.html', productos=data, usuario_nombre=session.get('cNombre'))


@app.route('/productos/crear', methods=['POST'])
def crearProducto():
    if not usuarioLogueado():
        return {"Resultado": "Sesion expirada"}
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    precio = request.form.get('fPrecio')
    stock = request.form.get('iStock')
    nombreImagen = None

    archivo = request.files.get('cImagen')
    if archivo and archivo.filename and extensionValida(archivo.filename):
        nombreImagen = secure_filename(archivo.filename)
        archivo.save(os.path.join(CARPETA_IMAGENES, nombreImagen))

    try:
        cursor.execute(
            'INSERT INTO producto(cNombre,fPrecio,iStock,cImagen) VALUES(%s,%s,%s,%s)',
            (nombre, precio, stock, nombreImagen)
        )
        mysql.connection.commit()
        return {"Resultado": "Producto creado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/productos/editar/<id>', methods=['POST'])
def editarProducto(id):
    if not usuarioLogueado():
        return {"Resultado": "Sesion expirada"}
    cursor = mysql.connection.cursor()
    nombre = request.form.get('cNombre')
    precio = request.form.get('fPrecio')
    stock = request.form.get('iStock')

    archivo = request.files.get('cImagen')
    nombreImagen = None
    if archivo and archivo.filename and extensionValida(archivo.filename):
        nombreImagen = secure_filename(archivo.filename)
        archivo.save(os.path.join(CARPETA_IMAGENES, nombreImagen))

    try:
        if nombreImagen:
            cursor.execute(
                'UPDATE producto SET cNombre=%s, fPrecio=%s, iStock=%s, cImagen=%s WHERE idProducto=%s',
                (nombre, precio, stock, nombreImagen, id)
            )
        else:
            cursor.execute(
                'UPDATE producto SET cNombre=%s, fPrecio=%s, iStock=%s WHERE idProducto=%s',
                (nombre, precio, stock, id)
            )
        mysql.connection.commit()
        return {"Resultado": "Producto actualizado correctamente"}
    except Exception as e:
        mysql.connection.rollback()
        return {"Resultado": f"Ocurrio un error: {e}"}


@app.route('/productos/estado/<id>', methods=['POST'])
def estadoProducto(id):
    if not usuarioLogueado():
        return {"Resultado": "Sesion expirada"}
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


if __name__ == '__main__':
    app.run(port=3000, debug=True)
