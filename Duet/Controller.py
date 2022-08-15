import requests
import os

import pandas as pd
import datetime

import json

import tempfile

from sympy import false

import time

# Example Watchdog Bot https://gist.githubusercontent.com/JSestito/34160e4a2f776274b57361eee26dba11/raw/f73142d01471de58d8e2b955e68966e6fc48adac/DuetRepRapFirmwarePushed.py
# rr Commands https://github.com/Duet3D/RepRapFirmware/blob/36488de6fc6635f470b311c91fe282efe7a3e559/src/Duet/Webserver.cpp#L28-L83
# Upload docs: https://forum.duet3d.com/topic/867/duet-wifi-s3d/29
# Curl and requests comparrison https://stackoverflow.com/questions/31061227/curl-vs-python-requests-when-hitting-apis
# GCode dictionary: https://duet3d.dozuki.com/Wiki/Gcode#M551:_Set_Password
# Authentication Set Password: https://forum.duet3d.com/topic/2219/authentication-for-using-the-web-interface
# More RR Commands: https://github.com/Duet3D/DuetWebControl/tree/legacy

# TODO Find out the auto disconnect time. I can find thbat out during the connect command Like 8000 seconds. So ping quicker than that
# TODO Do we want to just connect/disconnect after every command?



IP_key = "IP"
printer_name_key = "Printer"
printer_password_key = 'Password'
printer_verify_gcode_key = 'VerifyGCode'
printer_gcode_version_key = 'GCodeVersion'

password_key = "DuetPassword"
status_key = "Status"
time_remaining_key = "Time Remaining"

filament_extruded_key = "FilamentExtruded"
fraction_key = "Fraction"
print_duration_key = "PrintDuration"
filename_key = "FileName"

rr_key_status = "status"

offline_text = "Offline"

status_address  = 'rr_status?type=3'
machine_name_address    = 'rr_status?type=2' #Request 'name'
rr_fileinfo    = 'rr_fileinfo'
rr_connect = 'rr_connect'
rr_disconnect = 'rr_disconnect'
rr_status = 'rr_status'

rr_status1 = 'rr_status?type=1' # Pulled for data
rr_status2 = 'rr_status?type=2' # Pulled right after connection
rr_status3 = 'rr_status?type=3' # Pull while printing

'''
Type 1: Regular status request. The response for this is usually rather compact and only includes values that are expected to change quickly. The following types 2 and 3 include those values under any circumstances to keep the web interface up-to-date.
Type 2: Extended status request. This type of request is polled right after a connection has been established. This response provides information about the tool mapping and values that can change.
Type 3: Print status request. Unlike type 2, this type of request is always polled when a file print is in progress. It provides print time estimations and other print-related information which can be shown on the print status page.
'''

debug_file = 'DEBUG_controller.txt'
debug_file = tempfile.gettempdir() + '\\' + debug_file

rr_upload = 'rr_upload'

#timeout_default = 1
#connect_timeout = 0.25


class DuetController:


    printers = []
    data = {}
    timeout_default = 1
    connect_timeout = 0.25
    gcode_retry = 10

    def __init__(self, printers, data, debug=False):
        self.initialize(printers, data, debug)

    def reinitialize_variables(self, data):
        self.data = data
        self.timeout_default = float(data['TimeoutDefault'])
        self.connect_timeout = float(data['ConnectDefault'])
        self.gcode_retry = int(data['GCodeRetry'])


    def initialize(self, printers, data, debug=False):
        self.debug = debug
        
        self.printers = printers
        self.printers[status_key] = "" #pd.NaT
        self.printers[time_remaining_key] = 0 #pd.NaT
        self.printers['State'] = ""
        self.printers[filament_extruded_key] = 0.0
        self.printers[fraction_key] = 0.0
        self.printers[print_duration_key] = 0.0
        self.printers[filename_key] = ''

        self.data = data
        self.connect_printers()
        self.update_printers_status()

        self.timeout_default = float(data['TimeoutDefault'])
        self.connect_timeout = float(data['ConnectDefault'])
        self.gcode_retry = int(data['GCodeRetry'])


        if self.debug:
            self.f = open(debug_file, 'w')

    def destroy(self):
        if self.debug:
            self.f.close()

    def send_command(self, printer, command, timeout: float = -1):
        if timeout < 0:
            timeout = self.timeout_default

        base_address = 'http://' + self.find_ip(printer) + '/'
        address = base_address + command
        
        #print('Trying ' + printer + '   ' + command)
        try:
            #req_result = requests.get(url = address, timeout=(0.1,20)) #https://realpython.com/python-requests/#:~:text=If%20your%20application%20waits%20too,your%20background%20jobs%20could%20hang.&text=In%20the%20first%20request%2C%20the,will%20timeout%20after%203.05%20seconds.
            # TODO Can I just use post?
            # TODO Add in retrty
            req_result = requests.get(url = address, timeout=timeout)
            return req_result
        except: # Failed command
            return 0

    def find_ip(self, printer):
        printer_info = self.printers[self.printers[printer_name_key] == printer]
        ip = printer_info[IP_key].iloc[0]
        return ip


    def connect_printers(self, retry: int = 5):
        for index, row in self.printers.iterrows():
            
            command = rr_connect + '?password=' + row[printer_password_key] + '&time='
            command += datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            #print(command)

            req_result = self.send_command(row[printer_name_key], command, timeout=self.connect_timeout)

            #if req_result == 0: # Failed
            i = 0
            while i <= retry and req_result == 0:
                i += 1
                req_result = self.send_command(row[printer_name_key], command, timeout=self.connect_timeout)
            
            if req_result == 0: # Failed
                self.printers.at[index, status_key] = offline_text
            else:
                #print(req_result.text)
                self.printers.at[index, status_key] = ''
                pass




    def disconnect_printers(self):
        for index, row in self.printers.iterrows():
            req_result = self.send_command(row[printer_name_key], rr_disconnect)


    def update_printers_status(self):
        self.disconnect_printers()
        self.connect_printers()
        for index, row in self.printers.iterrows():
            if not row[status_key] == offline_text:
                # Initialize Variables
                status_text = ""
                print_time = 0#pd.NaT
                current_filament_extruded = 0.0
                current_fraction = 0.0
                current_print_duration = 0.0


                printer_name = row[printer_name_key]
                req_result = self.send_command(printer_name, rr_status3)
                if req_result == 0: # Failed
                    status_text = "Failed"

                else: # Get Status
                    try:
                        req_result_json = req_result.json()
                        #print(req_result_json)

                        status_letter = req_result_json[rr_key_status]
                        status_text = self.parse_status(status_letter)
                        if status_letter == 'P':
                            print_time = self.print_time_remaining(printer_name)


                        current_filament_extruded = req_result_json['coords']['extr'][0] #mm
                        current_fraction = req_result_json['fractionPrinted']
                        current_print_duration = req_result_json['printDuration']
                        
                    except:
                        status_text = "Failed"

                self.printers.at[index, status_key] =status_text
                self.printers.at[index, time_remaining_key] = print_time
                self.printers.at[index, filament_extruded_key] = current_filament_extruded
                self.printers.at[index, fraction_key] = current_fraction
                self.printers.at[index, print_duration_key] = current_print_duration
                
    def set_current_file(self):
        #self.disconnect_printers()
        #self.connect_printers()
        for index, row in self.printers.iterrows():
            if not row[status_key] == offline_text:
                # Initialize Variables
                file_name = ""


                printer_name = row[printer_name_key]

                req_result = self.send_command(printer_name, rr_fileinfo)
                
                if req_result == 0: # Failed
                    pass

                else: # Get Status
                    try:
                        req_result_json = req_result.json()

                        file_path = req_result_json["fileName"]
                        file_name = file_path.split('/')[-1]

                        
                    except:
                        pass
                #print(file_name)
                self.printers.at[index, filename_key] = file_name
        


        #print(self.printers)

    def send_gcode(self, printer, filepath, timeout: float = -1, retry: int = -1):
        #print(self.data)
        if timeout < 0:
            timeout = self.timeout_default

        if retry < 0:
            retry = self.gcode_retry

        #print(timeout, retry)

        self.disconnect_printers()
        self.connect_printers()

        filename = os.path.basename(filepath)

        command = '%s?name=gcodes/%s&time=YYY' % (rr_upload, filename)
        #self.send_command(printer, command, timeout=None, data = data, stream=False)
        
        base_address = 'http://' + self.find_ip(printer) + '/'
        address = base_address + command
        
        if self.debug:
            self.f.write("DEBUG: Print command started.\n")
            self.f.write(filepath + '\n')

        success = 0
        fail = 0

        attempts = 0
        while attempts <= retry:
        #while True:
            attempts += 1
            
            try:
                req_result = requests.post(url = address, data=open(filepath, 'rb'), timeout=timeout)
                attempts = retry + 1
                success += 1
            except:
                fail += 1
                time.sleep(1)
                if self.debug:
                    self.f.write('Timeout! Attempts: ' + str(attempts))

            print('Success: ' + str(success) + '  Fail: ' + str(fail))


        if self.debug:
            self.f.write('Success: ' + str(success) + '  Fail: ' + str(fail))
        

        
        if self.debug:
            self.f.write("DEBUG: Print command completed.\n")
        try:
            if req_result.json()['err'] == 0:
                #Success
                command = 'rr_gcode?gcode=M32%s' % (filename)
                address = base_address + command

                attempts = 0
                while attempts <= retry:
                    attempts += 1
                    
                    try:
                        req_result = requests.get(url = address, timeout=timeout)
                        attempts = retry + 10
                    except:
                        if self.debug:
                            self.f.write('Timeout on Print! Attempts: ' + str(attempts))

                if attempts == retry + 10:
                    return True
                else:
                    return False
            else:
                return False
        except:
            return False


    def get_most_recent_file(self, printer):
        try:
            first = 0
            command = 'rr_filelist?dir=gcodes&first=' + str(first)
            result = self.send_command(printer,command, timeout=self.timeout_default)
            files = result.json()['files']
            data_frame = pd.DataFrame(files)
            first = result.json()['next']

            while first != 0:
                command = 'rr_filelist?dir=gcodes&first=' + str(first)
                result = self.send_command(printer,command, timeout=self.timeout_default)
                files = result.json()['files']
                data_frame_append = pd.DataFrame(files)
                first = result.json()['next']
                data_frame = pd.concat([data_frame, data_frame_append], ignore_index = True)
            
            
            data_frame_sorted = data_frame.sort_values(by=['date'], na_position='first') # Sorts it from oldest to newest
            #most_recent = files[-1]["name"]
            most_recent = data_frame_sorted.iloc[-1]['name'] # Get the newest one



            return most_recent
        except:
            return ''


    def print_from_sd(self, printer, file):
        try:
            command = 'rr_gcode?gcode=M32%s' % (file)
            result = self.send_command(printer, command, timeout=self.timeout_default)
        except:
            pass

    def print_time_remaining(self, printer: str) -> int:
        """
        :return: Print time remaining in seconds
        """
        result = self.send_command(printer, rr_fileinfo, timeout=self.timeout_default)
        result = result.json()
        if int(result["err"]) == 1:
            return 0
        else:
            print_time = int(result['printTime'])
            print_duration = int(result['printDuration'])
            time_remaining = print_time - print_duration
            return time_remaining


    def parse_status(self, status):
        output = None
        printing = False
        paused = False

        if status == 'F': # Flashing new firmware
            output = 'Flashing new firmware'

        elif status == 'H': # Halted
            output = 'Halted'

        elif status == 'D': # Pausing / Decelerating
            output = 'Pausing / Decelerating'
            output = 'Pausing'
            printing = True
            paused   = True

        elif status == 'S':	# Paused / Stopped
            #output = 'Paused / Stopped'
            output = 'Paused'
            printing = True
            paused   = True

        elif status == 'R':	# Resuming
            output = 'Resuming'
            printing = True
            paused   = True

        elif status == 'P': # Printing
            output = 'Printing'
            printing = True
                
        elif status == 'M':	# Simulating
            output = 'Simulating'
            printing = True

        elif status == 'B':	# Busy
            output = 'Busy'

        elif status == 'T':	# Changing tool
            output = 'Changing tool'

        elif status ==  'I':	# Idle
            output = 'Idle'

        else:
            output = 'Unknown State'

        return output

    def purpose_code(self, purpose):
        if purpose == "Personal":
            return "P"
        elif purpose == "Research":
            return "R"
        elif purpose == "Senior Design":
            return "SD"
        elif purpose == "Class":
            return "C"
        elif purpose == "Student Org.":
            return "SO"

    def assemble_prefix(self, user, purpose):
        prefix = user + '.' + self.purpose_code(purpose) + '.'
        return prefix

    def filename_information(self, filename):
        parts = filename.split('.')
        user = parts[0]
        purpose_code = parts[1]
        file = '.'.join(parts[2:])

        data = {
            'fullfile': filename,
            'username': user,
            'purpose_code': purpose_code,
            'filename': file
        }
        
        return data



"""     
# Get only the machines that are connected
printers_name = []
printers_ip = []
for printer in printers_ip_given:
    base_address = 'http://' + printer + '/'
    address = base_address + machine_name_address

    try:
        r = requests.get(url = address) # Get the information for the printer
        data = r.json() #Parse the file
        name = data['name']

        printers_name.append(name)
        printers_ip.append(printer)

        string = 'Found at IP: ' + printer
        log(string, fileLog, name, debug, 'startup')

    except:
        string = 'No printer found at ip ' + printer
        log(string, fileLog, debug = debug, prefix = 'startup')



number_of_printers = len(printers_ip) 
"""