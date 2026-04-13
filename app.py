from flask import Flask, request, jsonify
import subprocess
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

app = Flask(__name__)

def get_drive_service():
    credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
    credentials_info = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=credentials)

@app.route('/')
def home():
    return 'Video Clip Agent is running!'

@app.route('/process', methods=['POST'])
def process_clip():
    data = request.json
    file_id = data.get('file_id')
    start_time = data.get('start_time')
    duration = data.get('duration', 30)
    emotion_text = data.get('emotion_text', '')
    output_name = data.get('output_name', 'clip.mp4')
    folder_id = data.get('folder_id', '')

    service = get_drive_service()
    request_drive = service.files().get_media(fileId=file_id)
    input_path = '/tmp/input.mp4'

    with open(input_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request_drive)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    output_path = f'/tmp/{output_name}'

    emotion_filter = ''
    if emotion_text:
        safe_text = emotion_text.replace("'", "")
        emotion_filter = f",drawtext=text='{safe_text}':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.6:boxborderw=10"

    command = [
        'ffmpeg', '-i', input_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-vf', f'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,hflip{emotion_filter}',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-y',
        output_path
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        return jsonify({'status': 'error', 'message': result.stderr})

    file_metadata = {'name': output_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(output_path, mimetype='video/mp4')
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    return jsonify({
        'status': 'success',
        'file_id': uploaded.get('id'),
        'link': uploaded.get('webViewLink')
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
