# Outline

I want to be able to launch root UI (that is, run the root UI python file) in development mode. Development mode means that the program should not try to access any of the connected equipment (as the equipment won't be connected). Whether the program is launched in development mode or not should be determined based on the value of the development_mode bool in the rootConfig.ini file.

The connections that the code tries to make are to the oscilloscopes, the DAQ cards and the AWG (potentially also the TDC, frequency counter and power meter but these don't need to be addressed straight away). Rather than connecting to these devices, a "dummy" should be loaded that simply prints out the commands that would be sent to the relevant instruments.

## DAQ cards
What needs to change?
 - The DAQ.py file tries to load the dll - this should only happen if not in development mode
 - There needs to be at least one dummy class that can be loaded into the Root_UI. I think it makes sense to make a dummy DAQ_controller class, as this contains all the daq objects. Then it can simply print what each channel is doing whenever a command is sent
 - This new dummy class needs to be correctly implemented so that root_UI and other files don't break


## Oscilloscopes
What needs to change?
 - There needs to be a dummy version of the keysight_3104A.py oscilloscope manager that can be loaded into the experimental runner
 - The same commands should be available but they should result in the commands being printed rather than sent to the scope.
 - This must be done in a way that doesn't break ExperimentalRunner.py

## AWG
What needs to change?
 - There needs to be a dummy version of the awg_manager.py file. This should be able to be loaded into ExperimentalRunner.py without breaking anything.
 - Rather than writing and querying the AWG the commands should be printed instead.


## How to handle querying the scope/awg
There should be methods in the dummy classes that can generate random data (with parameters I can set, such as the data structure) that can then be passed back to ExperimentalRunner.py when it tries to collect data.