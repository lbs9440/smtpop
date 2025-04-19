# SMTPOP - Caleb N. & Landon Spitzer

## Description
SMTPOP implements a basic email delivery and retreival systems using simplified versions of SMTP and POP3, and making use of a simple DNS server for SMTP server discovery.

## Getting Started:
### Starting the Virtual Environment
When installing dependencies for any Python project, it is good practice to do so from within a virtual environment.
To create a virtual environment for this project, run `python3 -m venv .venv` from a terminal window. 
To start the venv, on a Unix-based system, run `source .venv/bin/activate` from the same directory.

### Installing Dependencies
This project depends on a few required dependencies for building the documentation and sending multiline messages. To install these, 
run the following command from within the venv:
`pip install -r requirements.txt`

### A Note on Administrator Priveleges
The scripts in this project use raw UDP sockets for network communication. As such, when attempting communication 
between machines (rather than running scripts locally), the scripts must be run with admin privileges in order to 
bypass security restrictions. To do this on a Unix-based system, preface each command with `sudo`.

## Components

### 1. dns.py
A simple DNS server that maps domain names to IP/port pairs to enable SMTP server discovery. Each server, on startup, 
updates the DNS server with its newest IP and port. When a client wants to connect to a server, it requests the correct 
address from the DNS server.

### 2. smtp_client.py
An interactive email client that can use the DNS to locate a recipient's mail server, log in using SMTP plaintext AUTH,
compose and send emails, and can retrieve messages using the POP3 protocol implemented.

### 3. smtp_server.py
An SMTP and POP3 hybrid server that authenticates users via base-64 encoded credentials, accepts incoming mail via SMTP,
stores and manages user inboxes in JSON 'databases', and supports POP3 commands for transferring mail requested by clients.

## Running The System
To test the system as a whole in the simplest manner possible, three processes are needed. First, in a new terminal
window, run:
```
cd dns
python3 dns.py
```
This command will start the DNS server, a requirement for both the server and the client to begin running. Then, in a 
separate terminal window, start the SMTP server with: 
```
python3 smtp_server.py
```
The server will update the DNS as to its port and IP address, and begin listening for new connections from clients. 
Finally, in a third terminal, start the Email Client with: 
```
python3 smtp_client.py
```
This will start the email client for user interraction. First input some credentials, then begin interracting with the
client. One existing account for testing that can be used is `landon@abeersclass.com`, with the password `password`. 
For a description of all of the options available for each of the three participants in this test, each command can be 
run with `-h` to print a help message. 


## Communicating Across Machines and Between SMTP Servers
This example will demonstrate how to use the system to send emails both between physically different machines (via Local
Area Network) and between differing email domains (using SMTP forwarding between email servers).

### Setup.
To begin, first make sure that both machines are connected to the same Local Area Network. Note the LAN IP of the
machine on which the DNS server will be running, and start the DNS server by running the following command in a terminal
window: 
```
cd dns
python3 dns.py
```

### Starting the Servers
Once the DNS is running, the servers can be started. On each machine that will be participating, run the following
command, substituting {dns-ip} with the LAN IP of the machine on which the DNS Server is running. {domain} should also
be substituted with the domain to be attached to each server. The two pre-configured domains are `abeersclass.com` and
`email.com`. 
```
python3 smtp_server.py -dns="{dns-ip}" -domain="{domain}"
```

### Running the Clients
Finally, the clients may be started. To do so, run the following command in each desired client terminal, again 
substituting {dns-ip} as discussed above. 
```
python3 smtp_client.py -i="{dns-ip}"
```

## Adding Domains and Accounts
This project comes preconfigured with two email domains (`abeersclass.com` and `email.com`), with one user account per 
domain (`landon@abeersclass.com` and `caleb@email.com`, both with the password `password`). In case this proves
restrictive, instructions for adding new domains and accounts are as follows:

### Adding a Domain
To add a domain, copy the provided `template` directory, renaming it to correspond to the name of the new domain. For 
example, the folder `abeersclass` corresponds to the `abeersclass.com` domain. Now, follow the instructions in the
following subsection to add a new account to that domain. Your new domain is now able to be used! Simply start up a new 
server, passing in your new domain name to the `-domain` argument.

### Adding an account
To add a new account to any domain, first decide on a username and password for the account. Then, run the following
command to get the hashed version of the account's password, noting the output. {password} should be substituted for the
password of the new account. 
```
python3 get_password.py() -p {password}
```
Then, add the following line to the `accounts.json` file in the directory associated with the domain to which the new
account will belong, substituting {username} for the account's username and {hashed_password} for the output of the
previous command: 
```
"{username}": {hashed_password}
```
