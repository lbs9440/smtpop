"""
SMTP Server implementation
Author: Caleb Naeger - cmn4315@rit.edu
"""
from enum import Enum
import socket
import json
import select
import base64
import random

class States(Enum):
    INIT = "INIT"
    READY = "READY"
    DEST = "DEST"
    RCPT = "RCPT"
    AUTH_INIT = "AUTH_INIT"
    AUTH_USER = "AUTH_USER"
    AUTH_PW = "AUTH_PW"
    DATA = "DATA"

class Server:
    def __init__(self) -> None:
        self.clients = {}
        self.load_accounts("accounts.json")
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setblocking(False)
        self.server_sock.bind(('127.0.0.1', random.randint(5000, 8000)))
        self.inputs = [self.server_sock]

    def load_accounts(self, filename: str) -> None:
        with open(filename) as f:
            data = json.load(f)
            self.accounts = data

    def new_client(self):
        client, addr = self.server_sock.accept()
        client.setblocking(False)
        self.inputs.append(client)
        self.clients[client] = {"addr": addr, "buf": b"", "current_state": States.INIT, "dst": "", "from": b"", "msg": b""} # track the address, current buffer, and state machine state for the client

    def read_from_client(self, client):
        try:
            data = client.recv(1024)
            self.clients[client]["buf"] += data
            self.smtp_commands(client)
        except(ConnectionResetError):
            self.disconnect(client)

    def disconnect(self, client):
        del self.clients[client]
        self.inputs.remove(client)
        client.close()

    def parse_commands(self, lines) -> list[str]:
        commands = []
        for line in lines:
            if line.startswith("EHLO") or line.startswith("HELO"):
                commands.append("EHLO")
            elif line.startswith("AUTH LOGIN"):
                commands.append("AUTH LOGIN")
            elif line.startswith("MAIL FROM"):
                commands.append("MAIL FROM")
            elif line.startswith("RCPT TO"):
                commands.append("RCPT TO")
            elif line.startswith("DATA"):
                commands.append("DATA")
            elif line.startswith("QUIT"):
                commands.append("QUIT")
            else:
                commands.append("TEXT")
        return commands

    def verify_account(self, client):
        return self.accounts[client["username"].decode()] == client["pw"].decode()

    def forward_email(self, client):
        # do DNS lookup for dst
        # make Client instance
        # use that to send to the other server in a subprocess.
        pass

    def smtp_commands(self, client_sock):
        client = self.clients[client_sock]
        inputs = client['buffer'].split(b"\r\n")
        client['buffer'] = inputs[-1] # write unfinished line back to the dict
        input_lines = inputs[:-1]
        commands = self.parse_commands(input_lines)
        for i, command in enumerate(commands):
            line = input_lines[i]
            match command:
                case "EHLO" | "HELO":
                    if client["state"] == States.INIT:
                        client['state'] = States.AUTH_INIT
                        client_sock.send(b"250-smtp-server.abeersclass.com\r\n250-AUTH LOGIN PLAIN\r\n250 Ok\r\n")
                case "AUTH LOGIN":
                    if client["state"] == States.AUTH_INIT:
                        client_sock.send(b"334 " + base64.b64encode(b"Username:"))
                        client["state"] = States.AUTH_USER
                case "TEXT":
                    if client["state"] == States.AUTH_USER:
                        client["username"] = line
                        client_sock.send(b"334 " + base64.b64encode(b"Password:"))
                        client["state"] = States.AUTH_PW
                    elif client["state"] == States.AUTH_PW:
                        client["pw"] = line
                        if self.verify_account(client):
                            client_sock.send(b"235 2.7.0 Authentication successful")
                            client["state"] = States.READY
                        else:
                            client_sock.send(b"535 5.7.8 Authentication credentials invalid")
                            self.disconnect(client_sock)
                    elif client["state"] == States.DATA:
                        client["msg"] += line
                        if line == ".":
                            client_sock.send(b"250 Ok: queued")
                            self.forward_email(client)
                case "MAIL FROM":
                    if client["state"] == States.READY:
                        client["from"] = line
                        client["state"] = States.DEST
                        client_sock.send(b"250 Ok\r\n")
                case "RCPT TO":
                    if client["state"] == States.DEST:
                        client["dst"] = line[8:]
                        client["state"] = States.DATA
                        client_sock.send(b"250 Ok\r\n")
                case "DATA":
                    if client["state"] == States.DATA:
                        client_sock.send(b"354 End data with <CR><LF>.<CR><LF>")
                case "QUIT":
                    self.disconnect(client_sock)

    def run(self):
        while(True):
            readable_socks, _, _ = select.select(self.inputs, [], [])
            for sock in readable_socks:
                if sock is self.server_sock:
                    self.new_client()
                else:
                    self.read_from_client(sock)

