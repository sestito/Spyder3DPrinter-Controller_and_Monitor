# Get Started
## Data File
Your data file template is located in ./data. This is where you will add users, add printers, and adjust default variables. This file needs to be accessable by the Spyder Controller and the Spyder Status Bot. Either duplicate this file or save on a network folder.

## Config File
Make a copy of the config-template.ini file and name it as config.ini. Delete lines 1-3 in the file. In here you will insert the email information for the sender email. This email address will email users when prints are stopped. The DataFileLocation is wherever the data file from the above section is to be located.

## Spyder Status Bot
If you'd like to get statistics about the 3D printers, run this Python file.

## Spyder Controller
This is the main file that will be used to deploy GCode to the machines.

## Software
You will need Python 3 as well as the following Python packages:
* PyQT6
* configparser
* datetime
* pandas
* ssl
* requests
* sympy
* enum

# Build Executable
To build this as an executable, make sure to have pyinstaller installed. After installing the Pyinstaller, you will run the command below from the directory

Pyinstaller information: https://pyinstaller.readthedocs.io/en/stable/usage.html

pyinstaller --noconsole -i app.ico --onefile --add-data "Main.ui;." --add-data "table.xml;." --add-data "app.ico;." --add-data ".\data\SpyderPrintersInformation.xlsx;data" --add-data "config.ini;." SpyderController.py

instead of --onefile use --onedir

# Add a purpose code
If you'd like to add a purpose code to the program, do the following:
1. In SpyderController.py file, Add radio button to purpose group
2. In Controller.py file, add elif statement to purpose_code() method

