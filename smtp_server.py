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
    POP3_TRAN = "POP3_TRANSACTION"


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
        self.clients[client] = {"addr": addr, "buffer": b"", "current_state": States.INIT, "dst": "", "from": b"", "msg": b"", "type": "SMTP", "to_delete":[]} # track the address, current buffer, and state machine state for the client
        if addr[1] == 8110:
            self.clients[client]["type"] = "POP3"
            client.sendall((f'+OK smtp-server{self.server_sock.getsockname()[1]}.abeersclass.com POP3 server ready\r\n').encode())
            client['state'] = States.AUTH_USER

    def read_from_client(self, client):
        try:
            data = client.recv(1024)
            self.clients[client]["buffer"] += data
            if self.clients[client]["type"] == "SMTP":
                self.smtp_commands(client)
            elif self.clients[client]["type"] == "POP3":
                self.pop_commands(client)
        except(ConnectionResetError):
            self.disconnect(client)

    def pop_commands(self, client_sock):
        client = self.clients[client_sock]
        input_lines = client['buffer'].split(b"\r\n")
        if not client['buffer'].endswith(b"\r\n"):
            client['buffer'] = input_lines[-1] # write unfinished line back to the dict
            input_lines = input_lines[:-1]

        commands = self.parse_pop3_commands(input_lines)
        user_emails = None 
        for i, command in enumerate(commands):
            line = input_lines[i]
            match command:
                case "USER":
                    if client["state"] == States.AUTH_USER:
                        client["username"] = line[5:]
                        client_sock.sendall((f'+OK {client["username"]}\r\n').encode())
                        client["state"] = States.AUTH_PW
                case "PASS":
                    if client["state"] == States.AUTH_PW:
                        client["pw"] = line[5:]
                        if self.verify_account(client):
                            user_emails = self.load_emails(client["username"])
                            client_sock.sendall((f"+OK {client["username"]}'s maildrop has {len(user_emails)} messages ({sum(len(email["msg"]) for email in user_emails)} octets)\r\n").encode())
                            client["state"] = States.POP3_TRAN
                    else:
                        client_sock.sendall(b'-ERROR Authentication credentials invalid\r\n')
                        client["state"] = States.AUTH_USER
                case "STAT":
                    if client["state"] == States.POP3_TRAN:
                        total_bytes = 0;
                        for email in user_emails:
                            total_bytes += len(email['msg'])
                        client_sock.sendall((f'+OK {len(user_emails)} {total_bytes}\r\n').encode())
                case "LIST":
                    if client["state"] == States.POP3_TRAN:
                        parts = line.decode().split()
                        if len(parts) == 2 and int(parts[1]).isdigit():       
                            num = int(parts[1])
                            client_sock.sendall((f"+OK 1 {len(user_emails[num]["msg"])}\r\n").encode())
                        else:
                            total_bytes = 0;
                            for email in user_emails:
                                total_bytes += len(email['msg'])
                            
                            final_str = f"+OK {len(user_emails)} messages ({total_bytes} octets)\r\n"

                            for i, email in enumerate(user_emails):
                                final_str += f"{i+1} {len(email)}\r\n"
                            final_str += f".\r\n"
                            client_sock.sendall(final_str.encode())
                case "RETR":
                    if client["state"] == States.POP3_TRAN:
                        msg_num = int(list[5:])
                        if msg_num.isdigit() and len(user_emails) >= msg_num >= 1:
                            current_email = user_emails[msg_num-1]
                            multiline_response = f"+OK {len(current_email["msg"])} octets\r\n".encode()
                            multiline_response += f"From: {current_email["FROM"].decode()}\r\n".encode()
                            multiline_response += f"To: {client["username"].decode()}@{self.domain}\r\n".encode()
                            multiline_response += current_email["msg"]
                            client_sock.sendall(multiline_response)
                case "DELE":
                    if client["state"] == States.POP3_TRAN:
                        msg_num = int(list[5:])
                        if msg_num.isdigit() and len(user_emails) >= msg_num >= 1:
                            client["to_delete"].append(msg_num-1)
                            client_sock.sendall((f"+OK message {msg_num} deleted\r\n").encode())
                case "NOOP":
                    if client["state"] == States.POP3_TRAN:
                        client_sock.sendall(b"+OK\r\n")
                case "RSET":
                    if client["state"] == States.POP3_TRAN:
                        client["to_delete"] = []
                    client_sock.sendall((f"+OK maildrop has {len(user_emails)} messages ({sum(len(email["msg"]) for email in user_emails)} octets)").encode())
                case "QUIT":
                    self.disconnect(client_sock)



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
    
    def parse_pop3_commands(self, lines) -> list[str]:
        commands = []
        for line in lines:
            if line.startswith("USER"):
                commands.append("USER")
            elif line.startswith("PASS"):
                commands.append("PASS")
            elif line.startswith("QUIT"):
                commands.append("QUIT")
            elif line.startswith("STAT"):
                commands.append("STAT")
            elif line.startswith("LIST"):
                commands.append("LIST")
            elif line.startswith("RETR"):
                commands.append("RETR")
            elif line.startswith("DELE"):
                commands.append("DELE")
            elif line.startswith("NOOP"):
                commands.append("NOOP")
            elif line.startswith("LAST"):
                commands.append("LAST")
            elif line.startswith("RSET"):
                commands.append("RSET")
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
        input_lines = client['buffer'].split(b"\r\n")
        if not client['buffer'].endswith(b"\r\n"):
            client['buffer'] = input_lines[-1] # write unfinished line back to the dict
            input_lines = input_lines[:-1]
        commands = self.parse_commands(input_lines)
        for i, command in enumerate(commands):
            line = input_lines[i]
            match command:
                case "EHLO" | "HELO":
                    if client["state"] == States.INIT:
                        client['state'] = States.AUTH_INIT
                        client_sock.send(f"250-smtp-server{self.server_sock.getsockname()[1]}.abeersclass.com\r\n250-AUTH LOGIN PLAIN\r\n250 Ok\r\n".encode())
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

