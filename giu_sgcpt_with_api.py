# by Giu
# https://github.com/o-giu
# WITH API KEY

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import requests
from bs4 import BeautifulSoup
import logging
import random
import time
from threading import Thread, Lock, Event
from queue import Queue
import re
from concurrent.futures import ThreadPoolExecutor

class SteamPriceTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Giu - Steam Game Card Price Tracker - v1.0 ~ NEED API KEY")
        self.root.geometry("1200x800")
        
        # Centralizar a janela na tela
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - 1200) // 2
        y = (screen_height - 800) // 2
        self.root.geometry(f"1200x800+{x}+{y}")

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='steam_price_tracker.log'
        )

        self.currencies = {
            'BRL (R$)': 'br', 'USD ($)': 'us', 'EUR (€)': 'eu',
            'GBP (£)': 'uk', 'ARS ($)': 'ar', 'CAD ($)': 'ca',
            'AUD ($)': 'au', 'RUB (₽)': 'ru', 'JPY (¥)': 'jp',
            'CNY (¥)': 'cn', 'TRY (₺)': 'tr', 'UAH (₴)': 'ua',
            'MXN ($)': 'mx', 'NZD ($)': 'nz', 'PLN (zł)': 'pl',
            'CHF (Fr)': 'ch', 'CLP ($)': 'cl', 'PEN (S/.)': 'pe',
            'COP ($)': 'co', 'ZAR (R)': 'za', 'HKD ($)': 'hk',
            'TWD (NT$)': 'tw', 'SAR (﷼)': 'sa', 'AED (د.إ)': 'ae',
            'SEK (kr)': 'se', 'NOK (kr)': 'no', 'KRW (₩)': 'kr',
            'SGD ($)': 'sg', 'THB (฿)': 'th', 'VND (₫)': 'vn',
            'IDR (Rp)': 'id', 'MYR (RM)': 'my', 'PHP (₱)': 'ph',
            'INR (₹)': 'in', 'ILS (₪)': 'il'
        }

        self.data = None
        self.queue = Queue()        
        self.stop_thread = False
        # Variável para controlar a direção da ordenação
        self.price_sort_reverse = False

        self.setup_session()
        self.build_ui()

        self.lock = Lock()
        self.max_workers = 5

        self.stop_event = Event()
        # Registra o método 'on_closing' no evento de fechamento
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_session(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def build_ui(self):
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(control_frame, text="Load CSV", command=self.load_csv).pack(side=tk.LEFT, padx=5)

        # Adicionar o checkbox "No Free Games"
        self.no_free_games_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="No Free Games", variable=self.no_free_games_var, command=self.filter_free_games).pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Currency:").pack(side=tk.LEFT, padx=5)
        self.currency_var = tk.StringVar(value='BRL (R$)')
        currency_menu = ttk.Combobox(control_frame, textvariable=self.currency_var, values=list(self.currencies.keys()), state="readonly")
        currency_menu.pack(side=tk.LEFT, padx=5)

        # Adicionar campo para SteamID
        ttk.Label(control_frame, text="SteamID:").pack(side=tk.LEFT, padx=5)
        self.steamid_entry = ttk.Entry(control_frame)
        self.steamid_entry.pack(side=tk.LEFT, padx=5)

        # Adicionar campo para API Key
        ttk.Label(control_frame, text="API Key:").pack(side=tk.LEFT, padx=5)
        self.apikey_entry = ttk.Entry(control_frame)
        self.apikey_entry.pack(side=tk.LEFT, padx=5)

        # Adicionar um campo de texto somente leitura para o link da API Key
        self.api_key_link_entry = tk.Entry(control_frame, foreground="blue", width=40)
        self.api_key_link_entry.insert(0, "https://steamcommunity.com/dev/apikey")  # Insere o link no campo
        self.api_key_link_entry.configure(state="readonly")  # Configura como readonly após inserir o texto
        self.api_key_link_entry.pack(side=tk.LEFT, padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.status_var = tk.StringVar(value="Status: Idle")
        ttk.Label(self.root, textvariable=self.status_var).pack(fill=tk.X, padx=10, pady=5)

        table_frame = ttk.Frame(self.root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Configuração da Treeview com ordenação
        self.tree = ttk.Treeview(table_frame, columns=("Game", "AppID", "Price", "Cards"), show="headings")
        self.tree.heading("Game", text="Game")
        self.tree.heading("AppID", text="AppID")
        self.tree.heading("Price", text="Price ▲▼", command=self.sort_by_price)
        self.tree.heading("Cards", text="Steam Trading Cards")

        self.tree.column("Game", width=300)
        self.tree.column("AppID", width=100)
        self.tree.column("Price", width=100)
        self.tree.column("Cards", width=150)

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)

    def filter_free_games(self):
        if self.no_free_games_var.get():
            # Filtra os jogos que não são gratuitos
            for item in self.tree.get_children():
                values = self.tree.item(item)["values"]
                price = values[2].lower()
                # Verifica se o preço contém "free" ou "free to play"
                if "free" in price:
                    self.tree.detach(item)
        else:
            # Mostra todos os jogos novamente
            for item in self.tree.get_children():
                self.tree.reattach(item, '', 'end')

    def get_owned_games(self, steam_id, api_key):
        url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={api_key}&steamid={steam_id}&format=json"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and 'games' in data['response']:
                    return [game['appid'] for game in data['response']['games']]
            logging.error(f"Failed to fetch owned games: {response.status_code}")
            return []
        except Exception as e:
            logging.error(f"Error fetching owned games: {e}")
            return []

    def extract_price_value(self, price_str):
        if not isinstance(price_str, str):
            return (float('inf'), False)
        
        price_str = price_str.strip().lower()
        
        # Retorna tupla (valor, é_preço_válido)
        if price_str == 'free':
            return (0.0, True)
            
        # Procura por valores numéricos no preço
        numbers = re.findall(r'[\d.,]+', price_str)
        if not numbers:
            return (float('inf'), False)
        
        try:
            # Limpa e converte o preço para float
            price = numbers[0].replace(',', '.')
            return (float(price), True)
        except ValueError:
            return (float('inf'), False)

    def sort_by_price(self):
        self.price_sort_reverse = not self.price_sort_reverse
        
        # Lista para preços válidos e inválidos
        valid_prices = []
        invalid_items = []
        
        # Dicionário para armazenar as informações sobre cartas (usando AppID como chave)
        cards_info = {}
        
        # Separa os itens em duas listas e armazena as informações sobre cartas
        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            price_value, is_valid_price = self.extract_price_value(values[2])
            
            # Armazena a informação sobre cartas usando o AppID como chave
            app_id = values[1]  # Assume que o AppID está na posição 1
            has_cards = "Steam Trading Cards" in values[3]  # Assume que a informação sobre cartas está na posição 3
            cards_info[app_id] = has_cards
            
            if is_valid_price:
                valid_prices.append((values, price_value))
            else:
                invalid_items.append(values)
        
        # Ordena apenas os preços válidos
        valid_prices.sort(key=lambda x: x[1], reverse=self.price_sort_reverse)
        
        # Limpa a árvore
        self.tree.delete(*self.tree.get_children())
        
        # Insere primeiro todos os preços válidos ordenados
        for values, _ in valid_prices:
            item = self.tree.insert('', tk.END, values=values)
            
            # Recupera a informação sobre cartas usando o AppID
            app_id = values[1]
            has_cards = cards_info.get(app_id, False)
            
            # Aplica a cor apenas à coluna de cartas
            if has_cards:
                self.tree.set(item, "Cards", "Steam Trading Cards")
                self.tree.tag_configure("cards_green", background="light green")
                self.tree.item(item, tags=("cards_green",))
            else:
                self.tree.set(item, "Cards", "No Cards Tag")
                self.tree.tag_configure("cards_coral", background="light coral")
                self.tree.item(item, tags=("cards_coral",))
                
        # Insere os itens inválidos no final
        for values in invalid_items:
            item = self.tree.insert('', tk.END, values=values)
            
            # Recupera a informação sobre cartas usando o AppID
            app_id = values[1]
            has_cards = cards_info.get(app_id, False)
            
            # Aplica a cor apenas à coluna de cartas
            if has_cards:
                self.tree.set(item, "Cards", "Steam Trading Cards")
                self.tree.tag_configure("cards_green", background="light green")
                self.tree.item(item, tags=("cards_green",))
            else:
                self.tree.set(item, "Cards", "No Cards Tag")
                self.tree.tag_configure("cards_coral", background="light coral")
                self.tree.item(item, tags=("cards_coral",))

    def load_csv(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            try:
                self.data = pd.read_csv(file_path)
                if {'Game', 'AppId'}.issubset(self.data.columns):
                    self.data = self.data[['Game', 'AppId']].dropna()
                    
                    # Obter o SteamID e a API Key dos campos de entrada
                    steam_id = self.steamid_entry.get()
                    api_key = self.apikey_entry.get()
                    
                    if not steam_id or not api_key:
                        messagebox.showerror("Error", "Please enter SteamID and API Key.")
                        return
                    
                    # Obter a lista de jogos que o usuário já possui
                    owned_games = self.get_owned_games(steam_id, api_key)
                    
                    if not owned_games:
                        messagebox.showerror("Error", "Could not fetch games. Check your SteamID and API Key.")
                        return
                    
                    # Filtrar os jogos que o usuário não possui
                    self.data = self.data[~self.data['AppId'].isin(owned_games)]
                    
                    self.populate_tree()
                    self.filter_free_games()  # Aplica o filtro ao carregar o CSV
                    self.start_fetching_prices()
                else:
                    messagebox.showerror("Error", "CSV must have 'Game' and 'AppId' columns.")
            except Exception as e:
                logging.error(f"Failed to load CSV: {e}")
                messagebox.showerror("Error", f"Could not load file: {e}")

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        for _, row in self.data.iterrows():
            self.tree.insert('', tk.END, values=(row['Game'], row['AppId'], 'Loading...', 'Loading...'))

    def fetch_price(self, app_id, currency):
        url = f"https://store.steampowered.com/app/{app_id}/"
        params = {'cc': currency, 'l': 'english'}
        
        try:
            time.sleep(random.uniform(0.5, 1))
            response = self.session.get(url, params=params, timeout=5)
            
            if 'agecheck' in response.url or 'mature_content' in response.text:
                self.session.cookies.update({
                    'birthtime': '786236401',
                    'mature_content': '1',
                    'wants_mature_content': '1',
                    'lastagecheckage': '1-January-1990'
                })
                response = self.session.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                cards_info = soup.find('div', class_='label', string='Steam Trading Cards')
                has_cards = cards_info is not None

                # Log para depuração
                logging.info(f"AppID {app_id}: Has Cards = {has_cards}")

                # Função para verificar se o container é um bundle ou pacote
                def is_bundle_or_pack(container):
                    # Verifica se há múltiplos jogos/DLCs listados
                    package_contents = container.find('div', class_='game_area_purchase_game_packages')
                    if package_contents:
                        return True

                    # Verifica se há uma lista de itens incluídos
                    included_items = container.find('div', class_='game_area_included_items')
                    if included_items:
                        return True

                    # Verifica por indicadores específicos de bundle
                    bundle_indicators = container.find_all(['div', 'p'], class_=['package_contents', 'package_contents_title'])
                    if bundle_indicators:
                        return True

                    # Verifica se há uma lista de DLCs
                    dlc_list = container.find('div', class_='game_area_dlc_list')
                    if dlc_list:
                        return True

                    return False

                # Função para verificar se o container é uma demo
                def is_demo(container):
                    # Verifica se é uma demo no título do container
                    title = container.find('h1')
                    if title and 'demo' in title.text.lower():
                        return True
                        
                    # Verifica se há menção explícita de demo na descrição
                    desc = container.find('div', class_='game_purchase_subtitle')
                    if desc and 'demo' in desc.text.lower():
                        return True
                        
                    return False

                # Função para extrair o preço de um container
                def extract_price_from_container(container):
                    # Procura pelo preço com desconto
                    price = container.find('div', class_='discount_final_price')
                    if price and price.text.strip():
                        return price.text.strip()
                    
                    # Se não houver desconto, procura pelo preço normal
                    price = container.find('div', class_='game_purchase_price price')
                    if price and price.text.strip():
                        text = price.text.strip()
                        if 'free' not in text.lower():
                            return text
                    
                    return None

                # Procura na área de compra principal
                purchase_area = soup.find('div', {'id': 'game_area_purchase'})
                if purchase_area:
                    purchase_containers = purchase_area.find_all('div', class_='game_area_purchase_game')
                    
                    # Primeiro, procura pelo container do jogo principal (não demo, não bundle)
                    for container in purchase_containers:
                        if not is_demo(container) and not is_bundle_or_pack(container):
                            price = extract_price_from_container(container)
                            if price:
                                logging.info(f"Fetched price for AppID {app_id}: {price}, Has Cards: {has_cards}")
                                return price, has_cards
                    
                    # Se não encontrou preço no jogo principal, procura em outros containers
                    for container in purchase_containers:
                        if not is_bundle_or_pack(container):  # Ignora apenas bundles
                            price = extract_price_from_container(container)
                            if price:
                                logging.info(f"Fetched price for AppID {app_id}: {price}, Has Cards: {has_cards}")
                                return price, has_cards
                
                # Verifica se é um jogo gratuito
                free_indicators = [
                    'free to play',
                    'play for free',
                    'download for free'
                ]
                
                game_area = soup.find('div', {'class': 'game_area_purchase'})
                if game_area:
                    game_text = game_area.text.lower()
                    if not any(indicator in game_text for indicator in free_indicators):
                        # Se não encontrou indicadores de free to play, retorna N/A
                        logging.info(f"Fetched price for AppID {app_id}: N/A, Has Cards: {has_cards}")
                        return 'N/A', has_cards
                    else:
                        # Só retorna Free se realmente encontrou indicadores de free to play
                        logging.info(f"Fetched price for AppID {app_id}: Free, Has Cards: {has_cards}")
                        return 'Free', has_cards
                
                # Se não encontrou preço, retorna N/A
                logging.info(f"Fetched price for AppID {app_id}: N/A, Has Cards: {has_cards}")
                return 'N/A', has_cards
            
            # Se a requisição falhou, retorna o código de erro
            logging.error(f"Failed to fetch price for AppID {app_id}: Status Code {response.status_code}")
            return f'Error: {response.status_code}', False
            
        except Exception as e:
            # Loga o erro e retorna uma mensagem de erro
            logging.error(f"Error fetching price for AppID {app_id}: {e}")
            return f'Error: {str(e)}', False

    def fetch_prices_background(self):
        currency_code = self.currencies.get(self.currency_var.get(), 'br')
        total_games = len(self.data)

        def process_game(args):
            index, row = args
            app_id = row['AppId']
            game = row['Game']
            if self.stop_event.is_set():  # Interrompe se o evento foi sinalizado
                return None
            price, has_cards = self.fetch_price(app_id, currency_code)
            return index, game, app_id, price, has_cards

        game_args = list(self.data.iterrows())

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for result in executor.map(process_game, game_args):
                if self.stop_event.is_set():  # Interrompe se o evento foi sinalizado
                    break
                if result:
                    self.queue.put(result)

    def start_fetching_prices(self):
        self.status_var.set("Fetching prices...")
        Thread(target=self.fetch_prices_background, daemon=True).start()
        self.process_queue()

    def process_queue(self):
        try:
            while not self.queue.empty():
                if self.stop_event.is_set():  # Interrompe se o evento foi sinalizado
                    return
                item = self.queue.get()
                if item is None:
                    self.status_var.set("Price fetching complete!")
                    self.sort_by_price()
                    self.filter_free_games()  # Aplica o filtro após a conclusão
                    return
                index, game, app_id, price, has_cards = item
                # Verifica se o filtro está ativo e se o preço é "Free"
                if self.no_free_games_var.get() and "free" in price.lower():
                    continue  # Ignora jogos gratuitos se o filtro estiver ativo
                
                # Define o texto e a cor de fundo para a coluna de cartas
                cards_text = "Steam Trading Cards" if has_cards else "No Cards Tag"
                bg_color = "light green" if has_cards else "light coral"
                
                # Insere os valores na tabela
                self.tree.item(self.tree.get_children()[index], values=(game, app_id, price, cards_text))
                
                # Aplica a cor de fundo apenas à coluna de cartas
                self.tree.tag_configure(bg_color, background=bg_color)
                self.tree.item(self.tree.get_children()[index], tags=(bg_color,))
                
                self.progress_var.set((index + 1) / len(self.data) * 100)
            self.root.after(100, self.process_queue)  # Agenda a próxima execução após 100ms
        except Exception as e:
            logging.error(f"Error processing queue: {e}")


    def on_closing(self):
        self.stop_event.set()  # Sinaliza para as threads pararem
        self.steamid_entry.delete(0, tk.END)  # Limpa o campo SteamID
        self.apikey_entry.delete(0, tk.END)   # Limpa o campo API Key
        self.root.destroy()    # Fecha a janela principal

if __name__ == "__main__":
    root = tk.Tk()
    app = SteamPriceTracker(root)
    root.mainloop()
