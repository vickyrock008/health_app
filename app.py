from flask import Flask, request, send_file, render_template, redirect, url_for, session, jsonify
import gtts as gt
import os
import time
from docx import Document
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import re

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

# Text history model
class ExtractedText(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

TEMP_DIR = "temp_files"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        return 'Invalid username or password'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))



@app.route('/image_text_to_word', methods=['POST'])
def image_text_to_word():
    if 'user_id' not in session:
        print("User not logged in.")
        return redirect(url_for('login'))
    
    text = request.form['text']
    print(f"[SAVE TEXT] User ID: {session['user_id']} - Text: {text}")

    

    # Save to Word
    doc = Document()
    doc.add_paragraph(text)
    word_filename = f"extracted_text_{int(time.time())}.docx"
    word_path = os.path.join(TEMP_DIR, word_filename)
    doc.save(word_path)

    return send_file(word_path, as_attachment=True)

@app.route('/history')
def user_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    history = ExtractedText.query.filter_by(user_id=user_id).order_by(ExtractedText.created_at.desc()).all()
    print(f"[HISTORY] User ID: {user_id} - Found {len(history)} records")
    return render_template('history.html', history=history)

@app.route('/save_extracted_text', methods=['POST'])
def save_extracted_text():
    if 'user_id' not in session:
        return 'Unauthorized', 401

    text = request.form.get('text', '')
    if not text.strip():
        return 'No text to save', 400

    extracted = ExtractedText(
        user_id=session['user_id'],
        text=text
    )
    db.session.add(extracted)
    db.session.commit()
    return 'Saved', 200

@app.route('/download_audio/<filename>')
def download_audio(filename):
    return send_file(os.path.join(TEMP_DIR, filename), as_attachment=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
