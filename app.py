from flask import Flask, request, jsonify
import subprocess
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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

@app.route('/search', methods=['POST'])
def search_video():
    data = request.json
    query = data.get('query')
    
    result = subprocess.run([
        'yt-dlp',
        f'ytsearch1:{query} фильм полностью',
        '--get-id',
        '--get-title',
        '--no-playlist'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            return jsonify({
                'status': 'success',
                'title': lines[0],
                'video_id': lines[1]
            })
    
    return jsonify({'status': 'error', 'message': result.stderr})

@app.route('/process', methods=['POST'])
def process_clip():
    data = request.json
    video_url = data.get('video_url')
    start_time = data.get('start_time', '00:00:00')
    duration = data.get('duration', 30)
    emotion_text = data.get('emotion_text', '')
    output_name = data.get('output_name', 'clip.mp4')
    folder_id = data.get('folder_id', '')

    input_path = '/tmp/input.mp4'
    output_path = f'/tmp/{output_name}'

    # Скачиваем видео
    download = subprocess.run([
        'yt-dlp',
        '-f', 'best[ext=mp4]/best',
        '-o', input_path,
        '--no-playlist',
        video_url
    ], capture_output=True, text=True)

    if download.returncode != 0:
        return jsonify({'status': 'error', 'message': download.stderr})

    # Формируем фильтр эмоций
    emotion_filter = ''
    if emotion_text:
        safe_text = emotion_text.replace("'", "").replace(":", "")
        emotion_filter = f",drawtext=text='{safe_text}':fontsize=60:fontcolor=white:x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.6:boxborderw=10"

    # Нарезаем клип
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

    # Загружаем на Google Drive
    service = get_drive_service()
    file_metadata = {'name': output_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(output_path, mimetype='video/mp4')
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # Чистим временные файлы
    os.remove(input_path)
    os.remove(output_path)

    return jsonify({
        'status': 'success',
        'file_id': uploaded.get('id'),
        'link': uploaded.get('webViewLink')
    })
@app.route('/check', methods=['POST'])
def check_availability():
    data = request.json
    query = data.get('query')
    folder_id = data.get('folder_id', '')
    
    report = {}
    
    # 1. Проверяем сервер
    report['server'] = '✅ Сервер работает'
    
    # 2. Ищем фильм
    search = subprocess.run([
        'yt-dlp',
        f'ytsearch3:{query} фильм',
        '--get-title',
        '--get-id',
        '--no-playlist',
        '--flat-playlist'
    ], capture_output=True, text=True, timeout=30)
    
    if search.returncode == 0 and search.stdout.strip():
        lines = search.stdout.strip().split('\n')
        report['video'] = f'✅ Найдено видео: {lines[0]}'
        report['video_found'] = True
    else:
        report['video'] = '❌ Видео не найдено'
        report['video_found'] = False
    
    # 3. Проверяем Google Drive
    try:
        service = get_drive_service()
        about = service.about().get(fields='storageQuota').execute()
        quota = about.get('storageQuota', {})
        limit = int(quota.get('limit', 0))
        usage = int(quota.get('usage', 0))
        free_gb = (limit - usage) / (1024**3)
        
        if free_gb > 1:
            report['drive'] = f'✅ Google Drive: {free_gb:.1f} ГБ свободно'
            report['drive_ok'] = True
        else:
            report['drive'] = f'⚠️ Google Drive: мало места ({free_gb:.2f} ГБ)'
            report['drive_ok'] = False
    except Exception as e:
        report['drive'] = f'❌ Google Drive недоступен: {str(e)}'
        report['drive_ok'] = False
    
    # Итоговый статус
    all_ok = report.get('video_found') and report.get('drive_ok')
    report['ready'] = all_ok
    
    return jsonify(report)
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
