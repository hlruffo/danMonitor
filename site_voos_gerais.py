from flask import Flask, render_template, request, redirect, jsonify
import json
import os
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from flask_socketio import SocketIO, emit
import threading
from flask import request
import pandas as pd

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True, async_mode="threading")

data_progress = {"progress": 0, "total": 0}  # Variável para controle da barra de progresso

# Caminhos dos arquivos
DATABASE_JSON = 'dados.json'

# Configuração do WebDriver
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
service = Service(ChromeDriverManager().install())

def load_data():
    if os.path.exists(DATABASE_JSON):
        with open(DATABASE_JSON, 'r') as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATABASE_JSON, 'w') as f:
        json.dump(data, f, indent=4)

def format_date(date_str):
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%Y-%m-%dT00:00:00.000Z")
    except ValueError:
        return None

def generate_url(departure_iata, arrival_iata, departure_date, return_date=None):
    departure_date_formatted = format_date(departure_date)
    return_date_formatted = format_date(return_date) if return_date else ""
    is_round_trip = "true" if return_date else "false"

    if not departure_iata or not arrival_iata or not departure_date_formatted:
        return None

    url = (
        f"https://www.comprarviagem.com.br/bizutrips/flight-list?"
        f"departureDate={departure_date_formatted}"
        f"{f'&returnDate={return_date_formatted}' if is_round_trip == 'true' else ''}"
        f"&isRoundTrip={is_round_trip}"
        f"&adultsCount=1&infantCount=0&childCount=0"
        f"&departureIata={departure_iata}"
        f"&arrivalIata={arrival_iata}"
        f"&isPackage=false"
        f"&departureName={departure_iata}%20Todos%20os%20aeroportos"
        f"&arrivalName={arrival_iata}%20Todos%20os%20aeroportos"
        f"&departureCity={departure_iata}"
        f"&arrivalCity={arrival_iata}"
        f"&departureCountry=false"
        f"&isDepartureIataCity=true"
        f"&isArrivalIataCity=true"
        f"&source=f"
    )
    return url

def fetch_price_from_url(url):
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "progress-bar-value"))
        )
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element((By.CLASS_NAME, "progress-bar-value"))
        )
        price_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span.price.app-black.font-weight-bold"))
        )
        price = price_element.text.strip()

        # Remove caracteres indesejados e converte para float
        price = float(price.replace('R$', '').replace('.', '').replace(',', '.'))
        driver.quit()
        return price
    except Exception as e:
        print(f"Erro ao buscar o preço: {e}")
        if 'driver' in locals():
            driver.quit()
        return "Erro"

def update_prices_background():
    global data_progress
    data = load_data()
    total = len(data)
    data_progress["total"] = total
    data_progress["progress"] = 0

    for i, entry in enumerate(data):
        if entry['URL_cliente']:
            entry['Preco'] = fetch_price_from_url(entry['URL_cliente'])
            save_data(data)
            data_progress["progress"] = i + 1

            print(f"Atualizando linha {i + 1} de {total}. Preço: {entry['Preco']}")

            # Emitir progresso atualizado para o frontend
            socketio.emit('update_price', {
                'index': i, 
                'Preco': entry['Preco'],
                'total': total, 
                'progress': i + 1
            })
            socketio.sleep(0.1)  # Garante que o cliente receba os dados

    # Emitir evento indicando que o processamento foi concluído
    socketio.emit('processing_done', {'message': 'Concluído'})
    print("Processamento concluído para todas as URLs.")

@app.route('/')
def index():
    data = load_data()
    return render_template('index.html', data=data, progress=data_progress)

@app.route('/add', methods=['POST'])
def add_entry():
    data = load_data()
    preco_desejado = request.form.get('preco_desejado')
    # Converta para float, se preenchido
    preco_desejado = float(preco_desejado) if preco_desejado else None
    new_entry = {
        "Cliente": request.form['cliente'],
        "Telefone": request.form['telefone'],
        "Origem": request.form['origem'],
        "Data_Ida": request.form['data_ida'],
        "Destino": request.form['destino'],
        "Data_Volta": request.form.get('data_volta', None),
        "Preco": "A processar",
        "Preco_Desejado": preco_desejado,
        "URL_cliente": generate_url(
            request.form['origem'],
            request.form['destino'],
            request.form['data_ida'],
            request.form.get('data_volta', None),
        ),
        "Link_Whatsapp": ""
    }
    data.append(new_entry)
    save_data(data)
    return redirect('/')


@app.route('/delete/<int:index>', methods=['POST'])
def delete_entry(index):
    data = load_data()
    if 0 <= index < len(data):
        data.pop(index)
        save_data(data)
    return redirect('/')

@app.route('/update_prices', methods=['POST'])
def update_prices():
    thread = threading.Thread(target=update_prices_background)
    thread.start()
    return "", 204

@app.route('/update_price/<int:index>', methods=['POST'])
def update_price(index):
    data = load_data()
    if 0 <= index < len(data):
        entry = data[index]
        if entry['URL_cliente']:
            entry['Preco'] = fetch_price_from_url(entry['URL_cliente'])
            save_data(data)
            return jsonify({"success": True, "Preco": entry['Preco']})
    return jsonify({"success": False, "error": "Índice inválido ou URL não encontrada."}), 400

# Atualização para permitir upload de "Preço Desejado" via Excel
@app.route('/upload', methods=['POST'])
def upload_excel():
    file = request.files['file']
    if not file:
        return "Nenhum arquivo enviado", 400

    try:
        df = pd.read_excel(file)
        required_columns = ["Cliente", "Telefone", "Origem", "Data_Ida", "Destino", "Data_Volta", "Preco_Desejado"]
        if not all(col in df.columns for col in required_columns):
            return "Colunas inválidas no arquivo. Inclua: " + ", ".join(required_columns), 400
        
        # Converte as colunas de data para string (se não forem nulas)
        df["Data_Ida"] = df["Data_Ida"].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isnull(x) else None)
        df["Data_Volta"] = df["Data_Volta"].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isnull(x) else None)

        data = load_data()
        for _, row in df.iterrows():
            new_entry = {
                "Cliente": row["Cliente"],
                "Telefone": row["Telefone"],
                "Origem": row["Origem"],
                "Data_Ida": row["Data_Ida"],
                "Destino": row["Destino"],
                "Data_Volta": row.get("Data_Volta", None),
                "Preco": "A processar",
                "Preco_Desejado": row.get("Preco_Desejado", None),
                "URL_cliente": generate_url(
                    row["Origem"], row["Destino"], row["Data_Ida"], row.get("Data_Volta", None)
                ),
                "Link_Whatsapp": ""
            }
            data.append(new_entry)
        save_data(data)
        return redirect('/')
    except Exception as e:
        return f"Erro ao processar o arquivo: {str(e)}", 500

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)