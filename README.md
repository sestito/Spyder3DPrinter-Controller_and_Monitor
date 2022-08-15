# Build Executable
To build this as an executable, make sure to have pyinstaller installed. After installing the Pyinstaller, you will run the command below from the directory

Pyinstaller information: https://pyinstaller.readthedocs.io/en/stable/usage.html

pyinstaller --noconsole -i app.ico --onefile --add-data "Main.ui;." --add-data "table.xml;." --add-data "app.ico;." --add-data ".\data\SpyderPrintersInformation.xlsx;data" --add-data "config.ini;." SpyderController.py

instead of --onefile use --onedir

# Add a purpose code
1. In SpyderController.py file, Add radio button to purpose group
2. In Controller.py file, add elif statement to purpose_code() method

