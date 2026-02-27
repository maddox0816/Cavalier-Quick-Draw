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
import qrcode
from io import BytesIO
import sqlite3

db_connection = sqlite3.connect('users.db')
cursor = db_connection.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users(
               user_id INTEGER PRIMARY KEY,
               username TEXT NOT NULL,
               wins INTEGER,
               games_played INTEGER,
               UNIQUE (username) on conflict ABORT
               )""")
db_connection.commit()
cursor.close()
db_connection.close()

time_of_most_recent_movement = datetime.datetime.now()
allowed_to_shoot = False
connected_phones = 0
color_options = ["red", "blue", "green", "yellow", "purple", "orange"]
colors_used = []
winning_player = None

app = flask.Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

socketio = SocketIO(app)

@app.route("/qr-code", methods=['GET'])
def qr_code():
    url = request.args.get('url')
    if not url:
        return "URL parameter is required", 400
    img = qrcode.make(url)
    #send without needing to save to disk
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return flask.send_file(img_io, mimetype='image/png')



@app.route('/', methods=['GET','POST'])
def front_page():
    db_connection = sqlite3.connect('users.db')
    cursor = db_connection.cursor()
    if request.method=='POST':
        part1 = request.form['namepart1']
        part2 = request.form['chosenusername']
        NAME = f"{part1} {part2}"
        try:
            cursor.execute(f"""INSERT INTO users (username, wins, games_played) values ('{NAME}', 0, 0)""")
            db_connection.commit()
            print("user created")
            return flask.redirect(flask.url_for('phone', username=NAME))
        except sqlite3.IntegrityError:
            print('user already exists')
            return flask.redirect(flask.url_for('phone', username=NAME))
        finally:
            cursor.close()
            db_connection.close()
   
    return flask.render_template('login.html')

@app.route("/phone/<username>")
def phone(username):
    socketio.emit('phone_connected')
    #update global variable connected_phones
    global connected_phones
    connected_phones += 1
    socketio.emit('phone_status', {'slots': [True, True] if connected_phones >= 2 else [True, False]})
    color = random.choice([c for c in color_options if c not in colors_used])
    colors_used.append(color)
    return flask.render_template("phone.html", color=color, username=username)

@app.route("/phone-has-been-jerked-up", methods=['POST'])
def phone_has_been_jerked_up():
    payload = request.get_json()
    color = payload.get('color')
    username = payload.get('username')
    print("Phone has been jerked up by " + username)
    global time_of_most_recent_movement, allowed_to_shoot, winning_player
    if winning_player is not None:
        print("Game already won by " + winning_player)
        thing_to_return = jsonify({"winner": winning_player})
        thing_to_return.status_code = 200
        return thing_to_return
    if not allowed_to_shoot:
        print("Not allowed to shoot yet")
        return "Not allowed to shoot yet", 403
    if (datetime.datetime.now() - time_of_most_recent_movement).total_seconds() < 1:
        print("Too soon, ignoring movement")
        return "Too soon", 429
    socketio.emit('player_moved', {'player_name': f"Player {username}", 'movement': 'jerked up'})

    time_of_most_recent_movement = datetime.datetime.now()
    allowed_to_shoot = False
    winning_player = username
    print(f"winning player is: {winning_player}\nyour name is: {username}")
    if(username == winning_player):
        print(f"adding {username} win to database")
        db_connection = sqlite3.connect('users.db')
        cursor = db_connection.cursor()       
        win_results = cursor.execute(f"SELECT wins, games_played FROM users WHERE username='{winning_player}'")
        data_array = win_results.fetchone()
        winner_wins = data_array[0]
        winner_games = data_array[1]
        cursor.execute(f"UPDATE users SET wins={winner_wins+1}, games_played={winner_games+1} WHERE username='{winning_player}'")
        db_connection.commit()
        cursor.close()
        db_connection.close()
    else:
        print(f"adding {username} loss to database")
        db_connection = sqlite3.connect('users.db')
        cursor = db_connection.cursor()       
        win_results = cursor.execute(f"SELECT games_played FROM users WHERE username='{username}'")
        data_array = win_results.fetchone()
        loser_games = data_array[0]
        cursor.execute(f"UPDATE users SET games_played={loser_games+1} WHERE username='{username}'")
        db_connection.commit()
        cursor.close()
        db_connection.close()
    socketio.emit('game_over', {'winner': winning_player})
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
    socketio.emit('begin_shooting')
    allowed_to_shoot = True

@socketio.on('reset_game')
def handle_reset_game():
    global allowed_to_shoot, connected_phones, colors_used, winning_player
    colors_used = []
    connected_phones = 0
    winning_player = None
    allowed_to_shoot = False
    print("Game reset")
    socketio.emit('game_reset')
    


socketio.run(app, debug=True, host="0.0.0.0", port=5000)