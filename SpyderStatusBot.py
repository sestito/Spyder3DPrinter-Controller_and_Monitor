'''
Data To Store
DateTime, Username, 


'''


from Duet.Controller import DuetController

import traceback

from enum import Enum

import pandas as pd
import os

from datetime import datetime as dt
import datetime
import time

import smtplib, ssl

import math
import time

import configparser

from datetime import datetime as dt

default_path = os.path.dirname(os.path.realpath(__file__))

# Load config file
config = configparser.ConfigParser()
config.read(default_path + '\\' + 'config.ini')

# Data File Constants
data_file_location_local = default_path + '\\data\\SpyderPrintersInformation.xlsx'
data_file_location = config['DATAFILE']['DataFileLocation']
users_sheet = 'Users'
printers_sheet = 'Printers'
variables_sheet = 'Variables'

# Log Variables
log_path = default_path
log_name = 'MonitorLog.txt'

# Job Variables
joblog_path = default_path
joblog_name = 'MonitorJobData.csv'

# Keys
filament_extruded_key = "FilamentExtruded"
fraction_key = "Fraction"
print_duration_key = "PrintDuration"
printer_name_key = 'Printer'
users_key = "Username"
email_key = "Email"

def seconds_to_time(seconds):
    seconds = int(seconds)
    return str(datetime.timedelta(seconds=seconds))

def email(body, subject, emails):
    message = 'Subject: ' + subject + '\n\n' + body

    port = config['EMAIL']['Port']
    port = int(port)
    username = config['EMAIL']['Username']
    password = config['EMAIL']['AppPassword']
    sender_email = config['EMAIL']['SenderEmail']

    # Create a secure SSL context
    context = ssl.create_default_context()

    with smtplib.SMTP_SSL(config['EMAIL']['SmtpServer'], port, context=context) as server:
        server.login(username, password)
        for email in emails:
            server.sendmail(sender_email, email, message)   

class Logger:
    delimiter   = '\t'
    end_line = '\n'

    def __init__(self, path, filename):
        self.filename = path + '\\' + filename
        self.open()

    def __call__(self, string, prefix = 'LOG', printer = None, print_log = True):
        self.log(string, prefix, printer, print_log)

    def open(self):
        self.f = open(self.filename, 'a')

    def log(self, string, prefix = 'LOG', printer = None, print_log = True):
        # Date time pulled from https://www.programiz.com/python-programming/datetime/current-datetime
        now = dt.now()
        # dd/mm/YY H:M:S
        dt_string = now.strftime("%d/%m/%Y\t%H:%M:%S")

        prefix = '[' + prefix.upper() + ']'

        string_to_write = ''
        string_to_write += prefix + self.delimiter 
        string_to_write += dt_string + self.delimiter
        if printer is not None:
            string_to_write += printer + self.delimiter
        string_to_write += string
        
        self.f.write(string_to_write + self.end_line)

        if print_log:
            print(string_to_write)        

    def close(self):
        self.f.close()
        self.f = None


class JobLog:
    delimiter = ','
    end_line = '\n'

    def __init__(self, path, filename):
        self.filename = path + '\\' + filename
        self.open()
    
    def __call__(self, data):
        self.write(data)

    def open(self):
        self.f = open(self.filename,'a')

    def write(self, data):
        l = len(data)
        i = 0
        for string in data:
            self.f.write(str(string))
            if i != (l - 1):
                self.f.write(self.delimiter)
            i += 1
        self.f.write(self.end_line)

    def close(self):
        self.f.close()
        self.f = None


class PrinterStates(Enum):
    IDLE = 'Idle'
    PRINTING = 'Active - Printing'
    MAINTENANCE = 'Active - Maintenance'

class StatusBot:

    printers = {}
    users = {}
    data = {}
    controller = 0
    use_local_data = False

    log_print_text = True

    old_printer_state_row = {}

    def __init__(self):
        self.initialize()

    def initialize(self):
        self.log = Logger(log_path, log_name)
        self.job_log = JobLog(joblog_path, joblog_name)
        self.load_data()
        self.load_printers()
        self.controller = DuetController(self.printers, self.data, self.data['Debug'])
        # Controller initialization connects printers and updates the printers status

        self.log('BOOT', 'STARTUP')
        for index, row in self.controller.printers.iterrows():
            if row['Status'] != 'Offline':
                self.log('Printer Online', 'STARTUP', row[printer_name_key])
            else:
                self.log('Printer Offline', 'STARTUP', row[printer_name_key])


    def reload_data(self):
        #print(self.printers)
        self.load_data()
        self.controller.reinitialize_variables(self.data)
        #print(self.printers)

    def load_printers(self):
        # Load all of the data for data, users, and printers

        if self.use_local_data:

            self.printers = pd.read_excel(data_file_location_local, sheet_name=printers_sheet)
        else:


            try:
                self.printers = pd.read_excel(data_file_location, sheet_name=printers_sheet)
            except:
                self.printers = pd.read_excel(data_file_location_local, sheet_name=printers_sheet)


    def load_data(self):
        # Load all of the data for data, users, and printers

        if self.use_local_data:
            data = pd.read_excel(data_file_location_local, sheet_name=variables_sheet)
            self.users = pd.read_excel(data_file_location_local, sheet_name=users_sheet)
            #self.printers = pd.read_excel(data_file_location_local, sheet_name=printers_sheet)
        else:
            try:
                data = pd.read_excel(data_file_location, sheet_name=variables_sheet)
            except: 
                data = pd.read_excel(data_file_location_local, sheet_name=variables_sheet)

            try:
                self.users = pd.read_excel(data_file_location, sheet_name=users_sheet)
            except:
                self.users = pd.read_excel(data_file_location_local, sheet_name=users_sheet)

            #try:
            #    self.printers = pd.read_excel(data_file_location, sheet_name=printers_sheet)
            #except:
            #    self.printers = pd.read_excel(data_file_location_local, sheet_name=printers_sheet)


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

    def destroy(self):
        self.controller.disconnect_printers()
        self.controller.destroy()
        self.log.close()
        self.job_log.close()

    def reset_printers(self):
        self.controller.disconnect_printers()
        self.controller.connect_printers()
        self.controller.update_printers_status()

    def check_for_status_change(self):
        old_printer_state = self.controller.printers.copy() # Copy so you don't have reference
        #print(old_printer_state)
        self.controller.update_printers_status()
        self.controller.set_current_file()
        new_printer_state = self.controller.printers
        #print(new_printer_state)

        check = old_printer_state['Status'] == new_printer_state['Status']
        #print('State' in old_printer_state.index)
        #print(old_printer_state.columns)

        for i in range(len(check)):
            if check[i] == False or old_printer_state.loc[i,'State'] == '': # This signifies a status change
                old_row = old_printer_state.loc[i]
                new_row = new_printer_state.loc[i]
                
                # Log the status change
                self.log('Status Change: ' + new_row['Status'], printer=new_row['Printer'], print_log=self.log_print_text)



                # 3 States we can be in
                #   Idle
                #   Active - Printing
                #   Active - Maintenance

                # We are in Idle state
                if new_row['Status'] == 'Idle' or new_row['Status'] == 'Halted':
                    self.controller.printers.loc[i,'State'] = PrinterStates.IDLE
                    if old_row['State'] == PrinterStates.PRINTING:
                        # JOB JUST COMPLETED. 
                        # Check if last state was failed and then get previous old.
                        if old_row['Status'] == 'Failed' or old_row['Status'] == 'Offline':
                            old_row = self.old_printer_state_row[str(i)]

                        filament_extruded = old_row[filament_extruded_key]
                        fraction_completed = old_row[fraction_key]
                        print_duration = old_row[print_duration_key]
                        
                        

                        username = ''
                        purpose_code = ''
                        filename = ''
                        #filename_full = self.controller.get_most_recent_file(old_row[printer_name_key])
                        filename_full = old_row['FileName']
                        if filename_full != '':
                            datafile = self.controller.filename_information(filename_full)
                            username = datafile['username']
                            purpose_code = datafile['purpose_code']
                            filename = datafile['filename']

                        now = dt.now()
                        dt_string = now.strftime("%d/%m/%Y,%H:%M:%S")



                        #print(print_duration)


                        # 
                        # CHECK FOR PASS/FAIL
                        # LOG JOB
                        self.job_log(   [dt_string,
                                        old_row[printer_name_key],
                                        username,
                                        purpose_code,
                                        filename,
                                        int(print_duration),
                                        int(filament_extruded),
                                        float(fraction_completed)])

                        # Log COMPLETE
                        self.log('Job for ' + username + ' Complete: ' + filename, printer=old_row[printer_name_key])
                        
                        # SEND EMAIL
                        try:
                            user_info = self.users[self.users[users_key] == username] # Row of user
                            user_email = str(user_info[email_key].iloc[0])
                            if not user_email == 'nan':# TODO fix this
                                body = 'Your 3D print completed!\nFilename: ' + filename + '\nMachine: ' + old_row[printer_name_key] + '\nTotal Run Time: ' + seconds_to_time(print_duration)
                                subject = old_row[printer_name_key] + ': Print complete!'
                                email(body, subject, [user_email])
                                self.log('Email sent to ' + user_email, printer=old_row[printer_name_key])
                            else:
                                # TODO Maybe turn this log off?
                                self.log('User ' + username + ' has no email address.', printer=old_row[printer_name_key])

                        except:
                            self.log('Could not send email to user: ' + username + ' Full filename: ' + filename_full, 'ERROR',printer=old_row[printer_name_key])
                            #print(traceback.format_exc())



                        

                elif new_row['Status'] == 'Printing' and new_row['State'] != PrinterStates.PRINTING:
                    self.controller.printers.loc[i,'State'] = PrinterStates.PRINTING
                    # NEW JOB STARTED
                    username = ''
                    purpose_code = ''
                    filename = ''
                    #filename_full = self.controller.get_most_recent_file(old_row[printer_name_key])
                    filename_full = new_row['FileName']
                    #print(filename_full)
                    if filename_full != '':
                        datafile = self.controller.filename_information(filename_full)
                        username = datafile['username']
                        purpose_code = datafile['purpose_code']
                        filename = datafile['filename']
                    self.log('Job by ' + username + ' Started: ' + filename, printer=new_row['Printer'], print_log=self.log_print_text)

                elif new_row['State'] != PrinterStates.PRINTING:
                    self.controller.printers.loc[i,'State'] = PrinterStates.MAINTENANCE

                elif new_row['Status'] == 'Failed' or new_row['Status'] == 'Offline':
                    if old_row['Status'] != 'Failed' and old_row['Status'] != 'Offline':
                        self.old_printer_state_row[str(i)] = old_row


        
debug = False

interval_time = 20 # Seconds
data_reload_interval = 1 # hours
data_reload_interval = data_reload_interval * 60 * 60 # Convert from hours to seconds

reboot_check_interval = 18 #hours
reboot_check_interval = reboot_check_interval * 60 * 60
delay_one = False

if debug:
    interval_time = 1 # Second
    data_reload_interval = 3 # SEconds





bot = StatusBot()
data_reload_occured = time.time()
reboot_check_occured = time.time()

if debug:
    print('WE ARE IN DEBUG MODE!!!!!!!')

while True:
    current_time = time.time() # Get current time for all checks

    try:
        if (current_time - reboot_check_occured) > reboot_check_interval:
            reboot_check_occured = current_time

            if delay_one: # Could potentially be the same day
                delay_one = False
            else:
                # Check if it's Sunday
                day = dt.today().strftime('%A')
                if day == 'Sunday':
                    #Reboot
                    bot.log('Reboot','REBOOT')
                    bot.destroy()
                    del bot

                    bot = StatusBot()
                    

                    delay_one = True
    except:
        print('Error: Reboot Check')
        print(traceback.format_exc())



    try:
        bot.check_for_status_change()
        #print('Check Status Update')
    except:
        print('Error: Status Update')
        print(traceback.format_exc())

    
    try: # TEST THIS OUT
        
        if (current_time - data_reload_occured) > data_reload_interval:
            data_reload_occured = current_time
            bot.reload_data()
            #print('Data Reloaded')
    except:
        print('Error: Data Reload')
        print(traceback.format_exc())
    


    time.sleep(interval_time)

bot.destroy()

# Add in code to reboot every Sunday? What do I do for new printers?