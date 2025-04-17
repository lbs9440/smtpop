"""
SMTP Client implementation
Author: Landon Spitzer - lbs9440@rit.edu
"""
import socket
import base64
import hashlib
from prompt_toolkit import prompt  # for multiline input

DOMAIN = 'abeersclass.com'

class EmailClient:
    def __init__(self):
        self.smtp_ip = 'localhost'
        self.smtp_port = 2525
        self.username = None
        self.password = None
        self.password_hash = None
        self.s = None
        self.pop_socket = None
        self.pop_ip = 'localhost'
        self.pop_port = 8110

    def run(self):
        print("Welcome to abeersclass.com Email Client")
        if self.login():
            print(f"Logged in as {self.username}@{DOMAIN}")
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
        self.s = self.connect()
        if not self.s:
            return False
        
        try:
            self.send_and_print(self.s, "EHLO client.abeersclass.com")
            server_response = self.read_multiline(self.s)
            if "250-AUTH LOGIN PLAIN" not in server_response:
                print("Server does not support AUTH LOGIN.")
                self.s.close()
                return False

            self.send_and_print(self.s, "AUTH LOGIN")
            username_prompt = self.read_response(self.s).strip()
            if not username_prompt.startswith("334"):
                print("Expected username prompt.")
                self.s.close()
                return False

            encoded_user = base64.b64encode(self.username.encode()).decode()
            self.send_and_print(self.s, encoded_user)

            password_prompt = self.read_response(self.s).strip()
            if not password_prompt.startswith("334"):
                print("Expected password prompt.")
                self.s.close()
                return False

            encoded_pass = base64.b64encode(self.password_hash.encode()).decode()
            self.send_and_print(self.s, encoded_pass)

            auth_response = self.read_response(self.s).strip()
            print(f"Server: {auth_response}")

            if auth_response.startswith("235"):
                return True
        
        except Exception as e:
            print("Login error:", e)
            self.s.close()
            return False
        
    def login(self):
        user_input = input("Enter username or email: ").strip()
        if "@" in user_input:
            self.username, domain = user_input.split("@", 1)
            if domain.lower() != DOMAIN:
                print("You're not in Abeers Class!")
                self.s.close()
                return False
        else:
            self.username = user_input
        
        password = input("Enter password: ").strip()
        self.hashed_password = self.hash_password(password)

        if self.server_auth():
            self.send_and_print(self.s, "QUIT") 
            self.read_response(self.s)  
            self.s.close()
            return True



    def send_email(self):
        try:
            if self.server_auth():
                from_address = f"{self.username}@{DOMAIN}"
                to_address = input("To (recipient email): ").strip()
                if "@" not in to_address:
                    print("Invalid recipient address.")
                    return

                # MAIL FROM
                self.send_and_print(self.s, f"MAIL FROM:<{from_address}>")
                print(self.read_response(self.s).strip())

                # RCPT TO
                self.send_and_print(self.s, f"RCPT TO:<{to_address}>")
                print(self.read_response(self.s).strip())

                # DATA
                self.send_and_print(self.s, "DATA")
                response = self.read_response(self.s).strip()
                print(response)
                if not response.startswith("354"):
                    print("Server not ready for data.")
                    return

                # Compose message
                subject = input("Subject: ")
                print("Compose your email (end with Ctrl+D):")
                body = prompt("", multiline=True)

                message = f"Subject: {subject}\r\n\r\n{body}\r\n.\r\n"
                self.s.sendall(message.encode())
                print(self.read_response(self.s).strip())

        except Exception as e:
            print("Error sending email:", e)

    def connect(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.smtp_ip, self.smtp_port))
            greeting = self.read_response(s)
            print(f"Server: {greeting.strip()}")
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
            if "250 Ok" in chunk:
                break
        return "".join(lines)



    def send_and_print(self, sock, msg):
        sock.sendall((msg + "\r\n").encode())
        print(f"> {msg}")

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def fetch_inbox(self):
        try:
            if not self.pop3_auth():
                return

            self.send_and_print(self.pop_socket, "STAT")
            stat = self.read_response(self.pop_socket)
            print(f"Server: {stat.strip()}")
            count = int(stat.split()[1]) if stat.startswith("+OK") else -1

            if count == 0:
                print("Inbox is empty.")
                return
            elif count == -1:
                print(f"Error fetching inbox: {stat}")
                return

            print(f"\nYou have {count} messages. Showing first 10:\n")
            for i in range(1, min(11, count + 1)):
                self.send_and_print(self.pop_socket, f"RETR {i}")
                raw = self.read_multiline(self.pop_socket)
                from_line = next((line for line in raw.split("\r\n") if line.startswith("From:")), "From: ???")
                subject_line = next((line for line in raw.split("\r\n") if line.startswith("Subject:")), "Subject: ???")
                print(f"{i}. {from_line} | {subject_line}")

            self.pop3_trans(count)

        except Exception as e:
            print(f"Error fetching inbox: {e}")
    
    def pop3_auth(self):
        try:
            self.pop_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.pop_socket.connect((self.pop_ip, self.pop_port))
            ready = self.read_response(self.pop_socket)
            print(f"Server: {ready.strip()}")
            if not ready.startswith("+OK"):
                print("POP3 server not ready.")
                self.pop_socket.close()
                return False

            self.send_and_print(self.pop_socket, "USER " + self.username)
            user_response = self.read_response(self.pop_socket)
            print(f"Server: {user_response.strip()}")
            if not user_response.startswith(f"+OK {self.username}"):
                print("Error with username.")
                self.pop_socket.close()
                return False

            self.send_and_print(self.pop_socket, "PASS " + self.hashed_password)
            pass_response = self.read_response(self.pop_socket)
            print(f"Server: {pass_response.strip()}")
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
            print("l - LAST (I Dont know what this does)")
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
                print(self.read_multiline(self.pop_socket))
            elif action == "d":
                msg = input("Message number to delete: ").strip()
                self.send_and_print(self.pop_socket, f"DELE {msg}")
                print(self.read_response(self.pop_socket).strip())
            elif action == "r":
                self.send_and_print(self.pop_socket, "RSET")
                print(self.read_response(self.pop_socket).strip())
            elif action == "l":
                self.send_and_print(self.pop_socket, "LAST")
                print(self.read_response(self.pop_socket).strip())
            elif action == "q":
                self.send_and_print(self.pop_socket, "QUIT")
                print(self.read_response(self.pop_socket).strip())
                self.pop_socket.close()
                break
            else:
                print("Invalid option.")
            

def main():
    client = EmailClient()
    client.run()

if __name__ == "__main__":
    main()
