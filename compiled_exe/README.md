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
"rt73.exe --device COM2 upload codeplug.json"\
\
\
DMR ID Database Upload - From CSV File\
"Ham Contacts" as this radio calls it has been added to the script. It expects the file to be a CSV with headers, specifically the RadioID.net database.\
"RADIO_ID,CALLSIGN,FIRST_NAME,LAST_NAME,CITY,STATE,COUNTRY"\
\
To upload to the radio is as easy as uploading the codeplug, you just need the CSV file location and the contact byte amount you wish to write\
16 bytes = DMR ID + CALLSIGN ONLY\
128 bytes = DMR ID + CALLSIGN + NAME + CITY + STATE + COUNTRY\
\
"rt73.exe --device COM2 upload_dmrid users.csv --dmridtype 16 (or 128)"\
\
\
The latest World-Wide full database dump is available here, Updated Daily!\
https://www.radioid.net/static/user.csv
