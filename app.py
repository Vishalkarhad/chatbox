from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-a-secure-key'
socketio = SocketIO(app, cors_allowed_origins="*")  # simple CORS allow

# In-memory storage (simple). For production use a DB or Redis.
MESSAGES = []   # list of dicts: {sender, receiver, text, timestamp}
PREVIEWS = {}   # map username -> preview text
SID_TO_USER = {}  # map socket sid -> username

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history/<username>', methods=['GET'])
def history(username):
    # return messages relevant to this user (either sent or received)
    user_msgs = [m for m in MESSAGES if m['sender'] == username or m['receiver'] == username]
    # sort by timestamp ascending
    user_msgs.sort(key=lambda x: x['timestamp'])
    return jsonify(user_msgs)

@app.route('/clearchat', methods=['GET'])
def clear_chat():
    MESSAGES.clear()   # सर्व messages delete
    PREVIEWS.clear()   # typing previews delete
    return jsonify({"status": "success", "message": "Chat history and previews cleared"})


# Socket handlers
@socketio.on('register')
def on_register(data):
    """
    data: { username: 'friend1' }
    """
    username = data.get('username')
    if not username:
        return
    SID_TO_USER[request.sid] = username
    join_room(username)
    # send current history and preview to the connected client
    user_msgs = [m for m in MESSAGES if m['sender'] == username or m['receiver'] == username]
    user_msgs.sort(key=lambda x: x['timestamp'])
    emit('history', user_msgs)
    # send preview of the other user (if exists)
    other = 'friend1' if username == 'friend2' else 'friend2'
    if PREVIEWS.get(other):
        emit('preview', {'from': other, 'text': PREVIEWS[other]})

@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    username = SID_TO_USER.pop(sid, None)
    if username:
        leave_room(username)

@socketio.on('send_message')
def on_send_message(data):
    """
    data: { sender, receiver, text }
    """
    sender = data.get('sender')
    receiver = data.get('receiver')
    text = data.get('text', '').strip()
    if not sender or not receiver or not text:
        return
    msg = {
        'sender': sender,
        'receiver': receiver,
        'text': text,
        'timestamp': int(time.time() * 1000)
    }
    MESSAGES.append(msg)
    # clear any preview of sender (they sent it)
    PREVIEWS.pop(sender, None)
    # emit to both sender and receiver rooms so all connected clients for those users get update
    emit('new_message', msg, to=sender)
    emit('new_message', msg, to=receiver)

@socketio.on('typing')
def on_typing(data):
    """
    data: { sender, receiver, text }  - text may be empty to indicate cleared preview
    """
    sender = data.get('sender')
    receiver = data.get('receiver')
    text = data.get('text', '')
    if not sender or not receiver:
        return
    if text.strip() == '':
        PREVIEWS.pop(sender, None)
    else:
        PREVIEWS[sender] = text
    # send preview to receiver only
    emit('preview', {'from': sender, 'text': text}, to=receiver)

if __name__ == '__main__':
    # Use eventlet for async websockets
    socketio.run(app, host='0.0.0.0', port=5000)
