#!/usr/bin/env python3
#
# Example program using the Tello Drone SDK

import socket
import sys
import os
import time
import subprocess

commandSequence = [
  'command',
  'streamon',
  'battery?',
  'speed?',
  'takeoff',
  'flip f',
  'cw 180',
  'forward 50',
  'cw 180',
  'land'
]

# Check if the 'nmcli' binary exists to be able to control NetworkManager
def haveNmcli():
  try:
    netProc = subprocess.Popen(['nmcli'],
                               stdout=subprocess.DEVNULL)
    out,err = netProc.communicate()
  except FileNotFoundError as e:
    return False
  return True
  

# Get the UUID of the WiFi network for the Tello drone
def getWifiUUID():
  uuid = None
  netProc = subprocess.Popen(['nmcli', '-t', 'con'],
                             stdout=subprocess.PIPE)
  out,err = netProc.communicate()
  nets = out.decode(encoding='utf-8').rstrip('\n')
  for net in nets.split('\n'):
    name, nuuid, typ, dev = net.split(':')
    if 'TELLO' in name:
      if uuid is not None:
        # Don't support distinguishing between multiple drones
        print('Multiple Tello WiFi networks found')
        sys.exit(-1)
      uuid = nuuid
  if uuid == None:
    print('No Tello WiFi network found')
    sys.exit(-1)
  return uuid

# Check if there is a network adapter currently connected to the drone
def isConnected(uuid):
  connected = False
  netProc = subprocess.Popen(['nmcli', '-t', 'con'],
                             stdout=subprocess.PIPE)
  out,err = netProc.communicate()
  nets = out.decode(encoding='utf-8').rstrip('\n')
  for net in nets.split('\n'):
    name, nuuid, typ, dev = net.split(':')
    if (uuid == nuuid) and (len(dev) > 0):
      connected = True
      print('Connected to "{}"'.format(name))
  return connected

def main(disableNm, simulate):
  print('Tello Test Program')

  if disableNm or simulate:
    useNmcli = False
  else:
    if haveNmcli():
      useNmcli = True
    else:
      print('Cannot find "nmcli" to control NetworkManager')
      sys.exit(-1)

  if useNmcli:
    TELLO_WIFI_UUID = getWifiUUID()
    print('Drone WiFi: {}'.format(TELLO_WIFI_UUID))

    if isConnected(TELLO_WIFI_UUID):
      print('Already connected to drone')
    else:
      print('Connecting to Drone...')
      nm = subprocess.Popen(['nmcli', 'con', 'up', TELLO_WIFI_UUID],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
      nm.wait()
      if nm.returncode == 0:
        print('  Connected')
      else:
        print('  FAILED')
        sys.exit(-1)

  if not simulate:
    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # UDP:8889 used for commands to the drone
    tello_address = ('192.168.10.1', 8889)
    host = ''
    port = 9000
    locaddr = (host,port) 
    sock.bind(locaddr)

  running = True
  pendingCommands = list(commandSequence)

  vidProc = None
  vidFnamePrefix = "output"
  vidFnameCount = 1
  while os.path.exists(vidFnamePrefix+str(vidFnameCount)+".h264"):
    vidFnameCount += 1

  vidFname = vidFnamePrefix+str(vidFnameCount)+".h264"

  while running:
    if len(pendingCommands) > 0:
      cmd = pendingCommands[0]
      pendingCommands.pop(0)
      print('CMD : {}'.format(cmd))

      if not simulate:
        # Send command
        msg = cmd.encode(encoding='utf-8') 
        sent = sock.sendto(msg, tello_address)

        # Get response
        data, server = sock.recvfrom(1518)
        resp = data.decode(encoding='utf-8')
      else:
        resp = "sim ok"
      print('RESP: {}'.format(resp))

      if (cmd == 'streamon') and not simulate:
        # Give a delay to ensure the drone is streaming video
        # Video is sent on UDP port 11111
        time.sleep(5)
        vidProc = subprocess.Popen(['ffmpeg', '-v', '-8',
                                '-i', 'udp://@:11111',
                                '-vcodec', 'copy', '-acodec', 'none',
                                vidFname],
                                stdin=subprocess.PIPE,
                                stderr=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL)

    else:
      running = False

  if vidProc is not None:
    # Delay to ensure last part of video stream captured
    time.sleep(2)
    print('Closing video stream')
    vidProc.communicate('q'.encode(encoding='utf-8'))


if __name__=='__main__':
  import argparse

  parser = argparse.ArgumentParser(description='Tello Drone Example Program')
  parser.add_argument('-s', '--simulate', action='store_true', help='Simulate commands only')
  parser.add_argument('--no-nm', action='store_true', help='Don\'t use NetworkManager')

  args = parser.parse_args()

  main(args.no_nm, args.simulate)

