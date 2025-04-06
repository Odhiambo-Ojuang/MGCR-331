from flask import Flask, render_template, request
import requests
import numpy as np

# Initialize Flask app
app = Flask(__name__)

# Define your API key and base URL
API_KEY = "tUcG7zCjGpYqRBlSmqkfVApI5j9JiObD"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# Function to fetch companies by sector
def get_companies_by_sector(sector, limit=10):
    url = f"{BASE_URL}/sector-performance?apikey={API_KEY}"
    response = requests.get(url)
    companies = response.json()

    sector_companies = []
    for company in companies:
        if company['sector'] == sector:
            sector_companies.append(company['symbol'])
        if len(sector_companies) >= limit:  # Optional limit to number of companies
            break
    return sector_companies

# Function to fetch balance sheet data for a company
def get_balance_sheet_data(symbol):
    url = f"{BASE_URL}/balance-sheet-statement/{symbol}?apikey={API_KEY}"
    response = requests.get(url)
    data = response.json()
    
    if len(data) == 0:
        return None
    
    return data[0]  # Return the most recent balance sheet data

# Function to calculate average balance sheet values
def calculate_average_balance_sheet(sector, limit=10):
    companies = get_companies_by_sector(sector, limit)
    
    total_current_assets = []
    total_non_current_assets = []
    total_assets = []
    total_current_liabilities = []
    total_non_current_liabilities = []
    total_liabilities = []
    total_equity = []
    
    for company in companies:
        balance_sheet = get_balance_sheet_data(company)
        
        if balance_sheet:
            total_current_assets.append(balance_sheet.get('totalCurrentAssets', 0))
            total_non_current_assets.append(balance_sheet.get('totalNonCurrentAssets', 0))
            total_assets.append(balance_sheet.get('totalAssets', 0))
            total_current_liabilities.append(balance_sheet.get('totalCurrentLiabilities', 0))
            total_non_current_liabilities.append(balance_sheet.get('totalNonCurrentLiabilities', 0))
            total_liabilities.append(balance_sheet.get('totalLiabilities', 0))
            total_equity.append(balance_sheet.get('totalEquity', 0))
    
    average_current_assets = np.mean(total_current_assets) if total_current_assets else 0
    average_non_current_assets = np.mean(total_non_current_assets) if total_non_current_assets else 0
    average_total_assets = np.mean(total_assets) if total_assets else 0
    average_current_liabilities = np.mean(total_current_liabilities) if total_current_liabilities else 0
    average_non_current_liabilities = np.mean(total_non_current_liabilities) if total_non_current_liabilities else 0
    average_total_liabilities = np.mean(total_liabilities) if total_liabilities else 0
    average_total_equity = np.mean(total_equity) if total_equity else 0

    return {
        "average_current_assets": average_current_assets,
        "average_non_current_assets": average_non_current_assets,
        "average_total_assets": average_total_assets,
        "average_current_liabilities": average_current_liabilities,
        "average_non_current_liabilities": average_non_current_liabilities,
        "average_total_liabilities": average_total_liabilities,
        "average_total_equity": average_total_equity
    }

# Route for handling the sector input form
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Route to process the form and show the calculated averages
@app.route('/calculate_averages', methods=['POST'])
def calculate_averages():
    sector = request.form['sector']
    
    averages = calculate_average_balance_sheet(sector)
    
    return render_template('averages.html', sector=sector, averages=averages)

if __name__ == '__main__':
    app.run(debug=True)
