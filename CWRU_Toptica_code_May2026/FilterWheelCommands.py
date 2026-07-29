from labjack_unified.devices import LabJackU6
import serial
from time import sleep
import traceback

port = 'COM4'

def printThis():
    print('hi')
   
    
def toNext(numSlots):
    '''
    Rotates filter wheel 90 to next slot
    
    Returns:
        endPos (int): position of filter wheel after rotation
    '''
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    lj = LabJackU6()
    
    try:
        lj.set_quadrature(zphase1=True)
        portZ = 'FIO2'
        ppr = 4*2000
        stepsToNext = int(ppr/numSlots)
        print(stepsToNext)
        
        angle = 360/numSlots

        sleep(0.1)

        initPos = lj.get_counter()
        pos = initPos
        
        
        command = '/1aM1P0R'  # 1aM selects first drive.   P0 is "endless" move in positive direction.  R runs the command.
        ser.write(command.strip().encode() + b'\r\n')  # The 'b' here must mean set baud=9600.  ?
                
#         command = '/1aM1P'+str(stepsToNext)+'R'
#         ser.write(command.strip().encode() + b'\r\n')
        while 360/ppr*pos > angle:
            pos = lj.get_counter()
            print(pos)
                
        ser.write(b'/1T\r\n')  
    
    except KeyboardInterrupt:
        print('keyboard interrupt')
        ser.write(b'/1T\r\n')
    except Exception as e:
        print('error')
        ser.write(b'/1T\r\n')
        traceback.print_exc()
    finally:
        sleep(0.1)
        endPos = 360/ppr * lj.get_counter()
        return endPos    
        print('closing...')
        ser.close()
        lj.close()
        print('done')

def toZero():
    '''
    Rotates filter wheel to zero point defined by encoder
    
    Returns:
        endPos (int): position of filter wheel after rotation
    '''
    print('cwru-cmb/Toptica-Terascan/FilterwheelCommands.py version')
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    lj = LabJackU6()
    try:
        lj.set_quadrature(zphase1=True)
        portZ = 'FIO2'
        ppr = 4*2000
        numSlots = 4
        stepsToNext = int(ppr/numSlots)

        sleep(0.1)

        command = '/1aM1D0R'
        ser.write(command.strip().encode() + b'\r\n')

        flagref = False
        while not flagref:
            if lj.get_digital(portZ) == 1:
                flagref = True
                ser.write(b'/1T\r\n')

        sleep(0.1)
        endPos = 360/ppr * lj.get_counter()
        return endPos

    except KeyboardInterrupt:
        print('keyboard interrupt')
        ser.write(b'/1T\r\n')
    except Exception as e:
        print('error')
        ser.write(b'/1T\r\n')
        traceback.print_exc()
    finally:
        print('closing...')
        ser.close()
        lj.close()
        print('done')
        
def stop():
    '''
    Stops filter wheel rotation
    '''
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    ser.write(b'/1T\r\n')
    ser.close()
    
def rotate(numSteps):
    '''
    Rotates filter wheel forward by given number of steps
    
    Parameters:
        numSteps (int): number of steps to rotate motor
    '''
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    sleep(0.1)

    command = '/1aM1P'+str(numSteps)+'R'
    ser.write(command.strip().encode() + b'\r\n')
    
    ser.close()

def rotateBack(numSteps):
    '''
    Rotates filter wheel backward by given number of steps
    
    Parameters:
        numSteps (int): number of steps to rotate motor
    '''
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    sleep(0.1)

    command = '/1aM1D'+str(numSteps)+'R'
    ser.write(command.strip().encode() + b'\r\n')
    
    ser.close()
    
def rotateContinuous(direction='positive'):
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    if direction=='positive':
        command = '/1aM1P0R'
    else:
        command = '/1aM1D0R'
    ser.write(command.strip().encode() + b'\r\n')
    ser.close()
    

def toAngle(angle):
    '''
    Rotates filter wheel by given angle
    
    Parameters:
        angle (float): angle to rotate filter wheel by, in degrees.
        
    Returns:
        endPos (int): position of filter wheel after rotation
    '''
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    lj = LabJackU6()
    
    try:
        lj.set_quadrature(zphase1=False)  # True pays attention to z line, which resets count to zero at one point in the rotation.
        portZ = 'FIO2'
        ppr = 4*2000
        numSlots = 4

        sleep(0.1)
        
        endPos = int( (angle/360)*ppr)

        initPos = lj.get_counter()
        print(f"Initial position: {initPos}")
        print(f"End position: {endPos}")
        pos = initPos
                
        if angle > 0:
            command = '/1aM1D0R'
            ser.write(command.strip().encode() + b'\r\n')
            while pos < endPos:
                pos = lj.get_counter()
                if (pos >1940 ):
                    print(pos)
                
        elif angle < 0:
            command = '/1aM1P0R'
            ser.write(command.strip().encode() + b'\r\n')
            while 360/ppr*pos > angle:
                pos = lj.get_counter()
                print(pos)

        ser.write(b'/1T\r\n')
        sleep(0.1)
        ser.close()
        endPos = 360/ppr * lj.get_counter()
        return endPos
    
    except KeyboardInterrupt:
        print('keyboard interrupt')
        ser.write(b'/1T\r\n')
    except Exception as e:
        print('error')
        ser.write(b'/1T\r\n')
        traceback.print_exc()
    finally:
        print('closing...')
        ser.close()
        lj.close()
        print('done')
        
def setSpeed(speed):
    '''
    Sets speed of motor
    
    Parameters:
        speed (int): speed to set motor to
    '''
    ser = serial.Serial(port, 9600)
    ser.close()
    ser.open()
    sleep(0.1)

    command = '/1aM1V'+str(speed)+'R'
    ser.write(command.strip().encode() + b'\r\n')

    ser.close()
    
    