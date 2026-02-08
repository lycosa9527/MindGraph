# SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
# SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
#
# See LICENSE file for details.

#!/usr/bin/env python3
import argparse
import socket
import sys
from pathlib import Path
import os
from datetime import datetime
import logging

def get_primary_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()

def gen_filename():
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    return f'media_dump_{ts}.bin'

BUF_SIZE = 10240

def main():
    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    parser = argparse.ArgumentParser(description='Receive UDP media dump and save to file')
    parser.add_argument('--port', type=int, default=5000, help='UDP port (default: 5000)')
    args = parser.parse_args()

    primary_ip = get_primary_ip()
    logging.info(f'Host primary IP: {primary_ip}, port: {args.port}  (set MEDIA_DUMP_UDP_IP:PORT to this)')

    out_path = Path(gen_filename())
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(('0.0.0.0', args.port))
    except OSError as e:
        logging.error(f'Bind failed on 0.0.0.0:{args.port} - {e}')
        sys.exit(1)

    logging.info(f'Listening on 0.0.0.0:{args.port}, output file: {out_path.name} (created on first packet), buf={BUF_SIZE}')
    total = 0
    f = None
    try:
        while True:
            try:
                data, addr = sock.recvfrom(BUF_SIZE)
            except OSError:
                break
            if not data:
                logging.info('\nClose received, finishing and exiting')
                break
            if f is None:
                f = open(out_path, 'wb')
                logging.info(f'Receiving... writing to {out_path.resolve()}')
            f.write(data)
            total += len(data)
            sys.stdout.write(f'\r[INFO] recv={len(data)} bytes, total={total} bytes')
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        # ensure the progress line ends with newline
        try:
            sys.stdout.write('\n')
            sys.stdout.flush()
        except Exception:
            pass
        try:
            if f is not None:
                f.flush()
                os.fsync(f.fileno())
                f.close()
                logging.info(f'Saved file: {out_path.resolve()}')
            else:
                logging.info('No packets received, no file saved')
        except Exception as e:
            logging.error(f'Finalize file failed: {e}')
        logging.info(f'Done. Total bytes received: {total}')
        sys.exit(0)

if __name__ == '__main__':
    main()
