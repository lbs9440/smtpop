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
import dns.dns
import smtp_client
import subprocess

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
    def __init__(self, domain = "abeersclass.com", dns_ip = "127.0.0.1") -> None:
        self.clients = {}
        self.load_accounts("accounts.json")
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setblocking(False)
        port = random.randint(5000, 8000)
        dns.dns.dns_update(dns_ip, 8080, domain, "127.0.0.1", port)
        self.server_sock.bind(('127.0.0.1', port))
        self.inputs = [self.server_sock]
        self.domain = domain
        self.dns_port = 8080
        self.dns_ip = dns_ip

    def load_accounts(self, filename: str) -> None:
        with open(filename) as f:
            data = json.load(f)
            self.accounts = data

    def load_emails(self, username):
        with open("emails.json") as f:
            emails = json.load(f)
            return emails[username]

    def new_client(self):
        client, addr = self.server_sock.accept()
        client.setblocking(False)
        self.inputs.append(client)
        self.clients[client] = {"addr": addr, "buffer": b"", "current_state": States.INIT, "dst": "", "from": b"", "msg": b"", "type": "SMTP", "to_delete":[]} # track the address, current buffer, and state machine state for the client
        if addr[1] == 8110:
            self.clients[client]["type"] = "POP3"
            client.sendall((f'+OK pop3-server{self.server_sock.getsockname()[1]}.abeersclass.com POP3 server ready\r\n').encode())
            self.clients[client]['state'] = States.AUTH_USER

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
        user_emails = []
        if client["state"] not in [States.AUTH_USER, States.AUTH_PW]:
            user_emails = self.load_emails(client["username"])
        for i, command in enumerate(commands):
            line = input_lines[i]
            match command:
                case "USER":
                    if client["state"] == States.AUTH_USER:
                        client["username"] = line.decode()[5:]
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
                            client_sock.sendall(b'ERROR Authentication credentials invalid\r\n')
                            client["state"] = States.AUTH_USER
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "STAT":
                    if client["state"] == States.POP3_TRAN:
                        try:
                            total_bytes = 0
                            for email in user_emails:
                                total_bytes += len(email['msg'])
                            client_sock.sendall((f'+OK {len(user_emails)} {total_bytes}\r\n').encode())
                        except AttributeError:
                            client_sock.sendall("ERROR unable to display inbox stats".encode())
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock) 
                case "LIST":
                    if client["state"] == States.POP3_TRAN:
                        parts = line.decode().split()
                        if len(parts) == 2 and parts[1].isnumeric():       
                            num = int(parts[1])
                            client_sock.sendall((f"+OK 1 {len(user_emails[num]["msg"])}\r\n").encode())
                        else:
                            total_bytes = 0
                            for email in user_emails:
                                total_bytes += len(email['msg'])
                            
                            final_str = f"+OK {len(user_emails)} messages ({total_bytes} octets)\r\n"

                            for i, email in enumerate(user_emails):
                                final_str += f"{i+1} {len(email)}\r\n"
                            final_str += ".\r\n"
                            client_sock.sendall(final_str.encode())
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock) 
                case "RETR":
                    if client["state"] == States.POP3_TRAN:
                        msg_num = line[5:].decode()
                        if msg_num.isnumeric() and len(user_emails) >= msg_num >= 1:
                            msg_num = int(msg_num.strip())
                            current_email = user_emails[msg_num-1]
                            multiline_response = f"+OK {len(current_email["msg"])} octets\r\n".encode()
                            multiline_response += f"From: {current_email["FROM"].decode()}\r\n".encode()
                            multiline_response += f"To: {client["username"]}@{self.domain}\r\n".encode()
                            multiline_response += current_email["msg"]
                            client_sock.sendall(multiline_response)
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock) 
                case "DELE":
                    if client["state"] == States.POP3_TRAN:
                        msg_num = line[5:].decode()
                        if msg_num.isnumeric() and len(user_emails) >= msg_num >= 1:
                            msg_num = int(msg_num.strip())
                            client["to_delete"].append(msg_num-1)
                            client_sock.sendall((f"+OK message {msg_num} deleted\r\n").encode())
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "NOOP":
                    if client["state"] == States.POP3_TRAN:
                        client_sock.sendall(b"+OK\r\n")
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "RSET":
                    if client["state"] == States.POP3_TRAN:
                        client["to_delete"] = []
                    client_sock.sendall((f"+OK maildrop has {len(user_emails)} messages ({sum(len(email["msg"]) for email in user_emails)} octets)").encode())
                case "QUIT":
                    client_sock.sendall(f"+OK pop3-server{self.server_sock.getsockname()[1]} POP3 server signing off (maildrop empty)")
                    if client["to_delete"] != []:
                        keep_emails = []
                        for i in range(len(user_emails)):
                            if i not in client["to_delete"]:
                                keep_emails.append(user_emails[i])
                        self.write_emails(client["username"], keep_emails)
                    self.disconnect(client_sock)

    def write_emails(self, username, emails):
        with open("emails.json", 'rw') as f:
            emails = json.load(f)
            emails[username] = emails
            json.dump(emails, f, indent=4, ensure_ascii=False)

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
            elif line.startswith("LAST"):
                commands.append("LAST")
            elif line.startswith("RSET"):
                commands.append("RSET")
            else:
                commands.append("NOOP")
        return commands

    def verify_account(self, client):
        return self.accounts[client["username"]] == client["pw"].decode()

    def update_emails(self, client):
        with open("emails.json", 'rw') as f:
            emails = json.load(f)
            if client["username"] not in emails:
                emails[client["username"]] = []
            emails[client["username"]].append({"FROM": client["from"], "msg": client['msg']})
            json.dump(emails, f, indent=4, ensure_ascii=False)

    def forward_email(self, client_sock):
        client = self.clients[client_sock]
        to_domain = client["dst"].split("@")[-1]
        if to_domain == self.domain:
            self.update_emails(client)
        else:
            # do DNS lookup for dst
            dst_addr = dns.dns.dns_lookup(self.dns_ip, self.dns_port, to_domain)
            if dst_addr:
                # make Client instance
                sender = smtp_client.EmailClient()
                # use that to send to the other server in a subprocess.
                subprocess.run(sender.send_email(username=client["username"], pw=client["pw"], to_addr=client["dst"], msg = client["msg"], dst_addr = dst_addr, forward=True))

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
                        client_sock.sendall(f"250-smtp-server{self.server_sock.getsockname()[1]}.abeersclass.com\r\n250-AUTH LOGIN PLAIN\r\n250 Ok\r\n".encode())
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "AUTH LOGIN":
                    if client["state"] == States.AUTH_INIT:
                        client_sock.sendall(b"334 " + base64.b64encode(b"Username:"))
                        client["state"] = States.AUTH_USER
                    else:
                        client_sock.sendall(b'-ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "TEXT":
                    if client["state"] == States.AUTH_USER:
                        client["username"] = base64.b64decode(line.decode())
                        client_sock.sendall(b"334 " + base64.b64encode(b"Password:"))
                        client["state"] = States.AUTH_PW
                    elif client["state"] == States.AUTH_PW:
                        client["pw"] = line
                        if self.verify_account(client):
                            client_sock.sendall(b"235 2.7.0 Authentication successful")
                            client["state"] = States.READY
                        else:
                            client_sock.sendall(b"535 5.7.8 Authentication credentials invalid")
                            self.disconnect(client_sock)
                    elif client["state"] == States.DATA:
                        client["msg"] += line + b"\r\n"
                        if line == ".":
                            client_sock.sendall(b"250 Ok: queued")
                            self.forward_email(client_sock)
                    else:
                        client_sock.sendall(b'-ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "MAIL FROM":
                    if client["state"] == States.READY:
                        client["from"] = line.decode()[11:]
                        client["state"] = States.DEST
                        client_sock.sendall(b"250 Ok\r\n")
                    else:
                        client_sock.sendall(b'-ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "RCPT TO":
                    if client["state"] == States.DEST:
                        client["dst"] = line[8:]
                        client["state"] = States.DATA
                        client_sock.sendall(b"250 Ok\r\n")
                    else:
                        client_sock.sendall(b'-ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "DATA":
                    if client["state"] == States.DATA:
                        client_sock.sendall(b"354 End data with <CR><LF>.<CR><LF>")
                    else:
                        client_sock.sendall(b'-ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
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

