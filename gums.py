#!/usr/bin/env python3

"""

gums, Grande Unicast Multicast Sender


"""
import argparse
import os
import socket
import sys
import time
from functools import partial
from new_reader import reader


DGRAM_SIZE = 1316

DEFAULT_MULTICAST = "235.35.3.5:3535"

MAJOR = "0"
MINOR = "0"
MAINTAINENCE = "33"


def version():
    """
    version prints version as a string

    """
    return f"{MAJOR}.{MINOR}.{MAINTAINENCE}"


class GumS:
    """
    GumS class is the UDP Unicast/Multicast Sender
    """

    def __init__(self, addr=None, mttl=1, bind_addr="0.0.0.0"):
        self.dest_ip, self.dest_port = addr.rsplit(":", 1)
        self.src_ip = bind_addr.rsplit(":", 1)[0]
        self.src_port = 0
        self.ttl = mttl
        self.dest_grp = (self.dest_ip, int(self.dest_port))
        self.sock = self.mk_sock()
        self.sock.bind((self.src_ip, self.src_port))

    def is_multicast(self):
        """
        is_multicast tests the first byte of an ipv4 address
        to see if it is in the multicast range.
        """
        net_id = int(self.dest_ip.split(".", 1)[0])
        if net_id in range(224, 240):
            return True
        return False

    def mk_sock(self):
        """
        mk_sock makes a udp socket, self.sock
        and sets a few opts.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        return sock

    def iter_dgrams(self, vid, target_rate_kbit = None):
        """
        iter_dgrams iterates over the video and sends
        self.dgram_size chunks of video to the socket.
        """
        million = 1024 * 1024
        if target_rate_kbit:
            byterate = target_rate_kbit * 1024 / 8
            dgrams_per_second = byterate /DGRAM_SIZE
            sleep_time_rate_limiter = 1 / dgrams_per_second
        else:
            sleep_time_rate_limiter = 0
        start_time = time.time()
        time.sleep(0.0001)
        now = time.time
        total_bytes = 0
        with reader(vid) as gum:
            for dgram in iter(partial(gum.read, DGRAM_SIZE), b""):
                time.sleep(sleep_time_rate_limiter)
                self.sock.sendto(dgram, self.dest_grp)
                total_bytes += len(dgram)
                elapsed = now() - start_time
                rate = (total_bytes / million) / elapsed
                print(
                    f"\t{total_bytes/million:0.2f} MB sent in {elapsed:5.2f} seconds. {rate:3.2f} MB/Sec, {rate*8*1024:3.2f} kBit/Sec.",
                    end="\r",
                    file=sys.stderr,
                )
            print("\n", file=sys.stderr)

    def send_stream(self, vid, target_rate_kbit = None):
        """
        send_stream sets multicast ttl if needed,
        prints socket address info,
        calls self.iter_dgrams,
        and closes the socket
        """
        proto = "udp://"
        pre = "Unicast"
        if self.is_multicast():
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
            proto = proto + "@"
            pre = "Multicast"
        src_ip, src_port = self.sock.getsockname()
        print(
            f"\n\t{pre} Stream\n\t{proto}{self.dest_ip}:{self.dest_port}",
            file=sys.stderr,
        )
        print(f"\n\tSource\n\t{src_ip}:{src_port}\n", file=sys.stderr)

        self.iter_dgrams(vid, target_rate_kbit)
        self.sock.close()


def parse_args():
    """
    parse_args parse command line args
    """

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i",
        "--input",
        default=None,
        help="""like "/home/a/vid.ts"
                or "udp://@235.35.3.5:3535"
                or "https://futzu.com/xaa.ts"
             """,
    )

    parser.add_argument(
        "-a",
        "--addr",
        default=DEFAULT_MULTICAST,
        help='Destination IP:Port like "227.1.3.10:4310"',
    )

    parser.add_argument(
        "-b",
        "--bind_addr",
        default="0.0.0.0",
        help='Local IP to bind to like "192.168.1.34". Default is 0.0.0.0',
    )

    parser.add_argument(
        "-t",
        "--ttl",
        default=1,
        help="Multicast TTL 1 - 255",
    )
    
    parser.add_argument(
        "-r",
        "--ratelimit",
        default=None,
        type=float,
        help="Target rate limit for sending in kbit. Default is sending with maximum speed.",
    )

    parser.add_argument(
        "-v",
        "--version",
        action="store_const",
        default=False,
        const=True,
        help="Show version",
    )

    return parser.parse_args()


def fork():
    """
    fork
    """

    pid = os.fork()
    if pid > 0:
        sys.exit(0)


def daemonize():
    """
    The Steven's double fork
    """

    fork()
    fork()


def cli():
    """
    cli adds command line args
    passes them to a Gums instance
    and calls self.send_stream
    in just one function call

    Use like this

    import gums

    if __name__ == "__main__":
        gums.cli()


    """

    args = parse_args()
    if args.version:
        print(version())
        sys.exit()
    #  daemonize()
    ttl = int(args.ttl).to_bytes(1, byteorder="big")
    dest_addr = args.addr
    gummie = GumS(dest_addr, ttl, args.bind_addr)
    gummie.send_stream(args.input, args.ratelimit)
    sys.exit()


if __name__ == "__main__":
    cli()
