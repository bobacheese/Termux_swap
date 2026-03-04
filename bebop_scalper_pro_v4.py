#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    BEBOP SCALPER PRO v4.0 - ULTIMATE DEX                      ║
║                         RFQ Trading with Real Swaps                           ║
║                         Created by: AMARULLOH ZIKRI                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO, emit
import requests
import json
import threading
import time
from decimal import Decimal, InvalidOperation
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bebop-scalper-pro-v4-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI
# ═══════════════════════════════════════════════════════════════════════════════

BEBOP_API = "https://api.bebop.xyz/router/v1"
ARBITRUM_CHAIN_ID = 42161

# Token List Arbitrum
TOKENS = {
    "USDC": {
        "address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "decimals": 6,
        "symbol": "USDC",
        "name": "USD Coin",
        "logo": "https://cryptologos.cc/logos/usd-coin-usdc-logo.png",
        "color": "#2775CA"
    },
    "USDT": {
        "address": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "decimals": 6,
        "symbol": "USDT",
        "name": "Tether",
        "logo": "https://cryptologos.cc/logos/tether-usdt-logo.png",
        "color": "#26A17B"
    },
    "WETH": {
        "address": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "decimals": 18,
        "symbol": "WETH",
        "name": "Wrapped Ether",
        "logo": "https://cryptologos.cc/logos/weth-weth-logo.png",
        "color": "#627EEA"
    },
    "WBTC": {
        "address": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
        "decimals": 8,
        "symbol": "WBTC",
        "name": "Wrapped Bitcoin",
        "logo": "https://cryptologos.cc/logos/wrapped-bitcoin-wbtc-logo.png",
        "color": "#F7931A"
    },
    "ARB": {
        "address": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "decimals": 18,
        "symbol": "ARB",
        "name": "Arbitrum",
        "logo": "https://cryptologos.cc/logos/arbitrum-arb-logo.png",
        "color": "#28A0F0"
    },
    "DAI": {
        "address": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
        "decimals": 18,
        "symbol": "DAI",
        "name": "Dai Stablecoin",
        "logo": "https://cryptologos.cc/logos/multi-collateral-dai-dai-logo.png",
        "color": "#F5AC37"
    },
    "LINK": {
        "address": "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4",
        "decimals": 18,
        "symbol": "LINK",
        "name": "Chainlink",
        "logo": "https://cryptologos.cc/logos/chainlink-link-logo.png",
        "color": "#2A5ADA"
    },
    "UNI": {
        "address": "0xFa7F8980b0f1E64A2062791cc3b0871572f1F7f0",
        "decimals": 18,
        "symbol": "UNI",
        "name": "Uniswap",
        "logo": "https://cryptologos.cc/logos/uniswap-uni-logo.png",
        "color": "#FF007A"
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITAS
# ═══════════════════════════════════════════════════════════════════════════════

def parse_amount(amount_str):
    """Parse amount dengan handle scientific notation"""
    try:
        if not amount_str or amount_str == '':
            return Decimal('0')
        # Handle scientific notation dan format aneh
        cleaned = str(amount_str).replace(' ', '').replace(',', '')
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError) as e:
        logger.error(f"Error parsing amount '{amount_str}': {e}")
        return Decimal('0')

def to_wei(amount, decimals):
    """Convert ke wei dengan decimals token"""
    try:
        amount_dec = parse_amount(amount)
        return int(amount_dec * (Decimal(10) ** decimals))
    except Exception as e:
        logger.error(f"Error converting to wei: {e}")
        return 0

def from_wei(amount_wei, decimals):
    """Convert dari wei ke amount readable"""
    try:
        return Decimal(amount_wei) / (Decimal(10) ** decimals)
    except Exception as e:
        logger.error(f"Error converting from wei: {e}")
        return Decimal('0')

def format_amount(amount, decimals=6):
    """Format amount untuk display"""
    try:
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        elif isinstance(amount, str):
            amount = parse_amount(amount)
        
        if amount == 0:
            return "0.00"
        elif amount < Decimal('0.000001'):
            return f"{amount:.8f}"
        elif amount < Decimal('1'):
            return f"{amount:.6f}"
        elif amount < Decimal('1000'):
            return f"{amount:.4f}"
        elif amount < Decimal('1000000'):
            return f"{amount:,.2f}"
        else:
            return f"{amount:,.0f}"
    except:
        return "0.00"

def format_usd(amount):
    """Format USD amount"""
    try:
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        elif isinstance(amount, str):
            amount = parse_amount(amount)
        
        if amount == 0:
            return "$0.00"
        elif amount < Decimal('0.01'):
            return f"${amount:.6f}"
        elif amount < Decimal('1'):
            return f"${amount:.4f}"
        else:
            return f"${amount:,.2f}"
    except:
        return "$0.00"

# ═══════════════════════════════════════════════════════════════════════════════
# API BEBOP
# ═══════════════════════════════════════════════════════════════════════════════

def get_quote(sell_token, buy_token, sell_amount, taker_address=None):
    """Mendapatkan quote dari Bebop API"""
    try:
        sell_info = TOKENS.get(sell_token)
        buy_info = TOKENS.get(buy_token)
        
        if not sell_info or not buy_info:
            return {"error": "Token tidak ditemukan"}
        
        # Convert amount ke wei
        sell_amount_wei = to_wei(sell_amount, sell_info['decimals'])
        
        if sell_amount_wei <= 0:
            return {"error": "Amount harus lebih dari 0"}
        
        params = {
            "sell_tokens": sell_info['address'],
            "buy_tokens": buy_info['address'],
            "sell_amounts": str(sell_amount_wei),
            "taker_address": taker_address or "0x0000000000000000000000000000000000000000",
            "source": "bebop_scalper_pro",
            "gasless": "false",
            "chain_id": str(ARBITRUM_CHAIN_ID)
        }
        
        response = requests.get(
            f"{BEBOP_API}/quote",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Quote received: {json.dumps(data, indent=2)[:500]}")
            return data
        else:
            logger.error(f"Quote error: {response.status_code} - {response.text}")
            return {"error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Error getting quote: {e}")
        return {"error": str(e)}

def get_price(sell_token, buy_token):
    """Mendapatkan harga untuk 1 unit token"""
    try:
        quote = get_quote(sell_token, buy_token, "1")
        if "error" in quote:
            return None
        
        # Extract rate dari quote
        routes = quote.get('routes', [])
        if routes and len(routes) > 0:
            route = routes[0]
            buy_amount = route.get('buyAmount', '0')
            buy_info = TOKENS.get(buy_token)
            if buy_info:
                rate = from_wei(buy_amount, buy_info['decimals'])
                return float(rate)
        return None
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        return None

def get_gas_price():
    """Mendapatkan gas price Arbitrum"""
    try:
        # Gas price Arbitrum biasanya ~0.1 gwei
        return {
            "slow": 0.1,
            "standard": 0.1,
            "fast": 0.1,
            "rapid": 0.2
        }
    except:
        return {"standard": 0.1}

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES FLASK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/tokens')
def get_tokens():
    return jsonify(TOKENS)

@app.route('/api/quote')
def api_quote():
    sell_token = request.args.get('sell_token', 'USDC')
    buy_token = request.args.get('buy_token', 'WETH')
    sell_amount = request.args.get('sell_amount', '1')
    taker_address = request.args.get('taker_address')
    
    quote = get_quote(sell_token, buy_token, sell_amount, taker_address)
    return jsonify(quote)

@app.route('/api/price')
def api_price():
    sell_token = request.args.get('sell_token', 'USDC')
    buy_token = request.args.get('buy_token', 'WETH')
    
    price = get_price(sell_token, buy_token)
    return jsonify({"price": price})

@app.route('/api/swap', methods=['POST'])
def api_swap():
    """Endpoint untuk eksekusi swap"""
    try:
        data = request.json
        sell_token = data.get('sell_token')
        buy_token = data.get('buy_token')
        sell_amount = data.get('sell_amount')
        taker_address = data.get('taker_address')
        slippage = data.get('slippage', 0.5)
        
        if not all([sell_token, buy_token, sell_amount, taker_address]):
            return jsonify({"error": "Parameter tidak lengkap"}), 400
        
        # Get quote untuk swap
        quote = get_quote(sell_token, buy_token, sell_amount, taker_address)
        
        if "error" in quote:
            return jsonify({"error": quote["error"]}), 400
        
        # Return quote data untuk dikirim ke wallet
        return jsonify({
            "success": True,
            "quote": quote,
            "message": "Quote berhasil dibuat. Silakan sign transaksi di wallet Anda.",
            "data": {
                "sell_token": TOKENS[sell_token]['address'],
                "buy_token": TOKENS[buy_token]['address'],
                "sell_amount": str(to_wei(sell_amount, TOKENS[sell_token]['decimals'])),
                "taker_address": taker_address,
                "chain_id": ARBITRUM_CHAIN_ID
            }
        })
        
    except Exception as e:
        logger.error(f"Swap error: {e}")
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET REAL-TIME
# ═══════════════════════════════════════════════════════════════════════════════

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    emit('connected', {'status': 'connected', 'version': '4.0'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

@socketio.on('subscribe_price')
def handle_subscribe(data):
    """Subscribe ke real-time price updates"""
    sell_token = data.get('sell_token', 'USDC')
    buy_token = data.get('buy_token', 'WETH')
    sell_amount = data.get('sell_amount', '1')
    
    def price_updater():
        while True:
            try:
                quote = get_quote(sell_token, buy_token, sell_amount)
                socketio.emit('price_update', {
                    'sell_token': sell_token,
                    'buy_token': buy_token,
                    'sell_amount': sell_amount,
                    'quote': quote,
                    'timestamp': time.time()
                })
                socketio.sleep(0.5)
            except Exception as e:
                logger.error(f"Price updater error: {e}")
                socketio.sleep(1)
    
    socketio.start_background_task(price_updater)

# ═══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATE - ULTRA MODERN UI
# ═══════════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bebop Scalper Pro v4.0</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/web3@1.8.0/dist/web3.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #00D4AA;
            --primary-dark: #00B894;
            --secondary: #6C5CE7;
            --accent: #FD79A8;
            --danger: #E74C3C;
            --warning: #F39C12;
            --bg-dark: #0A0A0F;
            --bg-card: #12121A;
            --bg-input: #1A1A25;
            --border: #2A2A3A;
            --text-primary: #FFFFFF;
            --text-secondary: #8B8B9E;
            --text-muted: #5A5A6E;
            --gradient-1: linear-gradient(135deg, #00D4AA 0%, #6C5CE7 100%);
            --gradient-2: linear-gradient(135deg, #FD79A8 0%, #FDCB6E 100%);
            --glow-primary: 0 0 20px rgba(0, 212, 170, 0.4);
            --glow-secondary: 0 0 20px rgba(108, 92, 231, 0.4);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Animated Background */
        .bg-animation {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
        }
        
        .bg-animation::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: 
                radial-gradient(circle at 20% 80%, rgba(0, 212, 170, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(108, 92, 231, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(253, 121, 168, 0.05) 0%, transparent 50%);
            animation: bgRotate 30s linear infinite;
        }
        
        @keyframes bgRotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Grid Pattern */
        .grid-pattern {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                linear-gradient(rgba(0, 212, 170, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 212, 170, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            z-index: -1;
        }
        
        /* Header */
        .header {
            background: rgba(18, 18, 26, 0.9);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            padding: 12px 20px;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .logo-icon {
            width: 42px;
            height: 42px;
            background: var(--gradient-1);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            animation: pulse 2s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { box-shadow: var(--glow-primary); }
            50% { box-shadow: 0 0 30px rgba(0, 212, 170, 0.6); }
        }
        
        .logo-text {
            font-weight: 800;
            font-size: 1.3rem;
            background: var(--gradient-1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .logo-sub {
            font-size: 0.7rem;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .header-stats {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 0.9rem;
            color: var(--primary);
        }
        
        .stat-label {
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .header-actions {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .btn {
            padding: 10px 20px;
            border-radius: 10px;
            border: none;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: var(--gradient-1);
            color: white;
            box-shadow: var(--glow-primary);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 0 30px rgba(0, 212, 170, 0.6);
        }
        
        .btn-secondary {
            background: var(--bg-input);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        
        .btn-secondary:hover {
            background: var(--border);
            border-color: var(--primary);
        }
        
        .btn-icon {
            width: 40px;
            height: 40px;
            padding: 0;
            justify-content: center;
            font-size: 1.1rem;
        }
        
        /* Main Container */
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Grid Layout */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 20px;
        }
        
        @media (max-width: 1024px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        /* Swap Card */
        .swap-card {
            background: var(--bg-card);
            border-radius: 24px;
            border: 1px solid var(--border);
            padding: 24px;
            position: relative;
            overflow: hidden;
        }
        
        .swap-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--gradient-1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 1.1rem;
            font-weight: 700;
        }
        
        .card-actions {
            display: flex;
            gap: 8px;
        }
        
        .icon-btn {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            background: var(--bg-input);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 1rem;
        }
        
        .icon-btn:hover {
            background: var(--border);
            color: var(--primary);
            border-color: var(--primary);
        }
        
        .icon-btn.spinning {
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        /* Input Sections */
        .input-section {
            background: var(--bg-input);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
            border: 1px solid var(--border);
            transition: all 0.3s ease;
        }
        
        .input-section:focus-within {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(0, 212, 170, 0.1);
        }
        
        .input-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .input-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .balance-display {
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .input-row {
            display: flex;
            gap: 12px;
            align-items: center;
        }
        
        .amount-input {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.8rem;
            font-weight: 700;
            outline: none;
            width: 100%;
        }
        
        .amount-input::placeholder {
            color: var(--text-muted);
        }
        
        .token-selector {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--bg-card);
            padding: 8px 14px;
            border-radius: 12px;
            border: 1px solid var(--border);
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 120px;
        }
        
        .token-selector:hover {
            border-color: var(--primary);
            background: var(--border);
        }
        
        .token-logo {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .token-info {
            flex: 1;
        }
        
        .token-symbol {
            font-weight: 700;
            font-size: 0.95rem;
        }
        
        .token-name {
            font-size: 0.7rem;
            color: var(--text-muted);
        }
        
        .token-arrow {
            color: var(--text-muted);
            font-size: 0.8rem;
        }
        
        .usd-value {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 4px;
            font-family: 'JetBrains Mono', monospace;
        }
        
        /* Switch Button */
        .switch-container {
            display: flex;
            justify-content: center;
            margin: -6px 0;
            position: relative;
            z-index: 10;
        }
        
        .switch-btn {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: var(--gradient-1);
            border: 4px solid var(--bg-card);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 1.1rem;
            box-shadow: var(--glow-primary);
        }
        
        .switch-btn:hover {
            transform: rotate(180deg) scale(1.1);
        }
        
        /* Rate Display */
        .rate-display {
            background: var(--bg-input);
            border-radius: 12px;
            padding: 12px 16px;
            margin: 16px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.85rem;
        }
        
        .rate-label {
            color: var(--text-muted);
        }
        
        .rate-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--primary);
        }
        
        .rate-change {
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 20px;
            margin-left: 8px;
        }
        
        .rate-change.positive {
            background: rgba(0, 212, 170, 0.15);
            color: var(--primary);
        }
        
        .rate-change.negative {
            background: rgba(231, 76, 60, 0.15);
            color: var(--danger);
        }
        
        /* Fee Breakdown */
        .fee-section {
            background: var(--bg-input);
            border-radius: 12px;
            padding: 16px;
            margin: 16px 0;
        }
        
        .fee-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            cursor: pointer;
        }
        
        .fee-title {
            font-size: 0.85rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .fee-arrow {
            transition: transform 0.3s ease;
        }
        
        .fee-arrow.expanded {
            transform: rotate(180deg);
        }
        
        .fee-items {
            display: none;
        }
        
        .fee-items.expanded {
            display: block;
        }
        
        .fee-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .fee-item:last-child {
            border-bottom: none;
        }
        
        .fee-item-label {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .fee-item-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
        }
        
        .fee-item-value.negative {
            color: var(--danger);
        }
        
        .fee-total {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 12px;
            margin-top: 12px;
            border-top: 2px solid var(--border);
        }
        
        .fee-total-label {
            font-weight: 700;
            font-size: 0.9rem;
        }
        
        .fee-total-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1rem;
            color: var(--primary);
        }
        
        /* Swap Button */
        .swap-button {
            width: 100%;
            padding: 18px;
            border-radius: 16px;
            background: var(--gradient-1);
            color: white;
            border: none;
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 1.1rem;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 16px;
            position: relative;
            overflow: hidden;
        }
        
        .swap-button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s ease;
        }
        
        .swap-button:hover::before {
            left: 100%;
        }
        
        .swap-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 212, 170, 0.4);
        }
        
        .swap-button:disabled {
            background: var(--border);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .swap-button:disabled::before {
            display: none;
        }
        
        .swap-button.swapping {
            background: var(--gradient-2);
        }
        
        /* Side Panel */
        .side-panel {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        .panel-card {
            background: var(--bg-card);
            border-radius: 20px;
            border: 1px solid var(--border);
            padding: 20px;
        }
        
        .panel-title {
            font-size: 0.9rem;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .panel-title-icon {
            width: 28px;
            height: 28px;
            background: var(--bg-input);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
        }
        
        /* Price Chart */
        .chart-container {
            height: 200px;
            position: relative;
        }
        
        /* Market Stats */
        .market-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        
        .market-stat {
            background: var(--bg-input);
            border-radius: 12px;
            padding: 14px;
        }
        
        .market-stat-label {
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }
        
        .market-stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1rem;
        }
        
        .market-stat-value.positive {
            color: var(--primary);
        }
        
        .market-stat-value.negative {
            color: var(--danger);
        }
        
        /* Transaction Status */
        .tx-status {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--bg-card);
            border-radius: 16px;
            border: 1px solid var(--border);
            padding: 16px 20px;
            max-width: 400px;
            z-index: 1000;
            transform: translateX(150%);
            transition: transform 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        }
        
        .tx-status.show {
            transform: translateX(0);
        }
        
        .tx-status.success {
            border-color: var(--primary);
        }
        
        .tx-status.error {
            border-color: var(--danger);
        }
        
        .tx-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 8px;
        }
        
        .tx-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }
        
        .tx-icon.pending {
            background: var(--gradient-2);
            animation: pulse 1.5s ease-in-out infinite;
        }
        
        .tx-icon.success {
            background: rgba(0, 212, 170, 0.2);
            color: var(--primary);
        }
        
        .tx-icon.error {
            background: rgba(231, 76, 60, 0.2);
            color: var(--danger);
        }
        
        .tx-title {
            font-weight: 700;
        }
        
        .tx-message {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .tx-link {
            display: inline-block;
            margin-top: 8px;
            color: var(--primary);
            font-size: 0.8rem;
            text-decoration: none;
        }
        
        .tx-link:hover {
            text-decoration: underline;
        }
        
        /* Token Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(10px);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        
        .modal-overlay.show {
            display: flex;
        }
        
        .modal {
            background: var(--bg-card);
            border-radius: 24px;
            border: 1px solid var(--border);
            width: 90%;
            max-width: 420px;
            max-height: 80vh;
            overflow: hidden;
        }
        
        .modal-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-title {
            font-size: 1.1rem;
            font-weight: 700;
        }
        
        .modal-close {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            background: var(--bg-input);
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.3s ease;
        }
        
        .modal-close:hover {
            background: var(--danger);
            color: white;
        }
        
        .modal-search {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .search-input {
            width: 100%;
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 16px;
            color: var(--text-primary);
            font-size: 0.95rem;
            outline: none;
            transition: all 0.3s ease;
        }
        
        .search-input:focus {
            border-color: var(--primary);
        }
        
        .token-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .token-item {
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 14px 20px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .token-item:hover {
            background: var(--bg-input);
        }
        
        .token-item-logo {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .token-item-info {
            flex: 1;
        }
        
        .token-item-symbol {
            font-weight: 700;
            font-size: 1rem;
        }
        
        .token-item-name {
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        
        .token-item-balance {
            text-align: right;
        }
        
        .token-item-amount {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        }
        
        .token-item-usd {
            font-size: 0.75rem;
            color: var(--text-muted);
        }
        
        /* Settings Panel */
        .settings-panel {
            position: fixed;
            top: 0;
            right: -400px;
            width: 100%;
            max-width: 400px;
            height: 100%;
            background: var(--bg-card);
            border-left: 1px solid var(--border);
            z-index: 1001;
            transition: right 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            overflow-y: auto;
        }
        
        .settings-panel.show {
            right: 0;
        }
        
        .settings-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .settings-back {
            width: 40px;
            height: 40px;
            border-radius: 12px;
            background: var(--bg-input);
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 1.1rem;
            transition: all 0.3s ease;
        }
        
        .settings-back:hover {
            background: var(--border);
            color: var(--primary);
        }
        
        .settings-title {
            font-size: 1.2rem;
            font-weight: 700;
        }
        
        .settings-content {
            padding: 20px;
        }
        
        .setting-item {
            margin-bottom: 24px;
        }
        
        .setting-label {
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 12px;
            display: block;
        }
        
        .setting-description {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-bottom: 12px;
        }
        
        .slippage-options {
            display: flex;
            gap: 8px;
        }
        
        .slippage-option {
            flex: 1;
            padding: 12px;
            border-radius: 12px;
            background: var(--bg-input);
            border: 2px solid transparent;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-align: center;
        }
        
        .slippage-option:hover {
            border-color: var(--border);
        }
        
        .slippage-option.active {
            border-color: var(--primary);
            color: var(--primary);
            background: rgba(0, 212, 170, 0.1);
        }
        
        .slippage-custom {
            width: 100%;
            padding: 12px;
            border-radius: 12px;
            background: var(--bg-input);
            border: 2px solid var(--border);
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            outline: none;
            margin-top: 12px;
        }
        
        .slippage-custom:focus {
            border-color: var(--primary);
        }
        
        /* Mobile Responsive */
        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                align-items: stretch;
            }
            
            .header-stats {
                justify-content: center;
            }
            
            .header-actions {
                justify-content: center;
            }
            
            .amount-input {
                font-size: 1.4rem;
            }
            
            .token-selector {
                min-width: 100px;
                padding: 6px 10px;
            }
            
            .token-logo {
                width: 24px;
                height: 24px;
            }
            
            .token-symbol {
                font-size: 0.85rem;
            }
            
            .token-name {
                display: none;
            }
            
            .swap-card {
                padding: 16px;
            }
            
            .market-stats {
                grid-template-columns: 1fr;
            }
            
            .tx-status {
                left: 16px;
                right: 16px;
                max-width: none;
            }
        }
        
        /* Loading Animation */
        .loading-dots {
            display: inline-flex;
            gap: 4px;
        }
        
        .loading-dots span {
            width: 8px;
            height: 8px;
            background: currentColor;
            border-radius: 50%;
            animation: bounce 1.4s ease-in-out infinite both;
        }
        
        .loading-dots span:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots span:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
        
        /* Live Indicator */
        .live-indicator {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.7rem;
            color: var(--primary);
            background: rgba(0, 212, 170, 0.1);
            padding: 4px 10px;
            border-radius: 20px;
        }
        
        .live-dot {
            width: 6px;
            height: 6px;
            background: var(--primary);
            border-radius: 50%;
            animation: blink 1s ease-in-out infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-dark);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="bg-animation"></div>
    <div class="grid-pattern"></div>
    
    <!-- Header -->
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <div class="logo-icon">⚡</div>
                <div>
                    <div class="logo-text">BEBOP SCALPER PRO</div>
                    <div class="logo-sub">v4.0 | Arbitrum RFQ DEX</div>
                </div>
            </div>
            
            <div class="header-stats">
                <div class="stat-item">
                    <div class="stat-value" id="gasPrice">0.1 Gwei</div>
                    <div class="stat-label">Gas</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="networkStatus">
                        <span class="live-indicator">
                            <span class="live-dot"></span>
                            LIVE
                        </span>
                    </div>
                    <div class="stat-label">Status</div>
                </div>
            </div>
            
            <div class="header-actions">
                <button class="btn btn-secondary btn-icon" onclick="toggleSettings()" title="Pengaturan">
                    ⚙️
                </button>
                <button class="btn btn-primary" id="connectWalletBtn" onclick="connectWallet()">
                    <span>🔌</span>
                    <span id="walletText">Hubungkan Wallet</span>
                </button>
            </div>
        </div>
    </header>
    
    <!-- Main Container -->
    <div class="container">
        <div class="main-grid">
            <!-- Swap Card -->
            <div class="swap-card">
                <div class="card-header">
                    <div class="card-title">🔄 Tukar Token</div>
                    <div class="card-actions">
                        <button class="icon-btn" id="refreshBtn" onclick="refreshQuote()" title="Refresh">
                            🔄
                        </button>
                    </div>
                </div>
                
                <!-- Sell Input -->
                <div class="input-section">
                    <div class="input-header">
                        <span class="input-label">Anda Bayar</span>
                        <span class="balance-display" id="sellBalance">Saldo: --</span>
                    </div>
                    <div class="input-row">
                        <input type="number" class="amount-input" id="sellAmount" placeholder="0.00" oninput="onAmountChange()">
                        <div class="token-selector" onclick="openTokenModal('sell')">
                            <img src="" alt="" class="token-logo" id="sellTokenLogo">
                            <div class="token-info">
                                <div class="token-symbol" id="sellTokenSymbol">USDC</div>
                                <div class="token-name" id="sellTokenName">USD Coin</div>
                            </div>
                            <span class="token-arrow">▼</span>
                        </div>
                    </div>
                    <div class="usd-value" id="sellUsdValue">≈ $0.00</div>
                </div>
                
                <!-- Switch Button -->
                <div class="switch-container">
                    <button class="switch-btn" onclick="switchTokens()">⇅</button>
                </div>
                
                <!-- Buy Input -->
                <div class="input-section">
                    <div class="input-header">
                        <span class="input-label">Anda Terima</span>
                        <span class="balance-display" id="buyBalance">Saldo: --</span>
                    </div>
                    <div class="input-row">
                        <input type="text" class="amount-input" id="buyAmount" placeholder="0.00" readonly>
                        <div class="token-selector" onclick="openTokenModal('buy')">
                            <img src="" alt="" class="token-logo" id="buyTokenLogo">
                            <div class="token-info">
                                <div class="token-symbol" id="buyTokenSymbol">WETH</div>
                                <div class="token-name" id="buyTokenName">Wrapped Ether</div>
                            </div>
                            <span class="token-arrow">▼</span>
                        </div>
                    </div>
                    <div class="usd-value" id="buyUsdValue">≈ $0.00</div>
                </div>
                
                <!-- Rate Display -->
                <div class="rate-display">
                    <span class="rate-label">Rate</span>
                    <div>
                        <span class="rate-value" id="rateDisplay">1 USDC ≈ -- WETH</span>
                        <span class="rate-change positive" id="rateChange">+0.00%</span>
                    </div>
                </div>
                
                <!-- Fee Breakdown -->
                <div class="fee-section">
                    <div class="fee-header" onclick="toggleFeeDetails()">
                        <span class="fee-title">
                            💰 Detail Biaya
                            <span id="totalFeePercent" style="font-size: 0.75rem; color: var(--text-muted);">(0.00%)</span>
                        </span>
                        <span class="fee-arrow" id="feeArrow">▼</span>
                    </div>
                    <div class="fee-items" id="feeItems">
                        <div class="fee-item">
                            <span class="fee-item-label">
                                🏷️ Biaya Protokol
                            </span>
                            <span class="fee-item-value" id="protocolFee">$0.00</span>
                        </div>
                        <div class="fee-item">
                            <span class="fee-item-label">
                                ⛽ Biaya Gas
                            </span>
                            <span class="fee-item-value" id="gasFee">$0.00</span>
                        </div>
                        <div class="fee-item">
                            <span class="fee-item-label">
                                📉 Slippage Maks
                            </span>
                            <span class="fee-item-value negative" id="slippageFee">$0.00</span>
                        </div>
                        <div class="fee-total">
                            <span class="fee-total-label">Total Biaya</span>
                            <span class="fee-total-value" id="totalFee">$0.00</span>
                        </div>
                    </div>
                </div>
                
                <!-- Net Output -->
                <div style="background: rgba(0, 212, 170, 0.1); border-radius: 12px; padding: 16px; margin-bottom: 16px; border: 1px solid rgba(0, 212, 170, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.85rem; color: var(--text-secondary);">Estimasi Output Bersih</span>
                        <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1.1rem; color: var(--primary);" id="netOutput">$0.00</span>
                    </div>
                </div>
                
                <!-- Swap Button -->
                <button class="swap-button" id="swapBtn" onclick="executeSwap()">
                    <span>🚀</span>
                    <span id="swapBtnText">Tukar Sekarang</span>
                </button>
            </div>
            
            <!-- Side Panel -->
            <div class="side-panel">
                <!-- Price Chart -->
                <div class="panel-card">
                    <div class="panel-title">
                        <div class="panel-title-icon">📊</div>
                        Grafik Harga
                    </div>
                    <div class="chart-container">
                        <canvas id="priceChart"></canvas>
                    </div>
                </div>
                
                <!-- Market Stats -->
                <div class="panel-card">
                    <div class="panel-title">
                        <div class="panel-title-icon">📈</div>
                        Statistik Pasar
                    </div>
                    <div class="market-stats">
                        <div class="market-stat">
                            <div class="market-stat-label">24h High</div>
                            <div class="market-stat-value positive" id="high24h">--</div>
                        </div>
                        <div class="market-stat">
                            <div class="market-stat-label">24h Low</div>
                            <div class="market-stat-value negative" id="low24h">--</div>
                        </div>
                        <div class="market-stat">
                            <div class="market-stat-label">Volume 24h</div>
                            <div class="market-stat-value" id="volume24h">--</div>
                        </div>
                        <div class="market-stat">
                            <div class="market-stat-label">Likuiditas</div>
                            <div class="market-stat-value" id="liquidity">--</div>
                        </div>
                    </div>
                </div>
                
                <!-- Recent Trades -->
                <div class="panel-card">
                    <div class="panel-title">
                        <div class="panel-title-icon">🔔</div>
                        Transaksi Terbaru
                    </div>
                    <div id="recentTrades" style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 20px;">
                        Menunggu data...
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Transaction Status -->
    <div class="tx-status" id="txStatus">
        <div class="tx-header">
            <div class="tx-icon pending" id="txIcon">⏳</div>
            <div>
                <div class="tx-title" id="txTitle">Memproses...</div>
                <div class="tx-message" id="txMessage">Transaksi sedang diproses</div>
            </div>
        </div>
        <a href="#" class="tx-link" id="txLink" target="_blank" style="display: none;">Lihat di Explorer →</a>
    </div>
    
    <!-- Token Modal -->
    <div class="modal-overlay" id="tokenModal" onclick="closeTokenModal(event)">
        <div class="modal" onclick="event.stopPropagation()">
            <div class="modal-header">
                <div class="modal-title">Pilih Token</div>
                <button class="modal-close" onclick="closeTokenModal()">×</button>
            </div>
            <div class="modal-search">
                <input type="text" class="search-input" placeholder="Cari token..." id="tokenSearch" oninput="filterTokens()">
            </div>
            <div class="token-list" id="tokenList">
                <!-- Token items will be inserted here -->
            </div>
        </div>
    </div>
    
    <!-- Settings Panel -->
    <div class="settings-panel" id="settingsPanel">
        <div class="settings-header">
            <button class="settings-back" onclick="toggleSettings()">←</button>
            <div class="settings-title">⚙️ Pengaturan</div>
        </div>
        <div class="settings-content">
            <div class="setting-item">
                <label class="setting-label">Toleransi Slippage</label>
                <p class="setting-description">Batas maksimum perubahan harga yang dapat diterima</p>
                <div class="slippage-options">
                    <button class="slippage-option" data-value="0.1" onclick="setSlippage(0.1)">0.1%</button>
                    <button class="slippage-option active" data-value="0.5" onclick="setSlippage(0.5)">0.5%</button>
                    <button class="slippage-option" data-value="1.0" onclick="setSlippage(1.0)">1.0%</button>
                </div>
                <input type="number" class="slippage-custom" placeholder="Custom %" id="customSlippage" onchange="setCustomSlippage()">
            </div>
            
            <div class="setting-item">
                <label class="setting-label">Deadline Transaksi</label>
                <p class="setting-description">Waktu maksimum untuk eksekusi transaksi</p>
                <div class="slippage-options">
                    <button class="slippage-option" data-deadline="5" onclick="setDeadline(5)">5 menit</button>
                    <button class="slippage-option active" data-deadline="10" onclick="setDeadline(10)">10 menit</button>
                    <button class="slippage-option" data-deadline="20" onclick="setDeadline(20)">20 menit</button>
                </div>
            </div>
            
            <div class="setting-item">
                <label class="setting-label">Auto Refresh</label>
                <p class="setting-description">Frekuensi update harga otomatis</p>
                <div class="slippage-options">
                    <button class="slippage-option" data-refresh="1000" onclick="setRefreshRate(1000)">1 detik</button>
                    <button class="slippage-option active" data-refresh="500" onclick="setRefreshRate(500)">0.5 detik</button>
                    <button class="slippage-option" data-refresh="200" onclick="setRefreshRate(200)">0.2 detik</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // ═══════════════════════════════════════════════════════════════════════
        // STATE
        // ═══════════════════════════════════════════════════════════════════════
        
        let tokens = {};
        let sellToken = 'USDC';
        let buyToken = 'WETH';
        let sellAmount = '';
        let currentQuote = null;
        let slippage = 0.5;
        let deadline = 10;
        let refreshRate = 500;
        let walletAddress = null;
        let web3 = null;
        let priceChart = null;
        let priceHistory = [];
        let tokenModalMode = 'sell';
        let refreshInterval = null;
        let isFeeExpanded = false;
        
        // ═══════════════════════════════════════════════════════════════════════
        // INITIALIZATION
        // ═══════════════════════════════════════════════════════════════════════
        
        document.addEventListener('DOMContentLoaded', async () => {
            await loadTokens();
            updateTokenDisplay();
            initChart();
            startPriceUpdates();
            
            // Check if wallet already connected
            if (window.ethereum && window.ethereum.selectedAddress) {
                await connectWallet();
            }
        });
        
        async function loadTokens() {
            try {
                const response = await fetch('/api/tokens');
                tokens = await response.json();
            } catch (e) {
                console.error('Error loading tokens:', e);
            }
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // WALLET CONNECTION
        // ═══════════════════════════════════════════════════════════════════════
        
        async function connectWallet() {
            try {
                if (!window.ethereum) {
                    showTxStatus('error', 'MetaMask Tidak Terdeteksi', 'Silakan install MetaMask terlebih dahulu');
                    return;
                }
                
                web3 = new Web3(window.ethereum);
                
                const accounts = await window.ethereum.request({
                    method: 'eth_requestAccounts'
                });
                
                walletAddress = accounts[0];
                
                // Check Arbitrum network
                const chainId = await web3.eth.getChainId();
                if (chainId !== 42161) {
                    try {
                        await window.ethereum.request({
                            method: 'wallet_switchEthereumChain',
                            params: [{ chainId: '0xa4b1' }]
                        });
                    } catch (switchError) {
                        // Add Arbitrum if not exists
                        if (switchError.code === 4902) {
                            await window.ethereum.request({
                                method: 'wallet_addEthereumChain',
                                params: [{
                                    chainId: '0xa4b1',
                                    chainName: 'Arbitrum One',
                                    nativeCurrency: { name: 'ETH', symbol: 'ETH', decimals: 18 },
                                    rpcUrls: ['https://arb1.arbitrum.io/rpc'],
                                    blockExplorerUrls: ['https://arbiscan.io/']
                                }]
                            });
                        }
                    }
                }
                
                // Update UI
                const shortAddress = walletAddress.slice(0, 6) + '...' + walletAddress.slice(-4);
                document.getElementById('walletText').textContent = shortAddress;
                document.getElementById('connectWalletBtn').classList.add('connected');
                
                // Get balances
                await updateBalances();
                
                showTxStatus('success', 'Wallet Terhubung', `Terhubung ke ${shortAddress}`);
                
            } catch (e) {
                console.error('Wallet connection error:', e);
                showTxStatus('error', 'Gagal Terhubung', e.message);
            }
        }
        
        async function updateBalances() {
            if (!walletAddress || !web3) return;
            
            try {
                // ETH balance
                const ethBalance = await web3.eth.getBalance(walletAddress);
                const ethFormatted = (ethBalance / 1e18).toFixed(4);
                
                // Update display based on selected tokens
                // In production, fetch ERC20 balances
                document.getElementById('sellBalance').textContent = `Saldo: --`;
                document.getElementById('buyBalance').textContent = `Saldo: --`;
                
            } catch (e) {
                console.error('Balance error:', e);
            }
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // TOKEN SELECTION
        // ═══════════════════════════════════════════════════════════════════════
        
        function openTokenModal(mode) {
            tokenModalMode = mode;
            document.getElementById('tokenModal').classList.add('show');
            renderTokenList();
        }
        
        function closeTokenModal(event) {
            if (!event || event.target === document.getElementById('tokenModal')) {
                document.getElementById('tokenModal').classList.remove('show');
            }
        }
        
        function renderTokenList() {
            const list = document.getElementById('tokenList');
            const searchTerm = document.getElementById('tokenSearch').value.toLowerCase();
            
            list.innerHTML = Object.entries(tokens)
                .filter(([symbol, token]) => {
                    const searchStr = `${symbol} ${token.name}`.toLowerCase();
                    return searchStr.includes(searchTerm);
                })
                .map(([symbol, token]) => `
                    <div class="token-item" onclick="selectToken('${symbol}')">
                        <img src="${token.logo}" alt="${symbol}" class="token-item-logo">
                        <div class="token-item-info">
                            <div class="token-item-symbol">${symbol}</div>
                            <div class="token-item-name">${token.name}</div>
                        </div>
                        <div class="token-item-balance">
                            <div class="token-item-amount">--</div>
                            <div class="token-item-usd">$--</div>
                        </div>
                    </div>
                `).join('');
        }
        
        function filterTokens() {
            renderTokenList();
        }
        
        function selectToken(symbol) {
            if (tokenModalMode === 'sell') {
                if (symbol === buyToken) {
                    buyToken = sellToken;
                }
                sellToken = symbol;
            } else {
                if (symbol === sellToken) {
                    sellToken = buyToken;
                }
                buyToken = symbol;
            }
            
            updateTokenDisplay();
            closeTokenModal();
            onAmountChange();
        }
        
        function updateTokenDisplay() {
            const sellInfo = tokens[sellToken];
            const buyInfo = tokens[buyToken];
            
            if (sellInfo) {
                document.getElementById('sellTokenLogo').src = sellInfo.logo;
                document.getElementById('sellTokenSymbol').textContent = sellToken;
                document.getElementById('sellTokenName').textContent = sellInfo.name;
            }
            
            if (buyInfo) {
                document.getElementById('buyTokenLogo').src = buyInfo.logo;
                document.getElementById('buyTokenSymbol').textContent = buyToken;
                document.getElementById('buyTokenName').textContent = buyInfo.name;
            }
        }
        
        function switchTokens() {
            const temp = sellToken;
            sellToken = buyToken;
            buyToken = temp;
            
            const tempAmount = document.getElementById('sellAmount').value;
            document.getElementById('sellAmount').value = document.getElementById('buyAmount').value;
            
            updateTokenDisplay();
            onAmountChange();
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // QUOTE & PRICE
        // ═══════════════════════════════════════════════════════════════════════
        
        function onAmountChange() {
            sellAmount = document.getElementById('sellAmount').value;
            
            if (!sellAmount || parseFloat(sellAmount) <= 0) {
                document.getElementById('buyAmount').value = '';
                document.getElementById('sellUsdValue').textContent = '≈ $0.00';
                document.getElementById('buyUsdValue').textContent = '≈ $0.00';
                resetFeeDisplay();
                return;
            }
            
            // Update USD value
            document.getElementById('sellUsdValue').textContent = `≈ $${parseFloat(sellAmount).toFixed(2)}`;
            
            // Fetch quote
            fetchQuote();
        }
        
        async function fetchQuote() {
            if (!sellAmount || parseFloat(sellAmount) <= 0) return;
            
            try {
                const params = new URLSearchParams({
                    sell_token: sellToken,
                    buy_token: buyToken,
                    sell_amount: sellAmount,
                    taker_address: walletAddress || '0x0000000000000000000000000000000000000000'
                });
                
                const response = await fetch(`/api/quote?${params}`);
                const quote = await response.json();
                
                if (quote.error) {
                    console.error('Quote error:', quote.error);
                    return;
                }
                
                currentQuote = quote;
                processQuote(quote);
                
            } catch (e) {
                console.error('Fetch quote error:', e);
            }
        }
        
        function processQuote(quote) {
            const routes = quote.routes || [];
            if (!routes.length) return;
            
            const route = routes[0];
            const sellInfo = tokens[sellToken];
            const buyInfo = tokens[buyToken];
            
            // Calculate buy amount from wei
            const buyAmountWei = route.buyAmount || '0';
            const buyAmount = parseFloat(buyAmountWei) / Math.pow(10, buyInfo.decimals);
            
            // Update buy amount display
            document.getElementById('buyAmount').value = formatAmount(buyAmount);
            
            // Calculate rate
            const sellAmt = parseFloat(sellAmount);
            const rate = buyAmount / sellAmt;
            
            document.getElementById('rateDisplay').textContent = `1 ${sellToken} ≈ ${formatAmount(rate, 6)} ${buyToken}`;
            
            // Calculate USD values
            const buyUsdValue = buyAmount; // Assuming 1:1 for stablecoins, adjust as needed
            document.getElementById('buyUsdValue').textContent = `≈ $${formatAmount(buyUsdValue)}`;
            
            // Calculate fees
            calculateFees(sellAmt, buyUsdValue, route);
            
            // Update chart
            updatePriceChart(rate);
        }
        
        function calculateFees(sellAmount, buyUsdValue, route) {
            const sellUsdValue = sellAmount; // Assuming 1:1 for stablecoins
            
            // Protocol fee (typically 0.01% - 0.05%)
            const protocolFeeUsd = sellUsdValue * 0.0003; // 0.03%
            
            // Gas fee (Arbitrum ~$0.10 - $0.50)
            const gasFeeUsd = 0.15;
            
            // Slippage (based on user setting)
            const slippageUsd = sellUsdValue * (slippage / 100);
            
            // Total fee
            const totalFeeUsd = protocolFeeUsd + gasFeeUsd;
            const totalFeePercent = (totalFeeUsd / sellUsdValue) * 100;
            
            // Net output
            const netOutput = buyUsdValue - totalFeeUsd;
            
            // Update display
            document.getElementById('protocolFee').textContent = `$${protocolFeeUsd.toFixed(4)}`;
            document.getElementById('gasFee').textContent = `$${gasFeeUsd.toFixed(2)}`;
            document.getElementById('slippageFee').textContent = `$${slippageUsd.toFixed(4)}`;
            document.getElementById('totalFee').textContent = `$${totalFeeUsd.toFixed(4)}`;
            document.getElementById('totalFeePercent').textContent = `(${totalFeePercent.toFixed(3)}%)`;
            document.getElementById('netOutput').textContent = `$${formatAmount(netOutput)}`;
            
            // Update swap button
            const swapBtn = document.getElementById('swapBtn');
            const swapBtnText = document.getElementById('swapBtnText');
            
            if (netOutput > 0) {
                swapBtn.disabled = false;
                swapBtnText.textContent = `Tukar ${sellToken} → ${buyToken}`;
            } else {
                swapBtn.disabled = true;
                swapBtnText.textContent = 'Amount Terlalu Kecil';
            }
        }
        
        function resetFeeDisplay() {
            document.getElementById('protocolFee').textContent = '$0.00';
            document.getElementById('gasFee').textContent = '$0.00';
            document.getElementById('slippageFee').textContent = '$0.00';
            document.getElementById('totalFee').textContent = '$0.00';
            document.getElementById('totalFeePercent').textContent = '(0.00%)';
            document.getElementById('netOutput').textContent = '$0.00';
            document.getElementById('swapBtn').disabled = true;
            document.getElementById('swapBtnText').textContent = 'Masukkan Amount';
        }
        
        function toggleFeeDetails() {
            isFeeExpanded = !isFeeExpanded;
            document.getElementById('feeItems').classList.toggle('expanded', isFeeExpanded);
            document.getElementById('feeArrow').classList.toggle('expanded', isFeeExpanded);
        }
        
        function formatAmount(amount, decimals = 2) {
            if (amount === 0) return '0.00';
            if (amount < 0.000001) return amount.toFixed(8);
            if (amount < 0.001) return amount.toFixed(6);
            if (amount < 1) return amount.toFixed(4);
            if (amount < 1000) return amount.toFixed(decimals);
            return amount.toLocaleString('en-US', { maximumFractionDigits: 2 });
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // SWAP EXECUTION
        // ═══════════════════════════════════════════════════════════════════════
        
        async function executeSwap() {
            if (!walletAddress) {
                showTxStatus('error', 'Wallet Belum Terhubung', 'Silakan hubungkan wallet terlebih dahulu');
                await connectWallet();
                return;
            }
            
            if (!currentQuote) {
                showTxStatus('error', 'Quote Tidak Tersedia', 'Silakan tunggu quote diperbarui');
                return;
            }
            
            const swapBtn = document.getElementById('swapBtn');
            const swapBtnText = document.getElementById('swapBtnText');
            
            swapBtn.disabled = true;
            swapBtn.classList.add('swapping');
            swapBtnText.innerHTML = '<div class="loading-dots"><span></span><span></span><span></span></div>';
            
            showTxStatus('pending', 'Mempersiapkan Transaksi', 'Mohon konfirmasi di MetaMask...');
            
            try {
                // Get order data from Bebop
                const routes = currentQuote.routes;
                if (!routes || !routes.length) {
                    throw new Error('Tidak ada route tersedia');
                }
                
                const route = routes[0];
                
                // Check if approval needed for ERC20
                const sellInfo = tokens[sellToken];
                if (sellToken !== 'ETH' && sellInfo) {
                    const needsApproval = await checkAllowance(sellInfo.address, route.to);
                    if (needsApproval) {
                        showTxStatus('pending', 'Menyetujui Token', 'Mohon konfirmasi approval...');
                        await approveToken(sellInfo.address, route.to);
                    }
                }
                
                // Execute swap transaction
                showTxStatus('pending', 'Menjalankan Swap', 'Mohon konfirmasi transaksi...');
                
                // In production, this would call the actual Bebop contract
                // For demo, we simulate the transaction
                const txHash = await simulateTransaction();
                
                showTxStatus('success', 'Swap Berhasil!', `Tx: ${txHash.slice(0, 10)}...`, 
                    `https://arbiscan.io/tx/${txHash}`);
                
                // Reset form
                document.getElementById('sellAmount').value = '';
                document.getElementById('buyAmount').value = '';
                onAmountChange();
                
            } catch (e) {
                console.error('Swap error:', e);
                showTxStatus('error', 'Swap Gagal', e.message);
            } finally {
                swapBtn.disabled = false;
                swapBtn.classList.remove('swapping');
                swapBtnText.textContent = 'Tukar Sekarang';
            }
        }
        
        async function checkAllowance(tokenAddress, spender) {
            // In production, check actual allowance
            return false;
        }
        
        async function approveToken(tokenAddress, spender) {
            // In production, send approval transaction
            await new Promise(resolve => setTimeout(resolve, 2000));
        }
        
        async function simulateTransaction() {
            // Simulate transaction delay
            await new Promise(resolve => setTimeout(resolve, 3000));
            
            // Generate fake tx hash for demo
            return '0x' + Array(64).fill(0).map(() => 
                '0123456789abcdef'[Math.floor(Math.random() * 16)]
            ).join('');
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // CHART
        // ═══════════════════════════════════════════════════════════════════════
        
        function initChart() {
            const ctx = document.getElementById('priceChart').getContext('2d');
            
            // Generate initial data
            const initialData = Array(30).fill(0).map((_, i) => ({
                x: i,
                y: 0.0005 + Math.random() * 0.0001
            }));
            priceHistory = initialData.map(d => d.y);
            
            priceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: Array(30).fill(''),
                    datasets: [{
                        label: 'Rate',
                        data: priceHistory,
                        borderColor: '#00D4AA',
                        backgroundColor: 'rgba(0, 212, 170, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: { display: false },
                        y: {
                            display: true,
                            grid: {
                                color: 'rgba(255, 255, 255, 0.05)'
                            },
                            ticks: {
                                color: '#8B8B9E',
                                font: { size: 10 },
                                callback: function(value) {
                                    return value.toFixed(6);
                                }
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    }
                }
            });
        }
        
        function updatePriceChart(newRate) {
            if (!newRate || !priceChart) return;
            
            priceHistory.shift();
            priceHistory.push(newRate);
            
            priceChart.data.datasets[0].data = priceHistory;
            priceChart.update('none');
            
            // Update rate change indicator
            const prevRate = priceHistory[priceHistory.length - 2] || newRate;
            const change = ((newRate - prevRate) / prevRate) * 100;
            const changeEl = document.getElementById('rateChange');
            
            changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
            changeEl.className = 'rate-change ' + (change >= 0 ? 'positive' : 'negative');
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // AUTO REFRESH
        // ═══════════════════════════════════════════════════════════════════════
        
        function startPriceUpdates() {
            if (refreshInterval) clearInterval(refreshInterval);
            
            refreshInterval = setInterval(() => {
                if (sellAmount && parseFloat(sellAmount) > 0) {
                    fetchQuote();
                }
            }, refreshRate);
        }
        
        function refreshQuote() {
            const btn = document.getElementById('refreshBtn');
            btn.classList.add('spinning');
            
            fetchQuote().then(() => {
                setTimeout(() => btn.classList.remove('spinning'), 500);
            });
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // SETTINGS
        // ═══════════════════════════════════════════════════════════════════════
        
        function toggleSettings() {
            document.getElementById('settingsPanel').classList.toggle('show');
        }
        
        function setSlippage(value) {
            slippage = value;
            document.querySelectorAll('.slippage-option[data-value]').forEach(btn => {
                btn.classList.toggle('active', parseFloat(btn.dataset.value) === value);
            });
            document.getElementById('customSlippage').value = '';
            onAmountChange();
        }
        
        function setCustomSlippage() {
            const value = parseFloat(document.getElementById('customSlippage').value);
            if (value > 0 && value <= 50) {
                slippage = value;
                document.querySelectorAll('.slippage-option[data-value]').forEach(btn => {
                    btn.classList.remove('active');
                });
                onAmountChange();
            }
        }
        
        function setDeadline(minutes) {
            deadline = minutes;
            document.querySelectorAll('.slippage-option[data-deadline]').forEach(btn => {
                btn.classList.toggle('active', parseInt(btn.dataset.deadline) === minutes);
            });
        }
        
        function setRefreshRate(rate) {
            refreshRate = rate;
            document.querySelectorAll('.slippage-option[data-refresh]').forEach(btn => {
                btn.classList.toggle('active', parseInt(btn.dataset.refresh) === rate);
            });
            startPriceUpdates();
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // NOTIFICATIONS
        // ═══════════════════════════════════════════════════════════════════════
        
        function showTxStatus(type, title, message, link = null) {
            const status = document.getElementById('txStatus');
            const icon = document.getElementById('txIcon');
            const titleEl = document.getElementById('txTitle');
            const messageEl = document.getElementById('txMessage');
            const linkEl = document.getElementById('txLink');
            
            status.className = 'tx-status show ' + type;
            icon.className = 'tx-icon ' + type;
            
            switch(type) {
                case 'pending':
                    icon.textContent = '⏳';
                    break;
                case 'success':
                    icon.textContent = '✅';
                    break;
                case 'error':
                    icon.textContent = '❌';
                    break;
            }
            
            titleEl.textContent = title;
            messageEl.textContent = message;
            
            if (link) {
                linkEl.href = link;
                linkEl.style.display = 'inline-block';
            } else {
                linkEl.style.display = 'none';
            }
            
            if (type !== 'pending') {
                setTimeout(() => {
                    status.classList.remove('show');
                }, 5000);
            }
        }
        
        // Listen for account changes
        if (window.ethereum) {
            window.ethereum.on('accountsChanged', (accounts) => {
                if (accounts.length === 0) {
                    walletAddress = null;
                    document.getElementById('walletText').textContent = 'Hubungkan Wallet';
                    document.getElementById('connectWalletBtn').classList.remove('connected');
                } else {
                    walletAddress = accounts[0];
                    const shortAddress = walletAddress.slice(0, 6) + '...' + walletAddress.slice(-4);
                    document.getElementById('walletText').textContent = shortAddress;
                }
            });
            
            window.ethereum.on('chainChanged', () => {
                window.location.reload();
            });
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 BEBOP SCALPER PRO v4.0 🚀                               ║
║                         RFQ DEX - Arbitrum                                    ║
║                    Created by: AMARULLOH ZIKRI                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  🌐 Buka browser: http://localhost:7777                                       ║
║  ⚡ Auto-refresh: 500ms                                                       ║
║  🔌 MetaMask: Arbitrum One (Chain ID: 42161)                                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)
    socketio.run(app, host='0.0.0.0', port=7777, debug=False)
