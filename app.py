from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route('/')
def home():
    return 'Video Clip Agent is running!'

@app.route('/cut', methods=['POST'])
def cut_video():
    data = request.json
    input_file = data.get('input_file')
    start_time = data.get('start_time')
    duration = data.get('duration', 30)
    output_file = data.get('output_file', 'output.mp4')
    
    command = [
        'ffmpeg', '-i', input_file,
        '-ss', start_time,
        '-t', str(duration),
        '-vf', 'scale=1080:1920,hflip',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        output_file
    ]
    
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode == 0:
        return jsonify({'status': 'success', 'file': output_file})
    else:
        return jsonify({'status': 'error', 'message': result.stderr})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
