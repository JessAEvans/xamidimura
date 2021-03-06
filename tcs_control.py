""" 

tcs_control.py

	This script will contain the functions that will interact with the TCS 
	 computer. This includes connecting to the TCS via ssh, logging off at the 
	 end, and sending commands to take images.

"""
from pexpect import pxssh
import pexpect
import getpass
import logging
import settings_and_error_codes as set_err_codes
import timeout_decorator
import subprocess
import time



logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fileHand = logging.FileHandler(filename = set_err_codes.LOGFILES_DIRECTORY+\
		'tcs.log', mode = 'a')
fileHand.setLevel(logging.INFO)
logging.Formatter.converter = time.gmtime
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s - '\
		'%(message)s','%Y-%m-%d_%H:%M:%S_UTC')
fileHand.setFormatter(formatter)
logger.addHandler(fileHand)


""" 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 Commands to interact with telescope on TCS over ssh
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

def send_command(command, timeout_time = set_err_codes.tcs_coms_timeout):
	""" 
	Send a 'command' to the TCS computer over an ssh connection.
	 It will take any repsonse, return just the message
	
	PARAMETERS:
	
		command = A command that will be accepted by the command line interface 
			(cli). Although other general command-line commands will work as 
			well.
		
		timeout_time = the allow time for the command to execute
			
	RETURN:
	
		response = A string containing the message that is returned in response
			the command.
	
	"""
	
	try:
		#Send the command to the TCS	
		output = subprocess.run(['ssh','wasp@tcs', command],
				capture_output=True, timeout=timeout_time)
	except subprocess.TimeoutExpired:
		logger.critical('Failed to contact TCS')
	else:
		response = output.stdout
	
	#get rid of repeated command
	response = response.decode('utf-8')
	logger.info('FROM TCS: '+response)
	return response


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Functions to check the status of various things
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def telshow_command():
	
	response = send_command('telshow')
	return response

def split_ra_dec_alt_az(response_string):
	""" 
	Takes a string with the format 
			[hh mm ss hh mm ss hh mm ss hh mm ss hh mm ss status]
	 and splits it into ra, dec, ha, alt, az and telscope status
	 
	 PARAMETERS
	 
	 	response_string = the string to be split up
	 
	 RETURN
	 
	 	[ra,dec,ha, alt, az, status] as a list
	"""
	splitup = response_string.split()
	ra = ' '.join(splitup[:3])
	dec = ' '.join(splitup[3:6])
	ha = ' '.join(splitup[6:9])
	alt = ' '.join(splitup[9:12])
	az = ' '.join(splitup[12:15])
	stat = splitup[-1]

	return [ra, dec, ha, alt, az, stat]

def get_tel_target():
	""" 
	Send 'getstatus teltarget' to tcs and processes response
	
	 Response to the 'getstatus teltarget' command is a string showing the 
	  telescopes target RA, Dec, Ha, Alt, Az in sexagesimal format, using 3 
	  components separated by spaces (i.e. hh mm ss), followed by telescope 
	  status. If telescope is moving/slewing will report target position.
	
	RETURN
	
		split_ans = List containing the RA, Dec, Ha, Altitude, azimuth and 
			status of telescope, and show the target coordinates it is 
			moving/slewing.
	
	"""
	target = send_command('getstatus teltarget')
	split_ans = split_ra_dec_alt_az(target)
	
	return split_ans

def get_tel_pointing():
	""" 
	Sends 'getstatus tel' to the tcs and processes the response

	Response to the 'getstatus tel' command is a string showing the telescopes 
	 target RA, Dec, Ha, Alt, Az in sexagesimal format, using 3 components 
	 separated by spaces (i.e. hh mm ss), followed by telescope status.
	 
	Valid status messages are as follows:
		- STOPPED (telescope is stopped)
		- SLEWING (slewing rapidly)
		- HUNTING (slewing slowly)
		- TRACKING (tracking the given position)
		- HOMING (finding the home position)
		- LIMITING (finding the limit switches)

		
	RETURN
	
		split_ans = List containing the RA, Dec, Ha, Altitude, azimuth and 
			status of telescope, and show the target coordinates it is 
			moving/slewing.
	
	"""
	target = send_command('getstatus tel')
	split_ans = split_ra_dec_alt_az(target)
	
	return split_ans
	
def get_homed_status():
	""" 
	Sends the 'getstatus home' command to the tcs and processes the repsonse
	
	Will return the hommed status of the following in this order
	 HA DEC, rotator, focus, filterwheel
	Will show 'ABSENT' (if not present) or 'NOTHOMED'/'HOMED' 
	
			
	RETURN:
		
		split_ans = List with the homed status for the HA axism DEC axis, 
			rotator, focus and filterwheel in that order
	"""
	target = send_command('getstatus home')
	split_ans = target.split()
	
	return split_ans

def get_camera_status():

	""" 
	 Send the 'getstatus cam' to the tcs and processes it's repsonse.
	
	
	This will report the overall combine camera status of the all the CCDs.
	Possible states are:
		- IDLE
		- EXPOSING
		- READING
	Will also show the status of the cooler status (see below) and then the 
		current and target temperatures.
	 Cooler status values:
	 	- AtTemp (at target temp)
	 	- UnderTemp (under target temperature)
	 	- 0verTemp (over target temperature)
	 	- CoolerOff (cooler is switched off)
	 	- RampDown (ramping temperture down)
	 	- RampUp (ramping temperature up)
	 	- Stuck (temperature stuck, can't reach target)
	 	- AtMax (temperature can't go any higher)
	 	- CoolerIdle (cooler is idle, temperature is ambient)
	 
	
	RETURN
	
		split_ans = List containing the camera state, cooler state, current 
			temperature and target temperature, in that order
	"""

	target = send_command('getstatus cam')
	split_ans = target.split()
	
	return split_ans

def get_roof_status_from_tcs():
	""" 
	Send the 'getstatus dome' command to the TCS. This will get the TCS to
		respond with the roof's current status.
	 
	Possible states:
	 - ABSENT (no shutter present or shutter disabled)
	 - IDLE (stopped but not at open or closed limit)
	 - OPENING (currently opening)
	 - CLOSING (currently closing)
	 - OPEN (open)
	 - CLOSED (closed)
	 
	 Also returns an integer which indicates wheter the alarm has been trigger 
	 (will be 1 if triggered)
	 
	 PARAMETERS:
	 
	 	open_conn = the parameter storing the open ssh connection to the TCS
	 	
	 RETURN:
	 
	 	split_ans = List containing the roof status and alarm status, in that 
			order
	"""
	
	target = send_command('getstatus dome')
	split_ans = target.split()
	
	return split_ans


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#  Functions to send commands to telescope
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def stop_telescope_move():
	""" 
	Sends the 'stoptel' command to the TCS computer. This will stop any motion 
		of the telescope mount.

	 PARAMETERS:
	 
	 	open_conn = the parameter storing the open ssh connection to the TCS
	
	"""
	target = send_command('stoptel')
		
def startTel(startAll = False):
	""" 
	*** NOT TESTED ***
	
	Send the 'startTel' command to the TCS machine. This will start a basic set
		of OCAAS processes including 'telescoped' and 'xobs' [Check what these 
		are]. If startAll is set to True then it will add the '-all' argument 
		to the command, which will also start the camerad,shm,camera, xephem 
		and telsched processes
	
	 PARAMETERS:
	 
	 	open_conn = the parameter storing the open ssh connection to the TCS
		startAll = True/False, set to True to run all 'telescoped, xobs, 
			camerad, shm, camera, xephem and telsched processes. If set to
			False, only the telescoped and xobs will run.
	
	"""
	
	
	if startAll == True:
		logger.info('Running all telescope startup processes...')
		target = send_command('startTel -all')
	elif startAll == False:
		logger.info('Running telescope startup...')
		target = send_command('startTel')
	else:
		logger.error('Invaild input for startAll, use True/False')
		raise ValueError('Invaild input for startAll, use True/False')

def killTel(killAll = False):
	""" 
	*** NOT TESTED ***
	
	Send the 'startTel' command to the TCS machine. This will start a basic set 
	 of OCAAS processes including 'telescoped' and 'xobs' [Check what these 
	 are]. If startAll is set to True then it will add the '-all' argument to 
	 the command, which will also start the camerad, shm, camera, xephem and 
	 telsched processes
	
	 PARAMETERS:
	 
	 	open_conn = the parameter storing the open ssh connection to the TCS
		startAll = True/False, set to True to run all 'telescoped, xobs, 
			camerad, shm, camera, xephem and telsched processed. If set to 
			False, only the telescoped and xobs will run.
	
	"""
	
	
	if killAll == True:
		logger.info('Stopping all telescope processes...')
		target = send_command('killTel -all')
	elif killAll == False:
		logger.info('Stopping telescope startup...')
		target = send_command('killTel')
	else:
		logger.error('Invaild input for killAll, use True/False')
		raise ValueError('Invaild input for killAll, use True/False')
		
def check_tele_coords(coords, is_alt_az):
	""" 
	Checks to make sure that coordinates that will be sent to the telescope are 
	 valid, i.e. within valid ranges.
	 
	These check include that the list 'coords' connsists of two string 
		components, of the form '?? ?? ??'.
	 
	 PARAMETERS:
	 
	 	coords -  The coordinates to be checked.
	 	is_alt_az - True/False - If set to true, the coordinates will be taken 
			as altitude and azimuth.
	"""
	
	#Stuff check coords are OK values?
	if len(coords)!= 2:
		logger.error('Incorrect length for coords parameter, should be 2')
	else:
		for i in range(len(coords)):
		
			#print('Checking', coords[i], 'index:',i)
			valid_Coords = True
			try:
				j = str(coords[i])
				
			except:
				valid_Coords = False
			else:
				space_split = j.split(' ')
				colon_split = j.split(':')
				if len(space_split) == 3 or len(colon_split) == 3: 
					if len(space_split) == 3:
						valid_one = space_split
					if len(colon_split)==3:
						valid_one = colon_split
				else:
					valid_Coords = False
			
			try:
				valid_one = [float(valid_one[k]) for k in range(len(valid_one))]
			except:
				valid_Coords = False
			#Check the values entered are in valid ranges
			if valid_Coords == True:
				#Check mintues for all RA, DEC, Alt, Az,
				if valid_one[1] < 0 or valid_one[1] >= 60:
					valid_Coords =False
				# Check seconds for all RA, DEC, ALt, Az
				if valid_one[2] < 0 or valid_one[2]>= 60:
					valid_Coords =False
				
				# First value will have different ranges for RA, DEC, Alt, Az
				# i == 0 will be either RA or Alt..
				# is_alt_az==False for RA
				if i == 0 and is_alt_az == False:
					if valid_one[0] < 0 or valid_one[0] >=24:
						valid_Coords = False
				elif i == 0 and is_alt_az == True:
					if valid_one[0] <0 or valid_one[0] >90:
						valid_Coords =False
				# i == 1 will be DEC or Az
				# is_alt_az==False for DEC
				elif i== 1 and is_alt_az ==False:
					if valid_one[0] <-90 or valid_one[0] > 90:
						valid_Coords = False
				elif i == 1 and is_alt_az == True:
					if valid_one[0] <0 or valid_one[0] >=360:
						valid_Coords =False
				else:
					print("Issue with 'i' or 'is_alt_az'")
					
			if valid_Coords ==False:
				raise ValueError('Invalid Coordinates provided')
		
def slew_or_track_target(coords, track_target=True, is_alt_az = False,
	equinox='J2000'):

	""" 
	Send the command required to get the telescope to point at a target,
	 with the option to track the target. Uses the TCS cli commands.
	
	Coordinates can be sent as RA and DEC or altitude/azimuth (if is_alt_az = 
	 True). If they are in alt/az then the argument 'altaz' is added to the 
	 command string that gets sent to the TCS.
	
	 PARAMETERS:
	 
	 	coords = the RA and DEC or Alt/AZ coordinates for the telescope to move 
		 to and they can also be altitude and azimuth. Send in list as [RA, DEC]
		 or [Alt, Az]. Each component should be formatted as 'hh mm ss' or 
		 'dd mm ss' as appropriate. The dd component can be given as '+dd'. 
		 Will also accept hh:mm:ss dd:mm:ss as input. Example for RA/DEC 
		 ['12 32 13','+23 21 42']
	 	
	 	open_conn = the parameter storing the open ssh connection to the TCS

	 	track_target = True/False. If true, the telescope will start tracking 
		 once the target has been found.
	 	
	 	is_alt_az = True/False. If true, the 'altaz' argument will be added to 
		 the command so the telescope know that the coordinates are altitude and
		 azimuth rather than RA and DEC.
	 	 
	 	equinox = J2000 is the defualt. Bessellian epochs are not supported at 
		 present (e.g. B1950), please precess your coordinates first. The 
		 special equinox "A" specifies apparent place.
	 	
	"""
	#Check the coordinates that have been pas are valid values
	check_tele_coords(coords, is_alt_az)
	
	if track_target == False:
		command_str = 'slew '
		
	elif track_target == True:
		command_str = 'track '
	else:
		logger.error('Invaild input for track_target, use True/False')	
		raise ValueError('Invaild input for track_target, use True/False')
	
	if is_alt_az == True:
		command_str += 'altaz '
	elif is_alt_az == False:
		pass
	else:
		logger.error('Invaild input for track_target, use True/False')	
		raise ValueError('Invaild input for is_alt_az, use True/False')


	command_str += ' '.join(coords)

	#J2000 is the default, and the RA/DEC values are assumed to be J2000 is not
	#  specified
	if is_alt_az == False and equinox != 'J2000':
		command_str += ' '+equinox
	
	
	target = send_command(command_str)


	return target

def apply_offset_to_tele(ra_alt_off, dec_az_off, units='arcsec',
	is_alt_az=False):
	""" 
	
	 Send the 'offset' command to get the telescope to move by an amount 
	  relative to it's current position.
	  
	 The command can take two forms.
	   -  offset altaz unit altoff azoff
	   -  offset unit raoff decoff
	The first allows the offsets to be passed in alt/az coords, and the second 
	 allows it to be passed in RA/DEC.
	 
	
	PARAMETERS:
	
	 	ra_alt_off = The offset in RA or altitude (if is_alt_az is True)
	 	
	 	dec_az_off = The offset in DEC or azimuth (if is_alt_az is True) 
	 	
	 	open_conn = the parameter storing the open ssh connection to the TCS

	 	is_alt_az = True/False. If true, the 'altaz' argument will be added to 
		 the command so the telescope know that the coordinates are altitude 
		 and azimuth rather than RA and DEC.
		
		unit - either 'arcsec', 'arcmin' or 'deg'. 'arc' can also be used 
			instead of 'arcmin'
	
	"""
	command_str = 'offset '
	
	if is_alt_az == True:
		command_str += 'altaz '
	elif is_alt_az == False:
		pass
	else:
		logger.error('Invaild input for track_target, use True/False')	
		raise ValueError('Invaild input for is_alt_az, use True/False')

	valid_units = ['arcsec','arcmin','deg', 'arc']
	if units not in valid_units:
		logger.error('Invalid telescope offset unit provided')
		raise ValueError('Invalid telescope offset unit provided')
	
	command_str += units + ' '

	command_str += str(ra_alt_off)+' '
	command_str += str(dec_az_off)
	
	print(command_str)
	respond = send_command(command_str)

	return respond

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions to send exposure commands - not sure how these work with new system
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def tcs_exposure_request(image_type, duration = 0, number = 1):
	"""
	Send the expose command to the TCS, along with the exposure type number of 
	 exposures and their duration. The supplied 'type' will be checked to make 
	 sure it is a valid type. Note 'dark' type will be relabelled as 'thermal'.
	
	The expose command will get all of the CCD to expose simultaneously. If 
	 specified, number will be taken sequentially, waiting for each to read out 
	 before starting the next.
	
	Duration is required for all exposure except 'bias'. 
	
	THERMAL - A thermal (dark) exposure. The shutter will remain closed, and 
	 the CCD will integrate for the given duration, and then be read out.
		
	BIAS - A bias frame. The shutter will remain closed, and the CCD flushed 
	 and immediately read out.
		
	FLAT - A flat field. The same as flagged as a flat field in the FITS 
	 headers.
	
	OBJECT - A target frame. The shutter will be opened and the CCD integrated 
	 for the given duration.
	
	
	PARAMETERS:
	
		image_type = the type of exposures wanted. A valid list includes 'thermal', 
		 'dark', 'bias', 'flat', and 'object'
			
		duration = the length of the exposure in seconds.
		
		number = the number of exposures wanted. The default will be '1' as 
		 this is want will be requested by the main observing script
	"""

	valid_types = ['THERMAL','DARK', 'BIAS', 'FLAT','OBJECT']
	valid = image_type in valid_types

	if valid:
		image_type = image_type.lower()
		if image_type == 'dark':
			image_type = 'thermal'

		if number < 1:
			logger.error('Invalid number of exposures requested')
			respond = set_err_codes.STATUS_CODE_EXPOSURE_NOT_STARTED
			return respond

		if duration <0:
			logger.error('Invalid exposure time requested')
			respond = set_err_codes.STATUS_CODE_EXPOSURE_NOT_STARTED
			return respond

		command_str = 'expose ' + image_type
		if number != 1:
			command_str += ' '+str(number)
		if image_type != 'bias':
			command_str += ' ' + str(duration)
		
		try:
			tcs_respond = send_command(command_str)
		
		except:
			respond = set_err_codes.STATUS_CODE_EXPOSURE_NOT_STARTED
		else:
			
			cam_temp = get_camera_status()[2]
			#if good_response and cam_temp>-20:
			if float(cam_temp)>-20:
				respond = set_err_codes.STATUS_CODE_CCD_WARM
	
			else:
				respond = set_err_codes.STATUS_CODE_OK
			
		return respond

	else:
		logger.error('Invalid image type provided to exposure request '+str(
				image_type))
		print('Invalid image type provided to exposure request'+str(
			image_type))


#	return respond

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions for the cameras
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def camstart():

	"""
	Send the 'camstart' command to the TCS machine. This will start up the
	 cameras and cooling.
	"""

	respond = send_command('camstart')

def waspstat():

	"""
	Send the waspstat command to the TCS. This will return the status of cameras
	
	RETURN
	
		respond =  a message with the camera status
	"""

	respond = send_command('waspstat')

	return respond

def stopwasp():

	"""
	Send the stopwasp command to the TCS. This will stop the cameras cooling
	 and shutdown the cameras
	"""

	respond = send_command('stopwasp')

def stopcam_expose():

	""" 
	Send the 'stopcam' command to the TCS machine. This will abort any exposure 
		that may be in progress.
		
	**Not sure if will work with new system**


	RETURN:
	
		....	
	"""

	respond = send_command('stopcam')

def wait_till_read_out():

	""" 
	Send the 'waitreadout' command to the TCS. This command will wait for the 
	 CCD shutter to close and readout to start before the can be moved. This is 
	 to avoid disturbing the exposure.

	**Not sure if will work with new system**

	
	"""

	respond = send_command('waitreadout')

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Functions for flat fielding
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def scratchmode(state = 'off'):

	"""
	Send the scratchmode on/off command to the tcs. Sending 'on' will enable 
	 scratchmode meaning the allocation of image is disabled and each DAS 
	 writed the image to a file in SCRATCH/DASn_scratch.fts, where n is the 
	 DAS number. When 'off' is sent scratchmode is disabled, and images are 
	 stored in the normal places on the das machines. 
	 
	Use scratchmode to take test images that are not saved.
	"""

	validState = ['on','off']
	if state not in validState:
		raise ValueError('Invalid state enter for sctratchmode. Use "on" or "off"')

	else:
		respond = send_command('scratchmode ' + state)

def lastsky():
	"""
	Sends the 'lastsky' command to the tcs. This command will get the sky level 
	and noise level of the last image taken. It will produce a response with
	<sky level> <noise> for each das camera e.g.
	
	<das1 sky> <das1 noise> <das2sky> <das2noise> ...
	
	The sky level is calculated using a 3-sigma clipped median/MAD algorithm.
	
	RETURN:
		respond = This will be a list containing the returned values.
	
	"""

	respond = send_command('lastsky')
	return respond

