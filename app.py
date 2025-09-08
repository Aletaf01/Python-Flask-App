from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
socketio = SocketIO(app)

# Rotta principale che mostra un form HTML
@app.route("/", methods=["GET"])
def index():
    return render_template_string("""
        <h2>Flask App with SocketIO and File Writing</h2>
        <form action="/write" method="post">
            <input type="text" name="content" placeholder="Write something..."/>
            <button type="submit">Save</button>
        </form>
        <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
        <script>
            var socket = io();
            socket.on('message', function(msg) {
                alert('Received a message: ' + msg);
            });
        </script>
    """)

# Rotta per scrivere su file
@app.route("/write", methods=["POST"])
def write_file():
    content = request.form.get("content", "")
    with open("data.txt", "a") as f:
        f.write(content + "\n")
    # Emit event to WebSocket clients
    socketio.emit("message", f"New content added: {content}")
    return f"Content saved: {content}"

# API REST per aggiungere contenuti via JSON
@app.route("/api/write", methods=["POST"])
def api_write():
    data = request.json
    text = data.get("text", "")
    with open("data.txt", "a") as f:
        f.write(text + "\n")
    socketio.emit("message", f"API content added: {text}")
    return jsonify({"status": "ok", "text": text})

# Semplice evento WebSocket
@socketio.on("connect")
def handle_connect():
    emit("message", "You are connected to the WebSocket.")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
