"""
Basic 'DNS' server for our SMTP implementation
Author: Caleb Naeger - cmn4315@rit.edu and Landon Spitzer - lbs9440@rit.edu
"""

import json
import socket

def get_local_ip():
    """Returns the LAN IP address of the local machine.
    
    :return ip: The IP address of the local machine.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.0.8', 1027))
        ip = s.getsockname()[0]
    except socket.error:
        return None
    finally:
        s.close()
    return ip

def dns_lookup(dns_ip, dns_port, domain):
    """Returns the IP address and port of the server associated with the given domain name.
    
    :param dns_ip: The IP address of the DNS server.
    :param dns_port: The port of the DNS server.
    :param domain: The domain name of the server.
    :return ret: The IP address and port of the server associated with the given domain name. 
    """
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

def dns_update(dns_ip, dns_port, domain, my_port):
    """Updates the DNS server with the IP address and port of the server associated with the given domain name.
    
    :param dns_ip: The IP address of the DNS server.
    :param dns_port: The port of the DNS server.
    :param domain: The domain name of the server.
    :param my_port: The port of the server.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((dns_ip, dns_port))
        s.sendall(f"UPDATE {domain} {get_local_ip()} {my_port}".encode())
        s.close()
    except Exception as e:
        print(f"Connection failed: {e}")

class DNS:
    """DNS server for our SMTP implementation."""
    def __init__(self) -> None:
        """Initializes the DNS server."""
        with open("dns_table.json", "r") as f:
            self.table = json.load(f)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("0.0.0.0", 8080))


    def run(self):
        """Runs the DNS server.
        
        Listens for requests from the SMTP server and updates the DNS table accordingly.
        """
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
