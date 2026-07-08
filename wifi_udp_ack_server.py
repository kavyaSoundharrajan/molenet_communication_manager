import socket

HOST = "0.0.0.0"
PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print("WiFi UDP ACK server listening on port", PORT)

while True:

    data, addr = sock.recvfrom(2048)

    msg = data.decode(errors="ignore")

    print("\nRX from", addr)
    print("MSG:", msg)

    parts = msg.split("|")

    if len(parts) >= 3 and parts[0] == "DATA":

        seq = parts[2]

        ack = "WIFI_ACK:%s" % seq

        sock.sendto(ack.encode(), addr)

        print("TX:", ack)

    else:
        print("Invalid packet")