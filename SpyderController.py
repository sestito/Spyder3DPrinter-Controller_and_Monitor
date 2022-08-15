'''
TODO

If it fails to upload, it stays in an unsalvagable state.
    I think this happens if a file is copied over and then never deleted?
    Maybe add a timeout?

Enter Retrying in the Controller.py file for uploading

'''


#from pickle import FALSE
import sys
import PyQt6
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QDialog, QApplication, QFileDialog, QWidget, QMainWindow, QButtonGroup, QMessageBox
from PyQt6.uic import loadUi

import tempfile
from pathlib import Path
import distutils

import configparser

import json
#import sched, time
from threading import Event, Thread
import math

import shutil
from datetime import timedelta

from Duet.Controller import DuetController

import pandas as pd
import os

import traceback, sys

default_path = os.path.dirname(os.path.realpath(__file__))

# Load config file
config = configparser.ConfigParser()
config.read(default_path + '\\' + 'config.ini')


main_ui_file = default_path + '\\' + "Main.ui"
defaults_file = default_path + '\\' + 'defaults.json'

downloads_path = str(Path.home() / "Downloads")

transfer_rate =   (60*5) / (71188*1024) #s/b  # Should I add a * 2 because it seems to be 2x too much

time_remaining_key = "Time Remaining"
printer_name_key = "Printer"
status_key = "Status"
printer_refresh_key = "PrinterRefresh"
users_key = 'Username'
password_key = 'Password'
timeout_buffer_key = 'TimeoutBuffer'

default_printer_selection_text = 'Select Printer...'


users_sheet = 'Users'
printers_sheet = 'Printers'
variables_sheet = 'Variables'

# This can also be done using a google document
#google_doc_id = 'XXXXX'
#users_url = 'https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s' % (google_doc_id, users_sheet)
#printers_url = 'https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s' % (google_doc_id, printers_sheet)
#variables_url = 'https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s' % (google_doc_id, variables_sheet)

data_file_location = config['DATAFILE']['DataFileLocation']

# If using a google document, download each sheet as a csv file
#users_url_local = default_path + '\\data\\' + 'SpyderPrintersInformation - Users.csv'
#printers_url_local = default_path + '\\data\\' + 'SpyderPrintersInformation - Printers.csv'
#variables_url_local = default_path + '\\data\\' + 'SpyderPrintersInformation - Variables.csv'
data_file_location_local = default_path + '\\data\\SpyderPrintersInformation.xlsx'

'''
def call_repeatedly(interval, func, *args):
    stopped = Event()
    def loop():
        while not stopped.wait(interval): # the first call is in `interval` secs
            func(*args)
    Thread(target=loop).start()    
    return stopped.set
'''

# https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/
class WorkerSignals(QtCore.QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    result = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(int)

class Worker(QtCore.QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        #self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

class MyApp(QMainWindow):

    printers = [] # Printers list from google
    users = [] # Users list from google
    data = {}
    controller = 0

    purpose_buttons = []
    
    use_local_data = False


    def __init__(self):
        super().__init__()
        loadUi(main_ui_file, self)
        self.threadpool = QtCore.QThreadPool()
        self.tableWidget_PrinterStatuses.setColumnWidth(0,150)
        self.initialize()

        self.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, False)

        self.pushButton_GCode_Browse.clicked.connect(self.browsefiles)
        self.pushButton_UpdatePrinters.clicked.connect(self.forced_update_printer_status)
        self.pushButton_Clear.clicked.connect(self.clear_print_form)
        self.pushButton_Upload.clicked.connect(self.submit_gcode)
        self.comboBox_PrinterList.currentIndexChanged.connect(self.update_last_print)
        self.pushButton_RunPreviousFile.clicked.connect(self.reprint)
        #self.printer_refresh_call = call_repeatedly(self.data[printer_refresh_key], self.update_printer_status)
        
        self.printer_timer = QtCore.QTimer()
        self.printer_timer.setInterval(1000*int(self.data[printer_refresh_key]))
        self.printer_timer.timeout.connect(self.update_printer_status)
        self.printer_timer.start()

        self.upload_timer = QtCore.QTimer()
        self.upload_timer.setInterval(1000*1)
        self.upload_timer.timeout.connect(self.set_progress_bar)
        self.upload_timer_time = 0
        self.upload_timer_file_size = 1

        self.setFixedSize(self.size())


        self.group = QButtonGroup()
        self.purpose_buttons = [self.radioButton_Purpose_Class, self.radioButton_Purpose_SeniorDesign, self.radioButton_Purpose_Research, self.radioButton_Purpose_Org, self.radioButton_Purpose_Personal]
        for button in self.purpose_buttons:
            self.group.addButton(button)
    
    def destroy(self):
        self.controller.destroy()

    def update_last_print(self):
        try:
            printer = self.comboBox_PrinterList.currentText()
            if printer == default_printer_selection_text:
                self.lineEdit_PreviousFile.setText('')
                self.lineEdit_PreviousFile.setEnabled(False)
                self.pushButton_RunPreviousFile.setEnabled(False)
                self.previous_file_data = {}
            else:
                filename = self.controller.get_most_recent_file(printer)
                self.previous_file_data = self.controller.filename_information(filename)
                self.lineEdit_PreviousFile.setText(self.previous_file_data['filename'])
                self.lineEdit_PreviousFile.setEnabled(True)
                self.pushButton_RunPreviousFile.setEnabled(True)

            
            if not self.pushButton_Upload.isEnabled():
                self.lineEdit_PreviousFile.setEnabled(False)
                self.pushButton_RunPreviousFile.setEnabled(False)
            

        except:
            self.lineEdit_PreviousFile.setText('')
            self.lineEdit_PreviousFile.setEnabled(False)
            self.pushButton_RunPreviousFile.setEnabled(False)
            self.previous_file_data = {}


    def reprint(self):
        try:
            printer = self.comboBox_PrinterList.currentText()
            file = self.previous_file_data['fullfile']
            if printer != '' and file != '':
                self.controller.print_from_sd(printer,file)
        except:
            print('Reprint failed.')

    def closeEvent(self, *args, **kwargs):
        super(QMainWindow, self).closeEvent(*args, **kwargs)
        #self.printer_refresh_call()
        self.controller.disconnect_printers()

    # This is all the initialization
    def initialize(self):
        self.load_default_data()
        self.load_data()
        self.controller = DuetController(self.printers, self.data, self.data['Debug'])
        self.update_printer_status()

    # Run this on startup or whenever we want to update constants
    def load_default_data(self):
        
        if self.use_local_data:
            # If using a google doc
            #data = pd.read_csv(variables_url_local)

            data = pd.read_excel(data_file_location_local, sheet_name=variables_sheet)
        else:
            try:
                # If using a google doc
                #data = pd.read_csv(variables_url)

                data = pd.read_excel(data_file_location, sheet_name=variables_sheet)
            except: 
                data = pd.read_excel(data_file_location_local, sheet_name=variables_sheet)

                # If using a google doc
                #data = pd.read_csv(variables_url_local)
        
        
        self.data = {}
        for index, row in data.iterrows():
            variable_name = row['Variable']
            variable_value = row['Value']
            self.data[variable_name] = variable_value
        
        try:
            if self.data['Debug'] == 'True':
                self.data['Debug'] = True
            else:
                self.data['Debug'] = False
        except:
            pass

        try:
            if self.data['VerifyGCode'] == 'True':
                self.data['VerifyGCode'] = True
            else:
                self.data['VerifyGCode'] = False
        except:
            pass

        

        #f = open(defaults_file)
        #self.data = json.load(f)
        #f.close()
        

    # Run this whenever we want to update users / printers
    def load_data(self):
        # Load static Data file
        
        if self.use_local_data:
            # If using a google doc
            #self.users = pd.read_csv(users_url_local)
            #self.printers = pd.read_csv(printers_url_local)

            self.users = pd.read_excel(data_file_location_local, sheet_name=users_sheet)
            self.printers = pd.read_excel(data_file_location_local, sheet_name=printers_sheet)
        else:
            try:
                # If using a google doc
                #self.users = pd.read_csv(users_url)

                self.users = pd.read_excel(data_file_location, sheet_name=users_sheet)
            except:
                # If using a google doc
                #self.users = pd.read_csv(users_url_local)

                self.users = pd.read_excel(data_file_location_local, sheet_name=users_sheet)

            try:
                # If using a google doc
                #self.printers = pd.read_csv(printers_url)

                self.printers = pd.read_excel(data_file_location, sheet_name=printers_sheet)
            except:
                # If using a google doc
                #self.printers = pd.read_csv(printers_url_local)
                
                self.printers = pd.read_excel(data_file_location_local, sheet_name=printers_sheet)
        


    def forced_update_printer_status(self):
        # TODO Reget file from Google
        def update(self):
            self.controller.disconnect_printers()
            self.load_default_data()
            self.load_data()
            self.controller.initialize(self.printers, self.data)

        worker = Worker(update, self)
        worker.signals.result.connect(self.update_printer_status)
        self.threadpool.start(worker)


        

    # Update the printer statuses
    def update_printer_status(self):

        #print(time.time(), 'Updating Status')
        #self.tableWidget_PrinterStatuses
        #self.tableWidget_PrinterStatuses.updateFromDict(self.controller.printers)
        #self.controller.update_printers_status() # TODO have this launch in a new thread, then callback below
        worker = Worker(self.controller.update_printers_status)
        worker.signals.result.connect(self.update_printer_status_table)
        self.threadpool.start(worker)

    def update_printer_status_table(self):
        available_printers = [default_printer_selection_text]


        
        self.tableWidget_PrinterStatuses.clearContents()

        red = QtGui.QBrush(QtGui.QColor(255,0,0))
        yellow = QtGui.QBrush(QtGui.QColor(255,255,0))
        green = QtGui.QBrush(QtGui.QColor(0,255,0))
        white = QtGui.QBrush(QtGui.QColor(255,255,255))

        for index, row in self.controller.printers.iterrows():
            self.tableWidget_PrinterStatuses.insertRow(index)
            newitem1 = QtWidgets.QTableWidgetItem(row[printer_name_key])
            newitem2 = QtWidgets.QTableWidgetItem(row[status_key])
            if row[status_key] == 'Offline':
                #newitem1.setBackground(red)
                #newitem1.setForeground(white)
                newitem2.setBackground(red)

            elif row[status_key] == 'Idle':
                
                #newitem1.setBackground(green)
                newitem2.setBackground(green)
            else:
                #newitem1.setBackground(yellow)
                newitem2.setBackground(yellow)

            newitem1.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
            newitem2.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)

            if row[status_key] == 'Printing':
                # TODO incorporate this into the update_printers_status
                time_remaining = row[time_remaining_key] # seconds

                time_remaining = math.ceil(time_remaining / 60)
                if time_remaining > 1:
                    str_format = timedelta(seconds = time_remaining)
                    str_format = str(str_format)[2:]
                else:
                    str_format = '00:01'
                newitem3 = QtWidgets.QTableWidgetItem(str_format)
                newitem3.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.tableWidget_PrinterStatuses.setItem(index, 2, newitem3)


            self.tableWidget_PrinterStatuses.setItem(index, 0, newitem1)
            self.tableWidget_PrinterStatuses.setItem(index, 1, newitem2)
            if row[status_key] == 'Idle':
                available_printers.append(row[printer_name_key])
        
        self.update_available_printers(available_printers)


    # Update the rpinter selection box.            
    def update_available_printers(self, data):
        previous_text = self.comboBox_PrinterList.currentText()
        self.comboBox_PrinterList.clear() # Deletes all items
        self.comboBox_PrinterList.addItems(data)
        try:
            index = data.index(previous_text)
            self.comboBox_PrinterList.setCurrentIndex(index)
        except:
            self.comboBox_PrinterList.setCurrentIndex(0)



    def clear_print_form(self):
         # Set combo box to 1 selection
        self.comboBox_PrinterList.setCurrentIndex(0)

         # Clear Gcode File
        self.lineEdit_GCode_File.clear()

         # Clear username field
        self.lineEdit_Username.clear()
        self.lineEdit_Password.clear()

         # Deselect purpose
        self.group.setExclusive(False)
        for button in self.purpose_buttons:
            button.setChecked(False)
        self.group.setExclusive(True)

    def browsefiles(self):
        fname = QFileDialog.getOpenFileName(self, 'Select GCode', downloads_path, 'G-CODE files (*.gcode)') # TODO set file type
        self.lineEdit_GCode_File.setText(fname[0])

    # Submit to server
    '''
    def submit_gcode(self):
        worker = Worker(self.submit_gcode_function)
        self.threadpool.start(worker)
    '''

    def submit_gcode(self):
        self.set_gcode_fields(False)
        data = self.check_and_get_gcode_fields() # Get all fields

        # if all fields filled continue, else throw errr
        if data is not False:
                

            # freeze all fields
            self.set_gcode_fields(False)


            # Set update bar
            self.progressBar_Upload.setValue(1)

            self.printer_timer.stop()

            # Send command
            self.upload_timer_time = 0
            self.upload_timer_file_size = os.path.getsize(data['file'])
            worker = Worker(self.send_print_command, data, self.controller)
            worker.signals.result.connect(self.print_complete)
            self.threadpool.start(worker)
            #print_success =  self.send_print_command(data)
            self.upload_timer.start()

            # clear fields
            '''
            if print_success:
                self.clear_print_form()
            else:
                text = "Could not send G-code!"
                QMessageBox.warning(self, "Error", text)
            self.progressBar_Upload.setValue(0)
            self.set_gcode_fields(True)
            '''

        # unfreeze all fields
        else:
            self.set_gcode_fields(True)

    def set_progress_bar(self):
        total_time = self.upload_timer_file_size * transfer_rate
        amount = self.upload_timer_time / total_time
        amount = int(amount * 100)
        if amount > 99:
            amount = 99
        self.progressBar_Upload.setValue(amount)
        self.upload_timer_time += 1

    def print_complete(self, print_success):
        self.printer_timer.start()
        if print_success:
            self.clear_print_form()
        else:
            text = "Could not send G-code!"
            QMessageBox.warning(self, "Error", text)
        self.upload_timer.stop()
        self.progressBar_Upload.setValue(0)
        self.set_gcode_fields(True)
        self.upload_timer_time = 0
        self.upload_timer_file_size = 1
        


    def send_print_command(self, data, controller):
        
        try:
            printer = data["printer"]

            file_path = data['file']
            prefix = data['prefix']
            # Copy file with new name
            #REmove spaces from new file
            
            newfilename = os.path.basename(file_path)
            newfilename = newfilename.replace(" ","")
            #new_file_path = default_path + '\\' + prefix + newfilename
            new_file_path = tempfile.gettempdir() + '\\' + prefix + newfilename

            shutil.copyfile(file_path, new_file_path)


            # Send file over
            
            # Send print command
            #total_time = self.upload_timer_file_size * transfer_rate
            #timeout_time = int(total_time * float(self.data[timeout_buffer_key]))

            result = controller.send_gcode(printer, new_file_path)

            #result = self.controller.send_gcode(printer, new_file_path)
            

            #th = Thread(target=new_thread, args=(controller, printer, new_file_path)).start()
            #if th.is_alive():

            output_return = True

            if not result:

                output_return = False

        except:
            
            output_return = False

        try:
            # Delete all gcode files in directory
            #files_in_directory = os.listdir(default_path)
            files_in_directory = os.listdir(tempfile.gettempdir())
            filtered_files = [file for file in files_in_directory if file.endswith(".gcode")]
            for file in filtered_files:
                #path_to_file = os.path.join(default_path, file)
                path_to_file = os.path.join(tempfile.gettempdir(), file)
                os.remove(path_to_file)

            return output_return
        except:
            return output_return




    def set_gcode_fields(self, use = False):
        self.comboBox_PrinterList.setEnabled(use)
        self.lineEdit_GCode_File.setEnabled(use)
        self.pushButton_GCode_Browse.setEnabled(use)
        self.lineEdit_Username.setEnabled(use)
        self.lineEdit_Password.setEnabled(use)
        self.groupBox_Purpose.setEnabled(use)
        self.pushButton_Upload.setEnabled(use)
        self.pushButton_Clear.setEnabled(use)
        self.pushButton_UpdatePrinters.setEnabled(use)
        if not use:
            self.lineEdit_PreviousFile.setEnabled(False)
            self.pushButton_RunPreviousFile.setEnabled(False)

    def verify_username(self, username):
               
        total_usernames = self.users[self.users[users_key] == username]
        # self.users[self.users[users_key] == username]
        # This returns the row of the user
        if len(total_usernames) >= 1:
            return True
        else:
            return False
        

    def check_and_get_gcode_fields(self):
        data = {}

        # Get Printer
        printer = self.comboBox_PrinterList.currentText()
        if printer == default_printer_selection_text:
            text = "Select a printer!"
            QMessageBox.warning(self, "Error", text)
            return False
        data['printer'] = printer

        # Get File Path
        file_path = self.lineEdit_GCode_File.text()
        if file_path == "":
            text = "Select your G-code!"
            QMessageBox.warning(self, "Error", text)
            return False
        data['file'] = file_path

        # Get Username
        username = self.lineEdit_Username.text().lower()
        if username == "":
            text = "Insert your username!"
            QMessageBox.warning(self, "Error", text)
            return False
        elif not self.verify_username(username):
            text = "User does not have access to the printers!"
            QMessageBox.warning(self, "Error", text)
            return False
            

        # Purpose Buttons
        purpose = ""
        for button in self.purpose_buttons:
            if button.isChecked():
                purpose = button.text()
        if purpose == "":
            text = "Select a purpose for the print!"
            QMessageBox.warning(self, "Error", text)
            return False

        # Check password
        password = self.lineEdit_Password.text()

        #user_info = self.users
        user_info = self.users[self.users[users_key] == username] # Row of user
        user_password = str(user_info[password_key].iloc[0])

        if password != user_password:
            text = "Incorrect Password!"
            QMessageBox.warning(self, "Error", text)
            self.lineEdit_Password.setText('')
            return False

        # Assembly prefix
        prefix = self.controller.assemble_prefix(username, purpose)
        data["prefix"] = prefix
        
        return data
        
         
        

        


if __name__ == '__main__':


    
    app = QApplication(sys.argv)

    # app.setStyleSheet('''
    #     QMainWindow {
    #         front-style: 300px;
    #     }
    # ''')
        
    myApp = MyApp()
    myApp.show()

    try:
        sys.exit(app.exec())
    except SystemExit:
        myApp.destroy()
        print('Closing Window...')
