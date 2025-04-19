"""
SMTP Server implementation
Authors: Caleb Naeger - cmn4315@rit.edu, Landon Spitzer - lbs9440@rit.edu
"""
from enum import Enum
import argparse
import socket
import json
import select
import base64
import random
import dns.dns
import smtp_client

SERVER_PASSWORD = 'pass'

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
        """Constructor for email Server class.

        :param domain: the email domain for which this server should operate.
        :param dns_ip: the IP of the DNS server.
        """
        self.clients = {}
        self.domain = domain
        self.load_accounts(f"{self.domain.split(".")[0]}/accounts.json")
        port = random.randint(5000, 8000)
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setblocking(False)
        self.server_sock.bind(('0.0.0.0', port))
        self.server_sock.listen(5)
        print(f"Server socket bound to port {port}")
        dns.dns.dns_update(dns_ip, 8080, domain, "127.0.0.1", port)
        self.pop_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.pop_sock.setblocking(False)
        self.pop_sock.bind(('0.0.0.0', 8110))
        self.pop_sock.listen(5)
        self.inputs = [self.server_sock, self.pop_sock]
        self.dns_port = 8080
        self.dns_ip = dns_ip

    def load_accounts(self, filename: str):
        """Load known accounts from a json file

        :param filename: the path of the accounts json file
        """
        with open(filename) as f:
            data = json.load(f)
            self.accounts = data

    def load_emails(self, username):
        """Load saved emails from the email "database" json file associated with this domain

        :param username: the username for which to retrieve emails
        """
        with open(f"{self.domain.split(".")[0]}/emails.json", "r") as f:
            emails = json.load(f)
            if username not in emails:
                emails[username] = []
            return emails[username]

    def new_client(self, sock):
        """Accept a new client connection

        :param sock: the server socket from which to accept the connection
        """

        client, addr = sock.accept()
        client.setblocking(False)
        self.inputs.append(client)
        self.clients[client] = {"addr": addr, "buffer": b"", "state": States.INIT, "dst": "", "from": b"", "msg": b"", "type": "SMTP", "to_delete":[], "username": ""} # track the address, current buffer, and state machine state for the client
        if sock.getsockname()[1] == 8110:
            self.clients[client]["type"] = "POP3"
            client.sendall((f'+OK pop3-server8110.{self.domain} POP3 server ready\r\n').encode())
            self.clients[client]['state'] = States.AUTH_USER
        else:
            client.sendall(f"220 smtp-server{self.server_sock.getsockname()[1]}.abeeersclass.com".encode())

    def read_from_client(self, client):
        """Read a message from the client, responding to commands as needed

        :param client: the client socket from which to read
        """

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
        """Process client commands for a POP3 connection.

        :param client_sock: the client socket to retrieve communication from
        """

        client = self.clients[client_sock]
        input_lines = client['buffer'].split(b"\r\n")
        client['buffer'] = input_lines[-1] # write unfinished line back to the dict
        input_lines = input_lines[:-1]

        print(f"received form client, input={input_lines}")
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
                        client["pw"] = line[5:].decode()
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
                        print(f"In RETR, len(emails = {len(user_emails)}, msgnum = {msg_num})")
                        if msg_num.isnumeric() and len(user_emails) >= int(msg_num) >= 1:
                            msg_num = int(msg_num.strip())
                            current_email = user_emails[msg_num-1]
                            multiline_response = f"+OK {len(current_email["msg"])} octets\r\n".encode()
                            multiline_response += f"From: {current_email["FROM"]}\r\n".encode()
                            multiline_response += f"To: {client["username"]}@{self.domain}\r\n".encode()
                            multiline_response += current_email["msg"].encode()
                            client_sock.sendall(multiline_response)
                    else:
                        client_sock.sendall(b'ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock) 
                case "DELE":
                    if client["state"] == States.POP3_TRAN:
                        msg_num = line[5:].decode()
                        if msg_num.isnumeric() and len(user_emails) >= int(msg_num) >= 1:
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
                    client_sock.sendall(f"+OK pop3-server{self.server_sock.getsockname()[1]} POP3 server signing off (maildrop empty)".encode())
                    if client["to_delete"] != []:
                        keep_emails = []
                        for i in range(len(user_emails)):
                            if i not in client["to_delete"]:
                                keep_emails.append(user_emails[i])
                        self.write_emails(client["username"], keep_emails)
                    self.disconnect(client_sock)

    def write_emails(self, username, newemails):
        """Save a list of emails to the database json associated with this domain, replacing any previously stored emails.

        :param username: the username to which the emails belong
        :param newemails: the list of emails to save.
        """

        emails = {}
        with open(f"{self.domain.split(".")[0]}/emails.json", 'r') as f:
            emails = json.load(f)
            emails[username] = newemails
        with open(f"{self.domain.split(".")[0]}/emails.json", 'w') as f:
            json.dump(emails, f, indent=4, ensure_ascii=False)

    def disconnect(self, client):
        """Disconnect from a client

        :param client: the client from which to disconnect
        """

        del self.clients[client]
        self.inputs.remove(client)
        client.close()

    def parse_commands(self, lines) -> list[str]:
        """Parse client SMTP commands from a list of lines

        :param lines: the list of lines to parse.
        """

        commands = []
        for line in lines:
            line = line.decode()
            print(f"line={line}")
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
        """Parse client SMTP commands from a list of lines

        :param lines: the list of lines to parse
        """

        commands = []
        for line in lines:
            line = line.decode()
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
        """Verify that the client has provided correct credentials.

        :param client: the entry from self.clients of the client to check.
        """

        return self.accounts[client["username"]] == client["pw"]

    def update_emails(self, client):
        """Update the emails.json with a newly received email

        :param client: the entry from self.clients of the client to use.
        """

        emails = {}
        with open(f"{self.domain.split(".")[0]}/emails.json", 'r') as f:
            emails = json.load(f)
        with open(f"{self.domain.split(".")[0]}/emails.json", 'w') as f:
            if client["dst"].split(b"@")[0].decode() not in emails:
                emails[client["dst"].split(b"@")[0].decode()] = []
            emails[client["dst"].split(b"@")[0].decode()].append({"FROM": client["from"], "msg": client['msg']})
            json.dump(emails, f, indent=4, ensure_ascii=False)

    def forward_email(self, client_sock):
        """Check if a received email is addressed to this domain, saving it if it is and forwarding to another SMTP
        server if not.

        :param client_sock: the client socket from which the email was received
        """

        client = self.clients[client_sock]
        to_domain = client["dst"].split(b"@")[-1].decode()
        print(f"To domain = {to_domain}")
        if to_domain == self.domain:
            print("Updating Emails")
            self.update_emails(client)
        else:
            # do DNS lookup for dst
            dst_addr = dns.dns.dns_lookup(self.dns_ip, self.dns_port, to_domain)
            if dst_addr:
                dst_addr = dst_addr.split(" ")
                dst_addr = (dst_addr[0], int(dst_addr[1]))
                # make Client instance
                sender = smtp_client.EmailClient()
                # use that to send to the other server
                sender.send_email(self_username="server", username=client["from"].split("@")[0], pw=SERVER_PASSWORD, to_addr=client["dst"].decode(), msg = client["msg"], dst_addr = dst_addr, forward=True, domain=self.domain)

    def smtp_commands(self, client_sock):
        """Process smtp commands from the client, responding as appropriate.

        :param client_sock: the client socket from which to process the input
        """

        client = self.clients[client_sock]
        input_lines = client['buffer'].split(b"\r\n")
        client['buffer'] = input_lines[-1] # write unfinished line back to the dict
        input_lines = input_lines[:-1]
        print(f"received form client, input={input_lines}")
        commands = self.parse_commands(input_lines)
        for i, command in enumerate(commands):
            print(f"received command {command}")
            line = input_lines[i]
            match command:
                case "EHLO" | "HELO":
                    if client["state"] == States.INIT:
                        client['state'] = States.AUTH_INIT
                        client_sock.sendall(f"250-smtp-server{self.server_sock.getsockname()[1]}.{self.domain}\r\n250-AUTH LOGIN PLAIN\r\n250 Ok\r\n".encode())
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
                        client["username"] = base64.b64decode(line.decode()).decode()
                        client_sock.sendall(b"334 " + base64.b64encode(b"Password:"))
                        client["state"] = States.AUTH_PW
                    elif client["state"] == States.AUTH_PW:
                        client["pw"] = base64.b64decode(line.decode()).decode()
                        if self.verify_account(client):
                            client_sock.sendall(b"235 2.7.0 Authentication successful")
                            client["state"] = States.READY
                        else:
                            client_sock.sendall(b"535 5.7.8 Authentication credentials invalid")
                            self.disconnect(client_sock)
                    elif client["state"] == States.DATA:
                        client["msg"] += line + b"\r\n"
                        print(f"Added line to message: {line}")
                        if line == b".":
                            client_sock.sendall(b"250 Ok: queued")
                            client["msg"] = client["msg"].decode()
                            self.forward_email(client_sock)
                    else:
                        client_sock.sendall(b'-ERROR Unexpected Command\r\n')
                        self.disconnect(client_sock)
                case "MAIL FROM":
                    if client["state"] == States.READY:
                        client["from"] = line.decode()[10:]
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
        """Constructor for email Server class.

        :param domain: the email domain for which this server should operate.
        :param dns_ip: the IP of the DNS server.
        """

        try:
            while(True):
                readable_socks, _, _ = select.select(self.inputs, [], [])
                for sock in readable_socks:
                    if sock in [self.server_sock, self.pop_sock]:
                        self.new_client(sock)
                    else:
                        self.read_from_client(sock)
        except Exception as e:
            self.server_sock.close()
            self.pop_sock.close()
            raise e

def main(dns, domain):
    server = Server(dns_ip=dns, domain=domain)
    server.run()

if __name__ == "__main__":
    # Create the parser
    parser = argparse.ArgumentParser(description='Server for a simple reliable file-transfer application.')
    
    # Add arguments
    parser.add_argument('-dns',  required=False,type=str, default="127.0.0.1", help='The destination IP for the DNS server. Should be set to the LAN IP of the machine on which the DNS is running if communicating between machines. Defaults to localhost.')
    parser.add_argument('-domain',  required=False,type=str, default="abeersclass.com", help='Domain for which this server should operate. Defaults to "abeersclass.com"')
    
    args = parser.parse_args()
    main(args.dns, args.domain)

