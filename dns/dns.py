"""
Basic 'DNS' server for our SMTP implementation
Author: Caleb Naeger - cmn4315@rit.edu
"""

import json
import socket

def dns_lookup(dns_ip, dns_port, domain):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((dns_ip, dns_port))
        s.sendall(f"REQ {domain}".encode())
        ret = s.recv(1024).decode()
        if not ret.startswith("ERROR"):
            s.close()
            return ret
        else:
            s.close()
            print(f"DNS Couldn't resolve hostname {domain}")
            return None
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

def dns_update(dns_ip, dns_port, domain, my_ip, my_port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((dns_ip, dns_port))
        s.sendall(f"UPDATE {domain} {my_ip} {my_port}".encode())
        s.close()
    except Exception as e:
        print(f"Connection failed: {e}")

class DNS:
    def __init__(self) -> None:
        with open("dns_table.json", "r") as f:
            self.table = json.load(f)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("127.0.0.1", 8080))


    def run(self):
        try:
            while(True):
                self.socket.listen()
                client, addr = self.socket.accept()
                data = client.recv(1024)
                data = data.decode().split(" ")

                if data[0].startswith("REQ"):
                    if data[1] in self.table:
                        client.sendall(f"{self.table[data[1]][0]} {self.table[data[1]][1]}".encode())
                    else: 
                        client.sendall("ERROR Could not resolve hostname".encode())
                elif data[0].startswith("UPDATE"):
                    self.table[data[1]] = (data[2], int(data[3]))
                    with open("dns_table.json", "w") as f:
                        json.dump(self.table, f, indent=4, ensure_ascii=False)

                client.close()
                print("Client closed")
        except Exception as e:
            self.socket.close()
            raise e

def main():
    dns = DNS()
    dns.run()

if __name__ == "__main__":
    main()
