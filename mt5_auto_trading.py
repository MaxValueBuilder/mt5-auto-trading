from telethon import TelegramClient, events
import asyncio
import MetaTrader5 as mt5
from datetime import datetime, timedelta, timezone
from PIL import Image
import pytesseract
import os, math
import csv
import threading
import time

# Telegram Configuration
api_id = 23768637  # Replace with your Telegram API ID
api_hash = '0bd0cf722ff69125fc5872d7b34d518b'  # Replace with your Telegram API hash
phone_number = '+380668270383'  # Replace with your phone number
channel_id_1 = -1002573527842      # M15 Signals premium
channel_id_2 = -1001286966173      # Forex Signals

# MT5 Configuration
login = 95580237          # change with your mt5 account id
password = '-t1nAmNx'      # change with your mt5 account password
server = 'MetaQuotes-Demo'      # change with your broker server name
max_loss = 100               # change with your max loss amount in dollars 
# pip_value removed - will be calculated dynamically per symbol
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
            print(f"📝 Trade recorded to CSV: log_type -> {trade_data['log_type']}: {trade_data['symbol']} {trade_data['order_type']}")
        except Exception as e:
            print(f"❌ Error writing to CSV: {e}")

def connect_mt5():
    """Connect to MT5 terminal"""
    if not mt5.initialize():
        print("❌ MT5 initialization failed")
        return False
    
    # Login to MT5 account
    if not mt5.login(login=login, password=password, server=server):
        print("❌ MT5 login failed")
        mt5.shutdown()
        return False
    
    print("✅ MT5 connected successfully")
    return True

def disconnect_mt5():
    """Disconnect from MT5 terminal"""
    mt5.shutdown()
    print("🔌 MT5 disconnected")

def get_symbol_info(symbol):
    """Get symbol information from MT5"""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"❌ Symbol {symbol} not found")
        return None
    return symbol_info

def calculate_lot_size(symbol, open_price, stop_loss):
    """Calculate lot size based on max loss and stop loss distance"""
    symbol_info = get_symbol_info(symbol)
    if not symbol_info:
        return 0.01  # Default minimum lot size
    
    # Calculate stop loss distance in pips
    if symbol.endswith('JPY'):
        sl_distance = abs(float(stop_loss) - float(open_price)) * 100  # JPY pairs
    else:
        sl_distance = abs(float(stop_loss) - float(open_price)) * 10000  # Other pairs
    
    # Calculate pip value for this specific symbol
    # For JPY pairs: 1 pip = $10 per standard lot
    # For other pairs: 1 pip = $10 per standard lot (but pip size is different)
    if symbol.endswith('JPY'):
        pip_value_per_lot = 10.0  # $10 per standard lot for JPY pairs
    else:
        pip_value_per_lot = 10.0  # $10 per standard lot for other pairs
    
    # Calculate lot size to achieve exactly $100 risk
    if sl_distance > 0:
        lot_size = max_loss / (sl_distance * pip_value_per_lot)
    else:
        lot_size = 0.01  # Default if no stop loss distance
    
    # Round to 2 decimal places
    lot_size = math.floor(lot_size * 100) / 100
    
    # Ensure lot size is within limits
    min_lot = symbol_info.volume_min
    max_lot = symbol_info.volume_max
    lot_step = symbol_info.volume_step
    
    lot_size = max(min_lot, min(max_lot, lot_size))
    lot_size = round(lot_size / lot_step) * lot_step
    
    return lot_size

def adjust_stop_loss(symbol, open_price, stop_loss):
    """Adjust stop loss based on symbol type"""
    if symbol.endswith('JPY'):
        if abs(float(stop_loss) - float(open_price)) > 0.7:
            stop_loss = float(stop_loss) - (abs(float(stop_loss) - float(open_price)) - 0.7)
    else:
        if abs(float(stop_loss) - float(open_price)) > 0.007:
            stop_loss = float(stop_loss) - (abs(float(stop_loss) - float(open_price)) - 0.007)
    
    return stop_loss

async def order_send(symbol, order_type, lot_size, open_price, tp, sl):
    """Send order to MT5"""
    def send_order():
        try:
            # Get current market price
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"❌ Cannot get current price for {symbol}")
                return None
            
            current_ask = tick.ask
            current_bid = tick.bid
            
            # Initialize variables
            order_type_mt5 = None
            action = None
            final_price = open_price  # Use a separate variable for the final price
            
            # Determine order type based on price vs current market
            if order_type == 'BuyLimit':
                if open_price < current_bid:
                    # Price is below current market - use BuyLimit
                    order_type_mt5 = mt5.ORDER_TYPE_BUY_LIMIT
                    action = mt5.TRADE_ACTION_PENDING
                    final_price = open_price
                else:
                    # Price is above current market - use market buy
                    order_type_mt5 = mt5.ORDER_TYPE_BUY
                    action = mt5.TRADE_ACTION_DEAL
                    final_price = current_ask  # Use current ask price
            else:  # SellLimit
                if open_price > current_ask:
                    # Price is above current market - use SellLimit
                    order_type_mt5 = mt5.ORDER_TYPE_SELL_LIMIT
                    action = mt5.TRADE_ACTION_PENDING
                    final_price = open_price
                else:
                    # Price is below current market - use market sell
                    order_type_mt5 = mt5.ORDER_TYPE_SELL
                    action = mt5.TRADE_ACTION_DEAL
                    final_price = current_bid  # Use current bid price
            
            # Prepare the order request
            request = {
                "action": action,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type_mt5,
                "price": final_price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 234000,
                "comment": "python script order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send the order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"❌ Order failed, return code: {result.retcode}")
                print(f"   Symbol: {symbol}")
                print(f"   Order Type: {order_type}")
                print(f"   Price: {final_price}")
                print(f"   Current Bid: {current_bid}, Current Ask: {current_ask}")
                print(f"   Error Description: {result.comment}")
                return None
            
            print(f"✅ Order sent successfully, ticket: {result.order}")
            print(f"   Symbol: {symbol}, Type: {order_type}, Price: {final_price}")
            return order_type
            
        except Exception as e:
            print(f"❌ Error sending order: {e}")
            return None
    
    return await asyncio.to_thread(send_order)

@client.on(events.NewMessage(chats=[channel_id_1, channel_id_2]))
async def handler(event):
    chat_id = event.chat_id
    channel_source = "M15 Signals Premium" if chat_id == channel_id_1 else "Forex Signals"
    print(f"Message from {channel_source} Channel")
    
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
                open_price = float(snip[trade_index - 5].split(':')[1].strip())
                SL = float(snip[trade_index - 4].split(':')[1].strip().split(' ')[0].strip())
                TP1 = float(snip[trade_index - 3].split('TP:')[1].strip())
                TP2 = float(snip[trade_index - 2].split('TP:')[1].strip())
                TP3 = float(snip[trade_index - 1].split('TP:')[1].strip())
                
                # Calculate lot size
                lot_size = calculate_lot_size(symbol, open_price, SL)
                
                # Adjust stop loss
                SL = adjust_stop_loss(symbol, open_price, SL)
                
                order_state = await order_send(symbol, order_type, lot_size, open_price, TP3, SL)
                
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
                        'pip_value_used': 10.0,  # $10 per standard lot
                        'real_profit': ''
                    }
                    
                    # Record to CSV
                    record_history_to_csv(trade_data)
                    print(f'{emoji} {order_state} {symbol} at {open_price} with {lot_size} lots | TP: {TP3} | SL: {SL} | ({current_time})')
                else:
                    print(f'❌ {order_state} order opening failed -> ({datetime.now()}) {symbol}, {order_type}, {lot_size}, {open_price}, {TP3}, {SL}')
                    
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
                open_price = float(snip[0].split(' ')[1].strip())
                SL = float(snip[5].split(' ')[1].strip())
                TP1 = float(snip[2].split(' ')[1].strip())
                TP2 = float(snip[3].split(' ')[1].strip())
                TP3 = float(snip[4].split(' ')[1].strip())
                
                # Calculate lot size
                lot_size = calculate_lot_size(symbol, open_price, SL)
                
                # Adjust stop loss
                SL = adjust_stop_loss(symbol, open_price, SL)
                
                order_state = await order_send(symbol, order_type, lot_size, open_price, TP3, SL)
                
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
                        'pip_value_used': 10.0,  # $10 per standard lot
                        'real_profit': ''
                    }
                    
                    # Record to CSV
                    record_history_to_csv(trade_data)
                    print(f'{emoji} {order_state} {symbol} at {open_price} with {lot_size} lots | TP: {TP3} | SL: {SL} | ({current_time})')
                else:
                    print(f'❌ {order_state} order opening failed -> ({datetime.now()}) {symbol}, {order_type}, {lot_size}, {open_price}, {TP3}, {SL}')
            else:
                print('❌ No Trading Signal')
        else:
            print('❌ Never Trading Signal')
    except Exception as e:
        print(f"❌ Error processing message: {e}")
        return

async def opened_order_monitoring():
    """Monitor and modify opened orders"""
    global modified_tickets
    while True:
        try:
            # Get opened positions
            positions = mt5.positions_get()
            if positions is None:
                print("❌ Failed to get positions")
                await asyncio.sleep(5)
                continue
            
            for position in positions:
                if position.ticket not in modified_tickets:
                    # Check if position needs modification (break-even logic)
                    current_price = mt5.symbol_info_tick(position.symbol).ask if position.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(position.symbol).bid
                    
                    if position.type == mt5.POSITION_TYPE_BUY:
                        if (position.price_open - current_price) < 0 and abs(position.price_open - current_price) > abs(position.price_open - position.sl):
                            # Modify to break-even
                            request = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": position.symbol,
                                "sl": position.price_open,
                                "tp": position.tp
                            }
                            result = mt5.order_send(request)
                            if result.retcode == mt5.TRADE_RETCODE_DONE:
                                current_time = datetime.now()
                                trade_data = {
                                    'log_type': 'modify order',
                                    'timestamp': current_time.isoformat(),
                                    'date': current_time.strftime('%Y-%m-%d'),
                                    'time': current_time.strftime('%H:%M:%S'),
                                    'symbol': position.symbol,
                                    'order_type': 'Buy',
                                    'original_order_type': 'cancelled',
                                    'lot_size': position.volume,
                                    'open_price': position.price_open,
                                    'take_profit': position.tp,
                                    'stop_loss': position.price_open,
                                    'channel_source': '',
                                    'order_status': 'SUCCESS',
                                    'tp1': '',
                                    'tp2': '',
                                    'tp3': '',
                                    'max_loss_used': max_loss,
                                    'pip_value_used': 10.0,  # $10 per standard lot
                                    'real_profit': position.profit + position.commission
                                }
                                record_history_to_csv(trade_data)
                                print(f'🎨 ticket: {position.ticket}, {position.symbol} Buy order modified with tp: {position.tp}, sl: {position.price_open}')
                                modified_tickets.append(position.ticket)
                    
                    elif position.type == mt5.POSITION_TYPE_SELL:
                        if (position.price_open - current_price) > 0 and abs(position.price_open - current_price) > abs(position.price_open - position.sl):
                            # Modify to break-even
                            request = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": position.symbol,
                                "sl": position.price_open,
                                "tp": position.tp
                            }
                            result = mt5.order_send(request)
                            if result.retcode == mt5.TRADE_RETCODE_DONE:
                                current_time = datetime.now()
                                trade_data = {
                                    'log_type': 'modify order',
                                    'timestamp': current_time.isoformat(),
                                    'date': current_time.strftime('%Y-%m-%d'),
                                    'time': current_time.strftime('%H:%M:%S'),
                                    'symbol': position.symbol,
                                    'order_type': 'Sell',
                                    'original_order_type': 'cancelled',
                                    'lot_size': position.volume,
                                    'open_price': position.price_open,
                                    'take_profit': position.tp,
                                    'stop_loss': position.price_open,
                                    'channel_source': '',
                                    'order_status': 'SUCCESS',
                                    'tp1': '',
                                    'tp2': '',
                                    'tp3': '',
                                    'max_loss_used': max_loss,
                                    'pip_value_used': 10.0,  # $10 per standard lot
                                    'real_profit': position.profit + position.commission
                                }
                                record_history_to_csv(trade_data)
                                print(f'🎨 ticket: {position.ticket}, {position.symbol} Sell order modified with tp: {position.tp}, sl: {position.price_open}')
                                modified_tickets.append(position.ticket)
            
            await asyncio.sleep(5)
        except Exception as e:
            print(f'❌ Error in opened order monitoring: {e}')
            await asyncio.sleep(5)

async def closed_order_monitoring():
    """Monitor closed orders and pending orders"""
    last_deals_count = 0
    while True:
        try:
            # Get deal history
            deals = mt5.history_deals_get(datetime.now() - timedelta(hours=1), datetime.now())
            if deals is None:
                print("❌ Failed to get deal history")
                await asyncio.sleep(5)
                continue
            
            if len(deals) > last_deals_count:
                # New deals found
                new_deals = deals[last_deals_count:]
                last_deals_count = len(deals)
                
                for deal in new_deals:
                    if deal.entry == mt5.DEAL_ENTRY_OUT:  # Closed position
                        current_time = datetime.now()
                        trade_data = {
                            'log_type': 'closed order',
                            'timestamp': current_time.isoformat(),
                            'date': current_time.strftime('%Y-%m-%d'),
                            'time': current_time.strftime('%H:%M:%S'),
                            'symbol': deal.symbol,
                            'order_type': 'Buy' if deal.type == mt5.DEAL_TYPE_BUY else 'Sell',
                            'original_order_type': '',
                            'lot_size': deal.volume,
                            'open_price': deal.price,
                            'take_profit': 0,  # Will be filled from position info if available
                            'stop_loss': 0,    # Will be filled from position info if available
                            'channel_source': '',
                            'order_status': 'SUCCESS',
                            'tp1': '',
                            'tp2': '',
                            'tp3': '',
                            'max_loss_used': max_loss,
                            'pip_value_used': 10.0,  # $10 per standard lot
                            'real_profit': deal.profit + deal.commission
                        }
                        record_history_to_csv(trade_data)
                        print(f'💲 ticket: {deal.ticket}, {deal.symbol} {deal.type} deal closed with commission: {deal.commission}, profit: {deal.profit}, real_profit: {deal.profit + deal.commission}')
            
            # Check for cancelled pending orders
            orders = mt5.orders_get()
            if orders is not None:
                for order in orders:
                    if order.state == mt5.ORDER_STATE_CANCELED:
                        current_time = datetime.now()
                        trade_data = {
                            'log_type': 'missed order',
                            'timestamp': current_time.isoformat(),
                            'date': current_time.strftime('%Y-%m-%d'),
                            'time': current_time.strftime('%H:%M:%S'),
                            'symbol': order.symbol,
                            'order_type': 'BuyLimit' if order.type == mt5.ORDER_TYPE_BUY_LIMIT else 'SellLimit',
                            'original_order_type': 'cancelled',
                            'lot_size': order.volume_initial,
                            'open_price': order.price_open,
                            'take_profit': order.price_tp,
                            'stop_loss': order.price_sl,
                            'channel_source': '',
                            'order_status': 'SUCCESS',
                            'tp1': '',
                            'tp2': '',
                            'tp3': '',
                            'max_loss_used': max_loss,
                            'pip_value_used': 10.0,  # $10 per standard lot
                            'real_profit': 0
                        }
                        record_history_to_csv(trade_data)
                        print(f'❗ ticket: {order.ticket}, {order.symbol} {order.type} order missed/cancelled')
            
            await asyncio.sleep(5)
        except Exception as e:
            print(f'❌ Error in closed order monitoring: {e}')
            await asyncio.sleep(5)

async def main():
    # Initialize CSV file
    initialize_csv()
    print(f"📊 CSV trading history will be saved to: {csv_filename}")
    
    # Connect to MT5
    if not connect_mt5():
        print("❌ Failed to connect to MT5. Exiting.")
        return
    
    try:
        await client.start(phone=phone_number)
        print('✅ Telegram logged in successfully')
        print('👂 Listening for new messages...')
        
        # Start monitoring tasks
        opened_order_monitor_task = asyncio.create_task(opened_order_monitoring())
        closed_order_monitor_task = asyncio.create_task(closed_order_monitoring())
        
        # Run all tasks
        await asyncio.gather(opened_order_monitor_task, closed_order_monitor_task)
        
    except Exception as e:
        print(f"❌ Error in main tasks: {e}")
    finally:
        await client.disconnect()
        disconnect_mt5()

if __name__ == '__main__':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    asyncio.run(main())
