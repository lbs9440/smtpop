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
            print("2. Quit")

            choice = input("Select an option: ").strip()

            if choice == "1":
                self.send_email()
            elif choice == "2":
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
        return sock.recv(2048).decode()

    def read_multiline(self, sock):
        lines = []
        while True:
            chunk = sock.recv(2048).decode()
            lines.append(chunk)
            if "250 Ok" in chunk:
                break
        return "".join(lines)



    def send_and_print(self, sock, msg):
        sock.sendall((msg + "\r\n").encode())
        print(f"> {msg}")

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

def main():
    client = EmailClient()
    client.run()

if __name__ == "__main__":
    main()
