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

@app.route('/image_text_to_audio', methods=['POST'])
def image_text_to_audio_route():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    data = request.get_json()
    text = data.get('text', '').strip()
    selected_language = data.get('language', 'eng')

    if not text:
        return jsonify({"text": "No text detected", "audio_url": ""})

    language_mapping = {
        'eng': 'en', 'deu': 'de', 'fra': 'fr', 'hin': 'hi',
        'rus': 'ru', 'spa': 'es', 'tam': 'ta', 'ben': 'bn', 'mal': 'ml'
    }

    tts_language = language_mapping.get(selected_language, 'en')

    audio_filename = f"extracted_text_audio_{int(time.time())}.mp3"
    audio_path = os.path.join(TEMP_DIR, audio_filename)

    tts = gt.gTTS(text=text, lang=tts_language, slow=False)
    tts.save(audio_path)

    extracted_text = ExtractedText(user_id=user_id, text=text)
    db.session.add(extracted_text)
    db.session.commit()

    return jsonify({"text": text, "audio_url": f"/download_audio/{os.path.basename(audio_path)}"})

@app.route('/image_text_to_word', methods=['POST'])
def image_text_to_word():
    text = request.form['text']
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
    return render_template('history.html', history=history)

@app.route('/download_audio/<filename>')
def download_audio(filename):
    return send_file(os.path.join(TEMP_DIR, filename), as_attachment=True)

# New Route: Extract health parameters
@app.route('/extract_health_data', methods=['POST'])
def extract_health_data():
    import re
    data = request.get_json()
    text = data.get('text', '')

    # Enhanced pattern: capture label, value, unit (before/after), and range
    pattern = r'([A-Z][A-Za-z\s/()]+)[\s:]([\d.]+)\s*([a-zA-Z/%]+)?\s*([(\[]?[\d.]+\s*[-–]\s*[\d.]+[)\]]?)?\s*([a-zA-Z/%]+)?'

    matches = re.findall(pattern, text)
    parsed = []

    for name, value, unit1, range_str, unit2 in matches:
        range_cleaned = range_str.replace('(', '').replace(')', '').replace('[', '').replace(']', '').replace('–', '-').strip() if range_str else '-'

        # ✅ Combine units from before/after range
        final_unit = unit1 or unit2 or '-'

        parsed.append({
            'parameter': name.strip(),
            'value': value,
            'unit': final_unit,
            'range': range_cleaned
        })

    return jsonify(parsed)




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5500)
