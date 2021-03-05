import telnetlib
import time
import xlsxwriter
from datetime import datetime
import argparse

parser = argparse.ArgumentParser(description="Script to calculate the span losses of links between NEs with given IPs")
parser.add_argument('--filename', type=str, help='Please Enter the name of text file that contains a list of nodes loopback IPs each in a line.')

parser.add_argument('--version', action='version', version='SpanLoss Calculator 1.0')
args = parser.parse_args()

run_time = datetime.now().strftime('%Y-%m-%d_%H%M%S')

cmd_file = "inputTelnet" #intial telnet commands file name to extract the inventory of NE's and discover amplifiers. 

filename = args.filename.strip().split('.')[0]


with open (f"{filename}.txt",'r') as y: #Reading the ip's in network IP file and storing them in a list
	ip_list=y.readlines()
	for j,ip in enumerate(ip_list): ip_list[j]=ip.strip() #strip the line to remove \n
print (f"The IP list is {ip_list}")

'''
Telnet Function to connect to nodes.
'''
def open_telnet_conn(ip, cmd_file):
	x=False
	username="admin"
	password="admin"
	cli="cli"
	port = 23
	connection_timeout = 5
	reading_timeout = 5
	connection = telnetlib.Telnet(ip,port,connection_timeout)
	node_output = connection.read_until(b'Username:', connection_timeout) #username and passwords should be entered bit-encoded.
	#print(node_output)
	
	connection.write(cli.encode('ascii') + b'\n')
	node_output = connection.read_until(b'Username: ', reading_timeout)
	connection.write(username.encode('ascii') + b'\n')
	#print(node_output)
	node_output = connection.read_until(b"Password:", reading_timeout)
	#print(node_output)
	connection.write(password.encode('ascii') + b"\n")

	node_output = connection.read_until(b'(Y/N)?', reading_timeout)
	connection.write(b'y\n')
	time.sleep(2)
	with open (f"{cmd_file}.txt",'r') as i: #read commands from cmd file
		cmd = i.readlines()
		for line in cmd:
			connection.write(line.encode('ascii'))
			time.sleep(2)

	node_output = connection.read_very_eager()
	with open (f"output_{ip}.txt",'wb') as f:
		f.write(node_output)
	#print(type(node_output))
	print (node_output.decode('ascii'))
	connection.close()
	x=True
	return x



amplifiers = [] #A list to store the slots of Amplifiers
raman_type=["8DG60567AA", "8DG60567AB", "8DG64137AA"]
dict_connectivity={}
dict_output_power={}
dict_input_power={}
spanLoss=[]
raman_amp=[]
dict_raman={}
dict_connectivity_keys=[]
networkmap={}
dict_design_values={}
key_error_list=[]
osc_calc=[]
fiber_cut=[]
rx_siteA_osc='-99'



def analyse_output_file(rx_siteA_osc):
	
	with open (f"output_{ip}.txt",'r') as f: # open the output file from telnet function for site inventory and topology
		siteA = f.readlines()

		for line in siteA:
			if 'Ext' in line: #search for topolgies with external connection.
				amplifiers.append((line.lstrip()).split()[0]) #strip the spaces in the beginning of the line, take the first element in line (amplifier slot)
				print (amplifiers)
			if 'System Name' in line:
				node_name = (line.split(':')[-1]).lstrip()
				networkmap[ip] = node_name
			for raman in raman_type: #search for raman amplifiers in inventory
				if raman in line:
					raman_amp.append((line.lstrip()).split()[0])
					print (raman_amp)
				
	for amp in range(len(amplifiers)): #for loop to write the commands to grab the tx power and rx power for each port.
		amplifier_slot = amplifiers[amp].split('/')[0:2]
		amplifier_slot = '/'.join(amplifier_slot)
		
		with open (f'cmd_{ip}.txt','w') as c:
			c.write(f'show interface topology {amplifiers[amp]}'+'\n')
			c.write(f'show interface {amplifiers[amp]} detail'+'\n')
			c.write(f'config powermgmt egress {amplifier_slot} spanlossdefault'+'\n')
			
			
		finished = open_telnet_conn(ip,f"cmd_{ip}")
		if finished:
			with open (f"output_{ip}.txt",'r') as f:
				siteA = f.readlines()
				for line in siteA:

					if "To Destination" in line:
						connectivity=line.split(' : ')[-1].strip()
						connectivity = connectivity.split('/')
						connectivity[-1]='LINEIN'
						connectivity='/'.join(connectivity)
						dict_connectivity[f"{ip} {amplifiers[amp]}"] = connectivity
						print(f"the connectivity is: {dict_connectivity}")
						
					if "Powermgmt SpanLossOut" in line:
						design_value=float(line.split(' ')[2].strip())
						dict_design_values[f"{ip} {amplifiers[amp]}"] = design_value
						print(f"the design values are: {dict_design_values}")
					if "No egress IRoadmf or IRoadmv or IRoadm9m or IRoadm9r or IRoadm20 amplifier card." in line:
						dict_design_values[f"{ip} {amplifiers[amp]}"] = 'Design Value Not Supported'
					#else: 
						#dict_design_values[f"{ip} {amplifiers[amp]}"] = 'Design Value Not Supported'
						
					if 'LINEIN' in amplifiers[amp]:
					
						if "Supvy In Power" in line:
							print (line)
							rx_siteA_osc=(line.split(':')[-1]).strip()
							
						#if "Ingress OA Total Input Power" in line: #search for total input power.
						if ("Total Power In" in line) | ("Ingress OA Total Input Power" in line):
							print(line)
							rx_siteA=(line.split(':')[-1]).strip() #split the line with : and get the last element in the list.
							
							if ((rx_siteA == 'nil') | (rx_siteA == 'Off') | (rx_siteA == '')): 
								rx_siteA = rx_siteA_osc
								
								if ((rx_siteA_osc == 'nil') | (rx_siteA_osc == '')): 
									rx_siteA = '-99'
									fiber_cut.append(f"{ip} {amplifiers[amp]}")
									print(f"fiber cut is: {fiber_cut}")
								
						
							rx_siteA_num = float(rx_siteA.split(' ')[0]) #split the value to remove dBm and get the first element and convert it to float.
									
							dict_input_power[f"{ip} {amplifiers[amp]}"]= rx_siteA_num
							#print("the input power is: " + str(dict_input_power))

							
					if 'LINEOUT' in amplifiers[amp]:
						#if "Egress OA Total Output Power" in line: #search for total output power
						if "Supvy Out Power" in line:
							print (line)
							tx_siteA_osc=(line.split(':')[-1]).strip()
							
						if ("Total Power Out" in line) | ("Egress OA Total Output Power" in line): #search for total output power
							print(line)
							tx_siteA=(line.split(':')[-1]).strip()
							
							if ((tx_siteA == 'nil') | (tx_siteA == 'Off')) :
								tx_siteA_osc = '99'
								tx_siteA = tx_siteA_osc
								osc_calc.append(f"{ip} {amplifiers[amp]}")
								
								
							tx_siteA_num = float(tx_siteA.split(' ')[0])
							dict_output_power[f"{ip} {amplifiers[amp]}"] = tx_siteA_num
						
							#print("the output power is: " + str(dict_output_power))
							
						

def raman_process(raman_amp):
	
	for raman in range(len(raman_amp)):
		with open (f'cmd_{ip}.txt','a') as c:
			c.write(f'show interface {raman_amp[raman]}/LINEIN detail'+'\n')

	finished = open_telnet_conn(ip,f"cmd_{ip}")
	if finished:
		with open (f"output_{ip}.txt",'r') as f:
			siteA = f.readlines()
			for line in siteA:
				if 'Operating Gain' in line:
					print(line)
					raman_gain= (line.split(':')[-1]).strip() #split the line with : and get the last element in the list.
					#if (raman_gain == 'Off') : raman_gain = '0'
					raman_gain_num = float(raman_gain.split(' ')[0])
					dict_raman[f"{ip} {raman_amp[raman]}/LINEIN"]=raman_gain_num
					#print (dict_raman)
		raman_amp=[]


						
for ip in ip_list: #one main for loop for each ip
	ip.strip()
	finished = open_telnet_conn (ip,cmd_file) #call telnet function with initial commands to extract inventory for the first time only with cmd_file.
	if finished:
		analyse_output_file(rx_siteA_osc)
		
	amplifiers = []
	if raman_amp:
		raman_process(raman_amp)
	raman_amp = []

def create_excel_sheet():
	workbook = xlsxwriter.Workbook(f'result_{run_time}.xlsx')
	worksheet = workbook.add_worksheet("My sheet")
	worksheet.write(0,0 , 'Connection')
	worksheet.write(0,1 , 'Span Loss')
	worksheet.write(0,2 , 'Design Value')
	worksheet.write(0,3 , 'Comments')
	for i,key in enumerate(dict_connectivity.keys()):
		far_end_ip = dict_connectivity[key].split(' ')[0]
		far_end_port = dict_connectivity[key].split(' ')[-1]
		near_end_ip = key.split(' ')[0]
		near_end_port = key.split(' ')[-1]
		
		
		if far_end_ip in ip_list:
			if 'LINEOUT' in key:
				if (key in dict_output_power.keys()) | (dict_input_power[dict_connectivity[key]] in dict_input_power.keys()):
					spanLoss_value = dict_output_power[key] - dict_input_power[dict_connectivity[key]]
					spanLoss.append(spanLoss_value)
					if dict_connectivity[key] in dict_raman.keys(): 
						spanLoss_value = spanLoss_value + dict_raman[dict_connectivity[key]]
				else: spanLoss_value = 'KeyError'
				
				print(i)
				print(key)
				#if (dict_design_values[key] == 'Design Value Not Supported'): dict_design_values[dict_connectivity[key]]
				worksheet.write(i+1 ,0 , networkmap[near_end_ip] + " " + near_end_port + "<>" + networkmap[far_end_ip] + " " + far_end_port)
				worksheet.write(i+1 ,1 , spanLoss_value)
				worksheet.write(i+1 ,2 , dict_design_values[key])
				if key in osc_calc: worksheet.write(i+1 ,3 , "OSC Calculation")
				if dict_connectivity[key] in fiber_cut: worksheet.write(i+1 ,3 , "Fiber Cut")
				
			if 'LINEIN' in key:
				#if (dict_design_values[key] == 'Design Value Not Supported'): dict_design_values[dict_connectivity[key]]
				if (dict_connectivity[key] in dict_output_power.keys()) | (key in dict_input_power.keys()):
					spanLoss_value = dict_output_power[dict_connectivity[key]] - dict_input_power[key]
					spanLoss.append(spanLoss_value)
					if key in dict_raman.keys(): 
						spanLoss_value = spanLoss_value + dict_raman[dict_connectivity[key]]
				else: 
					spanLoss_value = 'KeyError'
					key_error_list.append(near_end_ip)
					key_error_list.append(far_end_ip)
				
				worksheet.write(i+1 ,0 , networkmap[near_end_ip] + " " + near_end_port + "<>" + networkmap[far_end_ip] + " " +far_end_port)
				worksheet.write(i+1 ,1 , spanLoss_value)
				worksheet.write(i+1 ,2 , dict_design_values[key])
				
				if key in fiber_cut: worksheet.write(i+1 ,3 , "Fiber Cut")
		else: 
			spanLoss_value = "Link is outside nodes"
			worksheet.write(i+1 ,0 , networkmap[near_end_ip] + " " + near_end_port + "<>" + far_end_ip + " " +far_end_port)
			worksheet.write(i+1 ,1 , spanLoss_value)
	workbook.close()

create_excel_sheet()

if key_error_list:
	print(f"Please repeat the the program with the following list: {key_error_list}")
	for ip in key_error_list: #one main for loop for each ip
		ip.strip()
		finished = open_telnet_conn (ip,cmd_file) #call telnet function with initial commands to extract inventory for the first time only with cmd_file.
		if finished:
			analyse_output_file(rx_siteA_osc)
		
	amplifiers = []
	
	if raman_amp:
		raman_process(raman_amp)
	raman_amp = []