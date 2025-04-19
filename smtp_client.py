"""
SMTP Client implementation 
Author: Landon Spitzer - lbs9440@rit.edu
"""
import socket
import base64
import hashlib
import argparse
import dns.dns
from prompt_toolkit import prompt  # for multiline input

DOMAIN = 'abeersclass.com'
DEBUG_MODE = True

class EmailClient:
    def __init__(self, dns_ip = "192.168.124.32"):
        self.dns_ip = dns_ip
        self.username = ""
        self.password = ""
        self.password_hash = ""
        self.s = None
        self.pop_socket = None
        self.pop_ip = 'localhost'
        self.pop_port = 8110

    def run(self):
        print("Welcome to Email Client")
        if self.login():
            print(f"Logged in as {self.username}@{self.domain}")
            self.menu()
        else:
            print("Login failed.")

    def menu(self):
        while True:
            print("\nMenu:")
            print("1. Compose Email")
            print("2. Inbox")
            print("3. Quit")

            choice = input("Select an option: ").strip()

            if choice == "1":
                self.send_email()
            elif choice == "2":
                self.fetch_inbox()
            elif choice == "3":
                print("Goodbye.")
                break
            else:
                print("Invalid choice.")

    def server_auth(self):
        if self.s is None:
            self.s = self.connect()

        if not self.s:
            return False
        
        try:
            self.send_and_print(self.s, f"EHLO client.{self.domain}")
            server_response = self.read_multiline(self.s)
            if "250-AUTH LOGIN PLAIN" not in server_response:
                print("Server does not support AUTH LOGIN.")
                self.s.close()
                self.s = None
                return False

            self.send_and_print(self.s, "AUTH LOGIN")
            username_prompt = self.read_response(self.s).strip()
            if not username_prompt.startswith("334"):
                print(f"Expected username prompt. {username_prompt}")
                self.s.close()
                self.s = None
                return False

            encoded_user = base64.b64encode(self.username.encode()).decode()
            self.send_and_print(self.s, encoded_user)

            password_prompt = self.read_response(self.s).strip()
            if not password_prompt.startswith("334"):
                print("Expected password prompt.")
                self.s.close()
                self.s = None
                return False

            encoded_pass = base64.b64encode(str(self.password_hash).encode()).decode()
            self.send_and_print(self.s, encoded_pass)

            auth_response = self.read_response(self.s).strip()
            print(f"Server: {auth_response}") if DEBUG_MODE else ""

            if auth_response.startswith("235"):
                return True
        
        except Exception as e:
            print("Login error:", e)
            self.s.close()
            self.s = None
            return False
        
    def login(self):
        user_input = input("Enter email: ").strip()
        if "@" in user_input:
            self.username, self.domain = user_input.split("@", 1)
            addr = dns.dns.dns_lookup(self.dns_ip, 8080, self.domain)
            if addr:
                addr = addr.split(" ")
                self.smtp_ip, self.smtp_port = addr[0], int(addr[1])
                print(f"DNS lookup found server on port {self.smtp_port}") if DEBUG_MODE else ""
                self.pop_ip = self.smtp_ip
            else:
                return False
        else:
            return False
        
        password = input("Enter password: ").strip()
        self.password_hash = self.hash_password(password)

        if self.server_auth():
            self.send_and_print(self.s, "QUIT") 
            self.read_response(self.s)  
            self.s.close()
            self.s = None
            return True



    def send_email(self, self_username="", username="", pw="", to_addr = "", msg = "", dst_addr = (), forward = False, domain=""):
        try:
            if forward:
                self.domain = domain
                self.username = self_username
                self.password_hash = pw
                try:
                    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.s.connect(dst_addr)
                    greeting = self.read_response(self.s)
                    print(f"Server: {greeting.strip()}") if DEBUG_MODE else ""
                except Exception as e:
                    print(f"Connection failed: {e}")
                    return None
                
            if self.server_auth():
                from_address = f"{str(self.username if not forward else username)}@{self.domain}"
                to_address = str(to_addr if forward else input("To (recipient email): ").strip())
                if "@" not in to_address:
                    print("Invalid recipient address.")
                    return

                # MAIL FROM
                self.send_and_print(self.s, f"MAIL FROM:{from_address}")
                response = self.read_response(self.s).strip()
                print(response) if DEBUG_MODE else ""
                if not response.startswith("250"):
                    return

                # RCPT TO
                self.send_and_print(self.s, f"RCPT TO:{to_address}")
                response = self.read_response(self.s).strip()
                print(response) if DEBUG_MODE else ""
                if not response.startswith("250"):
                    return

                # DATA
                self.send_and_print(self.s, "DATA")
                response = self.read_response(self.s).strip()
                print(response) if DEBUG_MODE else ""
                if not response.startswith("354"):
                    print("Server not ready for data.")
                    return

                if not forward:
                    # Compose message
                    subject = input("Subject: ")
                    print("Compose your email (end with ESC then Enter):")
                    body = prompt("", multiline=True)

                message = str(msg if forward else f"Subject: {subject}\r\n\r\n{body}\r\n.\r\n")
                self.s.sendall(message.encode())
                print(self.read_response(self.s).strip())

                self.send_and_print(self.s, "QUIT")
                self.read_response(self.s)

        except Exception as e:
            print("Error sending email:", e)

    def connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"trying to connect to: {self.smtp_ip}, {self.smtp_port}") if DEBUG_MODE else ""
            s.connect((self.smtp_ip, self.smtp_port))
            greeting = self.read_response(s)
            print(f"Server: {greeting.strip()}") if DEBUG_MODE else ""
            return s
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

    def read_response(self, sock):
        return sock.recv(1024).decode()

    def read_multiline(self, sock):
        lines = []
        while True:
            chunk = sock.recv(1024).decode()
            lines.append(chunk)
            if "250 Ok" in chunk or "\n.\r\n" in chunk:
                break
        return "".join(lines)



    def send_and_print(self, sock, msg):
        sock.sendall((msg + "\r\n").encode())
        if DEBUG_MODE:
            print(f"> {msg}")

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def fetch_inbox(self):
        try:
            if not self.pop3_auth():
                return

            self.send_and_print(self.pop_socket, "STAT")
            stat = self.read_response(self.pop_socket)
            print(f"Server: {stat.strip()}") if DEBUG_MODE else ""
            count = int(stat.split()[1]) if stat.startswith("+OK") else -1

            if count == 0:
                print("Inbox is empty.")
            elif count == -1:
                print(f"Error fetching inbox: {stat}")
                return
            self.pop3_trans(count)

        except Exception as e:
            print(f"Error fetching inbox: {e}")
    
    def pop3_auth(self):
        try:
            self.pop_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.pop_socket.connect((self.pop_ip, self.pop_port))
            ready = self.read_response(self.pop_socket)
            print(f"Server: {ready.strip()}") if DEBUG_MODE else ""
            if not ready.startswith("+OK"):
                print("POP3 server not ready.")
                self.pop_socket.close()
                return False

            self.send_and_print(self.pop_socket, "USER " + self.username)
            user_response = self.read_response(self.pop_socket)
            print(f"Server: {user_response.strip()}") if DEBUG_MODE else ""
            if not user_response.startswith(f"+OK {self.username}"):
                print("Error with username.")
                self.pop_socket.close()
                return False

            self.send_and_print(self.pop_socket, "PASS " + self.password_hash)
            pass_response = self.read_response(self.pop_socket)
            print(f"Server: {pass_response.strip()}") if DEBUG_MODE else ""
            if not pass_response.startswith(f"+OK {self.username}"):
                print("Error with password.")
                self.pop_socket.close()
                return False

            return True
        
        except Exception as e:
            print(f"POP3 error: {e}")
            return False
    
    def pop3_trans(self, total_msgs):
        page_size = 10
        current_page = 0

        while True:
            start_msg = current_page * page_size + 1
            end_msg = min(start_msg + page_size - 1, total_msgs)
            print(f"\nShowing messages {start_msg} to {end_msg} of {total_msgs}:\n")

            for i in range(start_msg, end_msg + 1):
                self.send_and_print(self.pop_socket, f"RETR {i}")
                raw = self.read_multiline(self.pop_socket)
                from_line = next((line for line in raw.split("\r\n") if line.startswith("From:")), "From: ???")
                subject_line = next((line for line in raw.split("\r\n") if line.startswith("Subject:")), "Subject: ???")
                print(f"{i}. {from_line} | {subject_line}")

            print("\nOptions:")
            print("n - Next page")
            print("p - Previous page")
            print("v - View a message")
            print("d - Delete a message")
            print("r - Unmark all deletions")
            print("q - Back to main menu")
            # Noop is not necessary for our system

            action = input("Choose: ").strip().lower()

            if action == "n":
                if end_msg < total_msgs:
                    current_page += 1
                else:
                    print("You're on the last page.")
            elif action == "p":
                if current_page > 0:
                    current_page -= 1
                else:
                    print("You're on the first page.")
            elif action == "v":
                msg = input("Message number to view: ").strip()
                self.send_and_print(self.pop_socket, f"RETR {msg}")
                response = self.read_multiline(self.pop_socket)
                if not self.isStatusOK(response):
                    self.pop_socket.close()
                    break
                print(response)
            elif action == "d":
                msg = input("Message number to delete: ").strip()
                self.send_and_print(self.pop_socket, f"DELE {msg}")
                response = self.read_response(self.pop_socket).strip()
                if not self.isStatusOK(response):
                    self.pop_socket.close()
                    break
                print(f"Email {msg} marked for deletion.")
                print(response) if DEBUG_MODE else ""
            elif action == "r":
                self.send_and_print(self.pop_socket, "RSET")
                response = self.read_response(self.pop_socket).strip()
                if not self.isStatusOK(response):
                    self.pop_socket.close()
                    break
                print("All emails unmarked from deletion for this session.")
                print(response) if DEBUG_MODE else ""
            elif action == "q":
                self.send_and_print(self.pop_socket, "QUIT")
                print(self.read_response(self.pop_socket).strip())
                self.pop_socket.close()
                break
            else:
                print("Invalid option.")
            
    def isStatusOK(self, msg):
        return msg.startswith("+OK") 


def main():
    parser = argparse.ArgumentParser(description="For running a SMTP/POP3 Client")

    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode (default: False)")
    parser.add_argument("--dns-ip", "-i", type=str, default="127.0.0.1", help="DNS server IP address (default: 127.0.0.1)")

    args = parser.parse_args()
    
    DEBUG_MODE = args.debug
    client = EmailClient(dns_ip=args.dns_ip)
    client.run()


if __name__ == "__main__":
    main()
