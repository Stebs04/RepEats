import socket, time, webbrowser 
for _ in range(60): 
    if socket.socket().connect_ex(('127.0.0.1', 8000)) == 0: 
        webbrowser.open('http://127.0.0.1:8000') 
        break 
    time.sleep(0.5) 
