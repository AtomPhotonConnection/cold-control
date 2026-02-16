#!/usr/bin/env python3
"""
Safe Arbitrary Waveform Upload for Rigol WX2184C/WX1284C AWG
This script safely uploads and plays arbitrary waveforms using PyVISA.

Key safety features based on the user manual:
1. Proper initialization sequence
2. Correct data formatting (14-bit, 16-bit words)
3. Segment size validation (minimum 192 points, multiple of 16)
4. Proper IEEE 488.2 binary block format
5. Clear error handling
"""

import pyvisa
import numpy as np
import struct
import time


class RigolAWG:
    """Safe interface for Rigol WX2184C/WX1284C Arbitrary Waveform Generator"""
    
    def __init__(self, resource_name):
        """
        Initialize connection to AWG
        
        Args:
            resource_name: VISA resource string (e.g., 'TCPIP0::192.168.1.100::INSTR')
        """
        self.rm = pyvisa.ResourceManager()
        self.instrument = None
        self.resource_name = resource_name
        
    def connect(self):
        """Establish connection and verify instrument"""
        try:
            self.instrument = self.rm.open_resource(self.resource_name)
            self.instrument.timeout = 10000  # 10 second timeout
            
            # Query identification
            idn = self.instrument.query('*IDN?')
            print(f"Connected to: {idn.strip()}")
            
            # Clear status and errors
            self.instrument.write('*CLS')
            time.sleep(0.1)
            
            return True
            
        except Exception as e:
            print(f"Error connecting to instrument: {e}")
            return False
    
    def check_errors(self):
        """Check for instrument errors"""
        try:
            error = self.instrument.query(':SYST:ERR?')
            if not error.startswith('0,'):
                print(f"Instrument error: {error.strip()}")
                return False
            return True
        except Exception as e:
            print(f"Error checking instrument status: {e}")
            return False
    
    def select_channel(self, channel):
        """
        Select the active channel (1-4)
        
        Args:
            channel: Channel number (1, 2, 3, or 4)
        """
        if channel not in [1, 2, 3, 4]:
            raise ValueError("Channel must be 1, 2, 3, or 4")
        
        self.instrument.write(f':INST:SEL {channel}')
        print(f"Selected channel {channel}")
        self.check_errors()
    
    def set_trace_mode(self, mode='SING'):
        """
        Set trace download mode
        
        Args:
            mode: 'SING' (single channel), 'DUPL' (duplicate to pair), 
                  'ZER' (zero other channel), or 'COMB' (combined/interleaved)
        """
        valid_modes = ['SING', 'DUPL', 'ZER', 'COMB']
        mode_upper = mode.upper()[:4]
        
        if mode_upper not in valid_modes:
            raise ValueError(f"Mode must be one of {valid_modes}")
        
        self.instrument.write(f':TRAC:MODE {mode_upper}')
        print(f"Set trace mode to {mode_upper}")
        self.check_errors()
    
    def validate_waveform_size(self, num_points):
        """
        Validate that waveform size meets requirements
        
        Requirements from manual:
        - Minimum: 192 points
        - Must be multiple of 16 points
        
        Args:
            num_points: Number of waveform points
            
        Returns:
            Validated number of points
        """
        if num_points < 192:
            raise ValueError(f"Waveform must be at least 192 points (got {num_points})")
        
        if num_points % 16 != 0:
            # Round up to nearest multiple of 16
            adjusted = ((num_points + 15) // 16) * 16
            print(f"Warning: Waveform size adjusted from {num_points} to {adjusted} (must be multiple of 16)")
            return adjusted
        
        return num_points
    
    def normalize_waveform(self, waveform_data):
        """
        Normalize waveform data to 14-bit DAC values (0-16383)
        
        The WX2184C uses 14-bit DAC values:
        - 0x0000 (0) corresponds to -2V
        - 0x2000 (8192) corresponds to 0V  
        - 0x3FFF (16383) corresponds to +2V
        
        Args:
            waveform_data: NumPy array of float values (typically -1.0 to +1.0)
            
        Returns:
            NumPy array of uint16 values (0-16383)
        """
        # Normalize to -1.0 to +1.0 range
        waveform_normalized = np.clip(waveform_data, -1.0, 1.0)
        
        # Scale to 0-16383 (14-bit range)
        # -1.0 -> 0, 0.0 -> 8192, +1.0 -> 16383
        dac_values = ((waveform_normalized + 1.0) * 8191.5).astype(np.uint16)
        
        # Ensure we don't exceed 14-bit range
        dac_values = np.clip(dac_values, 0, 16383)
        
        return dac_values
    
    def create_binary_block_header(self, num_bytes):
        """
        Create IEEE 488.2 binary block header
        
        Format: #<num_digits><byte_count><data>
        Example: #42048 means 4 digits follow, then 2048 bytes of data
        
        Args:
            num_bytes: Number of bytes in the data block
            
        Returns:
            Header string (e.g., '#42048')
        """
        byte_count_str = str(num_bytes)
        num_digits = len(byte_count_str)
        header = f'#{num_digits}{byte_count_str}'
        return header
    
    def upload_waveform(self, waveform_data, segment=1):
        """
        Upload arbitrary waveform to AWG memory
        
        This is the critical function that must be done correctly to avoid
        freezing the AWG. Follows the proper sequence from the manual.
        
        Args:
            waveform_data: NumPy array of float values (-1.0 to +1.0)
            segment: Segment number (1-32000)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Validate and adjust waveform size
            num_points = len(waveform_data)
            validated_points = self.validate_waveform_size(num_points)
            
            # Pad with zeros if size was adjusted
            if validated_points > num_points:
                waveform_data = np.pad(waveform_data, 
                                      (0, validated_points - num_points), 
                                      mode='constant')
            
            # Step 2: Convert to 14-bit DAC values
            dac_values = self.normalize_waveform(waveform_data)
            
            # Step 3: Define segment in memory
            # CRITICAL: Must define segment BEFORE uploading data
            print(f"Defining segment {segment} with {validated_points} points...")
            self.instrument.write(f':TRAC:DEF {segment},{validated_points}')
            time.sleep(0.05)  # Small delay after defining
            
            if not self.check_errors():
                print("Error defining segment!")
                return False
            
            # Step 4: Select the segment
            print(f"Selecting segment {segment}...")
            self.instrument.write(f':TRAC:SEL {segment}')
            time.sleep(0.05)
            
            if not self.check_errors():
                print("Error selecting segment!")
                return False
            
            # Step 5: Prepare binary data
            # Each point is 2 bytes (16-bit word, but only 14 bits used)
            binary_data = dac_values.astype('<u2').tobytes()  # Little-endian uint16
            num_bytes = len(binary_data)
            
            # Step 6: Create IEEE 488.2 binary block header
            header = self.create_binary_block_header(num_bytes)
            command = f':TRAC:DATA {header}'
            
            # Step 7: Upload data using binary write
            print(f"Uploading {validated_points} points ({num_bytes} bytes)...")
            
            # Write command header
            self.instrument.write_raw(command.encode('ascii'))
            
            # Write binary data
            self.instrument.write_raw(binary_data)
            
            # Write termination
            self.instrument.write_raw(b'\n')
            
            # Wait for operation to complete
            self.instrument.query('*OPC?')
            time.sleep(0.1)
            
            # Step 8: Verify no errors occurred
            if not self.check_errors():
                print("Error during waveform upload!")
                return False
            
            print(f"Successfully uploaded waveform to segment {segment}")
            return True
            
        except Exception as e:
            print(f"Error uploading waveform: {e}")
            return False
    
    def play_waveform(self, segment=1):
        """
        Start playing the specified waveform segment
        
        Args:
            segment: Segment number to play (1-32000)
        """
        try:
            # Select segment
            self.instrument.write(f':TRAC:SEL {segment}')
            time.sleep(0.05)
            
            # Set to arbitrary waveform function
            self.instrument.write(':FUNC:MODE USER')
            time.sleep(0.05)
            
            # Enable output
            print("Enabling output...")
            self.instrument.write(':OUTP ON')
            time.sleep(0.05)
            
            if self.check_errors():
                print(f"Playing waveform from segment {segment}")
                return True
            else:
                print("Error starting waveform playback")
                return False
                
        except Exception as e:
            print(f"Error playing waveform: {e}")
            return False
    
    def stop_output(self):
        """Stop output and turn off channel"""
        try:
            self.instrument.write(':OUTP OFF')
            print("Output disabled")
            return True
        except Exception as e:
            print(f"Error stopping output: {e}")
            return False
    
    def set_sample_rate(self, rate_hz):
        """
        Set the sample rate
        
        Args:
            rate_hz: Sample rate in Hz (e.g., 1e6 for 1 MHz)
        """
        try:
            self.instrument.write(f':FREQ:RAST {rate_hz}')
            actual = float(self.instrument.query(':FREQ:RAST?'))
            print(f"Sample rate set to {actual/1e6:.3f} MHz")
            self.check_errors()
        except Exception as e:
            print(f"Error setting sample rate: {e}")
    
    def set_amplitude(self, voltage):
        """
        Set output amplitude
        
        Args:
            voltage: Peak-to-peak voltage (0.02 to 4.0 V for DC coupled)
        """
        try:
            self.instrument.write(f':VOLT {voltage}')
            actual = float(self.instrument.query(':VOLT?'))
            print(f"Amplitude set to {actual} Vpp")
            self.check_errors()
        except Exception as e:
            print(f"Error setting amplitude: {e}")
    
    def set_offset(self, voltage):
        """
        Set output DC offset
        
        Args:
            voltage: DC offset voltage
        """
        try:
            self.instrument.write(f':VOLT:OFFS {voltage}')
            actual = float(self.instrument.query(':VOLT:OFFS?'))
            print(f"Offset set to {actual} V")
            self.check_errors()
        except Exception as e:
            print(f"Error setting offset: {e}")
    
    def disconnect(self):
        """Close connection to instrument"""
        if self.instrument:
            self.instrument.close()
            print("Disconnected from AWG")


def create_example_waveforms():
    """Create some example waveforms for testing"""
    
    # Example 1: Simple sine wave (1024 points)
    num_points = 1024
    samp_rate = 1e9  # 1 GHz sample rate

    t = np.linspace(0, num_points/samp_rate, num_points)

    # 60 MHz sine wave sampled at 1 GHz
    sine_wave = np.sin(2*np.pi*60e6*t)
    
    # Example 2: Sawtooth wave (1024 points)
    sawtooth = np.linspace(-1, 1, num_points)
    
    # Example 3: Pulse train (1024 points)
    pulse = np.concatenate([
        np.ones(128),      # High for 128 points
        -np.ones(128),     # Low for 128 points
    ])
    pulse = np.tile(pulse, 4)  # Repeat 4 times
    
    # Example 4: Gaussian pulse (1024 points)
    t = np.linspace(-4, 4, num_points)
    gaussian = np.exp(-t**2)
    
    return {
        'sine': sine_wave,
        'sawtooth': sawtooth,
        'pulse': pulse,
        'gaussian': gaussian
    }


def main():
    """Example usage of the safe AWG upload"""
    
    # Configure your AWG connection here
    RESOURCE_NAME = 'USB0::0x168C::0x1284::0000215582::0::INSTR'  # Change to your AWG's IP
    CHANNEL = 1  # Channel to use (1-4)
    
    print("="*60)
    print("Rigol AWG Safe Waveform Upload")
    print("="*60)
    
    # Create AWG instance
    awg = RigolAWG(RESOURCE_NAME)
    
    # Connect to instrument
    if not awg.connect():
        print("Failed to connect to AWG")
        return
    
    try:
        # Select channel
        awg.select_channel(CHANNEL)
        
        # Set trace mode to SINGLE (only affects selected channel)
        awg.set_trace_mode('SING')
        
        # Create example waveform (sine wave)
        waveforms = create_example_waveforms()
        waveform_data = waveforms['sine']
        
        print(f"\nUploading sine wave ({len(waveform_data)} points)...")
        
        # Upload waveform to segment 1
        if awg.upload_waveform(waveform_data, segment=1):
            
            # Configure output parameters
            awg.set_sample_rate(100e6)  # 100 MHz sample rate
            awg.set_amplitude(1.0)       # 1 Vpp
            awg.set_offset(0.0)          # 0V offset
            
            # Play the waveform
            awg.play_waveform(segment=1)
            
            print("\nWaveform is now playing!")
            print("Press Ctrl+C to stop...")
            
            # Keep running until user stops
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping...")
        
        # Stop output
        awg.stop_output()
        
    except Exception as e:
        print(f"Error during operation: {e}")
    
    finally:
        # Always disconnect
        awg.disconnect()
    
    print("\nDone!")


if __name__ == '__main__':
    main()
