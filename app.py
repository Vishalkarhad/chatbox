from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store chat messages in memory (simple demo)
chat_messages = []
typing_previews = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('send_message')
def handle_send_message(data):
    chat_messages.append(data)
    emit('new_message', data, broadcast=True)

@socketio.on('typing_preview')
def handle_typing_preview(data):
    typing_previews[data['sender']] = data['previewText']
    emit('typing_update', data, broadcast=True, include_self=False)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    if data['sender'] in typing_previews:
        del typing_previews[data['sender']]
    emit('typing_update', data, broadcast=True, include_self=False)

@socketio.on('request_history')
def handle_request_history():
    emit('history', chat_messages)

if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
