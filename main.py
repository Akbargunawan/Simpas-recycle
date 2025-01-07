from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
import bcrypt
import os
from werkzeug.utils import secure_filename
from models.model import initialize_llm, initialize_embeddings, initialize_vectorstore, create_rag_chain
from langchain_community.document_loaders import PyPDFLoader
from templates.indobert import SentimentAnalyzer
from flask_cors import CORS
import requests


# Membuat aplikasi Flask
app = Flask(__name__)
CORS(app)
app.secret_key = 'rahasiadong' 

model_indobert = 'models'
analyzer_indobert = SentimentAnalyzer(model_indobert)

# Konfigurasi database
db_config = {
    'host': 'localhost',
    'user': 'root',         
    'password': '',         
    'database': 'simpas',   
}

# Konfigurasi folder untuk upload gambar
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Hardcoded API Key and PDF path
GROQ__API__KEY = "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"
PDF_FILE_PATH = os.path.join(os.path.dirname(__file__), "data/dataset1.pdf")

def initialize_rag_model():
    """Initialize the RAG model and vector store retriever."""
    try:
        # Initialize LLM and embeddings
        llm = initialize_llm(GROQ__API__KEY)
        embeddings = initialize_embeddings()

        # Load and process PDF documents
        pdf_loader = PyPDFLoader(PDF_FILE_PATH)
        documents = pdf_loader.load()

        # Initialize vector store retriever
        retriever = initialize_vectorstore(documents, embeddings)
        app.config['llm'] = llm
        app.config['retriever'] = retriever
        print("Model and retriever initialized successfully.")
    except Exception as e:
        print(f"Error initializing model: {e}")
        raise e

@app.before_request
def setup_model():
    """Ensure model is initialized before the first request."""
    if 'llm' not in app.config or 'retriever' not in app.config:
        initialize_rag_model()

@app.route('/get', methods=['GET'])
def get_response():
    message = request.args.get('msg')

    # Check if message is present
    if not message:
        return "No input received."

    # Ensure model and retriever are initialized
    llm = app.config.get('llm')
    retriever = app.config.get('retriever')
    
    if not llm or not retriever:
        return "Model or retriever is not initialized."

    try:
        # Create the RAG chain with the retriever and llm
        rag_chain = create_rag_chain(retriever, llm)
        response = rag_chain.invoke({"input": message})
        return response['answer']
    except Exception as e:
        return f"Error: {e}"

# Fungsi untuk memeriksa ekstensi file gambar yang di-upload
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Halaman utama (landing page)
@app.route("/")
def hello_world():
    return render_template("landing.html")

# Halaman chatbot
@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

#Halaman setting Admin
@app.route('/admin/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Pastikan hanya admin yang login

    # Koneksi ke database untuk mengambil data admin
    connection = pymysql.connect(**db_config)
    cur = connection.cursor()
    
    # Ambil data admin berdasarkan user_id (admin yang sedang login)
    cur.execute("SELECT * FROM admin WHERE id = %s", (session['user_id'],))
    admin = cur.fetchone()

    if request.method == 'POST':
        new_email = request.form['email']
        new_password = request.form['password']

        # Hash password baru
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        # Update email dan password di database
        cur.execute("UPDATE admin SET email = %s, password = %s WHERE id = %s",
                    (new_email, hashed_password.decode('utf-8'), admin[0]))
        connection.commit()

        # Flash message sukses
        flash("Settings updated successfully!", "success")

        # Redirect kembali ke halaman dashboard admin
        return redirect(url_for('admin_dashboard'))
    
    cur.close()
    connection.close()

    return render_template('admin/settings.html', admin=admin)


# Halaman artikel
@app.route("/artikel")
def artikel():
    # Ambil data artikel dari database dengan DictCursor
    connection = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **db_config)
    cur = connection.cursor()
    cur.execute("SELECT id, title, content, image_filename FROM articles")  # Query untuk mengambil artikel
    articles = cur.fetchall()  # Hasilnya berupa list of dictionaries
    cur.close()
    connection.close()
    
    # Kirim data artikel ke template
    return render_template("artikel.html", articles=articles)

@app.route("/artikel/<int:id>")
def article_detail(id):
    # Ambil artikel berdasarkan id dari database
    connection = pymysql.connect(**db_config)
    cur = connection.cursor()
    cur.execute("SELECT title, content, image_filename FROM articles WHERE id = %s", (id,))
    article = cur.fetchone()
    cur.close()
    connection.close()
    return render_template("artikel_detail.html", article=article)

# Menampilkan daftar artikel
@app.route('/articles')
def articles():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Jika belum login, arahkan ke halaman login
    connection = pymysql.connect(**db_config)
    cur = connection.cursor()
    cur.execute("SELECT * FROM articles")
    articles = cur.fetchall()
    cur.close()
    connection.close()
    return render_template('admin/articles.html', articles=articles)

# Menambahkan artikel baru
@app.route('/add_article', methods=['GET', 'POST'])
def add_article():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Jika belum login, arahkan ke halaman login

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image = request.files['image']

        # Mengecek apakah file gambar di-upload dan memiliki ekstensi yang valid
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Menyimpan artikel ke database
            connection = pymysql.connect(**db_config)
            cur = connection.cursor()
            cur.execute("INSERT INTO articles (title, content, image_filename) VALUES (%s, %s, %s)",
                        (title, content, filename))
            connection.commit()
            cur.close()
            connection.close()
            flash("Article added successfully!")
            return redirect(url_for('articles'))
    return render_template('admin/add_article.html')

# Mengedit artikel
@app.route('/edit_article/<int:id>', methods=['GET', 'POST'])
def edit_article(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Jika belum login, arahkan ke halaman login

    connection = pymysql.connect(**db_config)
    cur = connection.cursor()
    cur.execute("SELECT * FROM articles WHERE id = %s", (id,))
    article = cur.fetchone()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image = request.files['image']
        
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = article[3]  # Jika gambar tidak diubah, gunakan gambar lama

        # Memperbarui artikel di database
        cur.execute("UPDATE articles SET title = %s, content = %s, image_filename = %s WHERE id = %s",
                    (title, content, filename, id))
        connection.commit()
        cur.close()
        connection.close()
        flash("Article updated successfully!")
        return redirect(url_for('articles'))

    connection.close()
    return render_template('admin/edit_article.html', article=article)

# Menghapus artikel
@app.route('/delete_article/<int:id>')
def delete_article(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Jika belum login, arahkan ke halaman login

    connection = pymysql.connect(**db_config)
    cur = connection.cursor()
    cur.execute("DELETE FROM articles WHERE id = %s", (id,))
    connection.commit()
    cur.close()
    connection.close()
    flash("Article deleted successfully!")
    return redirect(url_for('articles'))

#loginadmin
@app.route('/admin/login', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Koneksi ke database untuk mengecek data login
        connection = pymysql.connect(**db_config)
        cur = connection.cursor()
        
        # Query untuk mengambil data admin berdasarkan email
        cur.execute("SELECT * FROM admin WHERE email = %s", (email,))
        user = cur.fetchone()  # Ambil satu record
        
        if user:
            stored_hash = user[2]  # Ambil password yang telah di-hash dari database
            
            # Verifikasi password yang dimasukkan dengan password yang tersimpan di database
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                session['user_id'] = user[0]  # Simpan ID user di session
                flash("Login successful!", "success")
                return redirect(url_for('admin_dashboard'))  # Redirect ke dashboard admin
            else:
                flash("Invalid password", "danger")
        else:
            flash("Email not found", "danger")
        
        cur.close()
        connection.close()
    
    return render_template('admin/login_admin.html')  # Tampilkan halaman login

@app.route('/admin_dashboard')
def admin_dashboard():
    # Pastikan hanya admin yang login yang dapat mengakses dashboard
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Jika belum login, arahkan ke halaman login
    
    return render_template('admin/admin_dashboard.html')  # Dashboard admin

#menambah collector
@app.route('/add_collector', methods=['GET', 'POST'])
def add_collector():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Pastikan hanya admin yang dapat mengakses

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        password = request.form['password']
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Simpan ke database
        connection = pymysql.connect(**db_config)
        cur = connection.cursor()
        cur.execute("INSERT INTO collectors (name, email, address, password) VALUES (%s, %s, %s, %s)", 
                    (name, email, address, hashed_password.decode('utf-8')))
        connection.commit()
        cur.close()
        connection.close()

        # Flash success message
        flash("Pengepul telah ditambahkan!", "success")
        return redirect(url_for('add_collector'))  # Redirect ke halaman add_collector

    return render_template('admin/add_collector.html')

@app.route('/collectors')
def collectors():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Pastikan hanya admin yang bisa mengakses

    # Ambil data pengepul dari database
    connection = pymysql.connect(**db_config)
    cur = connection.cursor()
    cur.execute("SELECT id, name, email, address FROM collectors")
    collectors = cur.fetchall()
    cur.close()
    connection.close()

    return render_template('admin/collectors.html', collectors=collectors)

@app.route('/edit_collector/<int:id>', methods=['GET', 'POST'])
def edit_collector(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    connection = pymysql.connect(**db_config)
    cur = connection.cursor()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        cur.execute("UPDATE collectors SET name = %s, email = %s, address = %s WHERE id = %s",
                    (name, email, address, id))
        connection.commit()
        cur.close()
        connection.close()
        flash("Data pengepul berhasil diperbarui!", "success")
        return redirect(url_for('collectors'))

    cur.execute("SELECT id, name, email, address FROM collectors WHERE id = %s", (id,))
    collector = cur.fetchone()
    cur.close()
    connection.close()

    return render_template('admin/edit_collector.html', collector=collector)

@app.route('/delete_collector/<int:id>')
def delete_collector(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    connection = pymysql.connect(**db_config)
    cur = connection.cursor()
    cur.execute("DELETE FROM collectors WHERE id = %s", (id,))
    connection.commit()
    cur.close()
    connection.close()
    flash("Pengepul telah dihapus!", "success")
    return redirect(url_for('collectors'))


@app.route('/sentimen', methods=['GET'])
def sentimen():
    # Pastikan hanya admin yang sudah login yang dapat mengakses
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    # Lakukan permintaan ke API untuk mendapatkan data sentimen
    try:
        response = requests.get('http://localhost:3000/api/getSentimen') 
        feedbacks = response.json()
    except requests.exceptions.RequestException as e:
        # Tangani kesalahan saat request API
        return render_template('error.html', error_message="Gagal mendapatkan data dari API")

    sentiment_results = []
    for feedback in feedbacks:
        predicted_class, probabilities = analyzer_indobert.predict_sentiment(feedback['feedback_text'])
        sentiment = "Positif" if predicted_class == 1 else "Negatif"
        sentiment_results.append({
            "text": feedback['feedback_text'],
            "sentiment": sentiment
        })
    
    # Render halaman hasil analisis sentimen
    return render_template('admin/reviewsentimen.html', sentiment_results=sentiment_results)



@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('msg')

    # Check if message is present
    if not message:
        return jsonify({"error": "No input received."}), 400

    # Ensure model and retriever are initialized
    llm = app.config.get('llm')
    retriever = app.config.get('retriever')

    if not llm or not retriever:
        return jsonify({"error": "Model or retriever is not initialized."}), 500

    try:
        # Create the RAG chain with the retriever and llm
        rag_chain = create_rag_chain(retriever, llm)
        response = rag_chain.invoke({"input": message})
        return jsonify({"answer": response['answer']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Hapus data user_id dari session
    flash("You have been logged out.", "info")
    return redirect(url_for('login_admin'))  # Redirect ke halaman login





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)