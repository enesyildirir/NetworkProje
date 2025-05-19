import socket
import threading
import json

HOST = '192.168.1.103'
PORT = 5001

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"Server {HOST}:{PORT} adresinde dinliyor...")

players = {}              # {client_socket: "Player1" or "Player2"}
player_ships = {}         # {client_socket: [ships]}
ready_names = set()
current_turn = None

# --------------------------------------
# Yardımcı fonksiyonlar
# --------------------------------------
def coord_to_index(coord):
    col = ord(coord[0].upper()) - ord('A')
    row = int(coord[1:]) - 1
    return row, col

def send_message(client, message_dict):
    try:
        client.send(json.dumps(message_dict).encode())
    except:
        print("❌ Mesaj gönderilemedi.")

# --------------------------------------
# Client'i yöneten fonksiyon
# --------------------------------------
def handle_client(client_socket, addr):
    global current_turn

    print(f"🔌 Client bağlandı: {addr}")

    while True:
        try:
            data = client_socket.recv(2048).decode()
            if not data:
                print(f"📴 Bağlantı kesildi: {addr}")
                break

            message = json.loads(data)
            print(f"📨 {players.get(client_socket, addr)} gönderdi: {message}")

            if message["type"] == "join":
                name = message.get("name", f"Player{len(players)+1}")
                players[client_socket] = name
                print(f"👤 {name} bağlandı.")
                continue

            if message["type"] == "place":
                ships = []
                for ship in message["ships"]:
                    start_row, start_col = coord_to_index(ship["start"])
                    end_row, end_col = coord_to_index(ship["end"])
                    positions = []

                    if start_row == end_row:
                        for col in range(min(start_col, end_col), max(start_col, end_col)+1):
                            positions.append((start_row, col))
                    elif start_col == end_col:
                        for row in range(min(start_row, end_row), max(start_row, end_row)+1):
                            positions.append((row, start_col))

                    ships.append({
                        "positions": positions,
                        "hits": [],
                        "sunk": False
                    })

                player_ships[client_socket] = ships
                print(f"🚢 {players[client_socket]} gemilerini yerleştirdi.")

            if message["type"] == "ready":
                name = players[client_socket]
                ready_names.add(name)
                print(f"✅ {name} hazır oldu. Toplam hazır: {len(ready_names)}")

                print(f"🧪 ready_names içeriği: {ready_names}")

                if len(ready_names) == 2:
                    print("🎮 Her iki oyuncu hazır. Oyun başlatılıyor...")

                    # İsim sırasına göre oyuncuları sırala (Player1 → Player2)
                    player_list = sorted(players.items(), key=lambda x: x[1])  # [('socket', 'Player1'), ...]
                    player_sockets = [p[0] for p in player_list]

                    # Gameplay mesajını gönder
                    for c in player_sockets:
                        print(f"📤 start_gameplay gönderiliyor → {players[c]}")
                        send_message(c, {"type": "start_gameplay"})

                    # İlk oyuncuya sıra ver
                    current_turn = player_sockets[0]
                    send_message(current_turn, {"type": "turn", "message": "Sıra sende!"})

            
            if message["type"] == "move":
                player_list = sorted(players.items(), key=lambda x: x[1])
                player_sockets = [p[0] for p in player_list]

                if client_socket != current_turn:
                    error = {"type": "error", "message": "Sıra sende değil!"}
                    send_message(client_socket, error)
                    continue

                coord = message["coord"]
                target_row, target_col = coord_to_index(coord)
                opponent = player_sockets[0] if client_socket == player_sockets[1] else player_sockets[1]

                hit = False
                sunk = False
                sunk_ship = None

                for ship in player_ships[opponent]:
                    if (target_row, target_col) in ship["positions"]:
                        if (target_row, target_col) not in ship["hits"]:
                            ship["hits"].append((target_row, target_col))
                        hit = True
                        if set(ship["hits"]) == set(ship["positions"]):
                            ship["sunk"] = True
                            sunk = True
                            sunk_ship = ship
                        break

                if sunk:
                    response = {
                        "type": "result",
                        "status": "sink",
                        "coord": coord,
                        "sunk_coords": [chr(ord('A') + c) + str(r + 1) for (r, c) in sunk_ship["positions"]]
                    }
                else:
                    response = {
                        "type": "result",
                        "status": "hit" if hit else "miss",
                        "coord": coord
                    }

                send_message(client_socket, response)

                opponent_notify = {
                    "type": "opponent_move",
                    "coord": coord,
                    "status": "hit" if hit else "miss"
                }
                send_message(opponent, opponent_notify)

                all_sunk = all(ship["sunk"] for ship in player_ships[opponent])
                if all_sunk:
                    gameover = {"type": "gameover", "winner": players[client_socket]}
                    for c in player_sockets:
                        send_message(c, gameover)
                else:
                    current_turn = opponent
                    print(f"🔄 Sıra değişti → Şimdi sıra: {players[current_turn]}")
                    send_message(current_turn, {"type": "turn", "message": "Sıra sende!"})
        except Exception as e:
            print(f"❌ Hata: {e}")
            break

    client_socket.close()
    if client_socket in players:
        del players[client_socket]

while True:
    client_socket, addr = server_socket.accept()
    thread = threading.Thread(target=handle_client, args=(client_socket, addr))
    thread.start()
