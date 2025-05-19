import pygame
import sys
import socket
import json
import threading
import time
import select
import traceback
import ctypes
from pygame.locals import *

# ------------------------------
# Ana Değişkenler
# ------------------------------
my_name = "Player1"  # client2.py'de bu değeri "Player2" olarak değiştirin
current_screen = "start"
game_winner = None

running = True
start_clicked = False
start_button_rect = None
start_gameplay_flag = False
gameover_flag = False

your_turn = False
enemy_moves = []          # Rakipten gelen vuruşlar
your_moves = {}           # Senin yaptığın hamleler ve sonucu: {"B3": "hit"}

pygame.init()
# ------------------------------
# Socket Ayarları
# ------------------------------
HOST = '192.168.1.103'
PORT = 5001

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))

client_socket.settimeout(0.5)  # Timeout süresi 0.5 saniye

def listen_server():
    global start_gameplay_flag, your_turn, your_moves, enemy_moves, current_screen
    print("🔊 Dinleyici başlatıldı")

    while True:
        try:
            # Veri geldi mi diye 100ms bekle
            ready_to_read, _, _ = select.select([client_socket], [], [], 0.1)
            if ready_to_read:
                data = client_socket.recv(2048).decode()
                if not data:
                    continue

                for message in parse_multiple_json_objects(data):
                    try:
                        print("📩 Server mesajı:", message)

                        if message["type"] == "start_gameplay":
                            print("🟢 start_gameplay mesajı alındı.")
                            start_gameplay_flag = True

                        elif message["type"] == "turn":
                            print("🎯 Sıra sende")
                            your_turn = True

                        elif message["type"] == "result":
                            status = message["status"]
                            coord = message["coord"]
            
                            if status == "sink":
                                coords = message.get("sunk_coords", [coord])
                                for c in coords:
                                    your_moves[c] = "sink"
                            else:
                                your_moves[coord] = status

                            your_turn = False

                        elif message["type"] == "opponent_move":
                            coord = message["coord"]
                            status = message["status"]
                            enemy_moves.append((coord, status))

                            # 🔊 Miss sesini burada çal
                            if status == "miss":
                                miss_sound.play()
                            elif status == "hit":
                                hit_sound.play()
                            elif status == "sink":
                                hit_sound.play()

                        elif message["type"] == "gameover":
                            winner = message.get("winner")
                            print(f"🏁 Oyun bitti! Kazanan: {winner}")
                            #gameover_flag = True
                            game_winner = winner  # Kazananı kaydet
                            current_screen = "gameover"  # Ekranı değiştir
                            # Ses efekti / animasyon istersen burada tetikleyebilirsin

                    except Exception as e:
                        print("❌ Mesaj işlenemedi:", message)
                        traceback.print_exc()


        except Exception as e:
            print("❌ Dinleme hatası:", e)
            traceback.print_exc()


join_message = {"type": "join", "name": my_name}
client_socket.send(json.dumps(join_message).encode())
print("🔗 Join mesajı gönderildi:", join_message)


listen_thread = threading.Thread(target=listen_server, daemon=True)
listen_thread.start()

# 🔥 listen_server thread'ini en son başlat:
print("Server'a bağlanıldı!")

# ------------------------------
# Ekran Ayarları - TAM EKRAN
# ------------------------------
# Ekran boyutunu al ve taskbar için alan bırak
user32 = ctypes.windll.user32
SCREEN_WIDTH = user32.GetSystemMetrics(0)
SCREEN_HEIGHT = user32.GetSystemMetrics(1) - 40  # Taskbar için 40px boşluk bırak

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Amiral Battı")
clock = pygame.time.Clock()

# ------------------------------
# Sabitler ve Renkler
# ------------------------------
GRID_SIZE = 10
CELL_SIZE = min(SCREEN_HEIGHT // 15, SCREEN_WIDTH // 25)  # Duyarlı boyutlandırma
GRID_WIDTH = GRID_SIZE * CELL_SIZE

# Ekran boyutuna göre pozisyonlar hesapla
PLAYER_GRID_POS = (SCREEN_WIDTH - GRID_WIDTH - int(SCREEN_WIDTH * 0.15), int(SCREEN_HEIGHT * 0.15))
SHIP_PANEL_POS = (int(SCREEN_WIDTH * 0.1), int(SCREEN_HEIGHT * 0.15))

BG_COLOR = (30, 30, 30)
GRID_COLOR = (0, 128, 255)
SHIP_COLOR = (0, 200, 0)
SELECTED_SHIP_COLOR = (200, 0, 0)

BIG_CELL_SIZE = CELL_SIZE
SMALL_CELL_SIZE = CELL_SIZE // 2

BIG_GRID_POS = (SCREEN_WIDTH // 2, int(SCREEN_HEIGHT * 0.15))    # Rakip grid'i
SMALL_GRID_POS = (int(SCREEN_WIDTH * 0.1), int(SCREEN_HEIGHT * 0.15))    # Kendi küçük grid'in

# ------------------------------
# Gemi Görselleri Yükleme
# ------------------------------
# Gemilerin görsellerini yükle
ship_images = {
    2: pygame.image.load("C:\\Users\\asus\\OneDrive\\Masaüstü\\proje\\ship2.png").convert_alpha(),
    3: pygame.image.load("C:\\Users\\asus\\OneDrive\\Masaüstü\\proje\\ship3.png").convert_alpha(),
    4: pygame.image.load("C:\\Users\\asus\\OneDrive\\Masaüstü\\proje\\ship4.png").convert_alpha(),
    5: pygame.image.load("C:\\Users\\asus\\OneDrive\\Masaüstü\\proje\\ship5.png").convert_alpha()
}

# ------------------------------
# Yardımcı Fonksiyonlar
# ------------------------------
def get_occupied_cells(ship):
    gx, gy = PLAYER_GRID_POS
    start_col = (ship.x - gx) // CELL_SIZE
    start_row = (ship.y - gy) // CELL_SIZE
    return [(start_row + i, start_col) if ship.orientation == 'vertical' 
            else (start_row, start_col + i) for i in range(ship.size)]

def is_overlapping(new_ship, all_ships):
    new_cells = set(get_occupied_cells(new_ship))
    for other in all_ships:
        if other != new_ship and new_cells & set(get_occupied_cells(other)):
            return True
    return False

def is_out_of_bounds(ship):
    gx, gy = PLAYER_GRID_POS
    start_col = (ship.x - gx) // CELL_SIZE
    start_row = (ship.y - gy) // CELL_SIZE
    return (ship.orientation == 'horizontal' and start_col + ship.size > GRID_SIZE) or \
           (ship.orientation == 'vertical' and start_row + ship.size > GRID_SIZE)

def get_ship_at_pos(pos):
    for ship in ships:
        if ship.get_rect().collidepoint(pos):
            return ship
    return None

def draw_grid(start_x, start_y, cell_size=CELL_SIZE):
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            rect = pygame.Rect(start_x + col * cell_size, start_y + row * cell_size, cell_size, cell_size)
            pygame.draw.rect(screen, GRID_COLOR, rect, 2)

def draw_ships():
    for ship in ships:
        ship.draw(screen)

def is_ship_on_grid(ship):
    gx, gy = PLAYER_GRID_POS
    return gx <= ship.x < gx + GRID_WIDTH and gy <= ship.y < gy + GRID_WIDTH

def is_all_ships_placed():
    return all(is_ship_on_grid(ship) for ship in ships)

def index_to_coord(row, col):
    return chr(ord('A') + col) + str(row + 1)

def draw_start_button():
    """Başla butonunu çizer ve dikdörtgenini geri döner"""
    button_width, button_height = 200, 60
    button_x = (SCREEN_WIDTH - button_width) // 2
    button_y = SCREEN_HEIGHT - 120  # Taskbar'a çarpmayacak şekilde yukarı çekildi
    rect = pygame.Rect(button_x, button_y, button_width, button_height)
    pygame.draw.rect(screen, (0, 180, 0), rect)
    pygame.draw.rect(screen, (255, 255, 255), rect, 3)
    font = pygame.font.SysFont(None, 40)
    text = font.render("BAŞLA", True, (255, 255, 255))
    text_rect = text.get_rect(center=rect.center)
    screen.blit(text, text_rect)
    return rect

def draw_own_ships_on_small_grid():
    for ship in ships:
        cells = get_occupied_cells(ship)
        for row, col in cells:
            rect = pygame.Rect(SMALL_GRID_POS[0] + col * SMALL_CELL_SIZE,
                               SMALL_GRID_POS[1] + row * SMALL_CELL_SIZE,
                               SMALL_CELL_SIZE, SMALL_CELL_SIZE)
            pygame.draw.rect(screen, SHIP_COLOR, rect)

pygame.mixer.init()
miss_sound = pygame.mixer.Sound('miss.wav')
hit_sound = pygame.mixer.Sound('hit.wav')

#play sound tanımladım
def draw_move_result(coord, status, is_enemy=False,play_sound=False):
    row = int(coord[1:]) - 1
    col = ord(coord[0]) - ord('A')

    if is_enemy:
        x = SMALL_GRID_POS[0] + col * SMALL_CELL_SIZE
        y = SMALL_GRID_POS[1] + row * SMALL_CELL_SIZE
        size = SMALL_CELL_SIZE
    else:
        x = BIG_GRID_POS[0] + col * BIG_CELL_SIZE
        y = BIG_GRID_POS[1] + row * BIG_CELL_SIZE
        size = BIG_CELL_SIZE

    center = (x + size // 2, y + size // 2)

    if status == "miss":
        pygame.draw.circle(screen, (255, 255, 255), center, size // 6)
        if play_sound:
            miss_sound.play()

    elif status == "hit":
        if play_sound:
            hit_sound.play()
        inner = pygame.Rect(x, y, size, size).inflate(-size // 3, -size // 3)
        pygame.draw.rect(screen, (220, 20, 60), inner)

    elif status == "sink":
        if play_sound:
            hit_sound.play()
        pygame.draw.line(screen, (255, 255, 255), (x, y), (x + size, y + size), 3)
        pygame.draw.line(screen, (255, 255, 255), (x + size, y), (x, y + size), 3)

def parse_multiple_json_objects(data):
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(data):
        try:
            obj, offset = decoder.raw_decode(data[pos:])
            yield obj
            pos += offset
        except json.JSONDecodeError as e:
            print("🔴 JSON parse hatası:", e)
            break

##                                         ##
def reset_ships():
    global ships, start_clicked, start_gameplay_flag, your_turn, your_moves, enemy_moves
    ships = [Ship(size, x, y) for size, (x, y) in zip(ship_sizes, ship_positions)]
    start_clicked = False
    start_gameplay_flag = False
    your_turn = False
    your_moves = {}
    enemy_moves = []
##


# ------------------------------
# Gemi Sınıfı
# ------------------------------
class Ship:
    def __init__(self, size, x, y):
        self.size = size
        self.x = x
        self.y = y
        self.orientation = 'horizontal'
        self.selected = False
        self.image = ship_images[size]
        self.original_image = self.image  # Orijinal resmi sakla (döndürme için)

    def get_rect(self):
        width = self.size * CELL_SIZE if self.orientation == 'horizontal' else CELL_SIZE
        height = CELL_SIZE if self.orientation == 'horizontal' else self.size * CELL_SIZE
        return pygame.Rect(self.x, self.y, width, height)

    def draw(self, surface):
        # Gemi seçiliyse kırmızı bir kenar çizmek için
        if self.selected:
            # Gemi seçiliyse bir dikdörtgen çizilir (kırmızı kenar)
            pygame.draw.rect(surface, SELECTED_SHIP_COLOR, self.get_rect(), 3)
        
        # Yönlendirmeye göre resmi döndür
        if self.orientation == 'vertical':
            # Eğer dikey yönlenmişse, resmi 90 derece döndür
            rotated_image = pygame.transform.rotate(self.original_image, 90)
        else:
            # Yataysa orijinal resmi kullan
            rotated_image = self.original_image
        
        # Resmin boyutlarını geminin hücrelerine göre ayarla
        rect = self.get_rect()
        scaled_image = pygame.transform.scale(rotated_image, (rect.width, rect.height))
        
        # Resmi çiz
        surface.blit(scaled_image, rect)

# ------------------------------
# Gemi Başlangıç Konumları - DÜZENLENDI
# ------------------------------
ship_sizes = [2, 3, 4, 5]

# Gemileri sol panelde düzenli bir şekilde konumlandır
ship_positions = []
base_x = int(SCREEN_WIDTH * 0.05)  # Sol kenardan %5 içeride
ship_spacing = int(SCREEN_HEIGHT * 0.15)  # Ekran yüksekliğinin %15'i kadar aralık

for i, size in enumerate(ship_sizes):
    y_pos = int(SCREEN_HEIGHT * 0.2) + i * ship_spacing  # Ekranın %20'sinden başlayarak aşağı doğru
    ship_positions.append((base_x, y_pos))

ships = [Ship(size, x, y) for size, (x, y) in zip(ship_sizes, ship_positions)]

# ------------------------------
# Ana Döngü
# ------------------------------

def handle_start_screen():
    # Resim dosyası yüklendi
    background_img = pygame.image.load("C:\\Users\\asus\\OneDrive\\Masaüstü\\proje\\sea_background.jpg").convert()

    # Müzik dosyasını yükleyip çal
    pygame.mixer.music.load("start.mp3")
    pygame.mixer.music.play(-1)  # -1: Döngüde çalar

    blink = True
    blink_timer = 0
    blink_interval = 500

    while True:
        screen.blit(pygame.transform.scale(background_img, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0))
        current_time = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.mixer.music.stop()  # Çıkışta müziği durdur
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                pygame.mixer.music.stop()  # Oyuna geçerken müziği durdur
                return "placement"

        # Başlık metni
        font_title = pygame.font.SysFont("comicsansms", 60, bold=True)
        title_text = font_title.render("🛳️ AMİRAL BATTI 🛳️", True, (255, 255, 255))
        screen.blit(title_text, title_text.get_rect(center=(SCREEN_WIDTH // 2, 80)))

        # Yanıp sönen "Başlamak için" yazısı
        font_info = pygame.font.SysFont("comicsansms", 28, bold=True)
        if current_time - blink_timer > blink_interval:
            blink = not blink
            blink_timer = current_time

        if blink:
            start_text = font_info.render("▶ Başlamak için tıklayın veya bir tuşa basın ◀", True, (255, 255, 255))
            screen.blit(start_text, start_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 100)))

        # Alt bilgi
        footer_font = pygame.font.SysFont("arial", 20)
        footer_text = footer_font.render("Esc ile çıkabilirsiniz.", True, (255, 255, 255))
        screen.blit(footer_text, footer_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 40)))

        pygame.display.flip()
        clock.tick(60)

def handle_placement_screen():
    global start_clicked
    global start_button_rect

    screen.fill((0, 0, 20))
    
    # Başlık metni ekle
    font_title = pygame.font.SysFont("comicsansms", 48, bold=True)
    title_text = font_title.render("Gemilerini Yerleştir", True, (255, 255, 255))
    screen.blit(title_text, title_text.get_rect(center=(SCREEN_WIDTH // 2, 40)))
    
    # Yardım metni
    font_help = pygame.font.SysFont("arial", 20)
    help_text1 = font_help.render("1. Gemileri seçip oyun tahtasına sürükleyin", True, (200, 200, 200))
    help_text2 = font_help.render("2. Gemi yönünü değiştirmek için 'R' tuşuna basın", True, (200, 200, 200))
    screen.blit(help_text1, (int(SCREEN_WIDTH * 0.05), int(SCREEN_HEIGHT * 0.1)))
    screen.blit(help_text2, (int(SCREEN_WIDTH * 0.05), int(SCREEN_HEIGHT * 0.1) + 30))

    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            pygame.quit()
            sys.exit()

        # Gemi yön değiştirme
        if not start_clicked and event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            for ship in ships:
                if ship.selected:
                    original_orientation = ship.orientation
                    ship.orientation = 'vertical' if ship.orientation == 'horizontal' else 'horizontal'
                    if is_out_of_bounds(ship) or is_overlapping(ship, ships):
                        ship.orientation = original_orientation

        # Mouse ile seçim ve yerleştirme
        if event.type == pygame.MOUSEBUTTONDOWN:
            if start_clicked:
                continue

            x, y = event.pos
            if start_button_rect and start_button_rect.collidepoint((x, y)):
                start_clicked = True

                # Gemi pozisyonlarını server'a gönder
                ships_data = []
                for ship in ships:
                    cells = get_occupied_cells(ship)
                    start = index_to_coord(*cells[0])
                    end = index_to_coord(*cells[-1])
                    ships_data.append({"start": start, "end": end})

                place_message = {"type": "place","ships": ships_data}
                client_socket.send(json.dumps(place_message).encode())
                print("Gemiler gönderildi:", place_message)

                ready_message = {"type": "ready"}
                client_socket.send(json.dumps(ready_message).encode())
                print("Hazır mesajı gönderildi.")

                return "waiting"

            clicked_ship = get_ship_at_pos((x, y))
            if clicked_ship:
                for ship in ships:
                    ship.selected = False
                clicked_ship.selected = True
            else:
                gx, gy = PLAYER_GRID_POS
                if gx <= x < gx + GRID_WIDTH and gy <= y < gy + GRID_WIDTH:
                    col = (x - gx) // CELL_SIZE
                    row = (y - gy) // CELL_SIZE
                    for ship in ships:
                        if ship.selected:
                            old_x, old_y = ship.x, ship.y
                            ship.x = gx + col * CELL_SIZE
                            ship.y = gy + row * CELL_SIZE
                            if is_out_of_bounds(ship) or is_overlapping(ship, ships):
                                ship.x, ship.y = old_x, old_y
                            else:
                                ship.selected = False
                            break

    # Gemi yerleştirme gridini çiz
    draw_grid(*PLAYER_GRID_POS)
    
    # Tahtada mevcut gemileri çiz
    draw_ships()

    # "Hazırsan" bilgisi
    if is_all_ships_placed():
        font_ready = pygame.font.SysFont("arial", 24)
        ready_text = font_ready.render("Tüm gemiler hazır!", True, (0, 255, 0))
        screen.blit(ready_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT - 180))

    # Başla butonunu göster
    if is_all_ships_placed() and not start_clicked:
        start_button_rect = draw_start_button()

    pygame.display.flip()
    clock.tick(60)

    return "placement"

def handle_waiting_screen():
    global start_gameplay_flag
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            pygame.quit()
            sys.exit()

    if start_gameplay_flag:
        print("✅ waiting → gameplay geçişi")
        return "gameplay"

    screen.fill((0, 0, 20))
    
    # "Bekleniyor" yazısı
    font = pygame.font.SysFont("comicsansms", 50)
    text = font.render("Rakip oyuncu bekleniyor...", True, (200, 200, 200))
    screen.blit(text, (SCREEN_WIDTH // 2 - 250, SCREEN_HEIGHT // 2 - 50))
    
    # Dönen animasyon
    current_time = pygame.time.get_ticks()
    angle = (current_time // 10) % 360
    radius = 30
    cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50
    dx = int(radius * pygame.math.Vector2(1, 0).rotate(angle).x)
    dy = int(radius * pygame.math.Vector2(1, 0).rotate(angle).y)
    pygame.draw.circle(screen, (0, 128, 255), (cx + dx, cy + dy), 10)
    
    pygame.display.flip()
    clock.tick(60)

    return "waiting"

def handle_gameplay_screen():
    global your_turn, current_screen

    if current_screen != "gameplay":
        return current_screen  # Oyun bitti mesajı gelirse hemen ekranı değiştir

    if your_turn:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()

            # Hamle yapma: rakip gridine tıklandıysa ve sıra sende ise
            if event.type == pygame.MOUSEBUTTONDOWN and your_turn:
                x, y = event.pos
                gx, gy = BIG_GRID_POS
                if gx <= x < gx + BIG_CELL_SIZE * GRID_SIZE and gy <= y < gy + BIG_CELL_SIZE * GRID_SIZE:
                    col = (x - gx) // BIG_CELL_SIZE
                    row = (y - gy) // BIG_CELL_SIZE
                    coord = chr(ord('A') + col) + str(row + 1)

                    if coord not in your_moves:
                        move_msg = {"type": "move", "coord": coord}
                        client_socket.send(json.dumps(move_msg).encode())
                        print("📤 Hamle gönderildi:", coord)
                        your_turn = False
                    else:
                        print("❌ Bu hücreye zaten hamle yaptın:", coord)

    else:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()

    # Arka plan
    screen.fill((0, 0, 20))
    
    # Başlık
    font_title = pygame.font.SysFont("comicsansms", 36, bold=True)
    title_text = font_title.render("🛳️ AMİRAL BATTI - OYUN SAHASI 🛳️", True, (255, 255, 255))
    screen.blit(title_text, title_text.get_rect(center=(SCREEN_WIDTH // 2, 40)))

    # Sağda büyük rakip grid
    font_opponent = pygame.font.SysFont("arial", 24)
    opponent_text = font_opponent.render("Rakip Tahtası", True, (200, 200, 200))
    screen.blit(opponent_text, (BIG_GRID_POS[0] + GRID_WIDTH//2 - 80, BIG_GRID_POS[1] - 40))
    draw_grid(*BIG_GRID_POS, BIG_CELL_SIZE)

    # Solda küçük kendi gridin
    font_your = pygame.font.SysFont("arial", 24)
    your_text = font_your.render("Senin Tahtan", True, (200, 200, 200))
    screen.blit(your_text, (SMALL_GRID_POS[0] + (GRID_SIZE * SMALL_CELL_SIZE)//2 - 80, SMALL_GRID_POS[1] - 40))
    draw_grid(*SMALL_GRID_POS, SMALL_CELL_SIZE)
    draw_own_ships_on_small_grid()

    # Durum bilgisi
    status_font = pygame.font.SysFont("comicsansms", 30, bold=True)
    if your_turn:
        status_text = status_font.render("✓ SIRA SENDE! Rakip tahtasına tıkla", True, (0, 255, 0))
    else:
        status_text = status_font.render("⏳ Rakibin hamlesi bekleniyor...", True, (255, 165, 0))
    screen.blit(status_text, status_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120)))

    # Senin rakibe yaptığın hamleleri çiz
    for coord, status in your_moves.items():
        draw_move_result(coord, status, is_enemy=False)
        
    # Rakibin sana yaptığı hamleleri çiz
    for coord, status in enemy_moves:
        draw_move_result(coord, status, is_enemy=True)

    pygame.display.flip()
    clock.tick(60)
    return "gameplay"

def handle_gameover_screen(winner):
    print("Oyun Sonu Ekranı Açıldı")

    font_large = pygame.font.SysFont("comicsansms", 72, bold=True)
    font_small = pygame.font.SysFont("arial", 36)

    # Zafer müziği çal
    if winner == my_name:
        try:
            pygame.mixer.music.load("win.mp3")
            pygame.mixer.music.play()
        except:
            pass  # Dosya yoksa sessizce devam et

    # 🔥 Butonları en başta tanımla
    play_again_rect = pygame.Rect(screen.get_width() // 2 - 150, SCREEN_HEIGHT // 2 + 50, 300, 80)
    exit_rect = pygame.Rect(screen.get_width() // 2 - 150, SCREEN_HEIGHT // 2 + 150, 300, 80)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if play_again_rect.collidepoint(event.pos):
                    print("🔄 Tekrar Oyna seçildi.")
                    return "start"
                elif exit_rect.collidepoint(event.pos):
                    pygame.quit()
                    sys.exit()

        # Arka plan efekti
        screen.fill((10, 10, 50))
        
        # Parlayan efekt
        current_time = pygame.time.get_ticks()
        glow_value = 100 + int(50 * abs(pygame.math.Vector2(1, 0).rotate(current_time // 15 % 360).x))
        
        # Kazanan yazısı
        if winner == my_name:
            result_color = (255, 215, 0)  # Altın rengi
            text = "KAZANDIN!"
        else:
            result_color = (200, 200, 200)
            text = f"{winner} Kazandı!"
            
        text_surface = font_large.render(text, True, result_color)
        text_rect = text_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
        
        # Işık efekti
        glow_color = (min(result_color[0], glow_value), 
                      min(result_color[1], glow_value), 
                      min(result_color[2], glow_value))
        glow_text = font_large.render(text, True, glow_color)
        glow_rect = glow_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
        
        screen.blit(glow_text, glow_rect)
        screen.blit(text_surface, text_rect)

        # Tekrar Oyna butonu
        pygame.draw.rect(screen, (0, 180, 0), play_again_rect, border_radius=15)
        pygame.draw.rect(screen, (255, 255, 255), play_again_rect, 3, border_radius=15)
        play_again_text = font_small.render("Tekrar Oyna", True, (255, 255, 255))
        play_again_text_rect = play_again_text.get_rect(center=play_again_rect.center)
        screen.blit(play_again_text, play_again_text_rect)

        # Çıkış butonu
        pygame.draw.rect(screen, (180, 0, 0), exit_rect, border_radius=15)
        pygame.draw.rect(screen, (255, 255, 255), exit_rect, 3, border_radius=15)
        exit_text = font_small.render("Çıkış", True, (255, 255, 255))
        exit_text_rect = exit_text.get_rect(center=exit_rect.center)
        screen.blit(exit_text, exit_text_rect)

        pygame.display.flip()
        clock.tick(60)

                        
# Ana oyun döngüsü
while running:
    if current_screen == "start":
        # Reset oyuna dönerken
        your_moves.clear()
        enemy_moves.clear()
        your_turn = False
        start_gameplay_flag = False
        reset_ships()
        current_screen = handle_start_screen()
    elif current_screen == "placement":
        current_screen = handle_placement_screen()
    elif current_screen == "waiting":
        current_screen = handle_waiting_screen()
    elif current_screen == "gameplay":
        result = handle_gameplay_screen()
        if result != "gameplay":
            current_screen = result
    elif current_screen == "gameover":
        current_screen = handle_gameover_screen(game_winner)


pygame.quit()
sys.exit()