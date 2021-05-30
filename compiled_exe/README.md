This is a compiled exe version of the same script.\
This was made using pyinstaller and should contain all dependencies to run the script without the need to manually install Python or PySerial on your own PC/Laptop.\
\
To use this, open a command prompt (cmd.exe) and navigate to the directory where the exe is stored.\
Using the same command arguments as the python version you can download and upload to your radio.\
\
Download/Upload using the default COM port (COM1):\
"rt73.exe download codeplug.json"\
"rt73.exe upload codeplug.json"\
\
Specify your own COM port with the "--device COM*" parameter, e.g COM2:\
"rt73.exe --device COM2 download codeplug.json"\
"rt73.exe --device COM2 upload codeplug.json"
