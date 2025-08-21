shared_data = []

def add_data(row):
    print("[STORAGE] Adding row to shared_data")
    shared_data.append(row)
    print(f"[STORAGE] Total rows: {len(shared_data)}")
  
  
# New list for Telegram commands  
pending_commands = [] 
