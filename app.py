from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-a-secure-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# in-memory: { room_id: [ {sender, receiver, text, timestamp}, ... ] }
ROOM_MESSAGES = {}
ROOM_PREVIEWS = {}
SID_TO_INFO = {}  # { sid: {username, room_id} }

@app.route('/chat/<room_id>')
def chat_page(room_id):
    return render_template('index.html', room_id=room_id)

@app.route('/history/<room_id>/<username>')
def history(room_id, username):
    msgs = ROOM_MESSAGES.get(room_id, [])
    user_msgs = [m for m in msgs if m['sender'] == username or m['receiver'] == username]
    user_msgs.sort(key=lambda x: x['timestamp'])
    return jsonify(user_msgs)

@app.route('/clearchat/<room_id>', methods=['GET'])
def clear_chat(room_id):
    ROOM_MESSAGES[room_id] = []
    ROOM_PREVIEWS[room_id] = {}
    return jsonify({"status": "success", "message": f"Chat cleared for room {room_id}"})

# SOCKET EVENTS
@socketio.on('register')
def on_register(data):
    username = data.get('username')
    room_id = data.get('room_id')
    if not username or not room_id:
        return
    SID_TO_INFO[request.sid] = {'username': username, 'room_id': room_id}
    join_room(f"{room_id}_{username}")  # personal room
    join_room(room_id)  # common chat room

    msgs = ROOM_MESSAGES.get(room_id, [])
    user_msgs = [m for m in msgs if m['sender'] == username or m['receiver'] == username]
    user_msgs.sort(key=lambda x: x['timestamp'])
    emit('history', user_msgs)

    other_preview = None
    for user, text in ROOM_PREVIEWS.get(room_id, {}).items():
        if user != username:
            other_preview = {'from': user, 'text': text}
    if other_preview:
        emit('preview', other_preview)

@socketio.on('disconnect')
def on_disconnect():
    SID_TO_INFO.pop(request.sid, None)

@socketio.on('send_message')
def on_send_message(data):
    sender = data.get('sender')
    receiver = data.get('receiver')
    text = data.get('text', '').strip()
    room_id = data.get('room_id')
    if not sender or not receiver or not room_id or not text:
        return

    msg = {
        'sender': sender,
        'receiver': receiver,
        'text': text,
        'timestamp': int(time.time() * 1000)
    }
    ROOM_MESSAGES.setdefault(room_id, []).append(msg)
    ROOM_PREVIEWS.setdefault(room_id, {}).pop(sender, None)

    emit('new_message', msg, to=room_id)

@socketio.on('typing')
def on_typing(data):
    sender = data.get('sender')
    receiver = data.get('receiver')
    text = data.get('text', '')
    room_id = data.get('room_id')
    if not sender or not receiver or not room_id:
        return

    if text.strip() == '':
        ROOM_PREVIEWS.setdefault(room_id, {}).pop(sender, None)
    else:
        ROOM_PREVIEWS.setdefault(room_id, {})[sender] = text

    emit('preview', {'from': sender, 'text': text}, to=room_id)
