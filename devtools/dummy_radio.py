#! /usr/bin/python3
import os, pty, serial

master, slave = pty.openpty()
s_name = os.ttyname(slave)
ser = serial.Serial(s_name)
print ("Dummy RT73 now listening on device: " + s_name)
m_name = os.ttyname(master)
# To read from the device
while True:
    bytes = os.read(master,31)
    num_pages = int(bytes[18]) 
    print("Receiving " + str(num_pages) + " pages")



    os.write(master, b"\x20\x20\x57\x72\x69\x74\x65\x5f\x32\x4d\x5f\x00\x31\x30\x39\x45\x2e\x44\x34\x2e\x45\x41\x52\x53\x41\x42\x2e\x30\x30\x36\x2e\x4f\x63\x74\x20\x32\x38\x20\x32\x30\x32\x30\x00\x00\x00\x00\x00\x00\x00\x31\x31\x3a\x32\x33\x3a\x32\x35\x00\x00\x2b\x44\x52\x53\x2d\x33\x30\x30\x55\x56\x2b\x31\x33\x36\x2d\x34\x38\x30\x4d\x48\x5a\x2b\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff")

    f = open("codeplug",'rb')
    out = open("outplug", 'wb')
    for j in range(num_pages):
        byte_block  = os.read(master,2048)
        out.write(byte_block)
        out.flush()

        orig_block = f.read(2048)

        for i in range(2048):
            if byte_block[i] != orig_block[i]:
               print("Byte "+ hex(j*2048 + i) + " differs - " + hex(orig_block[i]) + " ->  " + hex(byte_block[i]))

        #Get next block
        print ("Writing page " + str(j) + "")
        os.write(master, "Write".encode('ascii'))
    
    out.close()


