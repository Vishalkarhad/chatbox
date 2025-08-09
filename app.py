from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

messages = []

@app.route('/')
def index():
    return render_template('index.html')  # तुझा HTML इथे टाक

@socketio.on('send_message')
def handle_send_message(data):
    messages.append(data)
    emit('new_message', data, broadcast=True)

@socketio.on('typing_preview')
def handle_typing(data):
    emit('typing_update', data, broadcast=True, include_self=False)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    emit('typing_update', {'sender': data['sender'], 'previewText': ''},
         broadcast=True, include_self=False)

@socketio.on('request_history')
def handle_history():
    emit('history', messages)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
