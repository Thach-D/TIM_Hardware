# Sydnee O'Donnell
# 10.17.2025

# Parallel-Coupled Belt-Driven BiSlide (VMX-2) + single ELGO EMIX23 encoder
# Python 3.x

# script to move the Parallel coupled BiSlide system + optional ELGO EMIX23 linear encoder

# VXM-2 Stepping motor controller hooks up to raspberry pi via usb cable, this motor controls both BiSlide arms
# This script supports only one arm having the encoder (as of right now we only have 1 encoder)

# right now this code supports having an encoder on only 1 arm
# otherwise positions are inferred from stepcounts and can be inaccurate

# Independent arm moves using -1 / -2 suffixes
#   R50      -> relative +50 mm on BOTH arms
#   R50-1    -> relative +50 mm on arm 1 only
#   L20-2    -> relative -20 mm on arm 2 only
#   120      -> absolute 120 mm on BOTH arms
#   120-1    -> absolute 120 mm on arm 1 only
#   120,130  -> absolute pair (X=120, Y=130) if you ever need skewed positions

import serial
import time
import sys
import os
import re


class ParallelSlide(object):
    # VMX-2 controller wrapper for a parallel-coupled, two-axis BiSlide with one encoder

    def __init__(self, ctrl_address, enc_address=None, speed='500', mm_per_unit=1/157.501, encoder_axis=1):
        print("welcome")

        # Controller serial (9600-8N1 typical for VMX-2)
        self.ctrl = serial.Serial(
            port=ctrl_address,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2  # prevent blocking forever
        )
        print("serial opened")

        # Go online (accept remote), then set both axis speeds
        self.ctrl.write(b'F')  # Physically: enables remote control
        print("F")
        time.sleep(0.1)
        self.speed = str(speed)
        # 'C' clear queue; S1M/S2M set speeds; 'R' run sequence
        cmd = 'C, S1M%s, S2M%s, R' % (self.speed, self.speed)
        self.ctrl.write(cmd.encode('ascii'))

        # Units conversion factor (controller unit -> mm)
        # If VMX-2 returns mm natively, set this to 1.0
        self.mm_per_unit = float(mm_per_unit)
        
        # Which axis has the encoder (1 or 2)
        self.encoder_axis = encoder_axis

        # --- Optional encoder serial ---
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
                print(f"Encoder connected on axis {self.encoder_axis}")
            except Exception as e:
                print("Warning: could not open encoder at %s: %s" % (enc_address, e))
                self.encoder = None

    # ===== Helpers =====
    def checkdone(self):
        """Poll until motion completes. 'V' contains 'B' while Busy (moving)."""
        print("Moving", end='')
        status = 'B'
        while 'B' in status:
            time.sleep(0.1)
            sys.stdout.write('.')
            sys.stdout.flush()
            self.ctrl.write(b'V')  # ask for status
            time.sleep(0.1)
            response = self.ctrl.read(self.ctrl.inWaiting())
            status = response.decode('ascii', errors='ignore') if response else ''
        print("\nMoved")

    def _read_axis(self, cmd):
        """Read one axis value: 'X' for axis-1, 'Y' for axis-2. Returns raw controller units text."""
        self.ctrl.write(cmd.encode('ascii'))
        time.sleep(0.1)
        raw = self.ctrl.read(self.ctrl.inWaiting()) or b''
        return raw.decode('ascii', errors='ignore').strip()
    
    def _read_encoder_mm(self):
        """Read encoder position in mm. Returns float or None if encoder not available."""
        if not self.encoder:
            return None
        try:
            self.encoder.write(self.encoder_cmd)
            time.sleep(0.1)
            out = b''
            while self.encoder.inWaiting() > 0:
                out += self.encoder.read(1)
            # Parse framed STX ... ETX; inside may include '-' and digits with 3 implied decimals
            out_str = out.decode('ascii', errors='ignore')
            core = out_str[1:-2] if len(out_str) >= 3 else ''
            sign = '-' if '-' in core else ''
            digits = ''.join(c for c in core if c.isdigit())
            if len(digits) >= 3:
                mm_text = sign + digits[:-3] + '.' + digits[-3:]
            else:
                mm_text = sign + '0.' + digits.zfill(3)
            return float(mm_text)
        except Exception as e:
            print("Encoder read failed:", e)
            return None

    def _move_with_encoder_feedback(self, target_mm, axis, tolerance=0.05, max_iterations=10):
        """Move using encoder feedback for closed-loop control.
           target_mm: desired absolute position in mm
           axis: which axis to move (must match encoder_axis)
           tolerance: acceptable error in mm
           max_iterations: max correction attempts"""
        
        if not self.encoder or axis != self.encoder_axis:
            print(f"Warning: Encoder not available for axis {axis}, using open-loop control")
            return False
        
        print(f"[ENCODER FEEDBACK] Moving axis {axis} to {target_mm} mm with encoder feedback")
        
        for iteration in range(max_iterations):
            # Read current encoder position
            current_mm = self._read_encoder_mm()
            if current_mm is None:
                print("Encoder read failed, falling back to open-loop")
                return False
            
            error = target_mm - current_mm
            print(f"[Iteration {iteration+1}] Current: {current_mm:.3f} mm, Target: {target_mm:.3f} mm, Error: {error:.3f} mm")
            
            # Check if we're within tolerance
            if abs(error) <= tolerance:
                print(f"[SUCCESS] Reached target within tolerance ({tolerance} mm)")
                return True
            
            # Calculate correction move (use a damping factor for stability)
            correction_mm = error * 0.9  # 90% of error to avoid overshooting
            
            # Send incremental move command
            controller_units = correction_mm / self.mm_per_unit
            controller_units_str = str(controller_units)
            
            if axis == 1:
                cmd = 'C, S1M%s, I1M%s, R' % (self.speed, controller_units_str)
            else:
                cmd = 'C, S2M%s, I2M%s, R' % (self.speed, controller_units_str)
            
            self.ctrl.write(cmd.encode('ascii'))
            self.checkdone()
            time.sleep(0.2)  # Allow settling time
        
        print(f"[WARNING] Max iterations reached, final error: {error:.3f} mm")
        return False

    # ===== Motion API (supports independent or both) =====
    def set_speed(self, speed):
        """Set controller speed for one or both axes (we set both)."""
        self.speed = str(speed)
        cmd = 'C, S1M%s, S2M%s, R' % (self.speed, self.speed)
        self.ctrl.write(cmd.encode('ascii'))

    def origin(self):
        """Seek negative (toward motor/limit) a large distance on both axes, then zero.
           This finds the physical/hardware origin (limit switches)."""
        # Physically: drives hard-negative until origin/limit switch triggers; then zero position.
        cmd = 'C, S1M%s, S2M%s, I1M-2000000, I2M-2000000, R' % (self.speed, self.speed)
        self.ctrl.write(cmd.encode('ascii'))
        self.checkdone()
        self.zero()
        print("Returned to absolute hardware origin")

    def home(self):
        """Return to the last zeroed position (user-defined origin) without re-zeroing.
           This moves to position 0,0 based on current coordinate system."""
        print("Returning to last zeroed position (0,0)...")
        self.move_abs(0, axis=None)
        print("Returned to home (last zeroed position)")

    def zero(self):
        """Zero internal position counters at current location (no motion).
           This sets the current position as the new origin (0,0)."""
        self.ctrl.write(b'N')
        time.sleep(0.1)
        print("Position zeroed at current location - this is now (0,0)")

    def move_rel(self, mm, axis=None, use_encoder=True):
        """Relative move on one arm or both.
           axis=None -> both; axis=1 -> only axis 1; axis=2 -> only axis 2.
           use_encoder: if True and encoder available on this axis, use closed-loop control"""
        
        # If using encoder feedback and moving encoder axis
        if use_encoder and self.encoder and axis == self.encoder_axis:
            # Get current position from encoder
            current_mm = self._read_encoder_mm()
            if current_mm is not None:
                target_mm = current_mm + mm
                success = self._move_with_encoder_feedback(target_mm, axis)
                if success:
                    return
                # If encoder feedback failed, fall through to open-loop
        
        # Open-loop control (original method)
        controller_units = float(mm) / self.mm_per_unit
            
        print(f"[DEBUG] Moving axis {axis if axis else 'both'} by {mm} mm ({controller_units} controller units)")
        
        controller_units_str = str(controller_units)
        if axis == 1:
            cmd = 'C, S1M%s, I1M%s, R' % (self.speed, controller_units_str)
        elif axis == 2:
            cmd = 'C, S2M%s, I2M%s, R' % (self.speed, controller_units_str)
        else:
            cmd = 'C, S1M%s, S2M%s, I1M%s, I2M%s, R' % (self.speed, self.speed, controller_units_str, controller_units_str)
        self.ctrl.write(cmd.encode('ascii'))
        self.checkdone()

    def move_abs(self, mm, axis=None, use_encoder=True):
        """Absolute move to 'mm' on one arm or both.
           axis=None -> both; axis=1 -> only axis 1; axis=2 -> only axis 2.
           use_encoder: if True and encoder available on this axis, use closed-loop control"""
        
        # If using encoder feedback and moving encoder axis
        if use_encoder and self.encoder and axis == self.encoder_axis:
            success = self._move_with_encoder_feedback(mm, axis)
            if success:
                return
            # If encoder feedback failed, fall through to open-loop
        
        # Open-loop control (original method)
        controller_units = float(mm) / self.mm_per_unit
            
        controller_units_str = str(controller_units)
        
        if axis == 1:
            cmd = 'C, S1M%s, IA1M%s, R' % (self.speed, controller_units_str)
        elif axis == 2:
            cmd = 'C, S2M%s, IA2M%s, R' % (self.speed, controller_units_str)
        else:
            cmd = 'C, S1M%s, S2M%s, IA1M%s, IA2M%s, R' % (self.speed, self.speed, controller_units_str, controller_units_str)
        self.ctrl.write(cmd.encode('ascii'))
        self.checkdone()

    def move_abs_pair(self, mm_x, mm_y, use_encoder=True):
        """Absolute move axis-1 (X) to mm_x and axis-2 (Y) to mm_y (rare for a hard-coupled system).
           use_encoder: if True, use encoder feedback for the axis that has an encoder"""
        
        # Move axis with encoder first if available
        if use_encoder and self.encoder:
            if self.encoder_axis == 1:
                self._move_with_encoder_feedback(mm_x, 1)
                # Then move axis 2 open-loop
                controller_y = float(mm_y) / self.mm_per_unit
                cmd = 'C, S2M%s, IA2M%s, R' % (self.speed, controller_y)
                self.ctrl.write(cmd.encode('ascii'))
                self.checkdone()
            else:  # encoder_axis == 2
                self._move_with_encoder_feedback(mm_y, 2)
                # Then move axis 1 open-loop
                controller_x = float(mm_x) / self.mm_per_unit
                cmd = 'C, S1M%s, IA1M%s, R' % (self.speed, controller_x)
                self.ctrl.write(cmd.encode('ascii'))
                self.checkdone()
        else:
            # No encoder, do standard open-loop move
            controller_x = float(mm_x) / self.mm_per_unit
            controller_y = float(mm_y) / self.mm_per_unit
            
            cmd = 'C, S1M%s, S2M%s, IA1M%s, IA2M%s, R' % (self.speed, self.speed, controller_x, controller_y)
            self.ctrl.write(cmd.encode('ascii'))
            self.checkdone()

    def kill(self):
        """Emergency stop now."""
        self.ctrl.write(b'K')

    def close(self):
        """Close serial connections."""
        if self.ctrl:
            self.ctrl.close()
        if self.encoder:
            self.encoder.close()

    # ===== Telemetry =====
    def position_controller_mm(self):
        """Return (x_mm, y_mm) from controller by converting internal counts with self.mm_per_unit."""
        try:
            x_raw = self._read_axis('X')
            y_raw = self._read_axis('Y')
            x = round(float(x_raw) * self.mm_per_unit, 2)
            y = round(float(y_raw) * self.mm_per_unit, 2)
            print("Controller reports: X=%.2f mm, Y=%.2f mm" % (x, y))
            return x, y
        except Exception as e:
            print("Controller position read failed:", e)
            return None, None

    def position_encoder_mm(self):
        """Return encoder mm text (xxx.xxx) if encoder present; else None."""
        if not self.encoder:
            print("(No encoder configured)")
            return None
        
        mm_val = self._read_encoder_mm()
        if mm_val is not None:
            print(f"Encoder reads position {mm_val:.3f} mm (axis {self.encoder_axis})")
            return mm_val
        return None

    def help(self):
        print("\n****Moving the Parallel BiSlide (VMX-2)****")
        print("'500'         \t- move BOTH axes to absolute position 500 mm")
        print("'120,130'     \t- move X to 120 mm and Y to 130 mm")
        print("'L40'         \t- move BOTH axes -40 mm (toward motor)")
        print("'R60'         \t- move BOTH axes +60 mm (away from motor)")
        print("'500-1'       \t- move ONLY axis 1 to absolute 500 mm")
        print("'500-2'       \t- move ONLY axis 2 to absolute 500 mm")
        print("'R40-1'       \t- relative +40 mm on axis 1 only")
        print("'L20-2'       \t- relative -20 mm on axis 2 only")
        print("'R20-2'       \t- relative +20 mm on axis 2 only")
        print("'S4000'       \t- set the speed to 4000 (controller units)")
        print("\n****Other Commands****")
        print("'origin'      \t- seek hardware origin (limit switches) and zero there")
        print("'home'        \t- return to last zeroed position (user-defined 0,0)")
        print("'zero'        \t- zero controller at current location (sets new 0,0)")
        print("'where'       \t- show controller X/Y (mm) and encoder (mm)")
        print("'k'           \t- kill current movement")
        print("'quit'        \t- quit the program")
        print("\n****Not Working?****")
        print("- Check USB addresses for BOTH controller and encoder.")
        print("- Ensure controller 'On-Line' is lit (no fault lights). Power-cycle if unsure.")
        print("- If /dev/ttyUSB# changes, consider /dev/serial/by-id/ stable names.")
        if self.encoder:
            print(f"\nEncoder feedback is ENABLED on axis {self.encoder_axis} for improved accuracy!")


if __name__ == "__main__":
    print("Welcome")
    ctrl_port = "/dev/tty.usbserial-1130"  # VMX-2 controller (prefer /dev/serial/by-id/..)
    enc_port = "/dev/tty.usbserial-AH03MOB7"  # "/dev/tty.usbserial-110"  # EMIX23 encoder (set to None if not connected)

    # encoder_axis: which axis has the encoder (1 or 2)
    slide = ParallelSlide(ctrl_port, enc_port, speed='500', mm_per_unit=1/157.501, encoder_axis=1)

    print("Welcome to the Parallel BiSlide (VMX-2) program!")
    print(" __________________________________")
    print("|          >>>>>>>|  |           |")
    print("|__________>>>>>>>|  |___________|")
    print("You can now control the coupled BiSlide.")
    print("Enter 'help' for instructions. Enter 'quit' to quit.")

    try:
        my_input = ""
        while my_input != "quit":
            my_input = input("\nWhere would you like to go?\n").strip()

            try: 
                # guard against mixing commands (keep it simple/safe)
                if (('L' in my_input and 'R' in my_input) or
                        ('L' in my_input and 'S' in my_input) or
                        ('R' in my_input and 'S' in my_input)):
                    print("Please pick one command.")

                elif my_input.lower() == 'help':
                    slide.help()

                elif my_input.lower() == 'origin':
                    slide.origin()

                elif my_input.lower() == 'home':
                    slide.home()

                elif my_input.lower() == 'zero':
                    slide.zero()

                elif my_input.lower() == 'where':
                    slide.position_controller_mm()
                    slide.position_encoder_mm()

                elif my_input.lower() == 'k':
                    slide.kill()

                elif my_input.lower().startswith('s'):
                    # Speed command e.g. S5000
                    myspeed = re.findall(r'\d+', my_input)
                    if not myspeed:
                        print("Please provide a speed like S4000.")
                    else:
                        speed = myspeed[0]
                        slide.set_speed(speed)
                        print("Speed set to %s" % speed)

                # ---- Relative moves with optional -1 / -2 suffix ----
                elif re.search(r'^[rR]\s*-?\d', my_input):
                    val = float(re.findall(r'-?\d+\.?\d*', my_input)[0])
                    if re.search(r'-1\s*$', my_input):
                        slide.move_rel(val, axis=1)
                    elif re.search(r'-2\s*$', my_input):
                        slide.move_rel(val, axis=2)
                    else:
                        slide.move_rel(val, axis=None)  # both

                elif re.search(r'^[lL]\s*-?\d', my_input):
                    val = -abs(float(re.findall(r'-?\d+\.?\d*', my_input)[0]))
                    if re.search(r'-1\s*$', my_input):
                        slide.move_rel(val, axis=1)
                    elif re.search(r'-2\s*$', my_input):
                        slide.move_rel(val, axis=2)
                    else:
                        slide.move_rel(val, axis=None)  # both

                # ---- Absolute pair: "i,j" ----
                elif ',' in my_input:
                    parts = my_input.replace(' ', '').split(',')
                    if len(parts) != 2:
                        print("Please use i,j for paired absolute move (e.g., 120,120).")
                    else:
                        x = float(parts[0])
                        y = float(parts[1])
                        slide.move_abs_pair(x, y)

                # ---- Absolute single with optional -1 / -2 suffix ----
                elif re.search(r'-1\s*$', my_input):
                    val = float(re.findall(r'-?\d+\.?\d*', my_input)[0])
                    slide.move_abs(val, axis=1)

                elif re.search(r'-2\s*$', my_input):
                    val = float(re.findall(r'-?\d+\.?\d*', my_input)[0])
                    slide.move_abs(val, axis=2)

                elif my_input.lower() == 'quit':
                    continue

                else:
                    # Bare number => absolute BOTH axes
                    val = float(re.findall(r'-?\d+\.?\d*', my_input)[0])
                    slide.move_abs(val, axis=None)

            except KeyboardInterrupt:
                slide.kill()
                continue
            except Exception as e:
                print("Please enter a valid command")
                print("Error:", e)
                continue

    except KeyboardInterrupt:
        slide.kill()
        slide.close()

    slide.kill()
    slide.close()
