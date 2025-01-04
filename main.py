from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymongo
import bcrypt
import os
from werkzeug.utils import secure_filename
from models.model import initialize_llm, initialize_embeddings, initialize_vectorstore, create_rag_chain
from langchain_community.document_loaders import PyPDFLoader
from langchain_experimental.text_splitter import SemanticChunker
from bson.objectid import ObjectId
from bson import ObjectId
from bson.errors import InvalidId



# Membuat aplikasi Flask
app = Flask(__name__)
app.secret_key = 'rahasiadong'

# Konfigurasi MongoDB
client = pymongo.MongoClient("mongodb+srv://akhmadretzasyahpahlevi:AVUJX87FwZH6ngpv@cluster0.snjfd.mongodb.net/databasecapstone?retryWrites=true&w=majority&appName=Cluster0")  # Ganti dengan connection string MongoDB Anda
db = client['databasecapstone']  # Nama database

# Konfigurasi folder untuk upload gambar
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

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

# Hardcoded API Key and PDF path
GROQ_API_KEY = "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"
PDF_FILE_PATH = os.path.join(os.path.dirname(__file__), "data/dataset1.pdf")

def initialize_rag_model():
    """Initialize the RAG model and vector store retriever."""
    try:
        # Initialize LLM and embeddings
        llm = initialize_llm(GROQ_API_KEY)
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

# Halaman artikel
@app.route("/artikel")
def artikel():
    articles = list(db.articles.find({}, {"_id": 1, "title": 1, "content": 1, "image_filename": 1}))
    return render_template("artikel.html", articles=articles)

@app.route("/artikel/<string:id>")
def article_detail(id):
    try:
        object_id = ObjectId(id)  # Mengubah id menjadi ObjectId
    except InvalidId:
        flash("Invalid article ID!")
        return redirect(url_for('articles'))  # Redirect jika ID tidak valid

    article = db.articles.find_one({"_id": object_id})
    
    if not article:
        flash("Article not found!")
        return redirect(url_for('articles'))  # Redirect jika artikel tidak ditemukan
    
    return render_template('artikel_detail.html', article=article)


# Menampilkan daftar artikel
@app.route('/articles')
def articles():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))
    articles = list(db.articles.find())
    return render_template('admin/articles.html', articles=articles)

# Menambahkan artikel baru
@app.route('/add_article', methods=['GET', 'POST'])
def add_article():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image = request.files['image']

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            db.articles.insert_one({
                "title": title,
                "content": content,
                "image_filename": filename
            })
            flash("Article added successfully!")
            return redirect(url_for('articles'))
        else:
            flash("Invalid image file type!")
    return render_template('admin/add_article.html')

# Mengedit artikel
@app.route('/edit_article/<string:id>', methods=['GET', 'POST'])
def edit_article(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    # Cek apakah id valid
    try:
        object_id = ObjectId(id)  # Coba ubah id menjadi ObjectId
    except InvalidId:
        flash("Invalid article ID!")
        return redirect(url_for('articles'))  # Redirect ke halaman daftar artikel jika ID tidak valid

    # Jika ID valid, lanjutkan pencarian artikel
    article = db.articles.find_one({"_id": object_id})

    if not article:
        flash("Article not found!")
        return redirect(url_for('articles'))  # Jika artikel tidak ditemukan, redirect

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image = request.files['image']

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = article['image_filename']  # Jika gambar tidak diubah, gunakan gambar lama

        db.articles.update_one(
            {"_id": object_id},
            {"$set": {
                "title": title,
                "content": content,
                "image_filename": filename
            }}
        )
        flash("Article updated successfully!")
        return redirect(url_for('articles'))

    return render_template('admin/edit_article.html', article=article)

# Menghapus artikel
@app.route('/delete_article/<string:id>')
def delete_article(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    # Mengubah id string menjadi ObjectId
    try:
        object_id = ObjectId(id)
    except InvalidId:
        flash("Invalid article ID!")
        return redirect(url_for('articles'))  # Redirect jika ID tidak valid

    # Menghapus artikel
    db.articles.delete_one({"_id": object_id})
    flash("Article deleted successfully!")
    return redirect(url_for('articles'))

@app.route('/admin/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))  # Pastikan hanya admin yang login

    # Koneksi ke MongoDB dan ambil data admin berdasarkan user_id
    admin = db.admin.find_one({"_id": ObjectId(session['user_id'])})

    if not admin:
        flash("Admin not found!", "danger")
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        new_email = request.form['email']
        new_password = request.form['password']

        # Hash password baru
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        # Update email dan password di database MongoDB
        db.admin.update_one(
            {"_id": ObjectId(session['user_id'])},
            {"$set": {
                "email": new_email,
                "password": hashed_password.decode('utf-8')
            }}
        )

        # Flash message sukses
        flash("Settings updated successfully!", "success")

        # Redirect kembali ke halaman dashboard admin
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/settings.html', admin=admin)



@app.route('/admin_dashboard')
def admin_dashboard():
    # Pastikan hanya admin yang login yang dapat mengakses dashboard
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "warning")
        return redirect(url_for('login_admin'))  # Jika belum login, arahkan ke halaman login

    return render_template('admin/admin_dashboard.html')

# Login admin
@app.route('/admin/login', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = db.admin.find_one({"email": email})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['user_id'] = str(user['_id'])
            flash("Login successful!", "success")
            return redirect(url_for('articles'))
        else:
            flash("Invalid email or password", "danger")

    return render_template('admin/login_admin.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login_admin'))

# Pengepul (collectors)
@app.route('/collectors')
def collectors():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))
    collectors = list(db.collectors.find({}, {"_id": 1, "name": 1, "email": 1, "address": 1}))
    return render_template('admin/collectors.html', collectors=collectors)

@app.route('/add_collector', methods=['GET', 'POST'])
def add_collector():
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        password = request.form['password']
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        db.collectors.insert_one({
            "name": name,
            "email": email,
            "address": address,
            "password": hashed_password.decode('utf-8')
        })
        flash("Collector added successfully!", "success")
        return redirect(url_for('collectors'))

    return render_template('admin/add_collector.html')

@app.route('/edit_collector/<string:id>', methods=['GET', 'POST'])
def edit_collector(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    # Cek apakah id valid
    try:
        object_id = ObjectId(id)  # Coba ubah id menjadi ObjectId
    except InvalidId:
        flash("Invalid collector ID!")
        return redirect(url_for('collectors'))  # Redirect ke halaman daftar kolektor jika ID tidak valid

    # Ambil data kolektor dari database
    collector = db.collectors.find_one({"_id": object_id})

    if not collector:
        flash("Collector not found!")
        return redirect(url_for('collectors'))  # Jika kolektor tidak ditemukan, redirect

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        address = request.form['address']
        # Update kolektor
        db.collectors.update_one(
            {"_id": object_id},
            {"$set": {
                "name": name,
                "email": email,
                "address": address
            }}
        )
        flash("Collector updated successfully!", "success")
        return redirect(url_for('collectors'))

    return render_template('admin/edit_collector.html', collector=collector)


@app.route('/delete_collector/<string:id>')
def delete_collector(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))
    db.collectors.delete_one({"_id": ObjectId(id)})
    flash("Collector deleted successfully!", "success")
    return redirect(url_for('collectors'))

@app.route('/admin/topup_requests')
def topup_requests():
    # Pastikan admin login
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))

    # Query MongoDB untuk mengambil data top-up request beserta nama dan email pengepul
    requests = list(db.topup_requests.aggregate([
        {
            "$lookup": {
                "from": "collectors",  # Nama koleksi yang di-join
                "localField": "collector_id",  # Field di koleksi topup_requests
                "foreignField": "_id",  # Field di koleksi collectors yang cocok
                "as": "collector_info"  # Alias untuk hasil join
            }
        },
        {
            "$unwind": {
                "path": "$collector_info",  # Mengubah array menjadi objek
                "preserveNullAndEmptyArrays": True  # Untuk tetap mengembalikan data jika tidak ada pencocokan
            }
        }
    ]))
    
    # Render halaman admin dengan data top-up request
    return render_template('admin/topup_requests.html', topup_requests=requests)


@app.route('/admin/update_topup_request/<string:id>', methods=['POST'])
def update_topup_request(id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))
    points = request.form['points']
    status = request.form['status']
    db.topup_requests.update_one({"_id": ObjectId(id)}, {"$set": {"points": int(points), "status": status}})
    flash("Top-up request updated successfully!", "success")
    return redirect(url_for('topup_requests'))

@app.route('/add_points/<topup_id>', methods=['GET', 'POST'])
def add_points(topup_id):
    if 'user_id' not in session:
        return redirect(url_for('login_admin'))
    
    # Cari data top-up berdasarkan topup_id
    topup_request = db.topup_requests.find_one({"_id": ObjectId(topup_id)})
    
    if not topup_request:
        return "Top-up request not found", 404
    
    # Proses jika metode POST (untuk menambah poin)
    if request.method == 'POST':
        points_to_add = request.form.get('points')
        status = request.form.get('status')
        
        # Update poin dan status di top-up request
        db.topup_requests.update_one(
            {"_id": ObjectId(topup_id)},
            {"$set": {"points": int(points_to_add), "status": status}}
        )
        
        return redirect(url_for('topup_requests'))
    
    # Render halaman untuk menambah poin
    return render_template('admin/add_points.html', topup_request=topup_request)


if __name__ == '__main__':
    app.run(debug=True)
