from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from pymongo import MongoClient
import time, random, string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-a-secure-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Connect to MongoDB using the provided URI
client = MongoClient('mongodb+srv://vishalkarhad99:Vishal%401999@chatbox.ybx9vki.mongodb.net/?retryWrites=true&w=majority&appName=chatBox')

# Choose the database and collection
db = client['chat_app_db']
rooms_collection = db['rooms']  # Collection for storing rooms, messages, and previews

# In-memory (no longer needed as we're using MongoDB)
SID_TO_INFO = {}

@app.route('/')
def home_page():
    return render_template('home.html')

@app.route('/chat/<room_id>')
def chat_page(room_id):
    room = rooms_collection.find_one({'room_id': room_id})
    if not room:
        return "Room not found", 404
    return render_template('index.html', room_id=room_id)

@app.route('/check_room/<room_id>')
def check_room(room_id):
    room = rooms_collection.find_one({'room_id': room_id})
    return jsonify({"exists": bool(room)})

@app.route('/create_room', methods=['POST'])
def create_room():
    room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    # Create new room in MongoDB
    rooms_collection.insert_one({'room_id': room_id, 'messages': [], 'previews': {}})
    return jsonify({"room_id": room_id, "link": f"/chat/{room_id}"})

@app.route('/history/<room_id>/<username>')
def history(room_id, username):
    room = rooms_collection.find_one({'room_id': room_id})
    if not room:
        return jsonify([])  # No history found
    user_msgs = [m for m in room['messages'] if m['sender'] == username or m['receiver'] == username]
    user_msgs.sort(key=lambda x: x['timestamp'])
    return jsonify(user_msgs)

@app.route('/clearchat/<room_id>', methods=['GET'])
def clear_chat(room_id):
    rooms_collection.update_one({'room_id': room_id}, {'$set': {'messages': [], 'previews': {}}})
    return jsonify({"status": "success", "message": f"Chat cleared for room {room_id}"})

# SOCKET EVENTS
@socketio.on('register')
def on_register(data):
    username = data.get('username')
    room_id = data.get('room_id')
    if not username or not room_id:
        return
    SID_TO_INFO[request.sid] = {'username': username, 'room_id': room_id}
    join_room(f"{room_id}_{username}")
    join_room(room_id)

    room = rooms_collection.find_one({'room_id': room_id})
    if room:
        msgs = room.get('messages', [])
        user_msgs = [m for m in msgs if m['sender'] == username or m['receiver'] == username]
        user_msgs.sort(key=lambda x: x['timestamp'])
        emit('history', user_msgs)

        other_preview = None
        for user, text in room.get('previews', {}).items():
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

    # Update MongoDB with the new message
    rooms_collection.update_one(
        {'room_id': room_id},
        {'$push': {'messages': msg}},
        upsert=True
    )

    # Remove the sender's preview from MongoDB
    rooms_collection.update_one(
        {'room_id': room_id},
        {'$unset': {f'previews.{sender}': ""}},
    )

    emit('new_message', msg, to=room_id)

@socketio.on('typing')
def on_typing(data):
    sender = data.get('sender')
    receiver = data.get('receiver')
    text = data.get('text', '')
    room_id = data.get('room_id')
    if not sender or not receiver or not room_id:
        return

    # Update MongoDB with the typing preview
    if text.strip() == '':
        rooms_collection.update_one(
            {'room_id': room_id},
            {'$unset': {f'previews.{sender}': ""}},
        )
    else:
        rooms_collection.update_one(
            {'room_id': room_id},
            {'$set': {f'previews.{sender}': text}},
        )

    emit('preview', {'from': sender, 'text': text}, to=room_id)

if __name__ == "__main__":
    socketio.run(app, debug=True)
