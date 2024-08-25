import os
import time
import re
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from datetime import timedelta
import yt_dlp
import threading

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for sessions
app.permanent_session_lifetime = timedelta(hours=1)

# Retrieve the secret code from the environment variable
SECRET_CODE = os.getenv('YTDL_SECRET', 'default_secret')

UPLOAD_FOLDER = 'downloads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Global dictionary to store the progress and download links
download_data = {}

# Thread to handle video downloading
def download_video(url, download_path):
    ydl_opts = {
        'format': '18',  # Set format to 18 (360p MP4)
        'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'progress_hooks': [lambda d: progress_hook(d, url)],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# Progress hook to track download progress
def progress_hook(d, url):
    if d['status'] == 'downloading': # Raw text with ANSI escape codes
        raw_text = f"{d['_percent_str']} - {d['_speed_str']} - ETA {d['_eta_str']}"
        
        # Regular expression to remove ANSI escape codes
        clean_text = re.sub(r'\x1B[@-_][0-?]*[ -/]*[@-~]', '', raw_text)
        
        # Store the clean text
        download_data[url]['progress'] = clean_text

    elif d['status'] == 'finished':
        download_data[url]['progress'] = 'Completed'
        download_data[url]['filename'] = d['filename']
        threading.Timer(60, delete_file, args=[d['filename']]).start()

def delete_file(filepath):
    try:
        # Remove all extension with that filename
        filepath = os.path.splitext(filepath)[0]
        os.remove(filepath + '.mp3')
        os.remove(filepath + '.mp4')

        print(f"Deleted file: {filepath}")
    except FileNotFoundError:
        print(f"File already deleted: {filepath}")
    except Exception as e:
        print(f"Error deleting file: {filepath}, {e}")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        code = request.form.get('code')
        if code == SECRET_CODE:
            session.permanent = True  # Session persists
            session['authenticated'] = True
            return redirect(url_for('main'))
        else:
            return render_template('index.html', error="Invalid code! Please try again.")
    return render_template('index.html')

@app.route('/main', methods=['GET', 'POST'])
def main():
    if not session.get('authenticated'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        urls = request.form.getlist('url')
        download_threads = []

        for url in urls:
            download_data[url] = {'progress': 'Starting...', 'filename': None}
            download_thread = threading.Thread(target=download_video, args=(url, UPLOAD_FOLDER))
            download_thread.start()
            download_threads.append(download_thread)

        return render_template('main.html', urls=urls)

    return render_template('main.html')

@app.route('/progress')
def progress():
    return jsonify(download_data)

@app.route('/download/<path:filename>')
def download_file(filename):
    if not session.get('authenticated'):
        return redirect(url_for('index'))

    # Send the mp3 file as an attachment
    filename = filename.replace('.mp4', '.mp3')    
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
