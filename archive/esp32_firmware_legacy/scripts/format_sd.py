#!/usr/bin/env python3
import serial
import time
import sys

port = 'COM6'
baudrate = 115200

try:
    print(f"Connecting to {port} at {baudrate} baud...")
    ser = serial.Serial(port, baudrate, timeout=10)
    time.sleep(2)  # Wait for connection
    
    print("Sending 'format_sd' command...")
    ser.write(b'format_sd\r\n')
    
    print("Waiting for response...")
    time.sleep(5)  # Wait for formatting to start
    
    # Read any available output
    output = b''
    for _ in range(20):  # Read for up to 10 seconds
        if ser.in_waiting > 0:
            output += ser.read(ser.in_waiting)
        time.sleep(0.5)
    
    if output:
        print("\nDevice response:")
        print(output.decode('utf-8', errors='ignore'))
    else:
        print("No response received (formatting may be in progress)")
    
    ser.close()
    print("\nDone!")
    
except serial.SerialException as e:
    print(f"Error: Could not open serial port: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
