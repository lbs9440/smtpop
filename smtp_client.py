"""
SMTP Client implementation 
Author: Landon Spitzer - lbs9440@rit.edu and Caleb Naeger - cmn4315@rit.edu
"""
import socket
import base64
import hashlib
import argparse
import dns.dns
from prompt_toolkit import prompt  # for multiline input

DOMAIN = 'abeersclass.com'

class EmailClient:
    """ An email client that supports SMTP and POP3, to send and receive emails respectively. """
    def __init__(self, dns_ip = "192.168.124.32", debug_mode=False):
        """
        Initialize the email client.
        
        :param dns_ip: The IP address of the DNS server.
        :param debug_mode: Enable debug mode.
        """
        self.dns_ip = dns_ip
        self.debug_mode = debug_mode
        self.username = ""
        self.password = ""
        self.password_hash = ""
        self.s = None
        self.pop_socket = None
        self.pop_ip = 'localhost'
        self.pop_port = 8110

    def run(self):
        """ Run the email client. 
        
        Calls the login method of the EmailClient class, authenticating with server.
        Then proceeds to the menu where the user can choose to compose or view emails.
        """
        print("Welcome to Email Client")
        if self.login():
            print(f"Logged in as {self.username}@{self.domain}")
            self.menu()
        else:
            print("Login failed.")

    def menu(self):
        """ Display a menu to the user, allowing them to compose or view emails. """
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
        """ Attempt to authenticate with the server. 
        
        First steps of SMTP to authenticate with the server whenever a command is given.

        :return: True if authentication is successful, False otherwise.
        """
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
            print(f"Server: {auth_response}") if self.debug_mode else ""

            if auth_response.startswith("235"):
                return True
        
        except Exception as e:
            print("Login error:", e)
            self.s.close()
            self.s = None
            return False
        
    def login(self):
        """Login to the email server. 
        
        Prompts the user to enter their email and password, then attempts to authenticate with the server.

        :return: True if login is successful, False otherwise.
        """
        user_input = input("Enter email: ").strip()
        if "@" in user_input:
            self.username, self.domain = user_input.split("@", 1)
            addr = dns.dns.dns_lookup(self.dns_ip, 8080, self.domain)
            if addr:
                addr = addr.split(" ")
                self.smtp_ip, self.smtp_port = addr[0], int(addr[1])
                print(f"DNS lookup found server on port {self.smtp_port}") if self.debug_mode else ""
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
        """ Sends an email to a recipient. 
        
        :param self_username: What to set username to when forwarding.
        :param username: Username of the original sender of the email when forwarding.
        :param pw: Password of the original sender of the email when forwarding.
        :param to_addr: Email address of the recipient when forwarding.
        :param msg: Message to send when forwarding.
        :param dst_addr: Address of the server to send the email to when forwarding.
        :param forward: Whether to forward the email or not.
        :param domain: Domain of the server to forward to when forwarding.

        :return: Returns if email is sent unsuccessfully.
        """
        try:
            if forward:
                self.domain = domain
                self.username = self_username
                self.password_hash = pw
                try:
                    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.s.connect(dst_addr)
                    greeting = self.read_response(self.s)
                    print(f"Server: {greeting.strip()}") if self.debug_mode else ""
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
                print(response) if self.debug_mode else ""
                if not response.startswith("250"):
                    return

                # RCPT TO
                self.send_and_print(self.s, f"RCPT TO:{to_address}")
                response = self.read_response(self.s).strip()
                print(response) if self.debug_mode else ""
                if not response.startswith("250"):
                    return

                # DATA
                self.send_and_print(self.s, "DATA")
                response = self.read_response(self.s).strip()
                print(response) if self.debug_mode else ""
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
        """Connects to the email server.
        
        :return s: Returns the socket object if connection is successful, None otherwise.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"trying to connect to: {self.smtp_ip}, {self.smtp_port}") if self.debug_mode else ""
            s.connect((self.smtp_ip, self.smtp_port))
            greeting = self.read_response(s)
            print(f"Server: {greeting.strip()}") if self.debug_mode else ""
            return s
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

    def read_response(self, sock):
        """ Reads a response from the server.

        :param sock: The socket object to read from.
        :return: The decoded response from the server.
        """
        return sock.recv(1024).decode()

    def read_multiline(self, sock):
        """ Reads a multiline response from the server.

        :param sock: The socket object to read from.
        :return: The decoded response from the server.
        """
        lines = []
        while True:
            chunk = sock.recv(1024).decode()
            lines.append(chunk)
            if "250 Ok" in chunk or "\n.\r\n" in chunk:
                break
        return "".join(lines)



    def send_and_print(self, sock, msg):
        """ Sends a message to the server and prints the message if in debug mode.

        :param sock: The socket object to send the message to.
        :param msg: The message to send.
        """
        sock.sendall((msg + "\r\n").encode())
        if self.debug_mode:
            print(f"> {msg}")

    def hash_password(self, password):
        """ Hashes the password using SHA256.

        :param password: The password to hash.
        :return: The hashed password.
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def fetch_inbox(self):
        """ Fetches the inbox of the user.
        
        Uses the POP3 command - STAT - to fetch the amount of emails (and size in octets) 
        of the user's inbox from the server. Calls pop3_trans().

        :return: Returns if uncessessful.
        """
        try:
            if not self.pop3_auth():
                return

            self.send_and_print(self.pop_socket, "STAT")
            stat = self.read_response(self.pop_socket)
            print(f"Server: {stat.strip()}") if self.debug_mode else ""
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
        """ Authenticates the user to the POP3 server.
        
        Uses POP3 commands - USER and PASS - to authenticate the user to the server.

        :return: Returns true if authentification is successful, false otherwise.
        """
        try:
            self.pop_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.pop_socket.connect((self.pop_ip, self.pop_port))
            ready = self.read_response(self.pop_socket)
            print(f"Server: {ready.strip()}") if self.debug_mode else ""
            if not ready.startswith("+OK"):
                print("POP3 server not ready.")
                self.pop_socket.close()
                return False

            self.send_and_print(self.pop_socket, "USER " + self.username)
            user_response = self.read_response(self.pop_socket)
            print(f"Server: {user_response.strip()}") if self.debug_mode else ""
            if not user_response.startswith(f"+OK {self.username}"):
                print("Error with username.")
                self.pop_socket.close()
                return False

            self.send_and_print(self.pop_socket, "PASS " + self.password_hash)
            pass_response = self.read_response(self.pop_socket)
            print(f"Server: {pass_response.strip()}") if self.debug_mode else ""
            if not pass_response.startswith(f"+OK {self.username}"):
                print("Error with password.")
                self.pop_socket.close()
                return False

            return True
        
        except Exception as e:
            print(f"POP3 error: {e}")
            return False
    
    def pop3_trans(self, total_msgs):
        """ POP3 Transaction function for client side.

        Provides the inbox menue once a user has authenticated to the POP3 server.
        Displays the inbox in pages of 10 messages at a time. 
        The user can choose to view a message, mark a message for deletion, or unmark all deletions.
        
        :param total_msgs: The total number of messages in the inbox.
        """
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
                print(response) if self.debug_mode else ""
            elif action == "r":
                self.send_and_print(self.pop_socket, "RSET")
                response = self.read_response(self.pop_socket).strip()
                if not self.isStatusOK(response):
                    self.pop_socket.close()
                    break
                print("All emails unmarked from deletion for this session.")
                print(response) if self.debug_mode else ""
            elif action == "q":
                self.send_and_print(self.pop_socket, "QUIT")
                print(self.read_response(self.pop_socket).strip())
                self.pop_socket.close()
                break
            else:
                print("Invalid option.")
            
    def isStatusOK(self, msg):
        """ Checks if a POP3 server response is a success message.
        
        :return: True if the response is a success message, False otherwise.
        """
        return msg.startswith("+OK") 


def main():
    parser = argparse.ArgumentParser(description="For running a SMTP/POP3 Client")

    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode (default: False)")
    parser.add_argument("--dns-ip", "-i", type=str, default="127.0.0.1", help="DNS server IP address (default: 127.0.0.1)")

    args = parser.parse_args()
    
    client = EmailClient(dns_ip=args.dns_ip, debug_mode=args.debug)
    client.run()


if __name__ == "__main__":
    main()
