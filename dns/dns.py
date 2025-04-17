"""
Basic 'DNS' server for our SMTP implementation
Author: Caleb Naeger - cmn4315@rit.edu
"""

import json
import socket


class DNS:
    def __init__(self) -> None:
        with open("dns_table.json") as f:
            self.table = json.load(f)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("127.0.0.1", 8080))


    def run(self):
        while(True):
            self.socket.listen()
            client, addr = self.socket.accept()
            data = client.recv(1024)
            data = data.decode().split(" ")

            if data[0].startswith("REQ"):
                client.sendall(self.table[data[1]].encode())
            elif data[0].startswith("UPDATE"):
                self.table[data[1]] = addr
                with open("dns_table.json") as f:
                    json.dump(self.table, f, indent=4, ensure_ascii=False)

            client.close()

def main():
    dns = DNS()
    dns.run()

if __name__ == "__main__":
    main()
