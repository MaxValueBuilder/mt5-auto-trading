from telethon import TelegramClient, events
import asyncio
import requests
from datetime import datetime, timedelta, timezone
from PIL import Image
import pytesseract
import os, math
import csv
import threading

api_id = 29890827  # Replace with your Telegram API ID
api_hash = '36b3a6f3363bf18ea98461a9a53a79d6'  # Replace with your Telegram API hash
phone_number = '+4917684323760'  # Replace with your phone number
channel_id_1 = -1001490464609      # M15 Signals premium
channel_id_2 = -1001286966173      # Forex Signals

login = 168283          # change with your mt4 account id
password = 'Maschinen00.,'      # change with your mt4 account password
broker = 'Pepperstone-Edge01'      # change with your broker name
account_token = None
token_update_time = 1200
max_loss = 10               # change with your max loss amount in dollars 
pip_value = 100000           # default - Pip Value per Standard Lot
modified_tickets = []

# CSV file configuration
csv_filename = 'trading_history.csv'
csv_lock = threading.Lock()

client = TelegramClient('token', api_id, api_hash)

def initialize_csv():
    """Initialize CSV file with headers if it doesn't exist"""
    if not os.path.exists(csv_filename):
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'log_type', 'timestamp', 'date', 'time', 'symbol', 'order_type', 'original_order_type',
                'lot_size', 'open_price', 'take_profit', 'stop_loss', 'channel_source',
                'order_status', 'tp1', 'tp2', 'tp3', 'max_loss_used', 'pip_value_used', 'real_profit'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

def record_history_to_csv(trade_data):
    """Record trade data to CSV file"""
    with csv_lock:
        try:
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'log_type', 'timestamp', 'date', 'time', 'symbol', 'order_type', 'original_order_type',
                    'lot_size', 'open_price', 'take_profit', 'stop_loss', 'channel_source',
                    'order_status', 'tp1', 'tp2', 'tp3', 'max_loss_used', 'pip_value_used', 'real_profit'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow(trade_data)
            print(f"📝 Trade recorded to CSV: long_type -> {trade_data['log_type']}: {trade_data['symbol']} {trade_data['order_type']}")
        except Exception as e:
            print(f"❌ Error writing to CSV: {e}")

async def get_token(login, password, broker):
    searchResponse = requests.get('http://138.201.123.93:3575/Search', params={'company': broker})
    if searchResponse.status_code == 200:
        data = searchResponse.json()
        connected = False
        if data:
            access = [b['access'] for b in data[0]['results'] if b['name'] == broker]
            if not access:
                print('❌ No broker found for the given name.')
            else:
                for hostURL in access[0]:
                    host = hostURL.split(':')[0]
                    port = int(hostURL.split(':')[1])
                    if host and port:
                        connectionResponse = requests.get('http://138.201.123.93:3575/Connect', params={'user': login, 'password': password, 'host': host, 'port': port})
                        if connected == False and connectionResponse.status_code == 200:
                            connected = True
                            return connectionResponse.text
                        else:
                            print(connectionResponse)
        else:
            print("❌ Empty for the given broker name.")
    else:
        print("❌ Error occurred while fetching broker data.")
    return ''

async def order_send(token, symbol, type, lot, open_price, tp, sl):
    def send_order():
        timenow = datetime.now(timezone.utc).replace(tzinfo=None)
        expiration_time = timenow + timedelta(hours=3, minutes=10)
        expiration_time_str = expiration_time.strftime("%Y-%m-%dT%H:%M:%S")  
        if type == 'BuyLimit':
            orderResponseBuyLimit = requests.get('http://138.201.123.93:3575/OrderSend', params={
                'id': token, 'symbol': symbol, 'operation': type, 'volume': lot, 'price': open_price, 'takeprofit': tp, 'stoploss': sl, 'expiration': expiration_time_str})
            if orderResponseBuyLimit.status_code == 200:
                data = orderResponseBuyLimit.json()
                if data['type'] == type:
                    return type
                else:
                    return None
            else:
                orderResponseBuyStop = requests.get('http://138.201.123.93:3575/OrderSend', params={
                    'id': token, 'symbol': symbol, 'operation': 'BuyStop', 'volume': lot, 'price': open_price, 'takeprofit': tp, 'stoploss': sl, 'expiration': expiration_time_str})
                if orderResponseBuyStop.status_code == 200:
                    data = orderResponseBuyStop.json()
                    if data['type'] == 'BuyStop':
                        return 'BuyStop'
                    else:
                        return None
                else:
                    return None
        elif type == 'SellLimit':
            orderResponseSellLimit = requests.get('http://138.201.123.93:3575/OrderSend', params={
                'id': token, 'symbol': symbol, 'operation': type, 'volume': lot, 'price': open_price, 'takeprofit': tp, 'stoploss': sl, 'expiration': expiration_time_str})
            if orderResponseSellLimit.status_code == 200:
                data = orderResponseSellLimit.json()
                if data['type'] == type:
                    return type
                else:
                    return None
            else:
                orderResponseSellStop = requests.get('http://138.201.123.93:3575/OrderSend', params={
                    'id': token, 'symbol': symbol, 'operation': 'SellStop', 'volume': lot, 'price': open_price, 'takeprofit': tp, 'stoploss': sl, 'expiration': expiration_time_str})
                if orderResponseSellStop.status_code == 200:
                    data = orderResponseSellStop.json()
                    if data['type'] == 'SellStop':
                        return 'SellStop'
                    else:
                        return None
                else:
                    return None
    return await asyncio.to_thread(send_order)

    
@client.on(events.NewMessage(chats=[channel_id_1, channel_id_2]))
async def handler(event):
    chat_id = event.chat_id
    channel_source = "M15 Signals Premium" if chat_id == channel_id_1 else "Forex Signals"
    print(f"Message from {channel_source} Channel")
    
    global account_token
    if not account_token:
        print("❌ No account token available.")
        return
    message = event.message.message
    current_time = datetime.now()
    
    try:
        if 'SL' in message and 'TP' in message:
            if 'Ref#:' in message and ('Long' in message or 'Short' in message):
                snip = message.split('\n')
                trade_index = None
                for i, line in enumerate(snip):
                    if 'Ref#' in line:
                        trade_index = i
                        break
                print('index of Ref#-> ', trade_index)
                symbol = snip[trade_index - 6].split(' ')[0]
                original_order_type = snip[trade_index - 6].split(' ')[1]
                order_type = 'BuyLimit' if original_order_type == 'Long' else 'SellLimit'
                emoji = '🟢' if order_type == 'BuyLimit' else '🔴'
                open_price = snip[trade_index - 5].split(':')[1].strip()
                SL = snip[trade_index - 4].split(':')[1].strip().split(' ')[0].strip()
                TP1 = snip[trade_index - 3].split('TP:')[1].strip()
                TP2 = snip[trade_index - 2].split('TP:')[1].strip()
                TP3 = snip[trade_index - 1].split('TP:')[1].strip()
                
                formula1 = (float(max_loss)) / (abs(float(SL) - float(open_price)) * float(pip_value))
                formula2 = (float(max_loss)) / (abs(float(SL) - float(open_price)) * float(pip_value) / float(150))
                lot_size = (float(max_loss)) / (abs(float(SL) - float(open_price)) * float(pip_value))
                lot_size = formula2 if symbol.endswith('JPY') else formula1
                lot_size = math.floor(lot_size * 100) / 100

                if symbol.endswith('JPY'):
                    if(abs(float(SL) - float(open_price)) > 0.7):
                        SL = SL - ((abs(float(SL) - float(open_price))) - 0.7)
                else:
                    if(abs(float(SL) - float(open_price)) > 0.007):
                        SL = SL - ((abs(float(SL) - float(open_price))) - 0.007)
                
                order_state = await order_send(account_token, symbol, order_type, lot_size, float(open_price), float(TP3), float(SL))
                
                if order_state:
                    # Prepare trade data for CSV
                    trade_data = {
                        'log_type': 'open order',
                        'timestamp': current_time.isoformat(),
                        'date': current_time.strftime('%Y-%m-%d'),
                        'time': current_time.strftime('%H:%M:%S'),
                        'symbol': symbol,
                        'order_type': order_state if order_state else order_type,
                        'original_order_type': original_order_type,
                        'lot_size': lot_size,
                        'open_price': open_price,
                        'take_profit': TP3,
                        'stop_loss': SL,
                        'channel_source': channel_source,
                        'order_status': 'SUCCESS' if order_state else 'FAILED',
                        'tp1': TP1,
                        'tp2': TP2,
                        'tp3': TP3,
                        'max_loss_used': max_loss,
                        'pip_value_used': pip_value,
                        'real_profit': ''
                    }
                    
                    # Record to CSV
                    record_history_to_csv(trade_data)
                    print(f'{emoji} {order_state} {symbol} at {open_price} with {lot_size} lots | TP: {TP3} | SL: {SL} | ({current_time})')
                else:
                    print(f'❌ {order_state} order opening failed -> ({datetime.now()}) {symbol}, {order_type}, {lot_size}, {float(open_price)}, {float(TP3)}, {float(SL)}')
                    
            elif 'SELL' in message or 'BUY' in message:
                symbol = None
                if event.message.photo:
                    filename = f"photo_{event.message.id}.jpg"
                    file_path = await event.message.download_media(file=filename)
                    try:
                        image = Image.open(file_path)
                        text = pytesseract.image_to_string(image)
                        lines = text.splitlines()
                        symbolSnip = [ line for line in lines if '/' in line ]
                        symbolPair1 = symbolSnip[0].split('/')[0].strip()
                        symbolPair2 = symbolSnip[0].split('/')[1].strip()
                        symbol = symbolPair1 + symbolPair2
                    except Exception as e:
                        print(f"Error processing image: {e}")
                        return
                    finally:
                        image.close()
                        if os.path.exists(file_path):
                            os.remove(file_path)
                else:
                    print("No symbol photo in this message.")
                    return
                    
                snip = message.split('\n')
                original_order_type = snip[0].split(' ')[0].strip()
                order_type = 'BuyLimit' if original_order_type == 'BUY' else 'SellLimit'
                emoji = '🟢' if order_type == 'BuyLimit' else '🔴'
                open_price = snip[0].split(' ')[1].strip()
                SL = snip[5].split(' ')[1].strip()
                TP1 = snip[2].split(' ')[1].strip()
                TP2 = snip[3].split(' ')[1].strip()
                TP3 = snip[4].split(' ')[1].strip()
                
                formula1 = (float(max_loss)) / (abs(float(SL) - float(open_price)) * float(pip_value))
                formula2 = (float(max_loss)) / (abs(float(SL) - float(open_price)) * float(pip_value) / float(150))
                lot_size = (float(max_loss)) / (abs(float(SL) - float(open_price)) * float(pip_value))
                lot_size = formula2 if symbol.endswith('JPY') else formula1
                lot_size = math.floor(lot_size * 100) / 100

                if symbol.endswith('JPY'):
                    if(abs(float(SL) - float(open_price)) > 0.7):
                        SL = SL - ((abs(float(SL) - float(open_price))) - 0.7)
                else:
                    if(abs(float(SL) - float(open_price)) > 0.007):
                        SL = SL - ((abs(float(SL) - float(open_price))) - 0.007)
                
                order_state = await order_send(account_token, symbol, order_type, lot_size, float(open_price), float(TP3), float(SL))
                
                if order_state:
                    # Prepare trade data for CSV
                    trade_data = {
                        'log_type': 'open order',
                        'timestamp': current_time.isoformat(),
                        'date': current_time.strftime('%Y-%m-%d'),
                        'time': current_time.strftime('%H:%M:%S'),
                        'symbol': symbol,
                        'order_type': order_state if order_state else order_type,
                        'original_order_type': original_order_type,
                        'lot_size': lot_size,
                        'open_price': open_price,
                        'take_profit': TP3,
                        'stop_loss': SL,
                        'channel_source': channel_source,
                        'order_status': 'SUCCESS' if order_state else 'FAILED',
                        'tp1': TP1,
                        'tp2': TP2,
                        'tp3': TP3,
                        'max_loss_used': max_loss,
                        'pip_value_used': pip_value,
                        'real_profit': ''
                    }
                    
                    # Record to CSV
                    record_history_to_csv(trade_data)
                    print(f'{emoji} {order_state} {symbol} at {open_price} with {lot_size} lots | TP: {TP3} | SL: {SL} | ({current_time})')
                else:
                    print(f'❌ {order_state} order opening failed -> ({datetime.now()}) {symbol}, {order_type}, {lot_size}, {float(open_price)}, {float(TP3)}, {float(SL)}')
            else:
                print('❌ No Trading Signal')
        else:
            print('❌ Never Trading Signal')
    except Exception as e:
        print(f"❌ Error processing message: {e}")
        return

async def update_token_periodically():
    global account_token
    while True:
        token = await get_token(login, password, broker)
        if token:
            print(f"✅ Account Token Updated ({token}) -> {datetime.now()}")
            account_token = token
        else:
            print("❌ Failed to update account token.")
        await asyncio.sleep(token_update_time)

async def opened_order_monitoring():
    global account_token
    global modified_tickets
    while True:
        try:
            if account_token:
                openedOrdersResponse = requests.get('http://138.201.123.93:3575/OpenedOrders', params={'id': account_token})
                if openedOrdersResponse.status_code == 200:
                    openedOrders = openedOrdersResponse.json()
                    for order in openedOrders:
                        if order['type'] == 'Buy' and order['ticket'] not in modified_tickets:
                            if (order['openPrice'] - order['closePrice']) < 0 and abs(order['openPrice'] - order['closePrice']) > abs(order['openPrice'] - order['stopLoss']):
                                modifyResponse = requests.get('http://138.201.123.93:3575/OrderModify', params={
                                    'id': account_token, 'ticket': order['ticket'], 'stoploss': order['openPrice'], 'takeprofit': order['takeProfit']})
                                if modifyResponse.status_code == 200:
                                    current_time = datetime.now()
                                    # Prepare trade data for CSV
                                    trade_data = {
                                        'log_type': 'modify order',
                                        'timestamp': current_time.isoformat(),
                                        'date': current_time.strftime('%Y-%m-%d'),
                                        'time': current_time.strftime('%H:%M:%S'),
                                        'symbol': order['symbol'],
                                        'order_type': order['type'],
                                        'original_order_type': 'cancelled',
                                        'lot_size': order['lots'],
                                        'open_price': order['openPrice'],
                                        'take_profit': order['takeProfit'],
                                        'stop_loss': order['openPrice'],
                                        'channel_source': '',
                                        'order_status': 'SUCCESS',
                                        'tp1': '',
                                        'tp2': '',
                                        'tp3': '',
                                        'max_loss_used': max_loss,
                                        'pip_value_used': pip_value,
                                        'real_profit': order['profit'] + order['commission']
                                    }
                                    
                                    # Record to CSV
                                    record_history_to_csv(trade_data)
                                    logs = f"🎨 ticket: {order['ticket']}, {order['symbol']} {order['type']} order modified with tp: {order['takeProfit']}, sl: {order['openPrice']}"
                                    modified_tickets.append(order['ticket'])
                                    print(logs)
                        elif order['type'] == 'Sell' and order['ticket'] not in modified_tickets:
                            if (order['openPrice'] - order['closePrice']) > 0 and abs(order['openPrice'] - order['closePrice']) > abs(order['openPrice'] - order['stopLoss']):
                                modifyResponse = requests.get('http://138.201.123.93:3575/OrderModify', params={
                                    'id': account_token, 'ticket': order['ticket'], 'stoploss': order['openPrice'], 'takeprofit': order['takeProfit']})
                                if modifyResponse.status_code == 200:
                                    current_time = datetime.now()
                                    # Prepare trade data for CSV
                                    trade_data = {
                                        'log_type': 'modify order',
                                        'timestamp': current_time.isoformat(),
                                        'date': current_time.strftime('%Y-%m-%d'),
                                        'time': current_time.strftime('%H:%M:%S'),
                                        'symbol': order['symbol'],
                                        'order_type': order['type'],
                                        'original_order_type': 'cancelled',
                                        'lot_size': order['lots'],
                                        'open_price': order['openPrice'],
                                        'take_profit': order['takeProfit'],
                                        'stop_loss': order['openPrice'],
                                        'channel_source': '',
                                        'order_status': 'SUCCESS',
                                        'tp1': '',
                                        'tp2': '',
                                        'tp3': '',
                                        'max_loss_used': max_loss,
                                        'pip_value_used': 10.0,  # $10 per standard lot
                                        'real_profit': order['profit'] + order['commission']
                                    }
                                    
                                    # Record to CSV
                                    record_history_to_csv(trade_data)
                                    logs = f"🎨 ticket: {order['ticket']}, {order['symbol']} {order['type']} order modified with tp: {order['takeProfit']}, sl: {order['openPrice']}"
                                    modified_tickets.append(order['ticket'])
                                    print(logs)
            await asyncio.sleep(5)
        except Exception as e:
            print('order monitoring ...')
            await asyncio.sleep(5)
            pass

async def closed_order_monitoring():
    global account_token
    timenow = datetime.now(timezone.utc).replace(tzinfo=None)
    start_time = timenow + timedelta(hours=3)
    start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
    init_order_num = 0
    while True:
        try:
            if account_token:
                closedOrderResponse = requests.get('http://138.201.123.93:3575/OrderHistory', params={'id': account_token, 'from': start_time_str})
                if closedOrderResponse.status_code == 200:
                    closedOrders = closedOrderResponse.json()
                    if closedOrders and init_order_num != len(closedOrders):
                        init_order_num = len(closedOrders)
                        order = closedOrders[-1]
                        # for order in closedOrders:
                        if order['type'] == 'Buy' or order['type'] == "Sell":
                            current_time = datetime.now()
                            # Prepare trade data for CSV
                            trade_data = {
                                'log_type': 'closed order',
                                'timestamp': current_time.isoformat(),
                                'date': current_time.strftime('%Y-%m-%d'),
                                'time': current_time.strftime('%H:%M:%S'),
                                'symbol': order['symbol'],
                                'order_type': order['type'],
                                'original_order_type': '',
                                'lot_size': order['lots'],
                                'open_price': order['openPrice'],
                                'take_profit': order['takeProfit'],
                                'stop_loss': order['stopLoss'],
                                'channel_source': '',
                                'order_status': 'SUCCESS',
                                'tp1': '',
                                'tp2': '',
                                'tp3': '',
                                'max_loss_used': max_loss,
                                'pip_value_used': pip_value,
                                'real_profit': order['profit'] + order['commission']
                            }
                            
                            # Record to CSV
                            record_history_to_csv(trade_data)
                            logs = f'💲 ticket: {order['ticket']}, {order['symbol']} {order['type']} order closed with commission: {order['commission']}, profit: {order['profit']}, real_profit: {order['profit'] + order['commission']}' 
                            print(logs)
                        elif order['type'] == 'SellLimit' or order['type'] == 'SellStop' or order['type'] == 'BuyLimit' or order['type'] == 'BuyStop':
                            current_time = datetime.now()
                            # Prepare trade data for CSV
                            trade_data = {
                                'log_type': 'missed order',
                                'timestamp': current_time.isoformat(),
                                'date': current_time.strftime('%Y-%m-%d'),
                                'time': current_time.strftime('%H:%M:%S'),
                                'symbol': order['symbol'],
                                'order_type': order['type'],
                                'original_order_type': 'cancelled',
                                'lot_size': order['lots'],
                                'open_price': order['openPrice'],
                                'take_profit': order['takeProfit'],
                                'stop_loss': order['stopLoss'],
                                'channel_source': '',
                                'order_status': 'SUCCESS',
                                'tp1': '',
                                'tp2': '',
                                'tp3': '',
                                'max_loss_used': max_loss,
                                'pip_value_used': pip_value,
                                'real_profit': order['profit'] + order['commission']
                            }
                            
                            # Record to CSV
                            record_history_to_csv(trade_data)
                            logs = f'❗ ticket: {order['ticket']}, {order['symbol']} {order['type']} order missed/cancelled' 
                            print(logs)
            await asyncio.sleep(5)
        except Exception as e:
            print('order monitoring ...')
            await asyncio.sleep(5)
            pass

async def main():
    global account_token
    
    # Initialize CSV file
    initialize_csv()
    print(f"📊 CSV trading history will be saved to: {csv_filename}")
    
    account_token = await get_token(login, password, broker)
    if not account_token:
        print("❌ Failed to get initial account token. Exiting.")
        return
    await client.start(phone=phone_number)
    print('Logged in successfully')
    print('Listening for new messages...')
    update_task = asyncio.create_task(update_token_periodically())
    opened_order_monitor_task = asyncio.create_task(opened_order_monitoring())
    closed_order_monitor_task = asyncio.create_task(closed_order_monitoring())
    try:
        await asyncio.gather(update_task, opened_order_monitor_task, closed_order_monitor_task)
    except Exception as e:
        print(f"Error in main tasks: {e}")
    finally:
        await client.disconnect()

if __name__ == '__main__':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
       
    asyncio.run(main())
