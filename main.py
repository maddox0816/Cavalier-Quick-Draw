"""
Maddox's super fancy quick draw game using mobile phones as controllers
Each player has a phone and it detects when it's jerked up

"""

import flask
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from flask import jsonify, request
import datetime
import time
import random

time_of_most_recent_movement = datetime.datetime.now()
allowed_to_shoot = False
connected_phones = 0
color_options = ["red", "blue", "green", "yellow", "purple", "orange"]
colors_used = []
winning_color = None

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

socketio = SocketIO(app)

@app.route("/")
def index():
    return flask.render_template("index.html")

@app.route("/phone")
def phone():
    socketio.emit('phone_connected')
    #update global variable connected_phones
    global connected_phones
    connected_phones += 1
    socketio.emit('phone_status', {'slots': [True, True] if connected_phones >= 2 else [True, False]})
    color = random.choice([c for c in color_options if c not in colors_used])
    colors_used.append(color)
    return flask.render_template("phone.html", color=color)

@app.route("/phone-has-been-jerked-up", methods=['POST'])
def phone_has_been_jerked_up():
    payload = request.get_json()
    color = payload.get('color')
    print("Phone has been jerked up by " + color)
    global time_of_most_recent_movement, allowed_to_shoot, winning_color
    if winning_color is not None:
        print("Game already won by " + winning_color)
        thing_to_return = jsonify({"winner": winning_color})
        thing_to_return.status_code = 200
        return thing_to_return
    if not allowed_to_shoot:
        print("Not allowed to shoot yet")
        return "Not allowed to shoot yet", 403
    if (datetime.datetime.now() - time_of_most_recent_movement).total_seconds() < 1:
        print("Too soon, ignoring movement")
        return "Too soon", 429
    socketio.emit('player_moved', {'player_name': f"Player {color}", 'movement': 'jerked up'})

    time_of_most_recent_movement = datetime.datetime.now()
    allowed_to_shoot = False
    winning_color = color
    socketio.emit('game_over', {'winner': winning_color})
    return "OK"

@app.route("/laptop")
def laptop():
    return flask.render_template("laptop.html")


@socketio.on('player_moved')
def handle_player_moved(data):
    print(f"Player moved: {data['player_name']} - {data['movement']}")
    socketio.emit('player_moved', {
        'player_name': data['player_name'],
        'movement': data['movement']
    })

@socketio.on('disconnect')
def handle_disconnect():
    print("Player disconnected")
    socketio.emit('player_left')

@socketio.on('laptop_connected')
def handle_laptop_connected():
    print("Laptop connected")
    socketio.emit('laptop_connected')

@socketio.on('begin_game')
def handle_begin_game():
    global allowed_to_shoot
    allowed_to_shoot = False
    #after at least two phones are connected
    #play go to paces then delay a random amount between 7 and 10 seconds
    print("Game started")
    socketio.emit('take_places')
    time.sleep(3)
    time_to_wait = 2 + (3 * random.random())
    print(f"Waiting for {time_to_wait} seconds")
    time.sleep(time_to_wait)
    socketio.emit('ready_aim')
    time.sleep(3)
    #sleep between 2 and 5 seconds before allowing to shoot
    time.sleep(2 + (3 * random.random()))
    socketio.emit('begin_shooting')
    allowed_to_shoot = True

@socketio.on('reset_game')
def handle_reset_game():
    global allowed_to_shoot, connected_phones, colors_used, winning_color
    colors_used = []
    connected_phones = 0
    winning_color = None
    allowed_to_shoot = False
    print("Game reset")
    socketio.emit('game_reset')
    


socketio.run(app, debug=True, host="0.0.0.0", port=5000)