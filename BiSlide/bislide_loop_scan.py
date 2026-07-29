# Thach Dang 11/16/2025
# Adapted from Sydnee + Amber
# # BiSlide Scanning Pattern Script 

import serial
import time
import sys
import re


class ParallelSlide(object):

    def __init__(self, ctrl_address, enc_address=None, speed='500', mm_per_unit=1/157.501):
        # Controller serial (9600-8N1 typical for VMX-2)
        self.ctrl = serial.Serial(
            port=ctrl_address,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2
        )

        # Set speeds
        self.ctrl.write(b'F')
        time.sleep(0.1)
        self.speed = str(speed)
        cmd = 'C, S1M%s, S2M%s, R' % (self.speed, self.speed)
        self.ctrl.write(cmd.encode('ascii'))
        
        # Units conversion factor
        self.mm_per_unit = float(mm_per_unit)
        
        # Encoder serial 
        self.encoder = None
        self.encoder_cmd = bytearray(b'\x02\x52\x44\x58\x03')  # STX 'RDX' ETX
        if enc_address:
            try:
                self.encoder = serial.Serial(
                    port=enc_address,
                    baudrate=9600,
                    parity=serial.PARITY_NONE,
                    bytesize=serial.EIGHTBITS,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.2
                )
                print("Encoder connected successfully")
            except Exception as e:
                raise Exception("ENCODER REQUIRED: Could not open encoder at %s: %s" % (enc_address, e))
        else:
            raise Exception("ENCODER REQUIRED: No encoder address provided")
        
        print("BiSlide controller initialized")

    def checkdone(self):
        """Poll until motion completes."""
        status = 'B'
        while 'B' in status:
            time.sleep(0.05)
            self.ctrl.write(b'V')
            time.sleep(0.05)
            response = self.ctrl.read(self.ctrl.inWaiting())
            status = response.decode('ascii', errors='ignore') if response else ''

    def _read_axis(self, cmd):
        """Read one axis value: 'X' for axis-1, 'Y' for axis-2."""
        self.ctrl.write(cmd.encode('ascii'))
        time.sleep(0.1)
        raw = self.ctrl.read(self.ctrl.inWaiting()) or b''
        return raw.decode('ascii', errors='ignore').strip()

    def set_speed(self, speed):
        """Set controller speed for both axes."""
        self.speed = str(speed)
        cmd = 'C, S1M%s, S2M%s, R' % (self.speed, self.speed)
        self.ctrl.write(cmd.encode('ascii'))

    def zero(self):
        """Zero internal position counters at current location."""
        self.ctrl.write(b'N')
        time.sleep(0.1)
        print("Position zeroed")

    def move_abs_pair(self, mm_x, mm_y, verbose=True):
        """Move to absolute position (x_mm, y_mm)."""
        if verbose:
            print(f"Moving to X={mm_x:.2f} mm, Y={mm_y:.2f} mm")
        x_units = mm_x * (1 / self.mm_per_unit)
        y_units = mm_y * (1 / self.mm_per_unit)
        cmd = 'C, S1M%s, S2M%s, IA1M%s, IA2M%s, R' % (
            self.speed, self.speed, x_units, y_units
        )
        self.ctrl.write(cmd.encode('ascii'))
        self.checkdone()

    def kill(self):
        """Emergency stop."""
        self.ctrl.write(b'K')

    def close(self):
        """Close serial connections."""
        if self.ctrl:
            self.ctrl.close()
        if self.encoder:
            self.encoder.close()

    def position_controller_mm(self):
        """Return (x_mm, y_mm) from controller."""
        try:
            x_raw = self._read_axis('X')
            y_raw = self._read_axis('Y')
            x = round(float(x_raw) * self.mm_per_unit, 2)
            y = round(float(y_raw) * self.mm_per_unit, 2)
            return x, y
        except Exception as e:
            print("Controller position read failed:", e)
            return None, None

    def position_encoder_mm(self):
        """Return encoder mm text if encoder present; else None."""
        if not self.encoder:
            return None
        try:
            self.encoder.write(self.encoder_cmd)
            time.sleep(0.1)
            out = b''
            while self.encoder.inWaiting() > 0:
                out += self.encoder.read(1)
            out_str = out.decode('ascii', errors='ignore')
            core = out_str[1:-2] if len(out_str) >= 3 else ''
            sign = '-' if '-' in core else ''
            digits = ''.join(c for c in core if c.isdigit())
            if len(digits) >= 3:
                mm_text = sign + digits[:-3] + '.' + digits[-3:]
            else:
                mm_text = sign + '0.' + digits.zfill(3)
            return mm_text
        except Exception as e:
            print("Encoder read failed:", e)
            return None


def perform_scan(slide, num_scans, width_mm, height_mm, dwell_time=0.1):
    """
    Perform a vertical scan pattern with encoder position verification.
    Pattern: down → right → up → right → down → ...
    
    Parameters:
    -----------
    slide : ParallelSlide
        The BiSlide controller object (must have encoder)
    num_scans : int
        Number of vertical scan segments
    width_mm : float
        Width of scan area in mm (X direction)
    height_mm : float
        Height of scan area in mm (Y direction)
    dwell_time : float
        Time to dwell at each corner (seconds)
    """
    
    print("\n" + "="*60)
    print("VERTICAL SCAN PARAMETERS")
    print("="*60)
    print(f"Number of scan segments: {num_scans}")
    print(f"Scan area: {width_mm} mm (X) × {height_mm} mm (Y)")
    print(f"Dwell time per corner: {dwell_time} s")
    print(f"Starting position: (0, 0) - top left")
    print(f"Pattern: DOWN → RIGHT → UP → RIGHT → DOWN → ...")
    print("Encoder: ACTIVE (position monitoring enabled)")
    print("="*60)
    
    # Calculate step size for X movements
    x_step = width_mm / num_scans
    
    print(f"\nX step size: {x_step:.3f} mm")
    print(f"Total movements: {num_scans * 2} (alternating vertical and horizontal)")
    
    # Confirm before starting
    response = input("\nReady to start scan? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Scan cancelled.")
        return
    
    print("\n" + "="*60)
    print("STARTING VERTICAL SCAN")
    print("="*60)
    start_time = time.time()
    
    current_x = 0
    current_y = 0
    
    # Start at top left (0, 0)
    print("\nStarting at (0, 0)")
    slide.move_abs_pair(0, 0, verbose=False)
    time.sleep(dwell_time)
    _show_position(slide)
    
    for i in range(num_scans):
        segment = i + 1
        
        # Alternate between scanning down and up
        if i % 2 == 0:
            # Scan DOWN
            print(f"\n--- Segment {segment}/{num_scans} ---")
            print(f"Scanning DOWN from ({current_x:.2f}, {current_y:.2f}) to ({current_x:.2f}, {height_mm})")
            slide.move_abs_pair(current_x, height_mm, verbose=False)
            current_y = height_mm
            time.sleep(dwell_time)
            _show_position(slide)
            
            # Move RIGHT (if not last segment)
            if i < num_scans - 1:
                current_x += x_step
                print(f"Moving RIGHT to ({current_x:.2f}, {current_y:.2f})")
                slide.move_abs_pair(current_x, current_y, verbose=False)
                time.sleep(dwell_time)
                _show_position(slide)
        else:
            # Scan UP
            print(f"\n--- Segment {segment}/{num_scans} ---")
            print(f"Scanning UP from ({current_x:.2f}, {current_y:.2f}) to ({current_x:.2f}, 0)")
            slide.move_abs_pair(current_x, 0, verbose=False)
            current_y = 0
            time.sleep(dwell_time)
            _show_position(slide)
            
            # Move RIGHT (if not last segment)
            if i < num_scans - 1:
                current_x += x_step
                print(f"Moving RIGHT to ({current_x:.2f}, {current_y:.2f})")
                slide.move_abs_pair(current_x, current_y, verbose=False)
                time.sleep(dwell_time)
                _show_position(slide)
        
        # Progress indicator
        progress = (segment / num_scans) * 100
        print(f"Progress: {progress:.1f}% complete")
    
    elapsed_time = time.time() - start_time
    print("\n" + "="*60)
    print("SCAN COMPLETE")
    print("="*60)
    print(f"Total time: {elapsed_time:.2f} seconds")
    print(f"Final scan position: ({current_x:.2f}, {current_y:.2f})")
    
    # Final position check
    print("\nFinal scan position verification:")
    _show_position(slide)
    
    # # Return to origin
    # print("\n" + "="*60)
    # print("RETURNING TO ORIGIN")
    # print("="*60)
    # print("Moving back to (0, 0)...")
    # slide.move_abs_pair(0, 0, verbose=False)
    # time.sleep(dwell_time)
    
    # print("\nOrigin position verification:")
    # _show_position(slide)
    
    total_time = time.time() - start_time
    print("\n" + "="*60)
    print("SCAN AND RETURN COMPLETE")
    print("="*60)
    print(f"Total time (including return): {total_time:.2f} seconds")
    print("BiSlide is now at origin (0, 0)")
    print("="*60)


def _show_position(slide):
    """Display current position from controller and encoder."""
    x, y = slide.position_controller_mm()
    enc = slide.position_encoder_mm()
    
    if x is not None and y is not None:
        print(f"  Controller: X={x:.2f} mm, Y={y:.2f} mm", end='')
    
    if enc:
        print(f" | Encoder: {enc} mm")
    else:
        print()  # newline if encoder failed


def main():
    print("\n" + "="*60)
    print("BiSlide Vertical Scan Script (with Encoder)")
    print("="*60)
    print("\nThis script performs a zigzag vertical scan pattern")
    print("Pattern: DOWN → RIGHT → UP → RIGHT → DOWN → ...")
    print("The current position will be set as the origin (0,0)")
    print("\nREQUIRES: ELGO EMIX23 encoder for position verification")
    print("="*60)
    
    # Configuration - UPDATE THESE FOR YOUR SYSTEM
    ctrl_port = "/dev/tty.PL2303-USBtoUART10"  # controller
    enc_port = "/dev/tty.usbserial-AH03MOB7"  # encoder 
    speed = '500'  # Controller speed units/second
    mm_per_unit = 1/157.501  # mm per controller unit, from
    
    # Get scan parameters from user
    try:
        num_scans = int(input("\nEnter number of vertical scan segments: "))
        if num_scans < 1:
            print("Error: Number of scans must be at least 1")
            return
        
        width_mm = float(input("Enter scan width in mm (X direction): "))
        if width_mm <= 0:
            print("Error: Width must be positive")
            return
        
        height_mm = float(input("Enter scan height in mm (Y direction): "))
        if height_mm <= 0:
            print("Error: Height must be positive")
            return
        
        dwell_time = float(input("Enter dwell time per corner in seconds (default 0.1): ") or "0.1")
        
    except ValueError as e:
        print(f"Error: Invalid input - {e}")
        return
    except KeyboardInterrupt:
        print("\nCancelled by user")
        return
    
    # Initialize BiSlide
    try:
        print(f"\nConnecting to BiSlide controller on {ctrl_port}...")
        print(f"Connecting to encoder on {enc_port}...")
        
        slide = ParallelSlide(ctrl_port, enc_port, speed=speed, mm_per_unit=mm_per_unit)
        
        # Zero the current position
        print("\nSetting current position as origin (0,0)...")
        slide.zero()
        time.sleep(0.5)
        
        # Show initial position with encoder reading
        print("\nInitial position (after zeroing):")
        _show_position(slide)
        
        # Perform the scan
        perform_scan(slide, num_scans, width_mm, height_mm, dwell_time)
        
    except serial.SerialException as e:
        print(f"\nError: Could not open serial port")
        print(f"Details: {e}")
        print("\nPlease check:")
        print("  - USB cables are connected (BOTH controller and encoder)")
        print("  - Device paths are correct:")
        print(f"    Controller: {ctrl_port}")
        print(f"    Encoder: {enc_port}")
        print("  - You have permissions (may need to add user to dialout group)")
        print("  - Try 'ls /dev/tty*' or 'ls /dev/ttyUSB*' to find devices")
        return
    
    except KeyboardInterrupt:
        print("\n\nEmergency stop - killing motion")
        slide.kill()
        slide.close()
        print("Stopped safely")
        return
    
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        if 'slide' in locals():
            slide.kill()
            slide.close()
        return
    
    finally:
        if 'slide' in locals():
            slide.close()
            print("\nBiSlide connection closed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
