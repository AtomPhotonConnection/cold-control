# Outline

Rather than the current mess with how the config files work, I want a much clearer structure that separates the control of each device into a separate config file, and these files are included in an overall experimental configuration file.

## Desired configuration structure
There should be broadly two different types of configuration files. Type one will be for managing experiments, type two will be for managing particular devices

### Config files for managing experiments
These config files should contain all of the relevant parameters needed for running an experiment. They should be read by a single ExperimentReader class, which will then delegate the reading of the details of the experiment to the class relevant to the particular experiment being performed. This class will load all of the relevant information from the config file into the configuration object as defined in experimental_configs.py. Examples of these types of configuration files would be Mot Fluorescence experiment files, absorption imaging experiment files and Mot Fluorescence sweep experiment files. These sweep experiments should be changed so that they include all the relevant parameters for a normal MOT fluorescence experiment, but also include extra details about how the sweep should be performed. These configuration files will contain links to the configuration files used to configure the experimental apparatus (the second type of file explained below) and the configuration objects will include the configuration objects used to configure the instrumental apparatus.

### Config files for managing instruments
These config files contain all the relevant parameters for managing a particular instrument. The primary examples that need to be introduced initially will be the oscilloscope (which will need a new configuration object creating), the AWG (which already has a config reader and object) and the DAQ cards (which also already have a reader under the name sequenceReader, and the sequence object is designed to manage this but it isn't passed to the experimental configurations at the moment). Potentially config objects and readers for the camera should be created at some point, but that isn't a priority. The actual files used to manage the DAQ cards, AWG and Oscilloscope are attached but these shouldn't be too important for these refactoring changes.

## UI changes to reflect this

Rather than the experimental UI being cluttered with so many options, the options should simply be to select a particular experimental config file (which will then load the relevant instrument config objects) and then play that experimental config. This should work for the mot fluorescence experiments, the mot fluorescence sweep experiments, and potentially for the absorption imaging experiments although that is a lower priority.

Viewing the sequence is no longer as important as the sequence object is part of the larger experimental configuration object - however, the code shouldn't be removed as it might be helpful occasionally to run a script to view a particular sequence file.