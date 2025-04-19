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
A simple DNS server that maps domain names to IP/port pairs to enable SMTP server discovery. Each server, on startup, updates the DNS server with its newest IP and port. When a client wants to connect to a server, it requests the correct address from the DNS server.

### 2. smtp_client.py
An interactive email client that can log in using SMTP AUTH, compose and send emails, connect via DNS to locate a recipient's mail server, and can retrieve messages using the POP3 protocol implemented.

### 3. smtp_server.py
An SMTP and POP3 hybrid server that authenticates users via base-64 encoded credentials, accepts incoming mail via SMTP, stores and manages user inboxes through JSON, and supports POP3 commands for transferring mail requested by clients.

## Testing Reliable Data Transfer
To test the reliability of data transfer, three separate processes must be run. First, start the RDTRecvr by running: 
```
python3 RDTUnit.py --mode="recv"
```
Then, in a separate terminal window, start the middleman with: 
```
python3 middleman.py -c -l -r
```
Finally, in a third terminal, start the RDTSender with: 
```
python3 RDTUnit.py --mode="send"
```
This will start the sender sending data through the middleman to the receiver, with the middleman occasionally
corruptin, dropping, and reordering packets. For a description of all of the options available for each of the three
participants in this test, each command can be run with `-h` to print a help message. 


## Transfering Files
Similarly to the above example, multiple processes must be run for file transfer. For a basic example, run the following
two commands in separate terminal windows: 
```
python3 RFTServer.py
python3 RFTClient.py --mode=send -f <filename>
```
This will transfer <filename> from the sender to the receiver. For a description of the available options for the clients 
and servers, run each of the above commands with `-h`. 

